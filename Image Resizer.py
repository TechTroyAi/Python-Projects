import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from PIL import Image

# ---------- Royal Violet ----------
BG = "#0e0820"
SURFACE = "#150d2e"
SURFACE2 = "#1d133c"
BORDER = "#2c1f55"
TEXT = "#efe8ff"
MUTED = "#9886c4"
ACCENT = "#8b5cf6"
ACCENT2 = "#a78bfa"
GOOD = "#34d399"
BAD = "#fb7185"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff", ".ico"}

MODES = ["Max width", "Max height", "Max side", "Exact (WxH)", "Percent"]
FORMATS = ["Keep original", "JPG", "PNG", "WEBP"]


def human_size(n):
    units = ["B", "KB", "MB", "GB"]
    i = 0
    while n >= 1024 and i < len(units) - 1:
        n /= 1024
        i += 1
    return f"{n:.0f} {units[i]}" if i == 0 else f"{n:.1f} {units[i]}"


def unique_path(directory, filename):
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(directory, filename)
    i = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base} ({i}){ext}")
        i += 1
    return candidate


def resize_image(img, mode, value, keep_aspect, only_shrink):
    w, h = img.size
    if w <= 0 or h <= 0:
        return img

    if mode == "Max width":
        if only_shrink and w <= value:
            return img
        scale = value / w
        return img.resize((value, round(h * scale)), Image.LANCZOS)

    if mode == "Max height":
        if only_shrink and h <= value:
            return img
        scale = value / h
        return img.resize((round(w * scale), value), Image.LANCZOS)

    if mode == "Max side":
        big = max(w, h)
        if only_shrink and big <= value:
            return img
        scale = value / big
        return img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)

    if mode == "Percent":
        scale = value / 100
        return img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)

    # Exact (WxH)
    if keep_aspect:
        scale = min(value[0] / w, value[1] / h)
        return img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
    return img.resize(value, Image.LANCZOS)


def pick_format(path, fmt):
    if fmt == "Keep original":
        return os.path.splitext(path)[1] or ".png"
    return {"JPG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[fmt]


class App:
    def __init__(self, root):
        self.root = root
        root.title("Bulk Image Resizer")
        root.configure(bg=BG)
        root.geometry("860x700")
        root.minsize(640, 560)

        self.in_folder = ""
        self.out_folder = ""
        self.running = False
        self.q = queue.Queue()

        self.mode_var = tk.StringVar(value=MODES[0])
        self.value_var = tk.StringVar(value="800")
        self.aspect_var = tk.BooleanVar(value=True)
        self.shrink_var = tk.BooleanVar(value=True)
        self.format_var = tk.StringVar(value=FORMATS[0])
        self.quality_var = tk.IntVar(value=85)

        self._build()
        self.root.after(150, self.poll_queue)

    # ---------- ui ----------
    def _build(self):
        tk.Label(self.root, text="🖼️ Bulk Image Resizer", bg=BG, fg=ACCENT2,
                 font=("Segoe UI", 20, "bold")).pack(pady=(16, 10))

        # folders
        card = tk.Frame(self.root, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=16, pady=(0, 8))

        self.in_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self._dir_row(card, "📁 From", self.in_var, self.pick_in)
        self._dir_row(card, "💾 To", self.out_var, self.pick_out)

        # settings
        setcard = tk.Frame(self.root, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        setcard.pack(fill="x", padx=16, pady=(0, 8))

        grid = tk.Frame(setcard, bg=SURFACE)
        grid.pack(fill="x", padx=14, pady=12)

        # mode
        tk.Label(grid, text="Mode", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", pady=4)
        self.mode_box = ttk.Combobox(grid, textvariable=self.mode_var, values=MODES,
                                     state="readonly", width=16, font=("Segoe UI", 9))
        self.mode_box.grid(row=0, column=1, sticky="w", padx=(8, 20), pady=4)

        tk.Label(grid, text="Value", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", pady=4)
        self.value_entry = tk.Entry(grid, textvariable=self.value_var, bg=SURFACE2,
                                    fg=TEXT, insertbackground=TEXT, relief="flat",
                                    highlightthickness=1, highlightbackground=BORDER,
                                    font=("Segoe UI", 10), width=14)
        self.value_entry.grid(row=0, column=3, sticky="w", padx=(8, 0), pady=4)

        # format + quality
        tk.Label(grid, text="Format", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", pady=4)
        self.format_box = ttk.Combobox(grid, textvariable=self.format_var, values=FORMATS,
                                       state="readonly", width=16, font=("Segoe UI", 9))
        self.format_box.grid(row=1, column=1, sticky="w", padx=(8, 20), pady=4)

        tk.Label(grid, text="Quality", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).grid(row=1, column=2, sticky="w", pady=4)
        qrow = tk.Frame(grid, bg=SURFACE)
        qrow.grid(row=1, column=3, sticky="w", padx=(8, 0), pady=4)
        self.quality_scale = tk.Scale(qrow, from_=1, to=100, orient="horizontal",
                                      variable=self.quality_var, bg=SURFACE, fg=TEXT,
                                      highlightthickness=0, troughcolor=SURFACE2,
                                      activebackground=ACCENT, length=140,
                                      font=("Segoe UI", 8), showvalue=True)
        self.quality_scale.pack(side="left")
        self.quality_lbl = tk.Label(qrow, text="", bg=SURFACE, fg=MUTED,
                                    font=("Segoe UI", 8))
        self.quality_lbl.pack(side="left", padx=(8, 0))

        # checkboxes
        checks = tk.Frame(setcard, bg=SURFACE)
        checks.pack(fill="x", padx=14, pady=(0, 12))
        tk.Checkbutton(checks, text="Keep aspect ratio", variable=self.aspect_var,
                       bg=SURFACE, fg=TEXT, selectcolor=SURFACE2, activebackground=SURFACE,
                       activeforeground=TEXT, font=("Segoe UI", 9),
                       cursor="hand2").pack(side="left")
        tk.Checkbutton(checks, text="Only shrink (never enlarge)", variable=self.shrink_var,
                       bg=SURFACE, fg=TEXT, selectcolor=SURFACE2, activebackground=SURFACE,
                       activeforeground=TEXT, font=("Segoe UI", 9),
                       cursor="hand2").pack(side="left", padx=(16, 0))

        # progress
        prog = tk.Frame(self.root, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        prog.pack(fill="x", padx=16, pady=(0, 8))

        self.progress_canvas = tk.Canvas(prog, bg=SURFACE, height=26, highlightthickness=0)
        self.progress_canvas.pack(fill="x", padx=12, pady=(12, 0))
        self.progress_canvas.bind("<Configure>", lambda e: self._draw_progress())

        self.progress_lbl = tk.Label(prog, text="Ready", bg=SURFACE, fg=MUTED,
                                     font=("Segoe UI", 9), anchor="w")
        self.progress_lbl.pack(fill="x", padx=12, pady=(4, 10))

        # start button
        self.go_btn = tk.Button(self.root, text="🪄 Resize", command=self.toggle,
                                bg=ACCENT, fg="#fff", activebackground=ACCENT2,
                                activeforeground="#fff", relief="flat", bd=0,
                                font=("Segoe UI", 12, "bold"), padx=20, pady=11,
                                cursor="hand2")
        self.go_btn.pack(fill="x", padx=16, pady=(0, 8))

        # results
        res = tk.Frame(self.root, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        res.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        tk.Label(res, text="RESULTS", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 4))

        wrap = tk.Frame(res, bg=SURFACE)
        wrap.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        self.canvas = tk.Canvas(wrap, bg=SURFACE, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        sb.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=sb.set)

        self.inner = tk.Frame(self.canvas, bg=SURFACE)
        self.inner.bind("<Configure>", lambda e:
                        self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _dir_row(self, parent, label, var, cmd):
        row = tk.Frame(parent, bg=SURFACE)
        row.pack(fill="x", padx=12, pady=(12, 0))
        tk.Label(row, text=label, bg=SURFACE, fg=MUTED, font=("Segoe UI", 9, "bold"),
                 width=9, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=var, bg=SURFACE2, fg=TEXT, insertbackground=TEXT,
                 relief="flat", font=("Segoe UI", 10), state="readonly").pack(
                 side="left", fill="x", expand=True, ipady=8)
        tk.Button(row, text="Browse", command=cmd, bg=SURFACE2, fg=ACCENT2,
                  activebackground=ACCENT, activeforeground="#fff", relief="flat",
                  bd=0, font=("Segoe UI", 9, "bold"), padx=12, pady=7,
                  cursor="hand2").pack(side="left", padx=(8, 0))
        tk.Frame(parent, bg=SURFACE).pack(fill="x", padx=12, pady=(0, 12))

    def _on_wheel(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120), "units")

    def _draw_progress(self):
        self.progress_canvas.delete("all")
        w = self.progress_canvas.winfo_width()
        frac = self._progress_frac
        if w > 10:
            self.progress_canvas.create_rectangle(0, 4, w, 22, fill=SURFACE2, outline="")
            if frac > 0:
                self.progress_canvas.create_rectangle(0, 4, w * frac, 22,
                                                      fill=ACCENT, outline="")

    # ---------- pickers ----------
    def pick_in(self):
        d = filedialog.askdirectory(title="Folder with images")
        if d:
            self.in_folder = d
            self.in_var.set(d)

    def pick_out(self):
        d = filedialog.askdirectory(title="Where to save resized images")
        if d:
            self.out_folder = d
            self.out_var.set(d)

    # ---------- run ----------
    def toggle(self):
        if self.running:
            self.running = False
            self.go_btn.config(text="🪄 Resize")
            self.progress_lbl.config(text="Stopped")
            return
        if not self.in_folder or not os.path.isdir(self.in_folder):
            self.progress_lbl.config(text="⚠️ Pick a folder with images")
            return
        self.running = True
        self.go_btn.config(text="⏹ Stop")
        self._progress_frac = 0
        self._draw_progress()
        self.q.put(("clear", None))
        threading.Thread(target=self._work, daemon=True).start()

    def _parse_value(self, mode, raw):
        raw = raw.strip()
        if mode == "Exact (WxH)":
            parts = raw.lower().replace("x", " ").split()
            if len(parts) == 2:
                w, h = int(parts[0]), int(parts[1])
                return (w, h)
            raise ValueError("exact")
        return int(raw)

    def _work(self):
        out = self.out_folder or os.path.join(self.in_folder, "resized")
        os.makedirs(out, exist_ok=True)

        files = []
        for fn in sorted(os.listdir(self.in_folder)):
            if os.path.splitext(fn)[1].lower() in IMAGE_EXTS:
                files.append(fn)

        if not files:
            self.q.put(("error", "No images found in that folder"))
            self.running = False
            return

        try:
            mode = self.mode_var.get()
            value = self._parse_value(mode, self.value_var.get())
        except ValueError:
            self.q.put(("error", "Bad value — for Exact use 800x600"))
            self.running = False
            return

        keep_aspect = self.aspect_var.get()
        only_shrink = self.shrink_var.get()
        fmt = self.format_var.get()
        quality = self.quality_var.get()

        done = 0
        for i, fn in enumerate(files):
            if not self.running:
                self.q.put(("status", "Stopped"))
                return
            src = os.path.join(self.in_folder, fn)
            try:
                with Image.open(src) as img:
                    if img.mode in ("P", "LA") or (img.mode == "RGBA" and fmt == "JPG"):
                        img = img.convert("RGB") if fmt == "JPG" else img.convert("RGBA")
                    orig_w, orig_h = img.size
                    new_img = resize_image(img, mode, value, keep_aspect, only_shrink)
                    ext = pick_format(fn, fmt)
                    base = os.path.splitext(fn)[0] + ext
                    dest = unique_path(out, base)
                    save_kwargs = {}
                    if ext in (".jpg", ".webp"):
                        save_kwargs["quality"] = quality
                    new_img.save(dest, **save_kwargs)
                osize = os.path.getsize(src)
                nsize = os.path.getsize(dest)
                done += 1
                self.q.put(("result", {"name": fn, "orig": f"{orig_w}x{orig_h}",
                                       "new": f"{new_img.size[0]}x{new_img.size[1]}",
                                       "before": human_size(osize), "after": human_size(nsize)}))
            except Exception as e:
                self.q.put(("result", {"name": fn, "orig": "—", "new": "⚠️ " + str(e),
                                       "before": "—", "after": "—"}))
            self.q.put(("progress", (i + 1, len(files))))

        self.q.put(("done", f"✅ {done} images resized → {out}"))
        self.running = False

    def poll_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "clear":
                    for w in self.inner.winfo_children():
                        w.destroy()
                elif kind == "progress":
                    done, total = payload
                    self._progress_frac = done / total if total else 0
                    self._draw_progress()
                    self.progress_lbl.config(text=f"{done}/{total}")
                elif kind == "result":
                    self._add_result(payload)
                elif kind == "error":
                    self.progress_lbl.config(text="⚠️ " + payload)
                elif kind == "done":
                    self.progress_lbl.config(text=payload)
                elif kind == "status":
                    self.progress_lbl.config(text=payload)
        except queue.Empty:
            pass
        self.root.after(150, self.poll_queue)

    def _add_result(self, r):
        row = tk.Frame(self.inner, bg=SURFACE)
        row.pack(fill="x", pady=1)
        tk.Label(row, text=r["name"], bg=SURFACE, fg=TEXT, anchor="w",
                 font=("Segoe UI", 9)).pack(side="left", padx=(10, 10))
        tk.Label(row, text=f"{r['orig']} → {r['new']}", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=10)
        tk.Label(row, text=f"{r['before']} → {r['after']}", bg=SURFACE, fg=GOOD,
                 font=("Segoe UI", 9, "bold")).pack(side="right", padx=10)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
