import math
import secrets
import string
import tkinter as tk

# ---------- Neon Terminal ----------
BG = "#060807"
SURFACE = "#0c120d"
SURFACE2 = "#121a13"
BORDER = "#1e2b20"
TEXT = "#dcffe9"
MUTED = "#6f8a76"
ACCENT = "#00ff9d"
ACCENT2 = "#00c2ff"
GOOD = "#00ff9d"
BAD = "#ff4d6d"
WARN = "#ffd34d"

COMMON = [
    "password", "123456", "12345678", "123456789", "qwerty", "abc123",
    "password1", "iloveyou", "admin", "welcome", "letmein", "monkey",
    "dragon", "football", "baseball", "sunshine", "princess", "shadow",
    "master", "111111", "123123", "654321", "000000", "superman",
    "batman", "trustno1", "freedom", "whatever", "qwerty123", "1q2w3e4r",
    "password123", "p@ssw0rd", "changeme", "secret", "login", "starwars",
]

LEVELS = [
    ("Very weak", BAD),
    ("Weak", "#ff8a4d"),
    ("Fair", WARN),
    ("Strong", "#7dff4d"),
    ("Very strong", GOOD),
]

LOWER = string.ascii_lowercase
UPPER = string.ascii_uppercase
DIGITS = string.digits
SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>?/~"
ALL = LOWER + UPPER + DIGITS + SYMBOLS


def analyze(pw):
    has = {
        "lower": any(c.islower() for c in pw),
        "upper": any(c.isupper() for c in pw),
        "digit": any(c.isdigit() for c in pw),
        "symbol": any(not c.isalnum() for c in pw),
    }
    pool = 0
    if has["lower"]:
        pool += 26
    if has["upper"]:
        pool += 26
    if has["digit"]:
        pool += 10
    if has["symbol"]:
        pool += 33
    if pool == 0:
        pool = 1

    entropy = len(pw) * math.log2(pool)
    common = pw.lower() in COMMON

    if not pw:
        level = 0
    elif common or entropy < 28:
        level = 0
    elif entropy < 36:
        level = 1
    elif entropy < 60:
        level = 2
    elif entropy < 90:
        level = 3
    else:
        level = 4
    return has, entropy, common, level


def crack_time(entropy):
    guesses = 2 ** entropy / 2
    per_sec = 10e9
    secs = guesses / per_sec
    if secs < 1:
        return "instantly"
    units = [(31536000, "years"), (86400, "days"), (3600, "hours"),
             (60, "minutes"), (1, "seconds")]
    for div, name in units:
        if secs >= div:
            v = round(secs / div)
            if name == "years" and v > 1000:
                return "centuries"
            return f"{v} {name}"
    return "instantly"


class App:
    def __init__(self, root):
        self.root = root
        root.title("Password Checker")
        root.configure(bg=BG)
        root.geometry("470x620")
        root.resizable(False, False)

        self.shown = False
        self._build()
        self.render()

    # ---------- ui ----------
    def _build(self):
        tk.Label(self.root, text="🔐", bg=BG, font=("Segoe UI Emoji", 30)).pack(pady=(20, 0))
        tk.Label(self.root, text="Password Checker", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 18, "bold")).pack(pady=(0, 16))

        # input
        wrap = tk.Frame(self.root, bg=SURFACE2, highlightthickness=1, highlightbackground=BORDER)
        wrap.pack(fill="x", padx=26)

        self.pw_var = tk.StringVar()
        self.entry = tk.Entry(wrap, textvariable=self.pw_var, bg=SURFACE2, fg=TEXT,
                              insertbackground=ACCENT, relief="flat", show="*",
                              font=("Consolas", 13), bd=0)
        self.entry.pack(side="left", fill="x", expand=True, padx=(12, 4), ipady=10)

        self.eye_btn = tk.Button(wrap, text="👁️", command=self.toggle_show, bg=SURFACE2,
                                 fg=MUTED, activebackground=SURFACE2, activeforeground=ACCENT,
                                 relief="flat", bd=0, font=("Segoe UI Emoji", 13),
                                 cursor="hand2")
        self.eye_btn.pack(side="left")

        self.copy_btn = tk.Button(wrap, text="📋", command=self.copy, bg=SURFACE2,
                                  fg=MUTED, activebackground=SURFACE2, activeforeground=ACCENT,
                                  relief="flat", bd=0, font=("Segoe UI Emoji", 13),
                                  cursor="hand2")
        self.copy_btn.pack(side="left", padx=(0, 4))

        # meter
        self.meter = tk.Frame(self.root, bg=BG)
        self.meter.pack(fill="x", padx=26, pady=(16, 4))
        self.segs = []
        for _ in range(5):
            s = tk.Frame(self.meter, bg=SURFACE2, highlightthickness=1, highlightbackground=BORDER)
            s.pack(side="left", fill="x", expand=True, padx=2, ipady=3)
            self.segs.append(s)

        self.label = tk.Label(self.root, text="—", bg=BG, fg=MUTED,
                              font=("Segoe UI", 9, "bold"), anchor="e")
        self.label.pack(fill="x", padx=26, pady=(0, 10))

        # stats
        stats = tk.Frame(self.root, bg=BG)
        stats.pack(fill="x", padx=26)

        self.crack_cell = self._stat_cell(stats, "—", "Time to crack")
        self.crack_cell.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entropy_cell = self._stat_cell(stats, "—", "Entropy")
        self.entropy_cell.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # checklist
        checks = tk.Frame(self.root, bg=BG)
        checks.pack(fill="x", padx=30, pady=(16, 12))

        self.check_rows = []
        for text in ["At least 12 characters", "Uppercase letter", "Lowercase letter",
                     "Number", "Symbol", "Not a common password"]:
            row = tk.Frame(checks, bg=BG)
            row.pack(fill="x", pady=3)
            box = tk.Label(row, text="✓", bg=SURFACE2, fg=SURFACE2,
                           font=("Segoe UI", 8, "bold"), width=2)
            box.pack(side="left", padx=(0, 8))
            lbl = tk.Label(row, text=text, bg=BG, fg=MUTED, anchor="w",
                           font=("Segoe UI", 9))
            lbl.pack(side="left")
            self.check_rows.append((box, lbl))

        # buttons
        btns = tk.Frame(self.root, bg=BG)
        btns.pack(fill="x", padx=26)

        tk.Button(btns, text="⚡ Generate", command=self.generate, bg=ACCENT, fg="#04120c",
                  activebackground=ACCENT2, activeforeground="#04120c", relief="flat",
                  bd=0, font=("Segoe UI", 10, "bold"), padx=14, pady=11,
                  cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 5))

        tk.Button(btns, text="✕ Clear", command=self.clear, bg=SURFACE2, fg=TEXT,
                  activebackground=SURFACE2, activeforeground=ACCENT, relief="flat",
                  highlightthickness=1, highlightbackground=BORDER, bd=0,
                  font=("Segoe UI", 10, "bold"), padx=14, pady=11,
                  cursor="hand2").pack(side="left", fill="x", expand=True, padx=(5, 0))

        tk.Label(self.root, text="Nothing is sent anywhere — all checks run on this page.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(pady=(16, 0))

        self.pw_var.trace_add("write", lambda *a: self.render())

    def _stat_cell(self, parent, val, label):
        cell = tk.Frame(parent, bg=SURFACE2, highlightthickness=1, highlightbackground=BORDER)
        tk.Label(cell, text=val, bg=SURFACE2, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(pady=(8, 0))
        tk.Label(cell, text=label, bg=SURFACE2, fg=MUTED,
                 font=("Segoe UI", 8)).pack(pady=(0, 8))
        return cell

    # ---------- actions ----------
    def toggle_show(self):
        self.shown = not self.shown
        self.entry.config(show="" if self.shown else "*")
        self.eye_btn.config(text="🙈" if self.shown else "👁️")

    def copy(self):
        pw = self.pw_var.get()
        if not pw:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(pw)
        self.copy_btn.config(text="✅")
        self.root.after(1200, lambda: self.copy_btn.config(text="📋"))

    def generate(self):
        pw = [secrets.choice(LOWER), secrets.choice(UPPER),
              secrets.choice(DIGITS), secrets.choice(SYMBOLS)]
        while len(pw) < 16:
            pw.append(secrets.choice(ALL))
        for i in range(len(pw) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            pw[i], pw[j] = pw[j], pw[i]
        self.pw_var.set("".join(pw))
        if not self.shown:
            self.toggle_show()
        self.root.after(1500, self._rehide)

    def _rehide(self):
        if self.shown:
            self.toggle_show()

    def clear(self):
        self.pw_var.set("")
        if self.shown:
            self.toggle_show()

    # ---------- render ----------
    def render(self):
        pw = self.pw_var.get()
        has, entropy, common, level = analyze(pw)
        name, color = LEVELS[level]

        for i, s in enumerate(self.segs):
            on = bool(pw) and i < level + 1
            s.config(bg=color if on else SURFACE2,
                     highlightbackground=color if on else BORDER)

        self.label.config(text=name if pw else "—",
                          fg=color if pw else MUTED)

        self.crack_cell.winfo_children()[0].config(
            text=crack_time(entropy) if pw else "—")
        self.entropy_cell.winfo_children()[0].config(
            text=f"{round(entropy)} bits" if pw else "—")

        reqs = [
            len(pw) >= 12,
            has["upper"],
            has["lower"],
            has["digit"],
            has["symbol"],
            bool(pw) and not common,
        ]
        for (box, lbl), ok in zip(self.check_rows, reqs):
            if ok:
                box.config(bg="#0d3b26", fg=ACCENT)
                lbl.config(fg=TEXT)
            else:
                box.config(bg=SURFACE2, fg=SURFACE2)
                lbl.config(fg=MUTED)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
