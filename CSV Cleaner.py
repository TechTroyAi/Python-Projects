import csv
import io
import os
import tkinter as tk
from tkinter import filedialog, ttk

# ---------- Ocean Breeze ----------
BG = "#f0f8fb"
SURFACE = "#ffffff"
SURFACE2 = "#e8f4f8"
BORDER = "#d6e8ef"
TEXT = "#0b2a36"
MUTED = "#5a7d8c"
ACCENT = "#0ea5b7"
ACCENT2 = "#22c3d6"
GOOD = "#10b981"
BAD = "#ef4444"
WARN = "#f59e0b"

MAX_ROWS = 100


def parse_csv(text):
    """Robust CSV parser that handles quotes and commas inside quotes."""
    reader = csv.reader(io.StringIO(text))
    rows = []
    for r in reader:
        if any(c.strip() != "" for c in r):
            rows.append(r)
    return rows


def to_csv(rows):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerows(rows)
    return out.getvalue()


def detect_issues(rows):
    issues = []
    if not rows:
        return issues

    empty_cells = sum(1 for r in rows for c in r if c == "")
    if empty_cells:
        issues.append((f"{empty_cells} empty cells", "bad"))

    empty_rows = sum(1 for r in rows if all(c == "" for c in r))
    if empty_rows:
        issues.append((f"{empty_rows} empty rows", "warn"))

    seen = set()
    dup_rows = 0
    for r in rows:
        k = tuple(r)
        if k in seen:
            dup_rows += 1
        else:
            seen.add(k)
    if dup_rows:
        issues.append((f"{dup_rows} duplicate rows", "warn"))

    header = rows[0] if rows else []
    names = [h.strip().lower() for h in header]
    dup_cols = len(names) - len(set(names))
    if dup_cols:
        issues.append((f"{dup_cols} duplicate columns", "warn"))

    ncols = max(len(r) for r in rows)
    ragged = sum(1 for r in rows if len(r) != ncols)
    if ragged:
        issues.append((f"{ragged} uneven rows", "warn"))

    whitespace = sum(1 for r in rows for c in r if c != c.strip())
    if whitespace:
        issues.append((f"{whitespace} cells with stray spaces", "warn"))

    return issues


def clean_rows(rows, opts):
    r = [list(row) for row in rows]
    if opts["trim"]:
        r = [[c.strip() for c in row] for row in r]
    if opts["empty_rows"]:
        r = [row for row in r if not all(c == "" for c in row)]
    if opts["dup_rows"]:
        seen = set()
        keep = []
        for row in r:
            k = tuple(row)
            if k not in seen:
                seen.add(k)
                keep.append(row)
        r = keep
    ncols = max((len(row) for row in r), default=0)
    if opts["empty_cols"]:
        keep = [c for c in range(ncols) if not all((row[c] if c < len(row) else "") == "" for row in r)]
        r = [[row[c] if c < len(row) else "" for c in keep] for row in r]
        ncols = len(keep)
    if opts["dup_cols"]:
        header = r[0] if r else []
        seen = set()
        keep = []
        for c in range(ncols):
            key = (header[c].strip().lower() if c < len(header) and header[c].strip() else f"col{c+1}")
            if key not in seen:
                seen.add(key)
                keep.append(c)
        r = [[row[c] if c < len(row) else "" for c in keep] for row in r]
    if opts["fill"] and opts["fill_value"]:
        r = [[(opts["fill_value"] if c == "" else c) for c in row] for row in r]
    return r


SAMPLE = """Name,Email,Age,City,Name
  Alice ,alice@mail.com,25, Davao,Alice
Bob,bob@mail.com,,Manila,Bob
"Smith, John",john@mail.com,30,Cebu,Smith
  Alice,alice@mail.com,25,Davao,Alice
,,,,
Carla,carla@mail.com,28,,Carla
Dennis,dennis@mail.com,,Quezon City,Dennis
Dennis,dennis@mail.com,,Quezon City,Dennis"""


class App:
    def __init__(self, root):
        self.root = root
        root.title("CSV Cleaner")
        root.configure(bg=BG)
        root.geometry("1000x760")
        root.minsize(720, 600)

        self.rows = []
        self.cleaned = []
        self.options = {"trim": True, "empty_rows": True, "dup_rows": True,
                        "empty_cols": True, "dup_cols": False, "fill": False,
                        "fill_value": ""}
        self.vars = {}

        self._style()
        self._build()
        self.refresh()

    # ---------- ttk style ----------
    def _style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background=SURFACE, fieldbackground=SURFACE,
                        foreground=TEXT, borderwidth=0, rowheight=26,
                        font=("Segoe UI", 9))
        style.configure("Treeview.Heading",
                        background=ACCENT, foreground="#ffffff",
                        font=("Segoe UI", 9, "bold"), relief="flat",
                        padding=6)
        style.map("Treeview.Heading", background=[("active", ACCENT2)])
        style.map("Treeview", background=[("selected", "#cdeef3")],
                  foreground=[("selected", TEXT)])

    # ---------- ui ----------
    def _build(self):
        tk.Label(self.root, text="🧹 CSV Cleaner", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 20, "bold")).pack(pady=(16, 10))

        # top buttons
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=16)

        tk.Button(bar, text="📄 Open CSV", command=self.open_file, bg=ACCENT,
                  fg="#fff", activebackground=ACCENT2, activeforeground="#fff",
                  relief="flat", bd=0, font=("Segoe UI", 10, "bold"),
                  padx=16, pady=9, cursor="hand2").pack(side="left")

        tk.Button(bar, text="🎲 Sample", command=self.load_sample, bg=SURFACE2,
                  fg=TEXT, activebackground=ACCENT2, activeforeground="#fff",
                  relief="flat", highlightthickness=1, highlightbackground=BORDER,
                  bd=0, font=("Segoe UI", 10, "bold"), padx=16, pady=9,
                  cursor="hand2").pack(side="left", padx=(8, 0))

        tk.Button(bar, text="✕", command=self.clear, bg=SURFACE2, fg=TEXT,
                  activebackground=BAD, activeforeground="#fff", relief="flat",
                  highlightthickness=1, highlightbackground=BORDER, bd=0,
                  font=("Segoe UI", 10, "bold"), width=4, pady=9,
                  cursor="hand2").pack(side="right")

        # issues
        self.issue_card = tk.Frame(self.root, bg=SURFACE, highlightthickness=1,
                                   highlightbackground=BORDER)
        self.issue_card.pack(fill="x", padx=16, pady=(12, 8))

        tk.Label(self.issue_card, text="FOUND", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 2))
        self.issues = tk.Frame(self.issue_card, bg=SURFACE)
        self.issues.pack(fill="x", padx=12, pady=(0, 10))

        # options
        self.opt_card = tk.Frame(self.root, bg=SURFACE, highlightthickness=1,
                                 highlightbackground=BORDER)
        self.opt_card.pack(fill="x", padx=16, pady=(0, 8))

        tk.Label(self.opt_card, text="CLEAN", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 4))

        opts = tk.Frame(self.opt_card, bg=SURFACE)
        opts.pack(fill="x", padx=12, pady=(0, 10))

        opt_defs = [
            ("trim", "✂️ Trim spaces"),
            ("empty_rows", "🗑️ Remove empty rows"),
            ("dup_rows", "👯 Remove duplicate rows"),
            ("empty_cols", "📭 Remove empty columns"),
            ("dup_cols", "🗂️ Remove duplicate columns"),
            ("fill", "✏️ Fill empty cells"),
        ]
        self.option_buttons = {}
        for i, (key, label) in enumerate(opt_defs):
            var = tk.BooleanVar(value=self.options[key])
            self.vars[key] = var
            cb = tk.Checkbutton(opts, text=label, variable=var, bg=SURFACE,
                                activebackground=SURFACE, selectcolor=SURFACE2,
                                font=("Segoe UI", 9), cursor="hand2",
                                command=self.on_option_change)
            cb.grid(row=i // 3, column=i % 3, sticky="w", padx=6, pady=4)

        self.fill_row = tk.Frame(self.opt_card, bg=SURFACE)
        self.fill_row.pack(fill="x", padx=18, pady=(0, 10))
        tk.Label(self.fill_row, text="with", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        self.fill_var = tk.StringVar()
        self.fill_entry = tk.Entry(self.fill_row, textvariable=self.fill_var, bg=SURFACE2,
                                   fg=TEXT, insertbackground=TEXT, relief="flat",
                                   highlightthickness=1, highlightbackground=BORDER,
                                   font=("Segoe UI", 9), width=16)
        self.fill_entry.pack(side="left", padx=(8, 0), ipady=5)
        self.fill_var.trace_add("write", lambda *a: self.on_option_change())

        # stats
        self.stats = tk.Frame(self.root, bg=BG)
        self.stats.pack(fill="x", padx=16, pady=(0, 8))
        self.stat_labels = []

        # preview
        self.table_card = tk.Frame(self.root, bg=SURFACE, highlightthickness=1,
                                   highlightbackground=BORDER)
        self.table_card.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        tk.Label(self.table_card, text="PREVIEW", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 4))

        wrap = tk.Frame(self.table_card, bg=SURFACE)
        wrap.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.tree = ttk.Treeview(wrap, show="headings")
        self.tree.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(self.table_card, orient="horizontal", command=self.tree.xview)
        hsb.pack(fill="x", padx=12, pady=(0, 10))
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.row_note = tk.Label(self.table_card, text="", bg=SURFACE, fg=MUTED,
                                 font=("Segoe UI", 8))
        self.row_note.pack(pady=(0, 8))

        # bottom
        bottom = tk.Frame(self.root, bg=SURFACE, highlightthickness=1,
                          highlightbackground=BORDER)
        bottom.pack(fill="x", side="bottom")

        self.download_btn = tk.Button(bottom, text="⬇️ Save cleaned CSV", command=self.save_file,
                                      bg=ACCENT, fg="#fff", activebackground=ACCENT2,
                                      activeforeground="#fff", relief="flat", bd=0,
                                      font=("Segoe UI", 10, "bold"), padx=18, pady=9,
                                      cursor="hand2")
        self.download_btn.pack(side="right", padx=12, pady=8)

        self.status_lbl = tk.Label(bottom, text="", bg=SURFACE, fg=MUTED,
                                   font=("Segoe UI", 10), anchor="w", padx=12)
        self.status_lbl.pack(side="left", fill="x", expand=True)

    # ---------- actions ----------
    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"),
                                                     ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                text = f.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="latin-1", newline="") as f:
                text = f.read()
        self.rows = parse_csv(text)
        self.refresh()
        self.status_lbl.config(text=f"📄 {os.path.basename(path)}")

    def load_sample(self):
        self.rows = parse_csv(SAMPLE)
        self.refresh()
        self.status_lbl.config(text="🎲 Sample loaded")

    def clear(self):
        self.rows = []
        self.cleaned = []
        self.refresh()
        self.status_lbl.config(text="")

    def save_file(self):
        if not self.cleaned:
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            initialfile="cleaned.csv",
                                            filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(to_csv(self.cleaned))
            self.status_lbl.config(text=f"💾 Saved {os.path.basename(path)}")
        except OSError:
            self.status_lbl.config(text="⚠️ Save failed")

    def on_option_change(self):
        for key in ["trim", "empty_rows", "dup_rows", "empty_cols", "dup_cols", "fill"]:
            self.options[key] = self.vars[key].get()
        self.options["fill_value"] = self.fill_var.get()
        if self.vars["fill"].get():
            self.fill_row.pack(fill="x", padx=18, pady=(0, 10))
        else:
            self.fill_row.pack_forget()
        self.refresh()

    # ---------- render ----------
    def refresh(self):
        if not self.rows:
            self.issue_card.pack_forget()
            self.opt_card.pack_forget()
            self.table_card.pack_forget()
            for w in self.stats.winfo_children():
                w.destroy()
            self.download_btn.pack_forget()
            self.tree.delete(*self.tree.get_children())
            return

        self.issue_card.pack(fill="x", padx=16, pady=(12, 8))
        self.opt_card.pack(fill="x", padx=16, pady=(0, 8))
        self.table_card.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.download_btn.pack(side="right", padx=12, pady=8)

        self.cleaned = clean_rows(self.rows, self.options)

        # issues
        for w in self.issues.winfo_children():
            w.destroy()
        issues = detect_issues(self.rows)
        if issues:
            for label, cls in issues:
                bg = {"bad": "#fdecec", "warn": "#fef3e2", "good": "#e7f8f1"}[cls]
                fg = {"bad": "#b91c1c", "warn": "#b45309", "good": "#047857"}[cls]
                tk.Label(self.issues, text=label, bg=bg, fg=fg,
                         font=("Segoe UI", 8, "bold"), padx=10, pady=4).pack(side="left", padx=(0, 6))
        else:
            tk.Label(self.issues, text="✓ All clean", bg="#e7f8f1", fg="#047857",
                     font=("Segoe UI", 8, "bold"), padx=10, pady=4).pack(side="left")

        # stats
        for w in self.stats.winfo_children():
            w.destroy()
        removed_rows = len(self.rows) - len(self.cleaned)
        ncols_raw = max((len(r) for r in self.rows), default=0)
        ncols_clean = max((len(r) for r in self.cleaned), default=0)

        stats_def = [
            (str(len(self.rows)), "Rows"),
            (str(len(self.cleaned)), "After"),
            (str(ncols_raw), "Columns"),
            ("-" + str(removed_rows), "Rows removed", GOOD),
            ("-" + str(ncols_raw - ncols_clean), "Cols removed", GOOD),
        ]
        for val, lbl, *color in stats_def:
            cell = tk.Frame(self.stats, bg=SURFACE, highlightthickness=1,
                            highlightbackground=BORDER)
            cell.pack(side="left", fill="x", expand=True, padx=3)
            fg = color[0] if color else TEXT
            tk.Label(cell, text=val, bg=SURFACE, fg=fg,
                     font=("Segoe UI", 14, "bold")).pack(pady=(8, 0))
            tk.Label(cell, text=lbl, bg=SURFACE, fg=MUTED,
                     font=("Segoe UI", 8)).pack(pady=(0, 8))

        # table
        self.tree.delete(*self.tree.get_children())
        shown = self.cleaned[:MAX_ROWS]
        if shown:
            header = shown[0] if shown else []
            cols = [f"c{i}" for i in range(max(len(header), 1))]
            self.tree["columns"] = cols
            self.tree.column("#0", width=0, stretch=False)
            for i, h in enumerate(header):
                self.tree.heading(cols[i], text=h if h != "" else "(empty)")
                self.tree.column(cols[i], width=140, minwidth=80, stretch=False)
            for row in shown[1:]:
                values = [(c if c != "" else "—") for c in row]
                while len(values) < len(cols):
                    values.append("")
                self.tree.insert("", "end", values=values[:len(cols)])
            self.row_note.config(text=(f"showing first {len(shown) - 1} of {len(self.cleaned) - 1} rows"
                                       if len(self.cleaned) > MAX_ROWS else ""))

    # refresh with proper option card packing after clear
    def ensure_cards(self):
        pass


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
