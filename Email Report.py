import datetime as dt
import json
import os
import queue
import smtplib
import threading
import time
import tkinter as tk
import webbrowser
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from tkinter import filedialog, messagebox, ttk

# ---------- Frost ----------
BG = "#f4f7fb"
SURFACE = "#ffffff"
SURFACE2 = "#eef2f8"
BORDER = "#dfe7f0"
TEXT = "#0f1c2e"
MUTED = "#5b6b80"
ACCENT = "#2563eb"
ACCENT2 = "#3b82f6"
GOOD = "#16a34a"
BAD = "#dc2626"

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE, "email_config.json")
LOG_FILE = os.path.join(BASE, "email_log.json")

PROVIDERS = {
    "Gmail":   {"server": "smtp.gmail.com",       "port": 587, "tls": True},
    "Outlook": {"server": "smtp.office365.com",   "port": 587, "tls": True},
    "Yahoo":   {"server": "smtp.mail.yahoo.com",  "port": 587, "tls": True},
    "Other":   {"server": "",                     "port": 587, "tls": True},
}


def build_email_html(title, subtitle, highlights, message, table=None):
    """Generate a clean, email-safe HTML report (inline styles)."""
    def esc(s):
        return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    cards = ""
    if highlights:
        cards = '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:18px 0;"><tr>'
        for h in highlights:
            cards += (
                '<td style="padding:5px;" valign="top">'
                '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                'style="border-collapse:collapse;background:#eef2f8;border-radius:8px;">'
                f'<tr><td style="padding:14px 16px;font-family:Arial,sans-serif;">'
                f'<div style="font-size:22px;font-weight:bold;color:#2563eb;">{esc(h["value"])}</div>'
                f'<div style="font-size:12px;color:#5b6b80;margin-top:2px;">{esc(h["label"])}</div>'
                '</td></tr></table></td>'
            )
        cards += "</tr></table>"

    rows = ""
    if table and table.get("headers") and table.get("rows"):
        head = "".join(
            f'<th style="padding:9px 12px;text-align:left;background:#2563eb;color:#ffffff;'
            f'font-size:12px;">{esc(c)}</th>' for c in table["headers"])
        body = ""
        for r in table["rows"]:
            cells = "".join(
                f'<td style="padding:8px 12px;border-top:1px solid #dfe7f0;font-size:12px;">{esc(c)}</td>'
                for c in r)
            body += f"<tr>{cells}</tr>"
        rows = (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="border-collapse:collapse;margin-top:16px;">'
            f'<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
        )

    paragraphs = "".join(f'<p style="margin:0 0 12px;line-height:1.5;">{esc(m)}</p>'
                         for m in message.split("\n\n") if m.strip())

    return f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f4f7fb;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7fb;padding:24px 0;">
  <tr><td align="center">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0"
           style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;
                  border:1px solid #dfe7f0;overflow:hidden;font-family:Arial,Helvetica,sans-serif;color:#0f1c2e;">
      <tr>
        <td style="background:#2563eb;padding:22px 28px;">
          <div style="font-size:20px;font-weight:bold;color:#ffffff;">{esc(title) or 'Report'}</div>
          {f'<div style="font-size:13px;color:#dbeafe;margin-top:4px;">{esc(subtitle)}</div>' if subtitle else ''}
        </td>
      </tr>
      <tr><td style="padding:24px 28px;">
        {cards}
        <div style="font-size:14px;line-height:1.6;">{paragraphs}</div>
        {rows}
      </td></tr>
      <tr><td style="padding:16px 28px;background:#eef2f8;font-size:11px;color:#5b6b80;">
        Sent {dt.datetime.now().strftime('%b %d, %Y at %I:%M %p')} · automated report
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""


def plain_text(title, highlights, message):
    parts = [title, ""]
    if highlights:
        parts.append(" · ".join(f"{h['label']}: {h['value']}" for h in highlights))
        parts.append("")
    parts.append(message)
    return "\n".join(parts)


def build_mime(cfg, html_body, text_body, attachment):
    msg = MIMEMultipart("alternative")
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    msg["Subject"] = cfg["subject"]
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    if attachment and os.path.isfile(attachment):
        part = MIMEBase("application", "octet-stream")
        with open(attachment, "rb") as f:
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment",
                        filename=os.path.basename(attachment))
        msg.attach(part)
    return msg


def send_email(cfg, html_body, text_body, attachment):
    p = PROVIDERS.get(cfg.get("provider", "Gmail"), PROVIDERS["Gmail"])
    server = cfg.get("server") or p["server"]
    port = int(cfg.get("port") or p["port"])
    use_tls = cfg.get("tls", p["tls"])

    msg = build_mime(cfg, html_body, text_body, attachment)

    if use_tls:
        smtp = smtplib.SMTP(server, port, timeout=30)
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
    else:
        smtp = smtplib.SMTP_SSL(server, port, timeout=30)

    smtp.login(cfg["from"], cfg["password"])
    smtp.sendmail(cfg["from"], [cfg["to"]], msg.as_string())
    smtp.quit()


class App:
    def __init__(self, root):
        self.root = root
        root.title("Email Report")
        root.configure(bg=BG)
        root.geometry("900x800")
        root.minsize(680, 620)

        self.cfg = self.load(CONFIG_FILE, {
            "provider": "Gmail", "from": "", "password": "", "server": "",
            "port": "", "tls": True, "to": "", "subject": "Daily Report",
        })
        self.log = self.load(LOG_FILE, [])
        self.highlights = []
        self.attachment = ""
        self.sending = False
        self.scheduled = False
        self.q = queue.Queue()
        self.last_sent_date = None

        self.vars = {k: tk.StringVar(value=str(v)) for k, v in self.cfg.items()
                     if k in ("provider", "from", "password", "server", "port", "to", "subject")}
        self.tls_var = tk.BooleanVar(value=self.cfg["tls"])
        self.sched_var = tk.BooleanVar(value=False)
        self.hour_var = tk.StringVar(value="08")
        self.min_var = tk.StringVar(value="00")

        self._style()
        self._build()
        self.refresh_highlights()
        self.render_log()
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
            self.cfg = {k: v.get() for k, v in self.vars.items()}
            self.cfg["tls"] = self.tls_var.get()
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=2)
        except OSError:
            pass

    def save_log(self):
        try:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.log[:100], f, indent=2)
        except OSError:
            pass

    # ---------- ui ----------
    def _style(self):
        style = ttk.Style()
        style.theme_use("clam")

    def _build(self):
        tk.Label(self.root, text="📧 Email Report", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 20, "bold")).pack(pady=(16, 10))

        # --- credentials ---
        card = tk.Frame(self.root, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=16, pady=(0, 8))

        tk.Label(card, text="EMAIL SETTINGS", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 4))

        g = tk.Frame(card, bg=SURFACE)
        g.pack(fill="x", padx=14, pady=(0, 10))

        tk.Label(g, text="Provider", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        prov = ttk.Combobox(g, textvariable=self.vars["provider"], values=list(PROVIDERS),
                            state="readonly", width=12)
        prov.grid(row=0, column=1, sticky="w", pady=3)
        prov.bind("<<ComboboxSelected>>", lambda e: self.on_provider())

        tk.Label(g, text="Your email", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(
            row=0, column=2, sticky="w", padx=(16, 8), pady=3)
        tk.Entry(g, textvariable=self.vars["from"], bg=SURFACE2, fg=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, width=30,
                 font=("Segoe UI", 9)).grid(row=0, column=3, sticky="w", pady=3)

        tk.Label(g, text="App password", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        tk.Entry(g, textvariable=self.vars["password"], show="*", bg=SURFACE2, fg=TEXT,
                 relief="flat", highlightthickness=1, highlightbackground=BORDER, width=24,
                 font=("Segoe UI", 9)).grid(row=1, column=1, sticky="w", pady=3)

        tk.Label(g, text="Server", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(
            row=1, column=2, sticky="w", padx=(16, 8), pady=3)
        tk.Entry(g, textvariable=self.vars["server"], bg=SURFACE2, fg=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, width=22,
                 font=("Segoe UI", 9)).grid(row=1, column=3, sticky="w", pady=3)

        tk.Label(g, text="Port", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=3)
        tk.Entry(g, textvariable=self.vars["port"], bg=SURFACE2, fg=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, width=10,
                 font=("Segoe UI", 9)).grid(row=2, column=1, sticky="w", pady=3)

        tk.Label(g, text="To", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(
            row=2, column=2, sticky="w", padx=(16, 8), pady=3)
        tk.Entry(g, textvariable=self.vars["to"], bg=SURFACE2, fg=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, width=30,
                 font=("Segoe UI", 9)).grid(row=2, column=3, sticky="w", pady=3)

        tk.Label(g, text="Subject", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(
            row=3, column=2, sticky="w", padx=(16, 8), pady=3)
        tk.Entry(g, textvariable=self.vars["subject"], bg=SURFACE2, fg=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, width=30,
                 font=("Segoe UI", 9)).grid(row=3, column=3, sticky="w", pady=3)

        tk.Checkbutton(g, text="TLS", variable=self.tls_var, bg=SURFACE, fg=TEXT,
                       selectcolor=SURFACE2, activebackground=SURFACE, font=("Segoe UI", 9),
                       cursor="hand2").grid(row=3, column=1, sticky="w", pady=3)

        self.on_provider()

        # --- report content ---
        rcard = tk.Frame(self.root, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        rcard.pack(fill="x", padx=16, pady=(0, 8))

        tk.Label(rcard, text="REPORT", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 4))

        rg = tk.Frame(rcard, bg=SURFACE)
        rg.pack(fill="x", padx=14, pady=(0, 6))

        self.title_var = tk.StringVar(value="Daily Report")
        self.sub_var = tk.StringVar(value="")

        tk.Label(rg, text="Title", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        tk.Entry(rg, textvariable=self.title_var, bg=SURFACE2, fg=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, width=40,
                 font=("Segoe UI", 9)).grid(row=0, column=1, sticky="w", pady=3)

        tk.Label(rg, text="Subtitle", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        tk.Entry(rg, textvariable=self.sub_var, bg=SURFACE2, fg=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, width=40,
                 font=("Segoe UI", 9)).grid(row=1, column=1, sticky="w", pady=3)

        tk.Label(rg, text="Message", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(
            row=2, column=0, sticky="nw", padx=(0, 8), pady=3)
        self.msg_text = tk.Text(rg, bg=SURFACE2, fg=TEXT, relief="flat",
                                highlightthickness=1, highlightbackground=BORDER,
                                width=46, height=5, font=("Segoe UI", 9),
                                wrap="word")
        self.msg_text.grid(row=2, column=1, sticky="w", pady=3)
        self.msg_text.insert("1.0", "Here is your automated report.")

        # highlights
        hg = tk.Frame(rcard, bg=SURFACE)
        hg.pack(fill="x", padx=14, pady=(0, 10))

        tk.Label(hg, text="Highlight", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        self.hl_label_var = tk.StringVar()
        self.hl_value_var = tk.StringVar()
        tk.Entry(hg, textvariable=self.hl_label_var, bg=SURFACE2, fg=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, width=18,
                 font=("Segoe UI", 9)).grid(row=0, column=1, sticky="w", pady=3)
        tk.Entry(hg, textvariable=self.hl_value_var, bg=SURFACE2, fg=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, width=10,
                 font=("Segoe UI", 9)).grid(row=0, column=2, sticky="w", padx=(8, 0), pady=3)
        tk.Button(hg, text="➕", command=self.add_highlight, bg=ACCENT, fg="#fff",
                  activebackground=ACCENT2, activeforeground="#fff", relief="flat", bd=0,
                  font=("Segoe UI", 10, "bold"), width=4, cursor="hand2").grid(
                  row=0, column=3, padx=(8, 0), pady=3)

        self.hl_list = tk.Listbox(hg, bg=SURFACE2, fg=TEXT, relief="flat",
                                  highlightthickness=1, highlightbackground=BORDER,
                                  height=4, font=("Segoe UI", 9))
        self.hl_list.grid(row=1, column=1, columnspan=3, sticky="ew", pady=(6, 0))
        tk.Button(hg, text="✕", command=self.remove_highlight, bg=SURFACE2, fg=BAD,
                  activebackground=SURFACE2, activeforeground=BAD, relief="flat", bd=0,
                  font=("Segoe UI", 10, "bold"), width=4, cursor="hand2").grid(
                  row=1, column=4, padx=(8, 0), pady=(6, 0), sticky="n")

        # attachment
        ag = tk.Frame(rcard, bg=SURFACE)
        ag.pack(fill="x", padx=14, pady=(0, 10))
        self.att_var = tk.StringVar()
        tk.Label(ag, text="Attachment", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        tk.Entry(ag, textvariable=self.att_var, bg=SURFACE2, fg=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER, state="readonly",
                 font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, padx=8, ipady=6)
        tk.Button(ag, text="Browse", command=self.pick_attachment, bg=SURFACE2, fg=ACCENT,
                  activebackground=ACCENT2, activeforeground="#fff", relief="flat", bd=0,
                  font=("Segoe UI", 9, "bold"), padx=10, pady=6, cursor="hand2").pack(side="left")

        # --- actions ---
        acard = tk.Frame(self.root, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        acard.pack(fill="x", padx=16, pady=(0, 8))

        ag2 = tk.Frame(acard, bg=SURFACE)
        ag2.pack(fill="x", padx=14, pady=10)

        self.send_btn = tk.Button(ag2, text="📨 Send now", command=self.send_now, bg=ACCENT,
                                  fg="#fff", activebackground=ACCENT2, activeforeground="#fff",
                                  relief="flat", bd=0, font=("Segoe UI", 10, "bold"),
                                  padx=16, pady=8, cursor="hand2")
        self.send_btn.pack(side="left")

        tk.Button(ag2, text="👁️ Preview", command=self.preview, bg=SURFACE2, fg=TEXT,
                  activebackground=ACCENT2, activeforeground="#fff", relief="flat", bd=0,
                  font=("Segoe UI", 10, "bold"), padx=16, pady=8,
                  cursor="hand2").pack(side="left", padx=(8, 0))

        tk.Checkbutton(ag2, text="Daily at", variable=self.sched_var, bg=SURFACE, fg=TEXT,
                       selectcolor=SURFACE2, activebackground=SURFACE, font=("Segoe UI", 10),
                       cursor="hand2", command=self.toggle_schedule).pack(side="left", padx=(20, 6))

        self.hour_entry = tk.Entry(ag2, textvariable=self.hour_var, bg=SURFACE2, fg=TEXT,
                                   relief="flat", highlightthickness=1,
                                   highlightbackground=BORDER, width=4, justify="center",
                                   font=("Segoe UI", 10))
        self.hour_entry.pack(side="left", ipady=4)
        tk.Label(ag2, text=":", bg=SURFACE, fg=TEXT, font=("Segoe UI", 10, "bold")).pack(side="left")
        self.min_entry = tk.Entry(ag2, textvariable=self.min_var, bg=SURFACE2, fg=TEXT,
                                  relief="flat", highlightthickness=1,
                                  highlightbackground=BORDER, width=4, justify="center",
                                  font=("Segoe UI", 10))
        self.min_entry.pack(side="left", ipady=4)

        self.sched_lbl = tk.Label(ag2, text="", bg=SURFACE, fg=MUTED, font=("Segoe UI", 9))
        self.sched_lbl.pack(side="left", padx=12)

        # --- log ---
        lcard = tk.Frame(self.root, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        lcard.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        tk.Label(lcard, text="SEND LOG", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 4))

        wrap = tk.Frame(lcard, bg=SURFACE)
        wrap.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        self.log_canvas = tk.Canvas(wrap, bg=SURFACE, highlightthickness=0)
        self.log_canvas.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self.log_canvas.yview)
        sb.pack(side="right", fill="y")
        self.log_canvas.configure(yscrollcommand=sb.set)

        self.log_inner = tk.Frame(self.log_canvas, bg=SURFACE)
        self.log_inner.bind("<Configure>", lambda e:
                            self.log_canvas.configure(scrollregion=self.log_canvas.bbox("all")))
        self.log_canvas.create_window((0, 0), window=self.log_inner, anchor="nw")

        # status bar
        bottom = tk.Frame(self.root, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        bottom.pack(fill="x", side="bottom")
        self.status_lbl = tk.Label(bottom, text="Ready", bg=SURFACE, fg=MUTED,
                                   font=("Segoe UI", 10), anchor="w", padx=12, pady=8)
        self.status_lbl.pack(fill="x")

    def on_provider(self):
        p = PROVIDERS.get(self.vars["provider"].get(), PROVIDERS["Gmail"])
        if not self.vars["server"].get():
            self.vars["server"].set(p["server"])
        if not self.vars["port"].get():
            self.vars["port"].set(str(p["port"]))
        self.tls_var.set(p["tls"])

    def add_highlight(self):
        label = self.hl_label_var.get().strip()
        value = self.hl_value_var.get().strip()
        if label and value:
            self.highlights.append({"label": label, "value": value})
            self.hl_label_var.set("")
            self.hl_value_var.set("")
            self.refresh_highlights()

    def remove_highlight(self):
        sel = self.hl_list.curselection()
        if sel:
            self.highlights.pop(sel[0])
            self.refresh_highlights()

    def refresh_highlights(self):
        self.hl_list.delete(0, tk.END)
        for h in self.highlights:
            self.hl_list.insert(tk.END, f"{h['label']}: {h['value']}")

    def pick_attachment(self):
        p = filedialog.askopenfilename(title="Attach a file")
        if p:
            self.attachment = p
            self.att_var.set(os.path.basename(p))

    def toggle_schedule(self):
        if self.sched_var.get():
            self.start_schedule()
        else:
            self.scheduled = False
            self.sched_lbl.config(text="")

    # ---------- report ----------
    def current_report(self):
        return build_email_html(
            self.title_var.get().strip() or "Report",
            self.sub_var.get().strip(),
            self.highlights,
            self.msg_text.get("1.0", "end").strip(),
        )

    def preview(self):
        html = self.current_report()
        path = os.path.join(BASE, "preview.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        webbrowser.open("file://" + path)
        self.status_lbl.config(text="👁️ Preview opened in browser")

    def send_now(self):
        if self.sending:
            return
        self.save_cfg()
        if not self.vars["from"].get() or not self.vars["password"].get():
            self.status_lbl.config(text="⚠️ Fill in your email + app password")
            return
        if not self.vars["to"].get():
            self.status_lbl.config(text="⚠️ Fill in the To address")
            return
        self.sending = True
        self.send_btn.config(text="⏳ Sending…")
        self.status_lbl.config(text="Sending…")
        threading.Thread(target=self._send, daemon=True).start()

    def _send(self):
        try:
            html = self.current_report()
            text = plain_text(self.title_var.get().strip() or "Report",
                              self.highlights, self.msg_text.get("1.0", "end").strip())
            cfg = {k: v.get() for k, v in self.vars.items()}
            cfg["tls"] = self.tls_var.get()
            send_email(cfg, html, text, self.attachment or None)
            self.q.put(("ok", f"✅ Sent to {self.vars['to'].get()}"))
        except Exception as e:
            self.q.put(("error", str(e)))

    def poll_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                self.sending = False
                self.send_btn.config(text="📨 Send now")
                if kind == "ok":
                    self.log.insert(0, {"ts": dt.datetime.now().strftime("%b %d %I:%M %p"),
                                        "to": self.vars["to"].get(),
                                        "subject": self.vars["subject"].get(), "ok": True})
                    self.save_log()
                    self.render_log()
                    self.status_lbl.config(text=payload)
                else:
                    self.log.insert(0, {"ts": dt.datetime.now().strftime("%b %d %I:%M %p"),
                                        "to": self.vars["to"].get(),
                                        "subject": self.vars["subject"].get(),
                                        "ok": False, "err": payload})
                    self.save_log()
                    self.render_log()
                    self.status_lbl.config(text="⚠️ " + payload)
        except queue.Empty:
            pass
        self.root.after(200, self.poll_queue)

    def render_log(self):
        for w in self.log_inner.winfo_children():
            w.destroy()
        if not self.log:
            tk.Label(self.log_inner, text="No emails sent yet", bg=SURFACE, fg=MUTED,
                     font=("Segoe UI", 10), pady=14).pack()
            return
        for e in self.log:
            row = tk.Frame(self.log_inner, bg=SURFACE)
            row.pack(fill="x", pady=1)
            icon = "✅" if e["ok"] else "❌"
            fg = GOOD if e["ok"] else BAD
            tk.Label(row, text=icon, bg=SURFACE, fg=fg, font=("Segoe UI", 10)).pack(side="left", padx=(8, 6))
            tk.Label(row, text=f"{e['ts']}  →  {e['to']}", bg=SURFACE, fg=TEXT,
                     font=("Segoe UI", 9)).pack(side="left")
            tk.Label(row, text=e.get("err", e["subject"]), bg=SURFACE, fg=MUTED,
                     font=("Segoe UI", 9)).pack(side="left", padx=10)

    # ---------- schedule ----------
    def start_schedule(self):
        self.scheduled = True
        self.sched_lbl.config(text=f"scheduled {self.hour_var.get()}:{self.min_var.get()}")
        threading.Thread(target=self._sched_loop, daemon=True).start()

    def _sched_loop(self):
        while self.scheduled:
            now = dt.datetime.now()
            try:
                h = int(self.hour_var.get())
                m = int(self.min_var.get())
            except ValueError:
                time.sleep(20)
                continue
            today = now.strftime("%Y-%m-%d")
            if now.hour == h and now.minute == m and self.last_sent_date != today:
                if not self.sending:
                    self.last_sent_date = today
                    self.send_now()
            time.sleep(20)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
