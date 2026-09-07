from __future__ import annotations

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from core.supabase_client import SupabaseClient, SupabaseError, DEFAULT_TABLE


class RegistrationAssistant:
    """Simple, human-reviewed registration workflow. Portal submission is intentionally not automatic here."""

    def __init__(self, root: tk.Toplevel | tk.Tk):
        self.root = root
        self.root.title("Student Registration Assistant")
        self.root.geometry("1050x700")
        self.query = tk.StringVar()
        self.form_path = tk.StringVar(value="No hardcopy selected")
        self.status = tk.StringVar(value="Step 1: select the student's hardcopy form.")
        self._build()

    def _build(self):
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Student Registration Assistant", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Simple workflow: Hardcopy → OCR → Check → Prepare BSEB", foreground="#666").pack(anchor="w", pady=(2, 16))

        steps = ttk.Frame(outer)
        steps.pack(fill="x", pady=(0, 12))
        for number, title in [("1", "Hardcopy"), ("2", "OCR"), ("3", "Verify"), ("4", "BSEB")]:
            box = ttk.LabelFrame(steps, text=f"Step {number}", padding=12)
            box.pack(side="left", fill="x", expand=True, padx=4)
            ttk.Label(box, text=title, font=("Segoe UI", 12, "bold")).pack()

        form = ttk.LabelFrame(outer, text="1. Hardcopy form", padding=12)
        form.pack(fill="x", pady=6)
        ttk.Button(form, text="Open Scan / Photo / PDF", command=self.open_form).pack(side="left")
        ttk.Label(form, textvariable=self.form_path).pack(side="left", padx=12)

        search = ttk.LabelFrame(outer, text=f"2. Find student in {DEFAULT_TABLE}", padding=12)
        search.pack(fill="x", pady=6)
        ttk.Entry(search, textvariable=self.query, width=48).pack(side="left", padx=(0, 8))
        ttk.Button(search, text="Find Student", command=self.find_student).pack(side="left")

        actions = ttk.LabelFrame(outer, text="3. Next actions", padding=12)
        actions.pack(fill="x", pady=6)
        ttk.Button(actions, text="Run OCR", command=self.ocr_placeholder).pack(side="left", padx=4)
        ttk.Button(actions, text="Compare & Verify", command=self.verify_placeholder).pack(side="left", padx=4)
        ttk.Button(actions, text="Prepare BSEB", command=self.portal_placeholder).pack(side="left", padx=4)

        ttk.Label(outer, text="Results", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(18, 4))
        self.results = tk.Text(outer, height=18, wrap="word")
        self.results.pack(fill="both", expand=True)
        ttk.Label(outer, textvariable=self.status, relief="sunken", anchor="w").pack(fill="x", pady=(8, 0))

    def open_form(self):
        path = filedialog.askopenfilename(filetypes=[("Forms", "*.pdf *.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff"), ("All files", "*.*")])
        if path:
            self.form_path.set(str(Path(path)))
            self.status.set("Hardcopy selected. Next: Run OCR.")

    def find_student(self):
        query = self.query.get().strip()
        if not query:
            messagebox.showinfo("Find student", "Enter Application No, name, father name, or mother name.")
            return
        try:
            rows = SupabaseClient().search_students(query, limit=20)
            self.results.delete("1.0", "end")
            if not rows:
                self.results.insert("end", "No matching student found.\n")
                self.status.set("No reference match found.")
                return
            for row in rows:
                self.results.insert("end", f"Application No: {row.get('Application No', '')}\nName: {row.get('Name', '')}\nFather: {row.get('Father Name', '')}\nMother: {row.get('Mother Name', '')}\nDOB: {row.get('Dob', '')}\nSchool ID: {row.get('School Id', '')}\n\n")
            self.status.set(f"Found {len(rows)} reference record(s). Review before using any value.")
        except SupabaseError as exc:
            messagebox.showerror("Supabase", str(exc))
            self.status.set("Supabase connection/reference lookup failed.")

    def ocr_placeholder(self):
        messagebox.showinfo("OCR", "OCR module is the next core feature. The selected hardcopy will be sent to the configured OCR provider without changing the reference record.")
        self.status.set("OCR step selected — human review required.")

    def verify_placeholder(self):
        messagebox.showinfo("Verify", "Verification will show Hardcopy/OCR and Supabase values side by side. Nothing will be silently overwritten.")
        self.status.set("Verification step selected.")

    def portal_placeholder(self):
        messagebox.showinfo("BSEB", "BSEB preparation will use only verified data and processed photo/signature. Final submission remains user-controlled.")
        self.status.set("BSEB preparation selected.")
