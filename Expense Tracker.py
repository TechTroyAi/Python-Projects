import calendar
import datetime as dt
import json
import os
import tkinter as tk
from tkinter import filedialog

# ---------- colors ----------
BG = "#060d1f"
CARD = "#0a1227"
CARD2 = "#0e1a35"
BORDER = "#1c2b4d"
TEXT = "#d4e2ef"
MUTED = "#859fc0"
ACCENT = "#315381"
ACCENT2 = "#4c638c"
ICE = "#cee0f4"
DANGER = "#f87171"

# ---------- categories ----------
CATS = [
    ("Food",      "🍔", "#315381"),
    ("Transport", "🚗", "#4c638c"),
    ("Fun",       "🎮", "#6b82ab"),
    ("Bills",     "💡", "#3d6e8c"),
    ("Shopping",  "🛍️", "#859fc0"),
    ("Health",    "💊", "#4a6fa5"),
    ("Others",    "📦", "#5a7aa8"),
]

PERIODS = [("day", "📅 Day"), ("week", "📆 Week"), ("month", "🗓️ Month"), ("year", "📈 Year")]

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expenses.json")


def cat_info(name):
    for c in CATS:
        if c[0] == name:
            return c
    return CATS[-1]


def peso(n):
    v = round(n, 2)
    if v == int(v):
        return "₱{:,.0f}".format(v)
    return "₱{:,.2f}".format(v)


def short_date(ts):
    d = dt.datetime.fromtimestamp(ts / 1000)
    return d.strftime("%b %d")


def period_range(period, now):
    if period == "day":
        start = dt.datetime(now.year, now.month, now.day)
    elif period == "week":
        monday = now - dt.timedelta(days=now.weekday())
        start = dt.datetime(monday.year, monday.month, monday.day)
    elif period == "month":
        start = dt.datetime(now.year, now.month, 1)
    else:
        start = dt.datetime(now.year, 1, 1)
    return start.timestamp() * 1000, now.timestamp() * 1000


class App:
    def __init__(self, root):
        self.root = root
        root.title("Expense Tracker")
        root.configure(bg=BG)
        root.geometry("900x800")
        root.minsize(620, 600)

        self.expenses = self.load()
        self.selected = CATS[0][0]
        self.period = "day"
        self.last_deleted = None
        self.data_file = DATA_FILE

        self._build()
        self.render()

    # ---------------- data ----------------
    def load(self):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return []

    def save(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.expenses, f, ensure_ascii=False, indent=2)
        except OSError:
            self.set_status("⚠️ Could not save")

    # ---------------- ui build ----------------
    def _build(self):
        tk.Label(self.root, text="💸 Expense Tracker", bg=BG, fg=ICE,
                 font=("Segoe UI", 20, "bold")).pack(pady=(16, 10))

        # --- add form ---
        form_card = tk.Frame(self.root, bg=CARD, highlightthickness=1,
                             highlightbackground=BORDER)
        form_card.pack(fill="x", padx=16, pady=(0, 8))

        row = tk.Frame(form_card, bg=CARD)
        row.pack(fill="x", padx=12, pady=(12, 0))

        self.name_var = tk.StringVar()
        self.amount_var = tk.StringVar()
        self.name_entry = tk.Entry(row, textvariable=self.name_var, bg=CARD2,
                                   fg=TEXT, insertbackground=TEXT, relief="flat",
                                   font=("Segoe UI", 11))
        self.name_entry.pack(side="left", fill="x", expand=True, ipady=9)
        self.name_entry.insert(0, "")
        self.name_entry.config(fg=TEXT)

        self.amount_entry = tk.Entry(row, textvariable=self.amount_var, bg=CARD2,
                                     fg=TEXT, insertbackground=TEXT, relief="flat",
                                     font=("Segoe UI", 11), width=14)
        self.amount_entry.pack(side="left", fill="x", padx=(8, 0), ipady=9)

        tk.Button(row, text="➕ Add", command=self.add_expense, bg=ACCENT, fg="#fff",
                  activebackground=ACCENT2, activeforeground="#fff", relief="flat",
                  bd=0, font=("Segoe UI", 11, "bold"), padx=18, pady=9,
                  cursor="hand2").pack(side="left", padx=(8, 0))

        self.picker = tk.Frame(form_card, bg=CARD)
        self.picker.pack(fill="x", padx=12, pady=12)

        self.amount_entry.bind("<Return>", lambda e: self.add_expense())

        # --- period + file buttons ---
        bar = tk.Frame(self.root, bg=CARD, highlightthickness=1,
                       highlightbackground=BORDER)
        bar.pack(fill="x", padx=16, pady=(0, 8))

        self.period_frame = tk.Frame(bar, bg=CARD)
        self.period_frame.pack(side="left", padx=12, pady=10)

        btns = tk.Frame(bar, bg=CARD)
        btns.pack(side="right", padx=12, pady=10)
        for text, cmd in [("💾 Save", self.save_as), ("⬇️ Export", self.export),
                          ("⬆️ Import", self.import_data)]:
            tk.Button(btns, text=text, command=cmd, bg=CARD2, fg=TEXT,
                      activebackground=ACCENT2, activeforeground="#fff", relief="flat",
                      bd=0, font=("Segoe UI", 9, "bold"), padx=10, pady=6,
                      cursor="hand2").pack(side="left", padx=4)

        # --- stats ---
        stats = tk.Frame(self.root, bg=BG)
        stats.pack(fill="x", padx=16, pady=(0, 8))

        self.stat_total = self._stat_cell(stats, "₱0", "Total")
        self.stat_total.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.stat_period = self._stat_cell(stats, "₱0", "This day")
        self.stat_period.pack(side="left", fill="x", expand=True, padx=4)
        self.stat_count = self._stat_cell(stats, "0", "Items")
        self.stat_count.pack(side="left", fill="x", expand=True, padx=(4, 0))

        # --- chart ---
        chart_card = tk.Frame(self.root, bg=CARD, highlightthickness=1,
                              highlightbackground=BORDER)
        chart_card.pack(fill="x", padx=16, pady=(0, 8))

        self.chart_lbl = tk.Label(chart_card, text="Spending", bg=CARD, fg=MUTED,
                                  font=("Segoe UI", 9, "bold"), anchor="w")
        self.chart_lbl.pack(fill="x", padx=12, pady=(10, 0))

        self.chart = tk.Canvas(chart_card, bg=CARD, height=140, highlightthickness=0)
        self.chart.pack(fill="x", padx=12, pady=(4, 12))
        self.chart.bind("<Configure>", lambda e: self.draw_chart())

        # --- breakdown ---
        bd_card = tk.Frame(self.root, bg=CARD, highlightthickness=1,
                           highlightbackground=BORDER)
        bd_card.pack(fill="x", padx=16, pady=(0, 8))

        tk.Label(bd_card, text="BY CATEGORY", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 2))

        self.breakdown = tk.Canvas(bd_card, bg=CARD, height=60, highlightthickness=0)
        self.breakdown.pack(fill="x", padx=12, pady=(0, 12))

        # --- list ---
        list_card = tk.Frame(self.root, bg=CARD, highlightthickness=1,
                             highlightbackground=BORDER)
        list_card.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        tk.Label(list_card, text="RECENT", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 4))

        wrap = tk.Frame(list_card, bg=CARD)
        wrap.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        self.list_canvas = tk.Canvas(wrap, bg=CARD, highlightthickness=0)
        self.list_canvas.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(wrap, orient="vertical", command=self.list_canvas.yview)
        sb.pack(side="right", fill="y")
        self.list_canvas.configure(yscrollcommand=sb.set)

        self.inner = tk.Frame(self.list_canvas, bg=CARD)
        self.inner.bind("<Configure>",
                        lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")))
        self.list_canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.list_canvas.bind_all("<MouseWheel>", self._on_wheel)

        # --- status bar ---
        bottom = tk.Frame(self.root, bg=CARD)
        bottom.pack(fill="x", side="bottom")

        self.status_lbl = tk.Label(bottom, text="", bg=CARD, fg=MUTED,
                                   font=("Segoe UI", 10), anchor="w", padx=12, pady=8)
        self.status_lbl.pack(side="left", fill="x", expand=True)

        self.undo_btn = tk.Button(bottom, text="↩️ Undo", command=self.undo,
                                  bg=ACCENT, fg="#fff", activebackground=ACCENT2,
                                  activeforeground="#fff", relief="flat", bd=0,
                                  font=("Segoe UI", 10, "bold"), padx=14, pady=6,
                                  cursor="hand2")

    def _stat_cell(self, parent, num, lbl):
        cell = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        tk.Label(cell, text=num, bg=CARD, fg=TEXT, font=("Segoe UI", 15, "bold")).pack(pady=(10, 0))
        tk.Label(cell, text=lbl, bg=CARD, fg=MUTED, font=("Segoe UI", 8)).pack(pady=(0, 10))
        return cell

    def _on_wheel(self, e):
        self.list_canvas.yview_scroll(int(-e.delta / 120), "units")

    def set_status(self, text):
        self.status_lbl.config(text=text)

    # ---------------- pickers ----------------
    def render_picker(self):
        for w in self.picker.winfo_children():
            w.destroy()
        for name, emoji, color in CATS:
            on = name == self.selected
            b = tk.Button(self.picker, text=f"{emoji} {name}",
                          bg=ACCENT2 if on else CARD2, fg="#fff" if on else MUTED,
                          activebackground=ACCENT2, activeforeground="#fff",
                          relief="flat", bd=0, font=("Segoe UI", 9, "bold"),
                          padx=12, pady=6, cursor="hand2",
                          command=lambda n=name: self.select_cat(n))
            b.pack(side="left", padx=(0, 6))

    def select_cat(self, name):
        self.selected = name
        self.render_picker()

    def render_periods(self):
        for w in self.period_frame.winfo_children():
            w.destroy()
        for pid, label in PERIODS:
            on = pid == self.period
            b = tk.Button(self.period_frame, text=label,
                          bg=ACCENT2 if on else CARD2, fg="#fff" if on else MUTED,
                          activebackground=ACCENT2, activeforeground="#fff",
                          relief="flat", bd=0, font=("Segoe UI", 9, "bold"),
                          padx=12, pady=6, cursor="hand2",
                          command=lambda p=pid: self.select_period(p))
            b.pack(side="left", padx=(0, 6))

    def select_period(self, pid):
        self.period = pid
        self.render_periods()
        self.render()

    # ---------------- actions ----------------
    def add_expense(self):
        name = self.name_var.get().strip()
        try:
            amount = float(self.amount_var.get().strip())
        except ValueError:
            return
        if not name or amount <= 0:
            return
        self.expenses.append({
            "id": int(dt.datetime.now().timestamp() * 1000) + len(self.expenses),
            "name": name, "amount": amount, "cat": self.selected,
            "ts": int(dt.datetime.now().timestamp() * 1000),
        })
        self.name_var.set("")
        self.amount_var.set("")
        self.save()
        self.render()

    def delete(self, eid):
        for i, e in enumerate(self.expenses):
            if e["id"] == eid:
                self.last_deleted = self.expenses.pop(i)
                self.save()
                self.render()
                self.show_undo()
                return

    def undo(self):
        if self.last_deleted:
            self.expenses.append(self.last_deleted)
            self.last_deleted = None
            self.save()
            self.render()
            self.hide_undo()
            self.set_status("↩️ Restored")

    def show_undo(self):
        self.undo_btn.pack(side="right", padx=12)
        self.set_status("Deleted")

    def hide_undo(self):
        self.undo_btn.pack_forget()

    # ---------------- file ----------------
    def save_as(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            initialfile="expenses.json",
                                            filetypes=[("JSON", "*.json")])
        if not path:
            return
        self.data_file = path
        self.save()
        self.set_status("💾 Saved")

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            initialfile="expenses-backup.json",
                                            filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.expenses, f, ensure_ascii=False, indent=2)
            self.set_status("⬇️ Exported")
        except OSError:
            self.set_status("⚠️ Export failed")

    def import_data(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.expenses = data
                self.save()
                self.render()
                self.set_status("⬆️ Imported")
        except (OSError, ValueError):
            self.set_status("⚠️ Import failed")

    # ---------------- render ----------------
    def period_list(self):
        now = dt.datetime.now()
        s, e = period_range(self.period, now)
        return [x for x in self.expenses if s <= x["ts"] <= e]

    def render(self):
        now = dt.datetime.now()
        plist = self.period_list()

        total = sum(x["amount"] for x in self.expenses)
        period_total = sum(x["amount"] for x in plist)

        self.stat_total.winfo_children()[0].config(text=peso(total))
        self.stat_period.winfo_children()[0].config(text=peso(period_total))
        self.stat_period.winfo_children()[1].config(text="This " + self.period)
        self.stat_count.winfo_children()[0].config(text=str(len(plist)))

        period_lbl = dict(PERIODS)[self.period].split(" ", 1)[1]
        self.chart_lbl.config(text="Spending — " + period_lbl)

        self.render_picker()
        self.render_periods()
        self.draw_chart()
        self.draw_breakdown(total)
        self.draw_list(plist)

    def chart_data(self):
        now = dt.datetime.now()
        plist = self.period_list()

        if self.period == "week":
            days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            vals = [0.0] * 7
            for e in plist:
                d = dt.datetime.fromtimestamp(e["ts"] / 1000)
                vals[d.weekday()] += e["amount"]
            today = now.weekday()
            return days, vals, today

        if self.period == "month":
            dim = calendar.monthrange(now.year, now.month)[1]
            vals = [0.0] * dim
            for e in plist:
                d = dt.datetime.fromtimestamp(e["ts"] / 1000)
                vals[d.day - 1] += e["amount"]
            labels = [str(i + 1) for i in range(dim)]
            return labels, vals, now.day - 1

        if self.period == "year":
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            vals = [0.0] * 12
            for e in plist:
                d = dt.datetime.fromtimestamp(e["ts"] / 1000)
                vals[d.month - 1] += e["amount"]
            return months, vals, now.month - 1

        # day -> hourly
        vals = [0.0] * 24
        for e in plist:
            d = dt.datetime.fromtimestamp(e["ts"] / 1000)
            vals[d.hour] += e["amount"]
        labels = [str(i) for i in range(24)]
        return labels, vals, now.hour

    def draw_chart(self):
        self.chart.delete("all")
        labels, vals, today = self.chart_data()
        w = self.chart.winfo_width()
        if w < 50:
            return
        h = self.chart.winfo_height()
        top, bottom = 6, h - 22
        bar_area = bottom - top

        n = len(vals)
        step = w / n
        gap = max(2, step * 0.25)
        bar_w = step - gap
        mx = max(vals) or 1

        # label thinning
        show_every = max(1, int(n / 12) + 1)

        for i, v in enumerate(vals):
            x0 = i * step + gap / 2
            bh = max(2, (v / mx) * bar_area) if v > 0 else 2
            y0 = bottom - bh
            color = ICE if i == today else ACCENT2
            self.chart.create_rectangle(x0, y0, x0 + bar_w, bottom,
                                        fill=color, outline="")
            if i % show_every == 0 or i == today:
                self.chart.create_text(x0 + bar_w / 2, bottom + 10,
                                       text=labels[i], fill=MUTED,
                                       font=("Segoe UI", 7))

    def draw_breakdown(self, total):
        self.breakdown.delete("all")
        by_cat = {}
        for e in self.expenses:
            by_cat[e["cat"]] = by_cat.get(e["cat"], 0) + e["amount"]

        rows = [(c, by_cat[c[0]]) for c in CATS if by_cat.get(c[0])]
        if not rows:
            self.breakdown.config(height=30)
            self.breakdown.create_text(10, 12, anchor="w", text="No expenses yet",
                                       fill=MUTED, font=("Segoe UI", 9))
            return

        row_h = 28
        self.breakdown.config(height=row_h * len(rows) + 6)
        w = self.breakdown.winfo_width()
        mx = max(v for _, v in rows) or 1

        for i, (c, amt) in enumerate(rows):
            y = i * row_h + 4
            name, emoji, color = c
            self.breakdown.create_text(12, y + row_h / 2, anchor="w",
                                       text=emoji, fill=TEXT, font=("Segoe UI", 11))
            self.breakdown.create_text(40, y + row_h / 2, anchor="w",
                                       text=name, fill=TEXT, font=("Segoe UI", 9))

            bar_x0, bar_x1 = 120, w - 150
            bw = (amt / mx) * (bar_x1 - bar_x0)
            self.breakdown.create_rectangle(bar_x0, y + 7, bar_x0 + bw, y + row_h - 7,
                                            fill=color, outline="")
            self.breakdown.create_text(bar_x1 + 8, y + row_h / 2, anchor="w",
                                       text=peso(amt), fill=TEXT, font=("Segoe UI", 9, "bold"))
            pct = round(amt / total * 100) if total else 0
            self.breakdown.create_text(w - 8, y + row_h / 2, anchor="e",
                                       text=f"{pct}%", fill=MUTED, font=("Segoe UI", 8))

    def draw_list(self, plist):
        for w in self.inner.winfo_children():
            w.destroy()

        if not plist:
            tk.Label(self.inner, text="Nothing here", bg=CARD, fg=MUTED,
                     font=("Segoe UI", 10), pady=16).pack()
            return

        for e in sorted(plist, key=lambda x: -x["ts"]):
            name, emoji, color = cat_info(e["cat"])
            row = tk.Frame(self.inner, bg=CARD)
            row.pack(fill="x", pady=1)

            tk.Label(row, text=emoji, bg=CARD, fg=TEXT,
                     font=("Segoe UI", 11)).pack(side="left", padx=(8, 6))

            tk.Label(row, text=e["name"], bg=CARD, fg=TEXT, anchor="w",
                     font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True)

            tk.Label(row, text=short_date(e["ts"]), bg=CARD, fg=MUTED,
                     font=("Segoe UI", 8), padx=8).pack(side="left")

            tk.Label(row, text=peso(e["amount"]), bg=CARD, fg=TEXT,
                     font=("Segoe UI", 10, "bold"), padx=8).pack(side="left")

            tk.Button(row, text="🗑️", command=lambda i=e["id"]: self.delete(i),
                      bg=CARD, fg=MUTED, activebackground=CARD2,
                      activeforeground=DANGER, relief="flat", bd=0,
                      font=("Segoe UI", 10), cursor="hand2", width=3).pack(
                      side="left", padx=(0, 6))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
