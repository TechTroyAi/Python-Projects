import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox

BG = "#060d1f"
CARD = "#0a1227"
CARD2 = "#0e1a35"
BORDER = "#1c2b4d"
TEXT = "#d4e2ef"
MUTED = "#859fc0"
ACCENT = "#315381"
ACCENT2 = "#4c638c"
DANGER = "#f87171"

CATEGORIES = [
    ("Images",     "🖼️", "#4c638c", {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".heic", ".ico", ".tiff"}),
    ("Videos",     "🎬", "#859fc0", {".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm", ".m4v", ".3gp"}),
    ("Music",      "🎵", "#315381", {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"}),
    ("Documents",  "📄", "#cee0f4", {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv", ".rtf", ".odt"}),
    ("Archives",   "🗜️", "#6b82ab", {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"}),
    ("Installers", "💿", "#4c638c", {".exe", ".msi", ".dmg", ".deb", ".apk", ".pkg", ".appimage"}),
    ("Code",       "💻", "#859fc0", {".py", ".js", ".html", ".css", ".json", ".xml", ".ipynb", ".c", ".cpp", ".java", ".ts", ".sql"}),
    ("Torrents",   "🧲", "#315381", {".torrent"}),
    ("Others",     "📦", "#859fc0", set()),
]

TRASH_NAME = ".trash"


def get_category(name):
    ext = os.path.splitext(name)[1].lower()
    for cat, emoji, color, exts in CATEGORIES:
        if ext in exts:
            return cat, emoji, color
    return "Others", "📦", "#859fc0"


def human_size(n):
    if not n:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.0f} {units[i]}" if i == 0 else f"{n:.1f} {units[i]}"


def unique_path(directory, name):
    base, ext = os.path.splitext(name)
    candidate = os.path.join(directory, name)
    i = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base} ({i}){ext}")
        i += 1
    return candidate


def text_on(hexcolor):
    r, g, b = int(hexcolor[1:3], 16), int(hexcolor[3:5], 16), int(hexcolor[5:7], 16)
    return "#060d1f" if (r * 0.299 + g * 0.587 + b * 0.114) > 150 else "#d4e2ef"


class App:
    def __init__(self, root):
        self.root = root
        root.title("Downloads Organizer")
        root.configure(bg=BG)
        root.geometry("920x720")
        root.minsize(640, 480)

        self.files = []
        self.trash = []
        self.root_dir = None
        self.last_deleted = []

        self._build()
        self.refresh()

    def _build(self):
        header = tk.Label(self.root, text="📁 Downloads Organizer", bg=BG, fg="#cee0f4",
                          font=("Segoe UI", 20, "bold"))
        header.pack(pady=(16, 12))

        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=16)

        self.preview = tk.BooleanVar(value=True)

        btn_open = tk.Button(top, text="📂 Open folder", command=self.open_folder,
                             bg=ACCENT, fg="#fff", activebackground=ACCENT2,
                             activeforeground="#fff", relief="flat", bd=0,
                             font=("Segoe UI", 11, "bold"), padx=16, pady=8, cursor="hand2")
        btn_open.pack(side="left")

        btn_org = tk.Button(top, text="🪄 Organize", command=self.organize,
                            bg=ACCENT2, fg="#fff", activebackground=ACCENT,
                            activeforeground="#fff", relief="flat", bd=0,
                            font=("Segoe UI", 11, "bold"), padx=16, pady=8, cursor="hand2")
        btn_org.pack(side="left", padx=(8, 0))

        chk = tk.Checkbutton(top, text="Preview only", variable=self.preview,
                             bg=BG, fg=MUTED, selectcolor=CARD2,
                             activebackground=BG, activeforeground=MUTED,
                             font=("Segoe UI", 10), cursor="hand2")
        chk.pack(side="left", padx=(14, 0))

        self.stats = tk.Label(self.root, text="", bg=BG, fg=MUTED, font=("Segoe UI", 10))
        self.stats.pack(anchor="w", padx=18, pady=(6, 4))

        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        sb.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=sb.set)

        self.inner = tk.Frame(self.canvas, bg=BG)
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

        self.status = tk.Label(self.root, text="Open a folder or Organize to start",
                               bg=CARD, fg=MUTED, font=("Segoe UI", 10), anchor="w",
                               padx=12, pady=8)
        self.status.pack(fill="x", side="bottom")

    def _on_wheel(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120), "units")

    def status(self, text):
        self.status.config(text=text)

    def scan(self, directory):
        result = []
        for dirpath, dirnames, filenames in os.walk(directory):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            rel = os.path.relpath(dirpath, directory)
            if rel == ".":
                rel = ""
            for fn in filenames:
                if fn.startswith("."):
                    continue
                full = os.path.join(dirpath, fn)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    size = 0
                result.append({"name": fn, "path": full, "rel": rel, "size": size})
        return result

    def open_folder(self):
        d = filedialog.askdirectory(title="Open folder")
        if not d:
            return
        self.root_dir = d
        self.trash = []
        self.files = self.scan(d)
        self.refresh()
        self.status(f"📂 {os.path.basename(d)} — {len(self.files)} files")

    def organize(self):
        if not self.root_dir:
            self.status("Open a folder first")
            return
        root = self.root_dir
        top = []
        for fn in os.listdir(root):
            if fn.startswith("."):
                continue
            full = os.path.join(root, fn)
            if os.path.isfile(full):
                top.append(full)

        if not top:
            self.status("No files to organize")
            return

        plan = {}
        if self.preview.get():
            for full in top:
                cat, _, _ = get_category(os.path.basename(full))
                plan[cat] = plan.get(cat, 0) + 1
            text = " · ".join(f"{c} {n}" for c, n in sorted(plan.items(), key=lambda x: -x[1]))
            self.status(f"🧪 Preview — {text}")
            return

        moved = 0
        for full in top:
            cat, _, _ = get_category(os.path.basename(full))
            dest = os.path.join(root, cat)
            os.makedirs(dest, exist_ok=True)
            target = unique_path(dest, os.path.basename(full))
            try:
                shutil.move(full, target)
                moved += 1
            except OSError:
                pass

        self.files = self.scan(root)
        self.trash = []
        self.refresh()
        self.status(f"✅ Moved {moved} files")

    def move_file(self, f):
        dest = filedialog.askdirectory(title="Move to")
        if not dest:
            return
        target = unique_path(dest, f["name"])
        try:
            shutil.move(f["path"], target)
            f["path"] = target
            f["rel"] = ""
            self.refresh()
            self.status(f"✅ Moved to {os.path.basename(dest)}")
        except OSError:
            self.status("⚠️ Move failed")

    def delete_file(self, f):
        trash_dir = os.path.join(self.root_dir, TRASH_NAME)
        os.makedirs(trash_dir, exist_ok=True)
        target = unique_path(trash_dir, f["name"])
        try:
            shutil.move(f["path"], target)
        except OSError:
            self.status("⚠️ Delete failed")
            return
        entry = {"name": f["name"], "trash_path": target,
                 "orig_dir": os.path.dirname(f["path"]), "size": f["size"]}
        self.trash.insert(0, entry)
        self.files = [x for x in self.files if x is not f]
        self.last_deleted = [entry]
        self.refresh()
        self.status("🗑️ Moved to trash")

    def undo(self):
        if not self.last_deleted:
            return
        for entry in self.last_deleted:
            target = unique_path(entry["orig_dir"], entry["name"])
            try:
                shutil.move(entry["trash_path"], target)
                self.trash.remove(entry)
                self.files.append({"name": entry["name"], "path": target,
                                   "rel": "", "size": entry["size"]})
            except OSError:
                pass
        self.last_deleted = []
        self.refresh()
        self.status("↩️ Restored")

    def restore_one(self, entry):
        target = unique_path(entry["orig_dir"], entry["name"])
        try:
            shutil.move(entry["trash_path"], target)
            self.trash.remove(entry)
            self.files.append({"name": entry["name"], "path": target,
                               "rel": "", "size": entry["size"]})
            self.refresh()
            self.status("↩️ Restored")
        except OSError:
            self.status("⚠️ Restore failed")

    def restore_all(self):
        for entry in list(self.trash):
            target = unique_path(entry["orig_dir"], entry["name"])
            try:
                shutil.move(entry["trash_path"], target)
                self.files.append({"name": entry["name"], "path": target,
                                   "rel": "", "size": entry["size"]})
                self.trash.remove(entry)
            except OSError:
                pass
        self.refresh()
        self.status("↩️ Restored all")

    def empty_trash(self):
        if not self.trash:
            return
        if not messagebox.askyesno("Empty trash", "Delete permanently?"):
            return
        for entry in self.trash:
            try:
                os.remove(entry["trash_path"])
            except OSError:
                pass
        self.trash = []
        self.refresh()
        self.status("🧹 Trash emptied")

    def refresh(self):
        for w in self.inner.winfo_children():
            w.destroy()

        groups = {}
        for f in self.files:
            cat, emoji, color = get_category(f["name"])
            groups.setdefault(cat, {"emoji": emoji, "color": color, "files": []})
            groups[cat]["files"].append(f)

        total = sum(f["size"] for f in self.files)
        self.stats.config(text=f"{len(self.files)} files · {len(groups)} folders · {human_size(total)}")

        for cat, info in sorted(groups.items(), key=lambda x: -len(x[1]["files"])):
            color = info["color"]
            head = tk.Frame(self.inner, bg=color)
            head.pack(fill="x", pady=(10, 2))
            tk.Label(head, text=f"{info['emoji']} {cat}  ({len(info['files'])})",
                     bg=color, fg=text_on(color), font=("Segoe UI", 11, "bold"),
                     anchor="w", padx=10, pady=4).pack(fill="x")

            for f in info["files"]:
                row = tk.Frame(self.inner, bg=CARD)
                row.pack(fill="x", pady=1)

                label = f["name"]
                if f["rel"]:
                    label = f"{f['rel']}/ {label}"
                lbl = tk.Label(row, text=label, bg=CARD, fg=TEXT, anchor="w",
                               font=("Segoe UI", 10), padx=10, pady=5)
                lbl.pack(side="left", fill="x", expand=True)

                tk.Label(row, text=human_size(f["size"]), bg=CARD, fg=MUTED,
                         font=("Segoe UI", 9), padx=8).pack(side="left")

                b_mv = tk.Button(row, text="📂", command=lambda f=f: self.move_file(f),
                                 bg=CARD, fg=MUTED, activebackground=CARD2,
                                 activeforeground=TEXT, relief="flat", bd=0,
                                 font=("Segoe UI", 11), cursor="hand2", width=3)
                b_mv.pack(side="right", padx=(2, 2))

                b_del = tk.Button(row, text="🗑️", command=lambda f=f: self.delete_file(f),
                                  bg=CARD, fg=MUTED, activebackground=CARD2,
                                  activeforeground=DANGER, relief="flat", bd=0,
                                  font=("Segoe UI", 11), cursor="hand2", width=3)
                b_del.pack(side="right", padx=(2, 6))

        if not self.files:
            tk.Label(self.inner, text="No files", bg=BG, fg=MUTED,
                     font=("Segoe UI", 11), pady=20).pack()

        if self.trash:
            head = tk.Frame(self.inner, bg=DANGER)
            head.pack(fill="x", pady=(16, 2))
            tk.Label(head, text=f"🗑️ Trash  ({len(self.trash)})", bg=DANGER,
                     fg="#fff", font=("Segoe UI", 11, "bold"), anchor="w",
                     padx=10, pady=4).pack(side="left", fill="x", expand=True)
            tk.Button(head, text="↩️ All", command=self.restore_all, bg=DANGER,
                      fg="#fff", activebackground=DANGER, activeforeground="#fff",
                      relief="flat", bd=0, font=("Segoe UI", 10), cursor="hand2",
                      padx=10).pack(side="left")
            tk.Button(head, text="🧹", command=self.empty_trash, bg=DANGER,
                      fg="#fff", activebackground=DANGER, activeforeground="#fff",
                      relief="flat", bd=0, font=("Segoe UI", 10), cursor="hand2",
                      padx=10).pack(side="left")

            for e in self.trash:
                row = tk.Frame(self.inner, bg=CARD)
                row.pack(fill="x", pady=1)
                tk.Label(row, text=e["name"], bg=CARD, fg=MUTED, anchor="w",
                         font=("Segoe UI", 10), padx=10, pady=5).pack(side="left",
                         fill="x", expand=True)
                tk.Button(row, text="↩️", command=lambda e=e: self.restore_one(e),
                          bg=CARD, fg=MUTED, activebackground=CARD2,
                          activeforeground=TEXT, relief="flat", bd=0,
                          font=("Segoe UI", 11), cursor="hand2", width=3).pack(
                          side="right", padx=(2, 6))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
