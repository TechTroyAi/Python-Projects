import datetime as dt
import json
import os
import queue
import shutil
import threading
import time
import zipfile
import tkinter as tk
from tkinter import filedialog

# ---------- Luxury Gold ----------
BG = "#12100a"
CARD = "#1a170e"
CARD2 = "#241f13"
BORDER = "#3a311c"
TEXT = "#f5ecd7"
MUTED = "#a89a76"
ACCENT = "#e0b64f"
ACCENT2 = "#b98a2f"
GOOD = "#4ade80"
BAD = "#ef4444"
ON_GOLD = "#12100a"  # text on gold buttons

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE, "backup_config.json")
HISTORY_FILE = os.path.join(BASE, "backup_history.json")


def count_source(source):
    files = 0
    size = 0
    for _, _, fnames in os.walk(source):
        for fn in fnames:
            files += 1
            try:
                size += os.path.getsize(os.path.join(source, fn))
            except OSError:
                pass
    return files, size


def do_backup(source, dest, compress):
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    name = "backup_" + stamp
    files, size = count_source(source)

    # Make the name unique so fast backups never collide
    i = 1
    while os.path.exists(os.path.join(dest, name + (".zip" if compress else ""))):
        name = f"backup_{stamp}_{i}"
        i += 1

    if compress:
        path = os.path.join(dest, name + ".zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, fnames in os.walk(source):
                for fn in fnames:
                    full = os.path.join(root, fn)
                    zf.write(full, os.path.relpath(full, source))
        size = os.path.getsize(path)
    else:
        path = os.path.join(dest, name)
        shutil.copytree(source, path)

    return {"name": name + (".zip" if compress else ""), "path": path,
            "files": files, "size": size, "compressed": compress}


def cleanup_old(dest, keep):
    if keep <= 0:
        return 0
    items = []
    for x in os.listdir(dest):
        if x.startswith("backup_"):
            p = os.path.join(dest, x)
            if os.path.isdir(p) or x.endswith(".zip"):
                items.append(p)
    items.sort(key=os.path.getmtime)
    removed = 0
    while len(items) > keep:
        p = items.pop(0)
        try:
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
            removed += 1
        except OSError:
            pass
    return removed


def human_size(n):
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.0f} {units[i]}" if i == 0 else f"{n:.1f} {units[i]}"


class App:
    def __init__(self, root):
        self.root = root
        root.title("Auto Backup")
        root.configure(bg=BG)
        root.geometry("860x720")
        root.minsize(620, 560)

        self.cfg = self.load(CONFIG_FILE, {
            "source": "", "dest": "", "interval": 30, "keep": 5, "compress": False,
        })
        self.history = self.load(HISTORY_FILE, [])
        self.running = False
        self.q = queue.Queue()
        self.interval_var = tk.IntVar(value=self.cfg["interval"])
        self.keep_var = tk.IntVar(value=self.cfg["keep"])
        self.compress_var = tk.BooleanVar(value=self.cfg["compress"])

        self._build()
        self.load_cfg_into_ui()
        self.render_history()
        self.root.after(200, self.poll_queue)

    # ---------- data ----------
    def load(self, path, default):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return default

    def save_cfg(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=2)
        except OSError:
            pass

    def save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history[:200], f, indent=2)
        except OSError:
            pass

    # ---------- ui ----------
    def _build(self):
        tk.Label(self.root, text="🛡️ Auto Backup", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 20, "bold")).pack(pady=(16, 10))

        # --- source / dest ---
        card = tk.Frame(self.root, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=16, pady=(0, 8))

        self.source_var = tk.StringVar()
        self.dest_var = tk.StringVar()

        self._dir_row(card, "📁 Source", self.source_var, self.pick_source)
        self._dir_row(card, "💾 Save to", self.dest_var, self.pick_dest)

        # --- schedule ---
        ctrl = tk.Frame(self.root, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        ctrl.pack(fill="x", padx=16, pady=(0, 8))

        left = tk.Frame(ctrl, bg=CARD)
        left.pack(side="left", padx=12, pady=10)

        self.start_btn = tk.Button(left, text="▶️ Start", command=self.toggle, bg=ACCENT,
                                   fg=ON_GOLD, activebackground=ACCENT2,
                                   activeforeground=ON_GOLD, relief="flat", bd=0,
                                   font=("Segoe UI", 10, "bold"), padx=16, pady=8,
                                   cursor="hand2")
        self.start_btn.pack(side="left")

        tk.Button(left, text="✨ Back up now", command=self.backup_now, bg=ACCENT2,
                  fg=ON_GOLD, activebackground=ACCENT, activeforeground=ON_GOLD,
                  relief="flat", bd=0, font=("Segoe UI", 10, "bold"), padx=16,
                  pady=8, cursor="hand2").pack(side="left", padx=(8, 0))

        tk.Label(left, text="every", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(16, 6))
        self.interval_entry = tk.Entry(left, textvariable=self.interval_var, bg=CARD2,
                                       fg=TEXT, insertbackground=TEXT, relief="flat",
                                       font=("Segoe UI", 10), width=4, justify="center")
        self.interval_entry.pack(side="left", ipady=6)
        tk.Label(left, text="min", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))

        right = tk.Frame(ctrl, bg=CARD)
        right.pack(side="right", padx=12, pady=10)

        tk.Checkbutton(right, text="Compress to .zip", variable=self.compress_var,
                       bg=CARD, fg=TEXT, selectcolor=CARD2, activebackground=CARD,
                       activeforeground=TEXT, font=("Segoe UI", 9),
                       cursor="hand2").pack(side="left")

        tk.Label(right, text="keep last", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(16, 6))
        self.keep_entry = tk.Entry(right, textvariable=self.keep_var, bg=CARD2,
                                   fg=TEXT, insertbackground=TEXT, relief="flat",
                                   font=("Segoe UI", 10), width=4, justify="center")
        self.keep_entry.pack(side="left", ipady=6)

        # --- history ---
        hist = tk.Frame(self.root, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        hist.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        tk.Label(hist, text="BACKUP HISTORY", bg=CARD, fg=ACCENT,
                 font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 4))

        wrap = tk.Frame(hist, bg=CARD)
        wrap.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        self.canvas = tk.Canvas(wrap, bg=CARD, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        sb.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=sb.set)

        self.inner = tk.Frame(self.canvas, bg=CARD)
        self.inner.bind("<Configure>", lambda e:
                        self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

        # --- status ---
        bottom = tk.Frame(self.root, bg=CARD)
        bottom.pack(fill="x", side="bottom")
        self.status_lbl = tk.Label(bottom, text="Pick a source folder to begin", bg=CARD,
                                   fg=MUTED, font=("Segoe UI", 10), anchor="w",
                                   padx=12, pady=8)
        self.status_lbl.pack(fill="x")

    def _dir_row(self, parent, label, var, cmd):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", padx=12, pady=(12, 0))
        tk.Label(row, text=label, bg=CARD, fg=MUTED, font=("Segoe UI", 9, "bold"),
                 width=10, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=var, bg=CARD2, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=("Segoe UI", 10), state="readonly").pack(
                 side="left", fill="x", expand=True, ipady=8)
        tk.Button(row, text="Browse", command=cmd, bg=CARD2, fg=ACCENT,
                  activebackground=ACCENT2, activeforeground=ON_GOLD, relief="flat",
                  bd=0, font=("Segoe UI", 9, "bold"), padx=12, pady=7,
                  cursor="hand2").pack(side="left", padx=(8, 0))
        tk.Frame(parent, bg=CARD).pack(fill="x", padx=12, pady=(0, 12))

    def _on_wheel(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120), "units")

    def set_status(self, text):
        self.status_lbl.config(text=text)

    def load_cfg_into_ui(self):
        if self.cfg["source"]:
            self.source_var.set(self.cfg["source"])
        if self.cfg["dest"]:
            self.dest_var.set(self.cfg["dest"])

    # ---------- pickers ----------
    def pick_source(self):
        d = filedialog.askdirectory(title="Source folder")
        if d:
            self.source_var.set(d)
            self.cfg["source"] = d
            self.save_cfg()

    def pick_dest(self):
        d = filedialog.askdirectory(title="Where to save backups")
        if d:
            self.dest_var.set(d)
            self.cfg["dest"] = d
            self.save_cfg()

    # ---------- backup ----------
    def _read_settings(self):
        source = self.cfg["source"]
        dest = self.cfg["dest"]
        try:
            interval = max(1, int(self.interval_var.get()))
        except Exception:
            interval = 30
        try:
            keep = max(0, int(self.keep_var.get()))
        except Exception:
            keep = 0
        compress = bool(self.compress_var.get())
        self.cfg.update(source=source, dest=dest, interval=interval,
                        keep=keep, compress=compress)
        self.save_cfg()
        return source, dest, interval, keep, compress

    def backup_now(self):
        source, dest, interval, keep, compress = self._read_settings()
        if not source or not os.path.isdir(source):
            self.set_status("⚠️ Pick a source folder")
            return
        if not dest or not os.path.isdir(dest):
            self.set_status("⚠️ Pick where to save")
            return
        self.set_status("Backing up…")
        threading.Thread(target=self._run_backup, daemon=True).start()

    def _run_backup(self):
        source = self.cfg["source"]
        dest = self.cfg["dest"]
        compress = self.cfg["compress"]
        keep = self.cfg["keep"]
        try:
            start = time.time()
            result = do_backup(source, dest, compress)
            result["secs"] = round(time.time() - start)
            removed = cleanup_old(dest, keep)
            result["removed"] = removed
            self.q.put(("done", result))
        except Exception as e:
            self.q.put(("error", str(e)))

    def toggle(self):
        if self.running:
            self.running = False
            self.start_btn.config(text="▶️ Start")
            self.set_status("Stopped")
        else:
            source, dest, interval, keep, compress = self._read_settings()
            if not source or not os.path.isdir(source):
                self.set_status("⚠️ Pick a source folder")
                return
            if not dest or not os.path.isdir(dest):
                self.set_status("⚠️ Pick where to save")
                return
            self.running = True
            self.start_btn.config(text="⏹ Stop")
            self.set_status(f"Auto backup every {interval} min")
            threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self.running:
            self.q.put(("status", "Backing up…"))
            try:
                start = time.time()
                result = do_backup(self.cfg["source"], self.cfg["dest"],
                                   self.cfg["compress"])
                result["secs"] = round(time.time() - start)
                removed = cleanup_old(self.cfg["dest"], self.cfg["keep"])
                result["removed"] = removed
                self.q.put(("done", result))
            except Exception as e:
                self.q.put(("error", str(e)))
            try:
                interval = max(1, int(self.interval_var.get()))
            except Exception:
                interval = 30
            for _ in range(interval * 60):
                if not self.running:
                    return
                time.sleep(1)

    def poll_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "status":
                    self.set_status(payload)
                elif kind == "error":
                    self.set_status("⚠️ " + payload)
                elif kind == "done":
                    self.history.insert(0, {
                        "ts": dt.datetime.now().strftime("%b %d · %I:%M:%S %p"),
                        "name": payload["name"],
                        "files": payload["files"],
                        "size": payload["size"],
                        "secs": payload["secs"],
                    })
                    self.save_history()
                    self.render_history()
                    self.set_status(
                        f"✅ {payload['name']} · {payload['files']} files · "
                        f"{human_size(payload['size'])} · {payload['secs']}s"
                        + (f" · removed {payload['removed']} old" if payload.get("removed") else "")
                    )
        except queue.Empty:
            pass
        self.root.after(200, self.poll_queue)

    def render_history(self):
        for w in self.inner.winfo_children():
            w.destroy()
        if not self.history:
            tk.Label(self.inner, text="No backups yet", bg=CARD, fg=MUTED,
                     font=("Segoe UI", 10), pady=16).pack()
            return
        for h in self.history:
            row = tk.Frame(self.inner, bg=CARD)
            row.pack(fill="x", pady=1)
            tk.Label(row, text="🛡️", bg=CARD, fg=ACCENT,
                     font=("Segoe UI", 11)).pack(side="left", padx=(8, 6))
            tk.Label(row, text=h["name"], bg=CARD, fg=TEXT, anchor="w",
                     font=("Segoe UI", 10, "bold")).pack(side="left")
            tk.Label(row, text=f"{h['files']} files · {human_size(h['size'])} · {h['secs']}s",
                     bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=10)
            tk.Label(row, text=h["ts"], bg=CARD, fg=MUTED,
                     font=("Segoe UI", 9)).pack(side="right", padx=10)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
