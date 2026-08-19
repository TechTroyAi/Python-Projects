import datetime as dt
import json
import os
import queue
import threading
import urllib.request
import urllib.parse
import tkinter as tk

# ---------- Rose Quartz ----------
BG = "#fdf5f7"
SURFACE = "#ffffff"
SURFACE2 = "#faeef2"
BORDER = "#f3dfe6"
TEXT = "#33151f"
MUTED = "#a06b7a"
ACCENT = "#e75480"
ACCENT2 = "#f472b6"
GOOD = "#10b981"
BAD = "#dc2626"

BASE = os.path.dirname(os.path.abspath(__file__))
FAVS_FILE = os.path.join(BASE, "weather_favs.json")


def wmo(code, is_day):
    if code == 0:
        return ("Clear" if is_day else "Clear night", "☀️" if is_day else "🌙")
    if code == 1:
        return ("Mostly clear", "🌤️" if is_day else "🌙")
    if code == 2:
        return ("Partly cloudy", "⛅")
    if code == 3:
        return ("Overcast", "☁️")
    if code in (45, 48):
        return ("Fog", "🌫️")
    if 51 <= code <= 57:
        return ("Drizzle", "🌦️")
    if 61 <= code <= 67:
        return ("Rain", "🌧️")
    if 71 <= code <= 77:
        return ("Snow", "🌨️")
    if 80 <= code <= 82:
        return ("Showers", "🌦️")
    if 85 <= code <= 86:
        return ("Snow showers", "🌨️")
    if code >= 95:
        return ("Thunderstorm", "⛈️")
    return ("—", "🌡️")


def deg(n):
    return f"{round(n)}°"


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (weather-app)"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.load(r)


def geocode(name):
    url = ("https://geocoding-api.open-meteo.com/v1/search?name="
           + urllib.parse.quote(name) + "&count=1&language=en&format=json")
    d = fetch_json(url)
    if not d.get("results"):
        return None
    res = d["results"][0]
    nm = res["name"] + (", " + res["admin1"] if res.get("admin1") else "")
    return {"name": nm, "lat": res["latitude"], "lon": res["longitude"]}


def my_location():
    d = fetch_json("http://ip-api.com/json?fields=status,lat,lon,city,regionName")
    if d.get("status") == "success":
        return {"name": d["city"] + ", " + d["regionName"],
                "lat": d["lat"], "lon": d["lon"]}
    return None


def weather(lat, lon):
    url = ("https://api.open-meteo.com/v1/forecast?latitude=" + str(lat)
           + "&longitude=" + str(lon)
           + "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
             "weather_code,wind_speed_10m,is_day,precipitation_probability"
           + "&daily=weather_code,temperature_2m_max,temperature_2m_min,"
             "precipitation_probability_max&timezone=auto&forecast_days=7")
    return fetch_json(url)


class App:
    def __init__(self, root):
        self.root = root
        root.title("Weather")
        root.configure(bg=BG)
        root.geometry("760x680")
        root.minsize(620, 620)

        self.favs = self.load_favs()
        self.current = None
        self.q = queue.Queue()

        self._build()
        self.render_favs()
        self.root.after(200, self.poll_queue)

        if self.favs:
            self.fetch_latlon(self.favs[0]["lat"], self.favs[0]["lon"], self.favs[0]["name"])
        else:
            self.fetch_city("Cagayan de Oro")

    # ---------- data ----------
    def load_favs(self):
        try:
            with open(FAVS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return []

    def save_favs(self):
        try:
            with open(FAVS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.favs, f, indent=2)
        except OSError:
            pass

    # ---------- ui ----------
    def _build(self):
        tk.Label(self.root, text="⛅ Weather", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 20, "bold")).pack(pady=(16, 8))

        # search
        search = tk.Frame(self.root, bg=BG)
        search.pack(fill="x", padx=16)

        self.q_var = tk.StringVar()
        self.q_entry = tk.Entry(search, textvariable=self.q_var, bg=SURFACE,
                                fg=TEXT, insertbackground=TEXT, relief="flat",
                                highlightthickness=1, highlightbackground=BORDER,
                                font=("Segoe UI", 11))
        self.q_entry.pack(side="left", fill="x", expand=True, ipady=9)
        self.q_entry.bind("<Return>", lambda e: self.search())

        tk.Button(search, text="🔍", command=self.search, bg=ACCENT, fg="#fff",
                  activebackground=ACCENT2, activeforeground="#fff", relief="flat",
                  bd=0, font=("Segoe UI", 12, "bold"), width=4, cursor="hand2"
                  ).pack(side="left", padx=(8, 0), ipady=6)

        tk.Button(search, text="📍", command=self.use_location, bg=SURFACE,
                  fg=ACCENT, activebackground=SURFACE2, activeforeground=ACCENT2,
                  relief="flat", highlightthickness=1, highlightbackground=BORDER,
                  bd=0, font=("Segoe UI", 12), width=4, cursor="hand2"
                  ).pack(side="left", padx=(8, 0), ipady=6)

        # favorites
        self.favs_frame = tk.Frame(self.root, bg=BG)
        self.favs_frame.pack(fill="x", padx=16, pady=(10, 4))

        # current
        self.now = tk.Frame(self.root, bg=SURFACE, highlightthickness=1,
                            highlightbackground=BORDER)
        self.now.pack(fill="x", padx=16, pady=(8, 8))

        top = tk.Frame(self.now, bg=SURFACE)
        top.pack(fill="x", padx=18, pady=(14, 0))

        self.star_btn = tk.Button(top, text="⭐", command=self.toggle_fav, bg=SURFACE,
                                  fg=MUTED, activebackground=SURFACE, relief="flat",
                                  bd=0, font=("Segoe UI", 16), cursor="hand2")
        self.star_btn.pack(side="right")

        self.place_lbl = tk.Label(top, text="—", bg=SURFACE, fg=MUTED,
                                  font=("Segoe UI", 11, "bold"))
        self.place_lbl.pack(anchor="w")

        mid = tk.Frame(self.now, bg=SURFACE)
        mid.pack(fill="x", padx=18, pady=(6, 0))

        self.emoji_lbl = tk.Label(mid, text="🌡️", bg=SURFACE,
                                  font=("Segoe UI Emoji", 34))
        self.emoji_lbl.pack(side="left", padx=(0, 14))

        temps = tk.Frame(mid, bg=SURFACE)
        temps.pack(side="left", anchor="w")
        self.temp_lbl = tk.Label(temps, text="—", bg=SURFACE, fg=ACCENT,
                                 font=("Segoe UI", 34, "bold"))
        self.temp_lbl.pack(anchor="w")
        self.cond_lbl = tk.Label(temps, text="—", bg=SURFACE, fg=MUTED,
                                 font=("Segoe UI", 10))
        self.cond_lbl.pack(anchor="w")

        self.hilo_lbl = tk.Label(self.now, text="", bg=SURFACE, fg=TEXT,
                                 font=("Segoe UI", 10, "bold"))
        self.hilo_lbl.pack(anchor="w", padx=18, pady=(8, 0))

        # details
        dets = tk.Frame(self.now, bg=SURFACE)
        dets.pack(fill="x", padx=18, pady=(14, 16))

        self.feels_v = self._det_cell(dets, "—", "Feels like")
        self.feels_v.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.hum_v = self._det_cell(dets, "—", "Humidity")
        self.hum_v.pack(side="left", fill="x", expand=True, padx=5)
        self.wind_v = self._det_cell(dets, "—", "Wind")
        self.wind_v.pack(side="left", fill="x", expand=True, padx=5)
        self.rain_v = self._det_cell(dets, "—", "Rain chance")
        self.rain_v.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # forecast
        fcard = tk.Frame(self.root, bg=SURFACE, highlightthickness=1,
                         highlightbackground=BORDER)
        fcard.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        tk.Label(fcard, text="7-DAY FORECAST", bg=SURFACE, fg=MUTED,
                 font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", padx=18, pady=(14, 6))

        self.forecast = tk.Frame(fcard, bg=SURFACE)
        self.forecast.pack(fill="x", padx=14, pady=(0, 14))

        # status
        bottom = tk.Frame(self.root, bg=SURFACE, highlightthickness=1,
                          highlightbackground=BORDER)
        bottom.pack(fill="x", side="bottom")
        self.status_lbl = tk.Label(bottom, text="Loading…", bg=SURFACE, fg=MUTED,
                                   font=("Segoe UI", 10), anchor="w", padx=12, pady=8)
        self.status_lbl.pack(fill="x")

    def _det_cell(self, parent, val, label):
        cell = tk.Frame(parent, bg=SURFACE2, highlightthickness=1,
                        highlightbackground=BORDER)
        tk.Label(cell, text=val, bg=SURFACE2, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(pady=(8, 0))
        tk.Label(cell, text=label, bg=SURFACE2, fg=MUTED,
                 font=("Segoe UI", 8)).pack(pady=(0, 8))
        return cell

    def set_status(self, text):
        self.status_lbl.config(text=text)

    # ---------- fetch (threaded) ----------
    def search(self):
        name = self.q_var.get().strip()
        if not name:
            return
        self.fetch_city(name)

    def fetch_city(self, name):
        self.set_status("Searching…")
        threading.Thread(target=self._t_city, args=(name,), daemon=True).start()

    def _t_city(self, name):
        try:
            g = geocode(name)
            if not g:
                self.q.put(("error", "City not found"))
                return
            d = weather(g["lat"], g["lon"])
            self.q.put(("ok", {"data": d, "place": g["name"],
                               "lat": g["lat"], "lon": g["lon"]}))
        except Exception as e:
            self.q.put(("error", str(e)))

    def fetch_latlon(self, lat, lon, name):
        self.set_status("Loading…")
        threading.Thread(target=self._t_latlon, args=(lat, lon, name), daemon=True).start()

    def _t_latlon(self, lat, lon, name):
        try:
            d = weather(lat, lon)
            self.q.put(("ok", {"data": d, "place": name, "lat": lat, "lon": lon}))
        except Exception as e:
            self.q.put(("error", str(e)))

    def use_location(self):
        self.set_status("Finding you…")
        threading.Thread(target=self._t_loc, daemon=True).start()

    def _t_loc(self):
        try:
            loc = my_location()
            if not loc:
                self.q.put(("error", "Could not find location"))
                return
            d = weather(loc["lat"], loc["lon"])
            self.q.put(("ok", {"data": d, "place": loc["name"],
                               "lat": loc["lat"], "lon": loc["lon"]}))
        except Exception as e:
            self.q.put(("error", str(e)))

    def poll_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "error":
                    self.set_status("⚠️ " + payload)
                elif kind == "ok":
                    self.current = {"name": payload["place"],
                                    "lat": payload["lat"], "lon": payload["lon"]}
                    self.render(payload["data"], payload["place"])
        except queue.Empty:
            pass
        self.root.after(200, self.poll_queue)

    # ---------- render ----------
    def render(self, data, place):
        c = data["current"]
        d = data["daily"]
        cond, emoji = wmo(c["weather_code"], c.get("is_day", 1))

        self.place_lbl.config(text=place)
        self.emoji_lbl.config(text=emoji)
        self.temp_lbl.config(text=deg(c["temperature_2m"]))
        self.cond_lbl.config(text=cond)
        self.hilo_lbl.config(text=f"H {deg(d['temperature_2m_max'][0])}  ·  "
                                  f"L {deg(d['temperature_2m_min'][0])}")

        self.feels_v.winfo_children()[0].config(text=deg(c["apparent_temperature"]))
        self.hum_v.winfo_children()[0].config(text=str(c["relative_humidity_2m"]) + "%")
        self.wind_v.winfo_children()[0].config(text=str(round(c["wind_speed_10m"])) + " km/h")
        rain = c.get("precipitation_probability")
        if rain is None and d.get("precipitation_probability_max"):
            rain = d["precipitation_probability_max"][0]
        self.rain_v.winfo_children()[0].config(text=str(rain or 0) + "%")

        self.update_star()
        self.render_forecast(d)
        self.set_status("Updated " + dt.datetime.now().strftime("%I:%M %p"))

    def render_forecast(self, d):
        for w in self.forecast.winfo_children():
            w.destroy()

        today = dt.date.today()
        for i in range(len(d["time"])):
            date_str = d["time"][i]
            day = dt.date.fromisoformat(date_str)
            day_name = "Today" if day == today else day.strftime("%a")
            _, emoji = wmo(d["weather_code"][i], True)

            cell = tk.Frame(self.forecast, bg=SURFACE2, highlightthickness=1,
                            highlightbackground=BORDER)
            cell.pack(side="left", fill="both", expand=True, padx=3)

            tk.Label(cell, text=day_name, bg=SURFACE2, fg=TEXT,
                     font=("Segoe UI", 9, "bold")).pack(pady=(10, 2))
            tk.Label(cell, text=emoji, bg=SURFACE2,
                     font=("Segoe UI Emoji", 18)).pack()
            tk.Label(cell, text=deg(d["temperature_2m_max"][i]), bg=SURFACE2,
                     fg=TEXT, font=("Segoe UI", 10, "bold")).pack(pady=(4, 0))
            tk.Label(cell, text=deg(d["temperature_2m_min"][i]), bg=SURFACE2,
                     fg=MUTED, font=("Segoe UI", 9)).pack(pady=(0, 10))

    def render_favs(self):
        for w in self.favs_frame.winfo_children():
            w.destroy()
        for f in self.favs:
            tk.Button(self.favs_frame, text=f["name"],
                      command=lambda f=f: self.fetch_latlon(f["lat"], f["lon"], f["name"]),
                      bg=SURFACE if not (self.current and self.current["lat"] == f["lat"]
                                         and self.current["lon"] == f["lon"]) else SURFACE2,
                      fg=TEXT, activebackground=SURFACE2, activeforeground=TEXT,
                      relief="flat", highlightthickness=1, highlightbackground=BORDER,
                      font=("Segoe UI", 9), padx=12, pady=5, cursor="hand2"
                      ).pack(side="left", padx=(0, 6), pady=4)

    def update_star(self):
        if not self.current:
            return
        saved = any(f["lat"] == self.current["lat"] and f["lon"] == self.current["lon"]
                    for f in self.favs)
        self.star_btn.config(fg=ACCENT if saved else MUTED, text="⭐" if saved else "☆")

    def toggle_fav(self):
        if not self.current:
            return
        i = next((i for i, f in enumerate(self.favs)
                  if f["lat"] == self.current["lat"] and f["lon"] == self.current["lon"]), -1)
        if i >= 0:
            self.favs.pop(i)
        else:
            self.favs.append({"name": self.current["name"],
                              "lat": self.current["lat"], "lon": self.current["lon"]})
        self.save_favs()
        self.render_favs()
        self.update_star()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
