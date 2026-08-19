import hashlib
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog

# ---------- Emerald Deep ----------
BG = "#04120c"
SURFACE = "#071a12"
SURFACE2 = "#0c241a"
BORDER = "#14372a"
TEXT = "#dff7ea"
MUTED = "#7aa08c"
ACCENT = "#10b981"
ACCENT2 = "#34d399"
GOOD = "#10b981"
BAD = "#f87171"

CHUNK = 1024 * 1024  # 1 MB


def human_size(n):
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.0f} {units[i]}" if i == 0 else f"{n:.1f} {units[i]}"


def hash_file(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def open_folder(path):
    folder = os.path.dirname(path)
    try:
        if sys.platform == "win32":
            os.startfile(folder)  # type: ignore
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
    except OSError:
        pass


def scan_duplicates(folder, progress=None):
    by_size = {}
    total_files = 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in files:
            if fn.startswith("."):
                continue
            full = os.path.join(root, fn)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size == 0:
                continue
            by_size.setdefault(size, []).append(full)
            total_files += 1

    candidates = []
    for size, files in by_size.items():
        if len(files) >= 2:
            candidates.extend((f, size) for f in files)

    by_hash = {}
    for i, (full, size) in enumerate(candidates):
        if progress:
            progress(i, len(candidates), total_files)
        try:
            h = hash_file(full)
        except OSError:
            continue
        by_hash.setdefault((h, size), []).append(full)

    groups = []
    for (h, size), files in by_hash.items():
        if len(files) >= 2:
            groups.append({"size": size, "files": sorted(files)})

    groups.sort(key=lambda g: -g["size"] * (len(g["files"]) - 1))
    return groups


class App:
    def __init__(self, root):
        self.root = root
        root.title("Duplicate Finder")
        root.configure(bg=BG)
        root.geometry("900x720")
        root.minsize(640, 520)

        self.folder = ""
        self.groups = []
        self.vars = []       # list of (path, BooleanVar) in render order
        self.trash = []      # list of (trash_path, original_path)
        self.q = queue.Queue()
        self.scanning = False

        self._build()
        self.root.after(150, self.poll_queue)

    # ---------- ui ----------
    def _build(self):
        tk.Label(self.root, text="🧹 Duplicate Finder", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 20, "bold")).pack(pady=(16, 10))

        # folder + scan
        card = tk.Frame(self.root, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=16, pady=(0, 8))

        row = tk.Frame(card, bg=SURFACE)
        row.pack(fill="x", padx=12, pady=12)

        self.folder_var = tk.StringVar()
        self.folder_entry = tk.Entry(row, textvariable=self.folder_var, bg=SURFACE2,
                                     fg=TEXT, insertbackground=TEXT, relief="flat",
                                     font=("Segoe UI", 10), state="readonly")
        self.folder_entry.pack(side="left", fill="x", expand=True, ipady=9)

        tk.Button(row, text="Browse", command=self.pick_folder, bg=SURFACE2, fg=ACCENT,
                  activebackground=ACCENT2, activeforeground=BG, relief="flat", bd=0,
                  font=("Segoe UI", 9, "bold"), padx=12, pady=9,
                  cursor="hand2").pack(side="left", padx=(8, 0))

        self.scan_btn = tk.Button(row, text="🔍 Scan", command=self.toggle_scan, bg=ACCENT,
                                  fg=BG, activebackground=ACCENT2, activeforeground=BG,
                                  relief="flat", bd=0, font=("Segoe UI", 10, "bold"),
                                  padx=16, pady=9, cursor="hand2")
        self.scan_btn.pack(side="left", padx=(8, 0))

        # summary
        self.summary = tk.Label(self.root, text="Pick a folder to scan", bg=BG, fg=MUTED,
                                font=("Segoe UI", 10))
        self.summary.pack(anchor="w", padx=18, pady=(0, 6))

        # results
        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        sb.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=sb.set)

        self.inner = tk.Frame(self.canvas, bg=BG)
        self.inner.bind("<Configure>", lambda e:
                        self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

        # bottom bar
        bottom = tk.Frame(self.root, bg=SURFACE, highlightthickness=1,
                          highlightbackground=BORDER)
        bottom.pack(fill="x", side="bottom")

        self.status_lbl = tk.Label(bottom, text="", bg=SURFACE, fg=MUTED,
                                   font=("Segoe UI", 10), anchor="w", padx=12, pady=8)
        self.status_lbl.pack(side="left", fill="x", expand=True)

        self.restore_btn = tk.Button(bottom, text="↩️ Restore all", command=self.restore_all,
                                     bg=SURFACE2, fg=TEXT, activebackground=SURFACE2,
                                     activeforeground=ACCENT, relief="flat", bd=0,
                                     font=("Segoe UI", 10, "bold"), padx=12, pady=6,
                                     cursor="hand2")
        self.delete_btn = tk.Button(bottom, text="🗑️ Delete selected", command=self.delete_selected,
                                    bg=BAD, fg="#fff", activebackground=BAD,
                                    activeforeground="#fff", relief="flat", bd=0,
                                    font=("Segoe UI", 10, "bold"), padx=14, pady=6,
                                    cursor="hand2")
        self.delete_btn.pack(side="right", padx=12)

    def _on_wheel(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120), "units")

    def set_status(self, text):
        self.status_lbl.config(text=text)

    # ---------- actions ----------
    def pick_folder(self):
        d = filedialog.askdirectory(title="Folder to scan")
        if d:
            self.folder = d
            self.folder_var.set(d)

    def toggle_scan(self):
        if self.scanning:
            self.scanning = False
            self.scan_btn.config(text="🔍 Scan")
            self.set_status("Stopped")
            return
        if not self.folder or not os.path.isdir(self.folder):
            self.set_status("⚠️ Pick a folder first")
            return
        self.scanning = True
        self.scan_btn.config(text="⏹ Stop")
        self.set_status("Scanning…")
        threading.Thread(target=self._scan, daemon=True).start()

    def _scan(self):
        folder = self.folder
        last = [0]
        def progress(i, total, files):
            if i - last[0] >= 50 or i == total - 1:
                last[0] = i
                self.q.put(("progress", f"Scanning… {i + 1}/{total} files to hash"))
        try:
            groups = scan_duplicates(folder, progress)
            self.q.put(("done", groups))
        except Exception as e:
            self.q.put(("error", str(e)))

    def poll_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "progress":
                    self.set_status(payload)
                elif kind == "error":
                    self.scanning = False
                    self.scan_btn.config(text="🔍 Scan")
                    self.set_status("⚠️ " + payload)
                elif kind == "done":
                    self.scanning = False
                    self.scan_btn.config(text="🔍 Scan")
                    self.groups = payload
                    self.render()
                    self.summarize()
        except queue.Empty:
            pass
        self.root.after(150, self.poll_queue)

    def summarize(self):
        dupes = sum(len(g["files"]) - 1 for g in self.groups)
        wasted = sum(g["size"] * (len(g["files"]) - 1) for g in self.groups)
        self.summary.config(text=f"{len(self.groups)} groups · {dupes} duplicates · "
                                 f"{human_size(wasted)} to reclaim")

    # ---------- render ----------
    def render(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.vars = []

        if not self.groups:
            tk.Label(self.inner, text="No duplicates found 🎉", bg=BG, fg=MUTED,
                     font=("Segoe UI", 11), pady=24).pack()
            self.delete_btn.pack_forget()
            self.restore_btn.pack_forget()
            return

        self.delete_btn.pack(side="right", padx=12)
        if self.trash:
            self.restore_btn.pack(side="right", padx=(0, 4))

        for gi, g in enumerate(self.groups):
            head = tk.Frame(self.inner, bg=ACCENT)
            head.pack(fill="x", pady=(12, 2))
            tk.Label(head, text=f"{human_size(g['size'])}  ·  {len(g['files'])} copies",
                     bg=ACCENT, fg=BG, font=("Segoe UI", 10, "bold"),
                     anchor="w", padx=10, pady=3).pack(fill="x")

            for fi, path in enumerate(g["files"]):
                var = tk.BooleanVar(value=(fi != 0))  # keep first, select rest
                self.vars.append((path, var))

                row = tk.Frame(self.inner, bg=SURFACE)
                row.pack(fill="x", pady=1)

                cb = tk.Checkbutton(row, variable=var, bg=SURFACE, activebackground=SURFACE,
                                    selectcolor=SURFACE2, cursor="hand2")
                cb.pack(side="left", padx=(6, 2))

                name = os.path.basename(path)
                folder = os.path.dirname(path)
                info = tk.Frame(row, bg=SURFACE)
                info.pack(side="left", fill="x", expand=True)
                tk.Label(info, text=name, bg=SURFACE, fg=TEXT, anchor="w",
                         font=("Segoe UI", 10)).pack(anchor="w")
                tk.Label(info, text=folder, bg=SURFACE, fg=MUTED, anchor="w",
                         font=("Segoe UI", 8)).pack(anchor="w")

                if fi == 0:
                    tk.Label(row, text="keep", bg=SURFACE, fg=ACCENT,
                             font=("Segoe UI", 9, "bold"), padx=8).pack(side="left")
                else:
                    tk.Button(row, text="📂", command=lambda p=path: open_folder(p),
                              bg=SURFACE, fg=MUTED, activebackground=SURFACE2,
                              activeforeground=ACCENT, relief="flat", bd=0,
                              font=("Segoe UI", 10), cursor="hand2", width=3).pack(
                              side="left", padx=(0, 6))

    def delete_selected(self):
        trash_root = os.path.join(self.folder, ".dupe_trash")
        os.makedirs(trash_root, exist_ok=True)

        removed = 0
        kept_groups = []
        new_vars = []
        for path, var in self.vars:
            if var.get():
                stamp = time.strftime("%Y%m%d_%H%M%S")
                base, ext = os.path.splitext(os.path.basename(path))
                dest = os.path.join(trash_root, f"{base}_{stamp}{ext}")
                i = 1
                while os.path.exists(dest):
                    dest = os.path.join(trash_root, f"{base}_{stamp}_{i}{ext}")
                    i += 1
                try:
                    os.rename(path, dest)
                    self.trash.append((dest, path))
                    removed += 1
                except OSError:
                    pass
            else:
                new_vars.append((path, var))

        # rebuild groups without deleted files
        remaining = set(p for p, _ in new_vars)
        new_groups = []
        for g in self.groups:
            files = [f for f in g["files"] if f in remaining]
            if len(files) >= 2:
                new_groups.append({"size": g["size"], "files": files})
        self.groups = new_groups

        self.render()
        self.summarize()
        if self.trash:
            self.restore_btn.pack(side="right", padx=(0, 4))
        self.set_status(f"🗑️ Moved {removed} to trash" if removed else "Nothing selected")

    def restore_all(self):
        restored = 0
        failed = []
        for dest, orig in self.trash:
            try:
                os.makedirs(os.path.dirname(orig), exist_ok=True)
                os.rename(dest, orig)
                restored += 1
            except OSError:
                failed.append((dest, orig))
        self.trash = failed
        if self.folder and os.path.isdir(self.folder):
            threading.Thread(target=self._rescan_after_restore, daemon=True).start()
        self.set_status(f"↩️ Restored {restored}")

    def _rescan_after_restore(self):
        try:
            groups = scan_duplicates(self.folder)
            self.q.put(("done", groups))
        except Exception:
            pass


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
