#!/usr/bin/env python3
# Kindle dashboard image generator: fetches weather / air quality / lunar
# calendar + reminders.json and renders a pure black-and-white PNG sized
# for a Kindle Paperwhite 3 (1072x1448).
# Primary source: Open-Meteo. Fallback: wttr.in (current/today) + JMA
# (weekly, Japan only). Air quality: Open-Meteo Air Quality API.
# Configuration is via environment variables; see .env.example.
import json, math, os, sys, urllib.request, urllib.parse
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont
import glob

TZ_NAME = os.environ.get("TZ", "Asia/Tokyo")
TZ = ZoneInfo(TZ_NAME)
LAT = float(os.environ.get("LAT", "35.6812"))   # default: Tokyo Station area
LON = float(os.environ.get("LON", "139.7671"))
W_PX = int(os.environ.get("SCREEN_W", "1072"))   # Paperwhite 3: 1072x1448
H_PX = int(os.environ.get("SCREEN_H", "1448"))
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("OUT_PATH", os.path.join(BASE, "out", "dashboard.png"))
REMINDERS = os.environ.get("REMINDERS_FILE", os.path.join(BASE, "reminders.json"))
WTTR_LOCATION = os.environ.get("WTTR_LOCATION", "Tokyo")
JMA_AREA_CODE = os.environ.get("JMA_AREA_CODE", "130000")  # 130000 = Tokyo

def fetch_json(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "kindle-dashboard/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

WMO = {0:"晴",1:"晴时多云",2:"多云时晴",3:"多云",45:"雾",48:"雾",51:"毛毛雨",53:"毛毛雨",
       55:"毛毛雨",56:"毛毛雨",57:"毛毛雨",61:"小雨",63:"中雨",65:"大雨",66:"冻雨",67:"冻雨",
       71:"小雪",73:"中雪",75:"大雪",77:"小雪",80:"阵雨",81:"阵雨",82:"大雨",85:"阵雪",
       86:"阵雪",95:"雷雨",96:"雷雨",99:"雷雨"}
JMA = {100:"晴",101:"晴时多云",102:"晴时有雨",103:"晴时有雨",104:"晴时有雪",105:"晴时有雪",
       106:"晴时雨雪",107:"晴时雨雪",108:"晴时雨雪",110:"晴后多云",111:"晴后多云",112:"晴后雨",
       113:"晴后雨",114:"晴后雨",115:"晴后雪",116:"晴后雪",117:"晴后雪",118:"晴后雨雪",119:"晴后雨雪",
       120:"晴时有雨",121:"晴时有雨",122:"晴晚有雨",123:"晴山沿雪",124:"晴山沿雪",125:"晴午后雷雨",
       126:"晴午后雨",127:"晴晚雷雨",128:"晴晚雨",130:"晨雾后晴",131:"晴晨雾",132:"晴时多云",
       140:"晴时雷雨",160:"晴时雨雪",170:"晴时雨雪",181:"晴后雨雪",200:"多云",201:"多云时晴",
       202:"多云时雨",203:"多云有雨",204:"多云时雪",205:"多云时雪",206:"多云时雨雪",207:"多云时雨雪",
       208:"多云时雨雪",209:"雾",210:"多云后晴",211:"多云后晴",212:"多云后雨",213:"多云后雨",
       214:"多云后雨",215:"多云后雪",216:"多云后雪",217:"多云后雪",218:"多云后雨雪",219:"多云后雨雪",
       220:"多云时有雨",221:"多云时有雨",222:"多云晚有雨",223:"多云时多云",224:"多云午后雨",
       225:"多云晚雨",226:"多云晚雪",228:"多云晚雪",229:"多云晚雪",230:"多云晚雪",231:"多云晨雾",
       240:"多云时雷雨",250:"多云时雨雪",260:"多云时雨雪",270:"多云时雨雪",281:"多云后雨雪",
       300:"雨",301:"雨时晴",302:"雨时停",303:"雨时雪",304:"雨",306:"大雨",308:"暴风雨",309:"雨时雪",
       311:"雨后晴",313:"雨后多云",314:"雨后多云",315:"雨后雪",316:"雨后雪",317:"雨后雨雪",
       320:"晨雨后晴",321:"晨雨后多云",322:"雨晚后雪",323:"雨午后晴",324:"雨午后停",325:"雨晚停",
       326:"雨晚雪",327:"雨时雪",328:"雨时雪",329:"雨时雪",340:"雪时雨",350:"雨时雷",361:"雪后多云",
       371:"雪后晴",400:"雪",401:"雪时晴",402:"雪时停",403:"雪时雨",405:"大雪",406:"风雪",407:"风雪",
       409:"雪时雨",411:"雪后晴",413:"雪后多云",414:"雪后雨",420:"晨雪后晴",421:"晨雪后多云",
       422:"雪午后雨",423:"雪午后停",425:"雪后停",426:"雪晚雨",427:"雪时雨",450:"雷雨"}
DIRS = ["北","东北","东","东南","南","西南","西","西北"]
WTTR = {"113":"晴","116":"晴时多云","119":"多云","122":"多云","143":"雾","176":"阵雨","179":"阵雪",
        "182":"冻雨","185":"冻雨","200":"雷雨","227":"阵雪","230":"大雪","248":"雾","260":"雾",
        "263":"毛毛雨","266":"毛毛雨","281":"冻雨","284":"冻雨","293":"小雨","296":"小雨","299":"中雨",
        "302":"中雨","305":"大雨","308":"大雨","311":"冻雨","314":"冻雨","317":"小雨","320":"阵雪",
        "323":"阵雪","326":"阵雪","329":"大雪","332":"大雪","335":"大雪","338":"大雪","350":"冻雨",
        "353":"阵雨","356":"阵雨","359":"大雨","362":"雨雪","365":"雨雪","368":"阵雪","371":"阵雪",
        "374":"冻雨","377":"冻雨","386":"雷雨","389":"雷雨","392":"雷雨","395":"大雪"}

def uv_label(uv):
    return "弱" if uv <= 2 else "中等" if uv <= 5 else "强" if uv <= 7 else "很强"

def aqi_label(a):
    return "优" if a <= 50 else "中等" if a <= 100 else "较差" if a <= 150 else "差"

def get_weather_openmeteo():
    u = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
         "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,wind_direction_10m,precipitation"
         "&hourly=temperature_2m,weather_code,uv_index,precipitation_probability"
         "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
         "&timezone=%s&forecast_days=8") % (LAT, LON, urllib.parse.quote(TZ_NAME, safe=""))
    w = fetch_json(u)
    cur, day, hr = w["current"], w["daily"], w["hourly"]
    today = datetime.now(TZ).date().isoformat()
    uvmax = 0; idx = [i for i, t in enumerate(hr["time"]) if t.startswith(today)]
    if idx: uvmax = max(hr["uv_index"][i] or 0 for i in idx)
    wk = []  # 一周预报从明天开始 : 取第 2~8 天
    for i in range(1, 8):
        dt = date.fromisoformat(day["time"][i])
        wk.append((dt, WMO.get(day["weather_code"][i], ""), round(day["temperature_2m_max"][i]),
                   round(day["temperature_2m_min"][i]), day["precipitation_probability_max"][i] or 0))
    now_h = datetime.now(TZ).strftime("%Y-%m-%dT%H:00")
    try: start = hr["time"].index(now_h)
    except ValueError: start = 0
    hrs = []
    for i in range(start, min(start + 8, len(hr["time"]))):
        hrs.append((int(hr["time"][i][11:13]), WMO.get(hr["weather_code"][i], ""),
                    round(hr["temperature_2m"][i]), hr["precipitation_probability"][i] or 0))
    return {
        "cond": WMO.get(cur["weather_code"], ""), "temp": round(cur["temperature_2m"]),
        "hum": cur["relative_humidity_2m"], "wind_dir": DIRS[round(cur["wind_direction_10m"] / 45) % 8],
        "wind": round(cur["wind_speed_10m"]), "precip": cur["precipitation"] or 0,
        "rain_prob": day["precipitation_probability_max"][0] or 0, "uv": round(uvmax),
        "hi": round(day["temperature_2m_max"][0]), "lo": round(day["temperature_2m_min"][0]), "week": wk,
        "hours": hrs, "src": "Open-Meteo",
    }

def get_weather_fallback():
    w = fetch_json("https://wttr.in/%s?format=j1" % urllib.parse.quote(WTTR_LOCATION))
    c = w["current_condition"][0]
    j = fetch_json("https://www.jma.go.jp/bosai/forecast/data/forecast/%s.json" % JMA_AREA_CODE)
    codes = j[1]["timeSeries"][0]["areas"][0]["weatherCodes"]
    pops = j[1]["timeSeries"][0]["areas"][0].get("pops", [""] * 7)
    tmin = j[1]["timeSeries"][1]["areas"][0]["tempsMin"]
    tmax = j[1]["timeSeries"][1]["areas"][0]["tempsMax"]
    rain_today = max(int(h.get("chanceofrain", 0)) for h in w["weather"][0]["hourly"])
    wk = []
    for i in range(7):
        dt = date.fromisoformat(j[1]["timeSeries"][0]["timeDefines"][i][:10])
        hi = int(tmax[i]) if tmax[i] else int(w["weather"][0]["maxtempC"]) if i == 0 else 0
        lo = int(tmin[i]) if tmin[i] else int(w["weather"][0]["mintempC"]) if i == 0 else 0
        wk.append((dt, JMA.get(int(codes[i]), ""), hi, lo, int(pops[i]) if str(pops[i]).isdigit() else rain_today if i == 0 else 0))
    uv = max(int(h["uvIndex"]) for h in w["weather"][0]["hourly"])
    now_h = datetime.now(TZ).hour
    hrs = []
    for doff, dayw in enumerate(w["weather"][:2]):
        for h in dayw["hourly"]:
            hv = int(h["time"]) // 100
            if doff * 24 + hv < now_h: continue
            hrs.append((hv, WTTR.get(h["weatherCode"], "多云"), int(h["tempC"]), int(h.get("chanceofrain", 0))))
            if len(hrs) >= 8: break
        if len(hrs) >= 8: break
    return {
        "cond": JMA.get(int(codes[0]), w["weather"][0]["hourly"][4]["weatherDesc"][0]["value"]),
        "temp": int(c["temp_C"]), "hum": int(c["humidity"]),
        "wind_dir": {"N":"北","NE":"东北","E":"东","SE":"东南","S":"南","SW":"西南","W":"西","NW":"西北"}.get(c["winddir16Point"], ""),
        "wind": int(c["windspeedKmph"]), "precip": float(c["precipMM"]),
        "rain_prob": rain_today, "uv": uv,
        "hi": int(w["weather"][0]["maxtempC"]), "lo": int(w["weather"][0]["mintempC"]), "week": wk,
        "hours": hrs, "src": "気象庁 · wttr.in",
    }

def get_aqi():
    try:
        a = fetch_json("https://air-quality-api.open-meteo.com/v1/air-quality?latitude=%s&longitude=%s"
                       "&current=us_aqi,pm2_5&timezone=%s" % (LAT, LON, urllib.parse.quote(TZ_NAME, safe="")))
        return round(a["current"]["us_aqi"])
    except Exception:
        return None

def lunar_str(today):
    try:
        from lunardate import LunarDate
        ld = LunarDate.from_solar_date(today.year, today.month, today.day)
        months = ["正","二","三","四","五","六","七","八","九","十","冬","腊"]
        days = ["初一","初二","初三","初四","初五","初六","初七","初八","初九","初十","十一","十二","十三",
                "十四","十五","十六","十七","十八","十九","二十","廿一","廿二","廿三","廿四","廿五","廿六",
                "廿七","廿八","廿九","三十"]
        # 只返回农历月日 (不带干支纪年) 
        return "农历%s%s月%s" % ("闰" if ld.isLeapMonth else "", months[ld.month - 1], days[ld.day - 1])
    except Exception:
        return ""

# ---------------- 字体 ----------------
def find_font(bold=True):
    for p in ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"]:
        try: open(p); return p
        except Exception: pass
    g = glob.glob("/usr/share/fonts/**/NotoSansCJK*%s*" % ("Bold" if bold else "Regular"), recursive=True)
    return g[0] if g else None

FB, FR = find_font(True), find_font(False)
def f(size, bold=True): return ImageFont.truetype(FB if bold else FR, size)

WK = ["周一","周二","周三","周四","周五","周六","周日"]
WD1 = "一二三四五六日"  # 单字星期, 配全角括号用: 11月7日（六）

def draw_icon(d, cond, cx, cy):
    # 按天气状况画大图标: 晴=太阳, 多云=太阳+云, 阴/雨=云(+雨丝), 雪=云+雪点, 雾=横线
    def sun(cx, cy, rad, wdt=12):
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=0, width=wdt)
        for k in range(8):
            a = math.radians(k * 45)
            d.line([(cx + (rad + 18) * math.cos(a), cy + (rad + 18) * math.sin(a)),
                    (cx + (rad + 50) * math.cos(a), cy + (rad + 50) * math.sin(a))], fill=0, width=wdt)
    def cloud(cx, cy, s=1.0, fillc=255):
        d.ellipse([cx - 105*s, cy - 38*s, cx + 5*s, cy + 72*s], outline=0, width=int(11*s), fill=fillc)
        d.ellipse([cx - 30*s, cy - 78*s, cx + 105*s, cy + 72*s], outline=0, width=int(11*s), fill=fillc)
        d.line([(cx - 105*s, cy + 72*s), (cx + 105*s, cy + 72*s)], fill=0, width=int(11*s))
    if "雷" in cond:
        cloud(cx, cy - 25); d.polygon([(cx - 8, cy + 62), (cx + 38, cy + 62), (cx + 2, cy + 108), (cx + 30, cy + 108), (cx - 28, cy + 165), (cx - 12, cy + 108), (cx - 38, cy + 108)], fill=0)
    elif "雪" in cond:
        cloud(cx, cy - 30)
        for dx in (-58, 0, 58):
            for r_ in (7,):
                d.ellipse([cx + dx - r_, cy + 88 - r_, cx + dx + r_, cy + 88 + r_], fill=0)
                d.ellipse([cx + dx - r_, cy + 128 - r_, cx + dx + r_, cy + 128 + r_], fill=0)
    elif "雨" in cond:
        cloud(cx, cy - 30)
        for dx in (-58, 0, 58):
            d.line([(cx + dx + 12, cy + 78), (cx + dx - 6, cy + 138)], fill=0, width=11)
    elif "雾" in cond:
        for i, ln in enumerate((150, 190, 110)):
            y = cy - 50 + i * 52
            d.line([(cx - ln, y), (cx + ln, y)], fill=0, width=13)
    elif "晴" in cond and ("多云" in cond or "时晴" in cond or "时多云" in cond):
        sun(cx - 45, cy - 40, 58, 10); cloud(cx + 25, cy + 45, 0.82)
    elif "晴" in cond:
        sun(cx, cy, 84)
    else:  # 多云/阴
        cloud(cx, cy)

def draw_icon_small(img, cond, cx, cy, size=88):
    # 小图标: 把大图标画在临时图上再缩小粘贴, 和今日大图标同一套画法
    tile = Image.new("L", (360, 360), 255)
    td = ImageDraw.Draw(tile)
    draw_icon(td, cond, 180, 180)
    tile = tile.resize((size, size), Image.LANCZOS)
    img.paste(tile, (int(cx - size / 2), int(cy - size / 2)))

def main():
    now = datetime.now(TZ); today = now.date()
    try:
        W = get_weather_openmeteo(); src = W.pop("src")
    except Exception as e:
        print("open-meteo failed, fallback:", e, file=sys.stderr)
        W = get_weather_fallback(); src = W.pop("src")
    aqi = get_aqi()

    img = Image.new("L", (W_PX, H_PX), 255)
    d = ImageDraw.Draw(img)
    M = 64
    # 顶部: 日期与农历同字号同一行 (日期左, 农历右), 不带干支
    date_txt = "%d月%d日（%s）" % (today.month, today.day, WD1[today.weekday()])
    lun = lunar_str(today)
    hs = 74
    while hs > 40 and d.textlength(date_txt, font=f(hs)) + d.textlength(lun, font=f(hs)) + 36 > W_PX - 2 * M:
        hs -= 2
    # 顶部留给 Kindle 系统状态栏 (时间/WiFi/电量会重绘那一条, 压住日期 —  预留已按真机间距收紧)
    d.text((M, 62), date_txt, font=f(hs), fill=0)
    if lun: d.text((W_PX - M - d.textlength(lun, font=f(hs)), 62), lun, font=f(hs), fill=0)
    d.line([(M, 152), (W_PX - M, 152)], fill=0, width=5)
    # 当天天气: 左侧图标, 右侧天气情况+温度信息; 详情在下方横排,
    # 只留 湿度/风速/降水概率/空气指数 (不显示降水量和紫外线)
    draw_icon(d, W["cond"], 232, 288)
    tx = 478
    d.text((tx, 180), W["cond"][:4], font=f(64), fill=0)
    temp_txt = "%d°" % W["temp"]
    tb = d.textbbox((tx, 238), temp_txt, font=f(128))
    d.text((tx, 238), temp_txt, font=f(128), fill=0)
    # 最高/最低: 当前温度右侧两行, 整体与当前温度下对齐
    hx = tb[2] + 36
    lo_txt = "最低 %d°" % W["lo"]
    lo_y = tb[3] - d.textbbox((0, 0), lo_txt, font=f(42))[3]
    d.text((hx, lo_y), lo_txt, font=f(42), fill=0)
    d.text((hx, lo_y - 58), "最高 %d°" % W["hi"], font=f(42), fill=0)
    aqi_txt = "AQI %d · %s" % (aqi, aqi_label(aqi)) if aqi is not None else "暂无数据"
    cells = [("湿度", "%d %%" % W["hum"]), ("风速", "%s风 %d km/h" % (W["wind_dir"], W["wind"])),
             ("降水概率", "%d %%" % W["rain_prob"]), ("空气指数", aqi_txt)]
    cw4 = (W_PX - 2 * M) // 4
    for i, (lab, val) in enumerate(cells):
        x = M + i * cw4
        d.text((x, 422), lab, font=f(32), fill=0)
        d.text((x, 460), val, font=f(38), fill=0)
    d.line([(M, 516), (W_PX - M, 516)], fill=0, width=4)
    # 未来8小时: 无图标; 温度折线 + 降水概率柱状, 时间在下方
    hrs = W.get("hours", [])[:8]
    hcw = (W_PX - 2 * M) / 8
    base_y = 716
    if hrs:
        temps = [h[2] for h in hrs]; tmin, tmax = min(temps), max(temps)
        for i, (hh, hcond, htemp, hpop) in enumerate(hrs):  # 柱状先画, 折线压在上面
            cx = M + hcw * (i + 0.5)
            bh = hpop * 0.5
            if bh >= 2: d.rectangle([cx - 30, base_y - bh, cx + 30, base_y], fill=0)
            pl = "%d%%" % hpop
            d.text((cx - d.textlength(pl, font=f(24)) / 2, base_y - bh - 30), pl, font=f(24), fill=0)
        pts = []
        for i, (hh, hcond, htemp, hpop) in enumerate(hrs):
            cx = M + hcw * (i + 0.5)
            yy = 668 - (htemp - tmin) * 52 / (tmax - tmin) if tmax > tmin else 642
            pts.append((cx, yy))
            tl = "%d°" % htemp
            d.text((cx - d.textlength(tl, font=f(28)) / 2, yy - 38), tl, font=f(28), fill=0)
        for a, b in zip(pts, pts[1:]): d.line([a, b], fill=0, width=4)
        for (cx, yy) in pts: d.ellipse([cx - 7, yy - 7, cx + 7, yy + 7], fill=0)
        d.line([(M, base_y), (W_PX - M, base_y)], fill=0, width=2)
        for i, (hh, hcond, htemp, hpop) in enumerate(hrs):
            cx = M + hcw * (i + 0.5)
            tt = "%d时" % hh
            d.text((cx - d.textlength(tt, font=f(30)) / 2, base_y + 8), tt, font=f(30), fill=0)
    d.line([(M, 766), (W_PX - M, 766)], fill=0, width=4)
    # 一周 (无标题; 从明天开始7天; 日期星期单行 11/8（日） 格式; 每列全部居中对齐)
    colw = (W_PX - 2 * M) / 7
    week = list(W["week"])
    def ctext(cx, txt, yy, font, fill):
        d.text((cx - d.textlength(txt, font=font) / 2, yy), txt, font=font, fill=fill)
    for i, (dt, cond, hi, lo, pop) in enumerate(week):
        x = M + i * colw; cx = x + colw / 2
        dl = "%d/%d（%s）" % (dt.month, dt.day, WD1[dt.weekday()])
        ds = 30
        while ds > 18 and d.textlength(dl, font=f(ds)) > colw - 4: ds -= 2
        ctext(cx, dl, 782, f(ds), 0)
        draw_icon_small(img, cond, cx, 860, size=76)
        ctext(cx, cond[:4], 912, f(28), 0)
        ctext(cx, "%d°" % hi, 944, f(32), 0)
        ctext(cx, "%d°" % lo, 980, f(32), 0)
        ctext(cx, "雨 %d%%" % pop, 1016, f(26), 0)
    d.line([(M, 1064), (W_PX - M, 1064)], fill=0, width=4)
    # 提醒事项
    d.text((M, 1076), "提醒事项", font=f(46), fill=0)
    rems = json.load(open(REMINDERS, encoding="utf-8"))
    groups = {}
    for it in rems:
        dt = date.fromisoformat(it["date"])
        if dt >= today: groups.setdefault(dt, []).append(it)
    rowdata = []
    for dt in sorted(groups)[:5]:
        items = sorted(groups[dt], key=lambda z: z["time"] or "99")
        if dt == today: lab = "今天"
        elif dt == today + timedelta(days=1): lab = "明天"
        else: lab = "%d/%d（%s）" % (dt.month, dt.day, WD1[dt.weekday()])
        # 第一列只放日期/星期 (今天就写"今天"); 时间进第二列内容, 多条用逗号分隔
        what = "，".join(((it["time"] + " ") if it["time"] else "") + it["text"] for it in items)
        rowdata.append((lab, what))
    # 两栏对齐: 日期标签固定 38 不缩; 内容列统一从最宽标签之后开始, 左对齐;
    # 内容过长只缩内容字号
    lab_w_max = max([d.textlength(lab, font=f(38)) for lab, _ in rowdata], default=0)
    content_x = M + 32 + lab_w_max + 20
    y = 1134; rows = 0
    max_w = W_PX - M - content_x
    for lab, what in rowdata:
        # 方案A : 内容改粗体, 字号下限 26 (原 20); 到下限还放不下就按 '，' 拆成两行, 不再硬缩字
        wsize = 38
        while wsize > 26 and d.textlength(what, font=f(wsize)) > max_w:
            wsize -= 2
        lines = [what]
        if d.textlength(what, font=f(wsize)) > max_w:
            parts = what.split("，")
            l1 = parts[0]
            for part in parts[1:]:
                if d.textlength(l1 + "，" + part, font=f(wsize)) <= max_w: l1 = l1 + "，" + part
                else: break
            rest = what[len(l1) + 1:] if what.startswith(l1 + "，") else ""
            if rest: lines = [l1, rest]
            else:  # 没有合适的逗号断点: 按字符贪心折行 (最多两行)
                l1 = ""
                for ch in what:
                    if d.textlength(l1 + ch, font=f(wsize)) > max_w: break
                    l1 += ch
                lines = [l1, what[len(l1):]] if what[len(l1):] else [l1]
        d.ellipse([M, y + 12, M + 16, y + 28], fill=0)
        d.text((M + 32, y), lab, font=f(38), fill=0)
        if len(lines) == 1:
            d.text((content_x, y + (38 - wsize) // 2), lines[0], font=f(wsize), fill=0)
            y += 50
        else:
            d.text((content_x, y + 2), lines[0], font=f(wsize), fill=0)
            d.text((content_x, y + 40), lines[1], font=f(wsize), fill=0)
            y += 88
        rows += 1
    if rows == 0:
        d.text((M + 32, y), "暂无待办提醒", font=f(38), fill=0)
    # 页脚的数据来源小字已按方案A删除 (字太小且最不重要, 空间让给提醒区)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    #  全屏只用纯黑白, 不要灰色 (文字/柱状/分隔线全黑, 最后二值化去掉抗锯齿灰边)
    img = img.point(lambda px: 0 if px < 128 else 255)
    img.save(OUT)
    print("saved", OUT, "| cond:", W["cond"], W["temp"], "| src:", src, "| aqi:", aqi)

if __name__ == "__main__":
    main()
