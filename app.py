import io
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageEnhance, ImageFilter, ImageGrab, ImageOps, ImageTk

APP_NAME = "Photo & Signature Studio"
WHITE = (255, 255, 255)
SUPPORTED = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".pdf")
PRESETS = {
    "Photo 200×230 px / 50 KB": ("photo", 200, 230, 50),
    "Photo 300×400 px / 100 KB": ("photo", 300, 400, 100),
    "Signature 140×60 px / 20 KB": ("signature", 140, 60, 20),
    "Signature 300×100 px / 50 KB": ("signature", 300, 100, 50),
    "Custom Photo": ("photo", 200, 230, 50),
    "Custom Signature": ("signature", 140, 60, 20),
}


class Studio:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1240x820")
        self.root.minsize(1040, 700)
        self.root.protocol("WM_DELETE_WINDOW", root.destroy)
        self.source = None
        self.processed = None
        self.source_name = ""
        self.pdf_page_images = []
        self._tkimgs = []
        self.kind = tk.StringVar(value="photo")
        self.w = tk.IntVar(value=200)
        self.h = tk.IntVar(value=230)
        self.maxkb = tk.IntVar(value=50)
        self.fit = tk.StringVar(value="cover")
        self.face_crop = tk.BooleanVar(value=True)
        self.white_bg = tk.BooleanVar(value=True)
        self.auto_enhance = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Ready — paste an image with Ctrl+V or open a file.")
        self.dimensions = tk.StringVar(value="200 × 230 px")
        self.size_info = tk.StringVar(value="Target ≤ 50 KB")
        self._build()
        root.bind("<Control-v>", self.paste)
        root.bind("<Control-V>", self.paste)
        root.bind("<Control-o>", lambda _e: self.open_file())
        root.bind("<Control-s>", lambda _e: self.save())

    def _build(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        top = ttk.Frame(self.root, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text=APP_NAME, font=("Segoe UI", 22, "bold")).pack(side="left")
        ttk.Button(top, text="Save Result", command=self.save).pack(side="right", padx=4)
        ttk.Button(top, text="Open PDF / Image", command=self.open_file).pack(side="right", padx=4)
        ttk.Button(top, text="Paste (Ctrl+V)", command=self.paste).pack(side="right", padx=4)
        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body, padding=(12, 4, 6, 12), width=350)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        right = ttk.Frame(body, padding=(6, 4, 12, 12))
        right.pack(side="right", fill="both", expand=True)
        self._controls(left)
        self._preview_area(right)

    def _controls(self, parent):
        box = ttk.LabelFrame(parent, text="Preset", padding=10)
        box.pack(fill="x", pady=4)
        self.preset = ttk.Combobox(box, values=list(PRESETS), state="readonly", width=31)
        self.preset.current(0)
        self.preset.pack(fill="x")
        self.preset.bind("<<ComboboxSelected>>", self.preset_changed)
        output = ttk.LabelFrame(parent, text="Output", padding=10)
        output.pack(fill="x", pady=4)
        ttk.Radiobutton(output, text="Photo", variable=self.kind, value="photo", command=self.sync).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(output, text="Signature", variable=self.kind, value="signature", command=self.sync).grid(row=0, column=1, sticky="w")
        self._entry(output, "Width px", self.w, 1)
        self._entry(output, "Height px", self.h, 2)
        self._entry(output, "Max KB", self.maxkb, 3)
        ttk.Label(output, textvariable=self.dimensions).grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(output, textvariable=self.size_info).grid(row=5, column=0, columnspan=2, sticky="w")
        auto = ttk.LabelFrame(parent, text="Automatic processing", padding=10)
        auto.pack(fill="x", pady=4)
        ttk.Checkbutton(auto, text="White background", variable=self.white_bg).pack(anchor="w")
        ttk.Checkbutton(auto, text="Automatic face crop", variable=self.face_crop).pack(anchor="w")
        ttk.Checkbutton(auto, text="Light auto-enhancement", variable=self.auto_enhance).pack(anchor="w")
        ttk.Label(auto, text="Fit mode").pack(anchor="w", pady=(8, 0))
        ttk.Combobox(auto, textvariable=self.fit, values=["contain", "cover"], state="readonly").pack(fill="x")
        ttk.Button(parent, text="PROCESS", command=self.process).pack(fill="x", pady=12, ipady=8)
        ttk.Button(parent, text="Reset", command=self.reset).pack(fill="x")
        info = ttk.LabelFrame(parent, text="Workflow", padding=10)
        info.pack(fill="x", pady=10)
        ttk.Label(info, text="1. Paste/open source\n2. Choose photo/signature\n3. Set exact pixels + KB\n4. Process\n5. Save result\n\nAll image processing stays local.", justify="left").pack(anchor="w")

    def _entry(self, parent, label, variable, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=(5 if row > 1 else 8, 0))
        entry = ttk.Entry(parent, textvariable=variable, width=10)
        entry.grid(row=row, column=1, sticky="w", pady=(5 if row > 1 else 8, 0))
        entry.bind("<KeyRelease>", self.update_dimensions)

    def _preview_area(self, parent):
        header = ttk.Frame(parent)
        header.pack(fill="x")
        ttk.Label(header, text="Preview", font=("Segoe UI", 13, "bold")).pack(side="left")
        ttk.Label(header, text="  •  Ctrl+V paste  •  Ctrl+O open  •  Ctrl+S save", foreground="#666").pack(side="left")
        self.canvas = tk.Canvas(parent, bg="#eeeeee", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, pady=6)
        self.canvas.bind("<Configure>", lambda _e: self.show_previews())
        ttk.Label(parent, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x")

    def update_dimensions(self, *_):
        try:
            w, h, kb = int(self.w.get()), int(self.h.get()), int(self.maxkb.get())
            if w > 0 and h > 0:
                self.dimensions.set(f"{w} × {h} px")
                self.size_info.set(f"Target ≤ {kb} KB")
        except (ValueError, tk.TclError):
            pass

    def preset_changed(self, *_):
        kind, w, h, kb = PRESETS[self.preset.get()]
        self.kind.set(kind); self.w.set(w); self.h.set(h); self.maxkb.set(kb); self.update_dimensions()

    def sync(self):
        self.preset.set("Custom Photo" if self.kind.get() == "photo" else "Custom Signature")
        self.update_dimensions()

    def _set_source(self, image, name):
        image = ImageOps.exif_transpose(image.convert("RGB"))
        self.source = image; self.processed = None; self.source_name = name
        self.status.set(f"Loaded: {name} ({image.width}×{image.height})")
        self.show_previews()

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("Images and PDF", "*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff *.pdf"), ("All files", "*.*")])
        if not path: return
        try:
            if path.lower().endswith(".pdf"): self._open_pdf(path)
            else: self._set_source(Image.open(path), Path(path).stem)
        except Exception as exc:
            messagebox.showerror("Open failed", str(exc))

    def _open_pdf(self, path):
        with pymupdf.open(path) as doc:
            if not doc.page_count: raise ValueError("PDF has no pages")
            self.pdf_page_images = []
            scale = 2.2 if max(doc[0].rect.width, doc[0].rect.height) < 1600 else 1.5
            for page in doc:
                pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
                self.pdf_page_images.append(Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB"))
        if len(self.pdf_page_images) == 1:
            self._set_source(self.pdf_page_images[0], f"{Path(path).stem} — page 1"); return
        picker = tk.Toplevel(self.root); picker.title("Select PDF page"); picker.geometry("760x520"); picker.transient(self.root)
        ttk.Label(picker, text=f"Select a page ({len(self.pdf_page_images)} pages)", font=("Segoe UI", 13, "bold")).pack(pady=10)
        listbox = tk.Listbox(picker, height=18); listbox.pack(fill="both", expand=True, padx=12, pady=6)
        for i, image in enumerate(self.pdf_page_images): listbox.insert("end", f"Page {i + 1} — {image.width}×{image.height} px")
        listbox.selection_set(0)
        def choose():
            selection = listbox.curselection()
            if selection:
                idx = selection[0]; self._set_source(self.pdf_page_images[idx], f"{Path(path).stem} — page {idx + 1}"); picker.destroy()
        ttk.Button(picker, text="Use selected page", command=choose).pack(pady=10)

    def paste(self, *_):
        try:
            data = ImageGrab.grabclipboard()
            if isinstance(data, Image.Image): self._set_source(data, "Clipboard image"); return
            if isinstance(data, list) and data:
                candidate = data[0]
                if os.path.isfile(candidate) and Path(candidate).suffix.lower() in SUPPORTED:
                    if candidate.lower().endswith(".pdf"): self._open_pdf(candidate)
                    else: self._set_source(Image.open(candidate), Path(candidate).stem)
                    return
            messagebox.showinfo("Clipboard", "No image or supported file was found in the clipboard.")
        except Exception as exc:
            messagebox.showerror("Paste failed", str(exc))

    @staticmethod
    def _face_box(img):
        gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
        if len(faces) == 0: return None
        x, y, w, h = max(faces, key=lambda r: r[2] * r[3]); cx = x + w / 2
        return max(0, int(cx - w * 1.45)), max(0, int(y - h * 0.70)), min(img.width, int(cx + w * 1.45)), min(img.height, int(y + h * 2.2))

    def process_photo(self, image):
        img = ImageOps.exif_transpose(image.convert("RGB"))
        if self.auto_enhance.get():
            img = ImageEnhance.Contrast(img).enhance(1.03); img = ImageEnhance.Sharpness(img).enhance(1.05)
        if self.face_crop.get():
            box = self._face_box(img)
            if box: img = img.crop(box)
        target = (self.w.get(), self.h.get())
        if self.fit.get() == "cover": return ImageOps.fit(img, target, method=Image.Resampling.LANCZOS, centering=(0.5, 0.42))
        img.thumbnail(target, Image.Resampling.LANCZOS); result = Image.new("RGB", target, WHITE)
        result.paste(img, ((target[0] - img.width) // 2, (target[1] - img.height) // 2)); return result

    def process_signature(self, image):
        img = ImageOps.exif_transpose(image.convert("RGB")); gray = np.array(img.convert("L"))
        smooth = cv2.GaussianBlur(gray, (0, 0), sigmaX=15)
        normalized = cv2.divide(gray, smooth, scale=255)
        _, ink = cv2.threshold(normalized, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        ink = cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)); ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
        ys, xs = np.where(ink > 0)
        if len(xs) > 25:
            pad = max(4, int(min(img.size) * 0.015)); crop = img.crop((max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad), min(img.width, int(xs.max()) + pad + 1), min(img.height, int(ys.max()) + pad + 1)))
        else: crop = img
        crop = crop.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3)); crop.thumbnail((self.w.get(), self.h.get()), Image.Resampling.LANCZOS)
        result = Image.new("RGB", (self.w.get(), self.h.get()), WHITE); result.paste(crop, ((result.width - crop.width) // 2, (result.height - crop.height) // 2)); return result

    def process(self):
        if self.source is None: messagebox.showwarning("No input", "Paste or open an image/PDF first."); return
        try:
            w, h, maxkb = int(self.w.get()), int(self.h.get()), int(self.maxkb.get())
            if min(w, h, maxkb) <= 0: raise ValueError("Width, height and KB must be positive.")
            self.processed = self.process_photo(self.source) if self.kind.get() == "photo" else self.process_signature(self.source)
            self.status.set(f"Processed ✓ {w}×{h} px — target ≤ {maxkb} KB"); self.show_previews()
        except Exception as exc: messagebox.showerror("Processing failed", str(exc))

    @staticmethod
    def _jpeg_bytes(img, quality):
        bio = io.BytesIO(); img.save(bio, "JPEG", quality=quality, optimize=True, subsampling=0); return bio.getvalue()

    def encode_under_kb(self, img, path, maxkb):
        maxbytes = maxkb * 1024
        if path.lower().endswith(".png"):
            img.save(path, "PNG", optimize=True); return os.path.getsize(path) <= maxbytes
        lo, hi = 10, 96; best = None
        while lo <= hi:
            quality = (lo + hi) // 2; payload = self._jpeg_bytes(img, quality)
            if len(payload) <= maxbytes: best = payload; lo = quality + 1
            else: hi = quality - 1
        if best is None: return False
        with open(path, "wb") as handle: handle.write(best)
        return True

    def save(self):
        if self.processed is None: messagebox.showwarning("Nothing to save", "Process an input first."); return
        path = filedialog.asksaveasfilename(defaultextension=".jpg", filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png")], initialfile=f"{self.source_name or 'output'}_{self.kind.get()}.jpg")
        if not path: return
        try:
            if not self.encode_under_kb(self.processed, path, int(self.maxkb.get())):
                messagebox.showwarning("Size limit", "The requested KB limit cannot be met with the current dimensions without excessive quality loss. Try a larger KB limit or smaller dimensions."); return
            kb = os.path.getsize(path) / 1024; self.status.set(f"Saved ✓ {Path(path).name} — {self.processed.width}×{self.processed.height} px — {kb:.1f} KB")
            messagebox.showinfo("Saved", f"Saved successfully.\n\n{path}\n{self.processed.width}×{self.processed.height} px\n{kb:.1f} KB")
        except Exception as exc: messagebox.showerror("Save failed", str(exc))

    def reset(self):
        self.source = None; self.processed = None; self.source_name = ""; self.pdf_page_images = []
        self.status.set("Ready — paste an image with Ctrl+V or open a file."); self.show_previews()

    def show_previews(self):
        self.canvas.delete("all"); width = max(300, self.canvas.winfo_width()); height = max(260, self.canvas.winfo_height())
        images = []
        if self.source: images.append(("INPUT", self.source))
        if self.processed: images.append(("OUTPUT", self.processed))
        if not images:
            self.canvas.create_text(width // 2, height // 2, text="Paste an image (Ctrl+V)\nor open a PDF/image", fill="#777", font=("Segoe UI", 16)); return
        each = width // len(images); self._tkimgs = []
        for idx, (label, img) in enumerate(images):
            thumb = img.copy(); thumb.thumbnail((each - 40, height - 90), Image.Resampling.LANCZOS); x = idx * each + each // 2; y = height // 2 + 10
            tkimg = ImageTk.PhotoImage(thumb); self._tkimgs.append(tkimg); self.canvas.create_image(x, y, image=tkimg)
            self.canvas.create_text(x, 20, text=label, fill="#333", font=("Segoe UI", 12, "bold")); self.canvas.create_text(x, height - 14, text=f"{img.width} × {img.height} px", fill="#555")


def main():
    root = tk.Tk(); Studio(root); root.mainloop()


if __name__ == "__main__": main()
