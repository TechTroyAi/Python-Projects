import json
import os
import queue
import threading
import time
import datetime as dt
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import messagebox

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
UP = "#34d399"
DOWN = "#f87171"

BASE = os.path.dirname(os.path.abspath(__file__))
SITES_FILE = os.path.join(BASE, "sites.json")
HISTORY_FILE = os.path.join(BASE, "history.json")


def normalize(url):
    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def check(site):
    url = site["url"]
    start = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (uptime-monitor)"})
        with urllib.request.urlopen(req, timeout=10) as r:
            ms = round((time.time() - start) * 1000)
            return {"name": site["name"], "url": url, "ok": r.status < 400,
                    "code": r.status, "ms": ms}
    except urllib.error.HTTPError as e:
        ms = round((time.time() - start) * 1000)
        return {"name": site["name"], "url": url, "ok": False,
                "code": e.code, "ms": ms}
    except Exception as e:
        ms = round((time.time() - start) * 1000)
        return {"name": site["name"], "url": url, "ok": False,
                "code": None, "ms": ms, "err": type(e).__name__}


class App:
    def __init__(self, root):
        self.root = root
        root.title("Website Uptime Monitor")
        root.configure(bg=BG)
        root.geometry("920x760")
        root.minsize(640, 560)

        self.sites = self.load(SITES_FILE)
        self.history = self.load(HISTORY_FILE)
        self.status = {}
        self.running = False
        self.q = queue.Queue()
        self.interval_var = tk.IntVar(value=30)

        self._build()
        self.render_sites()
        self.render_history()
        self.root.after(200, self.poll_queue)

    # ---------- data ----------
    def load(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return []

    def save_sites(self):
        try:
            with open(SITES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.sites, f, indent=2)
        except OSError:
            pass

    def save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history[:200], f, indent=2)
        except OSError:
            pass

    # ---------- build ui ----------
    def _build(self):
        tk.Label(self.root, text="📡 Website Uptime Monitor", bg=BG, fg=ICE,
                 font=("Segoe UI", 20, "bold")).pack(pady=(16, 10))

        # add form
        form = tk.Frame(self.root, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        form.pack(fill="x", padx=16, pady=(0, 8))

        row = tk.Frame(form, bg=CARD)
        row.pack(fill="x", padx=12, pady=12)

        self.name_var = tk.StringVar()
        self.url_var = tk.StringVar()
        self.name_entry = tk.Entry(row, bg=CARD2, fg=TEXT, insertbackground=TEXT,
                                   relief="flat", font=("Segoe UI", 11))
        self.name_entry.pack(side="left", fill="x", expand=True, ipady=9)

        self.url_entry = tk.Entry(row, bg=CARD2, fg=TEXT, insertbackground=TEXT,
                                  relief="flat", font=("Segoe UI", 11), width=34)
        self.url_entry.pack(side="left", fill="x", padx=(8, 0), ipady=9)

        tk.Button(row, text="➕ Add", command=self.add_site, bg=ACCENT, fg="#fff",
                  activebackground=ACCENT2, activeforeground="#fff", relief="flat",
                  bd=0, font=("Segoe UI", 11, "bold"), padx=18, pady=9,
                  cursor="hand2").pack(side="left", padx=(8, 0))

        self.url_entry.bind("<Return>", lambda e: self.add_site())
        self.name_entry.bind("<Return>", lambda e: self.add_site())

        # controls
        ctrl = tk.Frame(self.root, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        ctrl.pack(fill="x", padx=16, pady=(0, 8))

        left = tk.Frame(ctrl, bg=CARD)
        left.pack(side="left", padx=12, pady=10)

        self.start_btn = tk.Button(left, text="▶️ Start", command=self.toggle,
                                   bg=ACCENT, fg="#fff", activebackground=ACCENT2,
                                   activeforeground="#fff", relief="flat", bd=0,
                                   font=("Segoe UI", 10, "bold"), padx=16, pady=8,
                                   cursor="hand2")
        self.start_btn.pack(side="left")

        tk.Button(left, text="🔁 Check now", command=self.check_now, bg=ACCENT2,
                  fg="#fff", activebackground=ACCENT, activeforeground="#fff",
                  relief="flat", bd=0, font=("Segoe UI", 10, "bold"), padx=16,
                  pady=8, cursor="hand2").pack(side="left", padx=(8, 0))

        tk.Label(left, text="every", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(16, 6))
        self.interval_entry = tk.Entry(left, textvariable=self.interval_var, bg=CARD2,
                                       fg=TEXT, insertbackground=TEXT, relief="flat",
                                       font=("Segoe UI", 10), width=4, justify="center")
        self.interval_entry.pack(side="left", ipady=6)
        tk.Label(left, text="sec", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))

        self.summary = tk.Label(ctrl, text="", bg=CARD, fg=MUTED,
                                font=("Segoe UI", 10, "bold"))
        self.summary.pack(side="right", padx=12)

        # sites list
        sites_card = tk.Frame(self.root, bg=CARD, highlightthickness=1,
                              highlightbackground=BORDER)
        sites_card.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        wrap = tk.Frame(sites_card, bg=CARD)
        wrap.pack(fill="both", expand=True, padx=6, pady=6)

        self.sites_canvas = tk.Canvas(wrap, bg=CARD, highlightthickness=0)
        self.sites_canvas.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self.sites_canvas.yview)
        sb.pack(side="right", fill="y")
        self.sites_canvas.configure(yscrollcommand=sb.set)

        self.sites_inner = tk.Frame(self.sites_canvas, bg=CARD)
        self.sites_inner.bind("<Configure>", lambda e:
                              self.sites_canvas.configure(scrollregion=self.sites_canvas.bbox("all")))
        self.sites_canvas.create_window((0, 0), window=self.sites_inner, anchor="nw")

        # history
        hist_card = tk.Frame(self.root, bg=CARD, highlightthickness=1,
                             highlightbackground=BORDER)
        hist_card.pack(fill="x", padx=16, pady=(0, 8))

        tk.Label(hist_card, text="HISTORY", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=12, pady=(10, 4))

        hwrap = tk.Frame(hist_card, bg=CARD)
        hwrap.pack(fill="x", padx=6, pady=(0, 8))

        self.hist_canvas = tk.Canvas(hwrap, bg=CARD, height=120, highlightthickness=0)
        self.hist_canvas.pack(side="left", fill="both", expand=True)
        hsb = tk.Scrollbar(hwrap, orient="vertical", command=self.hist_canvas.yview)
        hsb.pack(side="right", fill="y")
        self.hist_canvas.configure(yscrollcommand=hsb.set)

        self.hist_inner = tk.Frame(self.hist_canvas, bg=CARD)
        self.hist_inner.bind("<Configure>", lambda e:
                             self.hist_canvas.configure(scrollregion=self.hist_canvas.bbox("all")))
        self.hist_canvas.create_window((0, 0), window=self.hist_inner, anchor="w")

        # status bar
        bottom = tk.Frame(self.root, bg=CARD)
        bottom.pack(fill="x", side="bottom")
        self.status_lbl = tk.Label(bottom, text="Add a website to begin", bg=CARD,
                                   fg=MUTED, font=("Segoe UI", 10), anchor="w",
                                   padx=12, pady=8)
        self.status_lbl.pack(fill="x")

    def set_status(self, text):
        self.status_lbl.config(text=text)

    # ---------- actions ----------
    def add_site(self):
        url = normalize(self.url_var.get())
        if not url:
            return
        name = self.name_var.get().strip() or url
        if any(s["url"] == url for s in self.sites):
            self.set_status("Already added")
            return
        self.sites.append({"name": name, "url": url})
        self.save_sites()
        self.name_var.set("")
        self.url_var.set("")
        self.render_sites()
        self.set_status(f"Added {url}")

    def remove_site(self, url):
        self.sites = [s for s in self.sites if s["url"] != url]
        self.status.pop(url, None)
        self.save_sites()
        self.render_sites()

    def toggle(self):
        if self.running:
            self.running = False
            self.start_btn.config(text="▶️ Start")
            self.set_status("Stopped")
        else:
            self.running = True
            self.start_btn.config(text="⏹ Stop")
            self.set_status("Monitoring…")
            threading.Thread(target=self._loop, daemon=True).start()

    def check_now(self):
        threading.Thread(target=self._once, daemon=True).start()

    def _once(self):
        for s in list(self.sites):
            self.q.put(check(s))

    def _loop(self):
        while self.running:
            for s in list(self.sites):
                if not self.running:
                    return
                self.q.put(check(s))
            try:
                secs = max(3, int(self.interval_var.get()))
            except Exception:
                secs = 30
            for _ in range(secs):
                if not self.running:
                    return
                time.sleep(1)

    def poll_queue(self):
        try:
            while True:
                res = self.q.get_nowait()
                self.apply_result(res)
        except queue.Empty:
            pass
        self.root.after(200, self.poll_queue)

    def apply_result(self, res):
        url = res["url"]
        prev = self.status.get(url)

        if prev and prev.get("ok") != res["ok"]:
            event = "UP" if res["ok"] else "DOWN"
            if not res["ok"]:
                self.root.bell()
            self.history.insert(0, {
                "ts": dt.datetime.now().strftime("%b %d %I:%M:%S %p"),
                "name": res["name"], "event": event,
                "code": res.get("code"), "ms": res.get("ms"),
            })
            self.save_history()
            self.render_history()

        res["time"] = dt.datetime.now().strftime("%I:%M:%S %p")
        self.status[url] = res
        self.render_sites()

    # ---------- render ----------
    def render_sites(self):
        for w in self.sites_inner.winfo_children():
            w.destroy()

        up = sum(1 for r in self.status.values() if r.get("ok"))
        down = len(self.status) - up
        self.summary.config(text=f"{up} up · {down} down")

        if not self.sites:
            tk.Label(self.sites_inner, text="No websites yet", bg=CARD, fg=MUTED,
                     font=("Segoe UI", 11), pady=20).pack()
            return

        for s in self.sites:
            r = self.status.get(s["url"])
            row = tk.Frame(self.sites_inner, bg=CARD)
            row.pack(fill="x", pady=2)

            dot = tk.Canvas(row, width=18, height=18, bg=CARD, highlightthickness=0)
            dot.pack(side="left", padx=(8, 6), pady=8)
            if r:
                color = UP if r["ok"] else DOWN
            else:
                color = MUTED
            dot.create_oval(3, 3, 15, 15, fill=color, outline="")

            info = tk.Frame(row, bg=CARD)
            info.pack(side="left", fill="x", expand=True)
            tk.Label(info, text=s["name"], bg=CARD, fg=TEXT, anchor="w",
                     font=("Segoe UI", 10, "bold")).pack(anchor="w")
            tk.Label(info, text=s["url"], bg=CARD, fg=MUTED, anchor="w",
                     font=("Segoe UI", 8)).pack(anchor="w")

            if r:
                if r["ok"]:
                    txt = f"{r['code']} · {r['ms']} ms"
                elif r.get("code"):
                    txt = f"HTTP {r['code']} · {r['ms']} ms"
                else:
                    txt = f"{r.get('err', 'Error')} · {r['ms']} ms"
                tk.Label(row, text=txt, bg=CARD,
                         fg=UP if r["ok"] else DOWN,
                         font=("Segoe UI", 9, "bold"), padx=10).pack(side="left")
                tk.Label(row, text=r.get("time", ""), bg=CARD, fg=MUTED,
                         font=("Segoe UI", 8), padx=8).pack(side="left")
            else:
                tk.Label(row, text="not checked", bg=CARD, fg=MUTED,
                         font=("Segoe UI", 9), padx=10).pack(side="left")

            tk.Button(row, text="✕", command=lambda u=s["url"]: self.remove_site(u),
                      bg=CARD, fg=MUTED, activebackground=CARD2,
                      activeforeground=DOWN, relief="flat", bd=0,
                      font=("Segoe UI", 10), cursor="hand2", width=3).pack(
                      side="right", padx=(0, 6))

    def render_history(self):
        for w in self.hist_inner.winfo_children():
            w.destroy()
        if not self.history:
            tk.Label(self.hist_inner, text="No events yet", bg=CARD, fg=MUTED,
                     font=("Segoe UI", 9), pady=8).pack(anchor="w", padx=8)
            return
        for h in self.history[:50]:
            icon = "⬆️" if h["event"] == "UP" else "⬇️"
            color = UP if h["event"] == "UP" else DOWN
            code = f" · {h['code']}" if h.get("code") else ""
            ms = f" · {h['ms']} ms" if h.get("ms") else ""
            txt = f"{icon} {h['ts']}  {h['name']} is {h['event']}{code}{ms}"
            tk.Label(self.hist_inner, text=txt, bg=CARD, fg=color, anchor="w",
                     font=("Segoe UI", 9), padx=8, pady=1).pack(anchor="w")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
