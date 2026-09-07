import tkinter as tk
from tkinter import ttk

from app import Studio
from registration_app import RegistrationAssistant


def open_studio(root):
    window = tk.Toplevel(root)
    Studio(window)


def open_registration(root):
    window = tk.Toplevel(root)
    RegistrationAssistant(window)


def main():
    root = tk.Tk()
    root.title("Photo & Signature Studio")
    root.geometry("760x500")
    root.minsize(650, 430)

    outer = ttk.Frame(root, padding=30)
    outer.pack(fill="both", expand=True)
    ttk.Label(outer, text="Photo & Signature Studio", font=("Segoe UI", 26, "bold")).pack(pady=(20, 4))
    ttk.Label(outer, text="Choose what you want to do", font=("Segoe UI", 12)).pack(pady=(0, 25))

    cards = ttk.Frame(outer)
    cards.pack(fill="x", padx=25)
    ttk.Button(cards, text="📷  PHOTO\n\nCreate / resize student photo", command=lambda: open_studio(root)).grid(row=0, column=0, padx=8, pady=8, sticky="nsew", ipadx=25, ipady=30)
    ttk.Button(cards, text="✍  SIGNATURE\n\nCreate / clean student signature", command=lambda: open_studio(root)).grid(row=0, column=1, padx=8, pady=8, sticky="nsew", ipadx=25, ipady=30)
    ttk.Button(cards, text="📄  STUDENT FORM\n\nOCR + registration verification", command=lambda: open_registration(root)).grid(row=0, column=2, padx=8, pady=8, sticky="nsew", ipadx=25, ipady=30)
    for col in range(3):
        cards.columnconfigure(col, weight=1)

    ttk.Label(outer, text="Photo and Signature are the main tools. Student registration and BSEB work are assistance/automation around them.", foreground="#666", wraplength=650, justify="center").pack(pady=28)
    ttk.Label(outer, text="All final registration information is reviewed by the user before submission.", foreground="#666").pack()
    root.mainloop()


if __name__ == "__main__":
    main()
