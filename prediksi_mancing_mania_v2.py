from telegram import BotCommand
import requests
import pytz
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import io
import calendar


from datetime import datetime
from astral import LocationInfo
from astral.sun import sun

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ================= CONFIG =================

BOT_TOKEN = "8781466052:AAFxLbLUspQsxQi6s-3HSQmyOZR__0yK93k"
OPENWEATHER_API = "8854b8d5e49bd772ab6f9551daf1ba71"
WORLD_TIDES_API = "9f99d069-ff74-4e2e-bacf-c1b62a4277bc"

SUPPORT_URL = "https://sociabuzz.com/padlian/tribe"

TIMEZONE = pytz.timezone("Asia/Makassar")
matplotlib.rcParams['font.family'] = 'DejaVu Sans'

# ================= LOKASI =================

LOCATIONS = {
    "bpp_laut": (-1.2379,116.8529,"Balikpapan Laut"),
    "bpp_sungai": (-1.1481,116.9037,"Balikpapan Sungai"),
    "smr_laut": (-0.5022,117.1537,"Samarinda Laut"),
    "smr_sungai": (-0.4948,117.1436,"Samarinda Sungai")
}

# ================= MENU UTAMA =================

def main_menu():

    kb=[
        [InlineKeyboardButton("📍 Balikpapan",callback_data="city_bpp")],
        [InlineKeyboardButton("📍 Samarinda",callback_data="city_smr")],
        [InlineKeyboardButton("❓ Help",callback_data="help")],
        [InlineKeyboardButton("❤️ Support Me",url=SUPPORT_URL)]
    ]

    return InlineKeyboardMarkup(kb)

# ================= DATA =================

def sun_time(lat, lon, date):
    loc = LocationInfo("", "", "Asia/Makassar", lat, lon)
    s = sun(loc.observer, date=date)
    return s["sunrise"].hour, s["sunset"].hour

def get_weather(lat, lon):
    try:
        url=f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API}&units=metric"
        data=requests.get(url).json()

        return (
            data["wind"]["speed"]*3.6,
            data["main"]["pressure"],
            data["weather"][0]["main"],
            data["main"]["temp"]
        )

    except:
        return 5,1010,"Clear",28


def get_tide(lat, lon, date):

    try:

        start=int(datetime(date.year,date.month,date.day,0,0,tzinfo=TIMEZONE).timestamp())
        end=int(datetime(date.year,date.month,date.day,23,59,tzinfo=TIMEZONE).timestamp())

        url=f"https://www.worldtides.info/api/v3?heights&lat={lat}&lon={lon}&start={start}&end={end}&key={WORLD_TIDES_API}"

        data=requests.get(url).json()

        return data.get("heights",[])

    except:

        return []

# ================= AI =================

def predict(lat, lon, date):

    sunrise, sunset = sun_time(lat, lon, date)

    wind, pressure, weather, temp = get_weather(lat, lon)

    hours=[]
    scores=[]

    for h in range(24):

        score=40

        score+=30*np.exp(-((h-sunrise)**2)/4)
        score+=30*np.exp(-((h-sunset)**2)/4)

        if wind<10:
            score+=10

        if pressure>1008:
            score+=10

        if weather=="Clouds":
            score+=5

        score=int(min(score,95))

        hours.append(f"{h:02d}:00")
        scores.append(score)

    return hours,scores,wind,pressure,weather,temp,sunrise,sunset

# ================= UMPAN =================

def rekomendasi_umpan(lokasi, weather, wind, pressure):

    if "Laut" in lokasi:

        if wind>20:
            return "Jig berat / Umpan potong ikan"

        if weather=="Rain":
            return "Cumi segar / Ikan hidup"

        return "Cumi / Udang Hidup / Ikan Kecil"

    if "Sungai" in lokasi:

        if weather=="Rain":
            return "Cacing tanah"

        return "Lumut / Pelet / Cacing"


# ================= CHART =================

def strike_chart(lat, lon, date):

    hours,scores,_,_,_,_,_,_=predict(lat,lon,date)

    best_hour=hours[scores.index(max(scores))]
    best_score=max(scores)

    plt.figure(figsize=(12,5))

    colors=["#2ecc71" if s>=80 else "#f1c40f" if s>=60 else "#e74c3c" for s in scores]

    bars=plt.bar(hours,scores,color=colors)

    bars[scores.index(best_score)].set_color("#27ae60")

    plt.title(f"Strike Probability\n{date.strftime('%d %B %Y')}")

    plt.ylabel("Probability (%)")

    plt.xticks(rotation=45)

    plt.grid(axis="y",alpha=0.3)

    plt.text(
        0.02,0.95,
        f"Jam Terbaik: {best_hour} ({best_score}%)",
        transform=plt.gca().transAxes,
        bbox=dict(boxstyle="round",facecolor="white",alpha=0.9)
    )

    plt.tight_layout()

    buf=io.BytesIO()

    plt.savefig(buf,format="png",bbox_inches="tight")

    buf.seek(0)

    plt.close()

    return buf

# ================= PASANG SURUT =================

def tide_chart(data, date):

    if not data:
        return None

    daily=[]

    for x in data:

        dt=datetime.fromtimestamp(x["dt"],TIMEZONE)

        if dt.date()==date.date():

            daily.append((dt,x["height"]))

    if len(daily)<2:

        return None

    daily=sorted(daily,key=lambda x:x[0])

    times=[d[0].strftime("%H:%M") for d in daily]
    heights=[d[1] for d in daily]

    max_h=max(heights)
    min_h=min(heights)

    max_i=heights.index(max_h)
    min_i=heights.index(min_h)

    plt.figure(figsize=(12,5))

    plt.plot(times,heights,linewidth=3,color="#1f77b4")

    plt.fill_between(times,heights,alpha=0.25,color="#1f77b4")

    plt.scatter(times[max_i],max_h,color="green",s=120)

    plt.scatter(times[min_i],min_h,color="red",s=120)

    plt.title(f"Grafik Pasang Surut\n{date.strftime('%d %B %Y')}")

    plt.ylabel("Tinggi Air (m)")

    plt.xticks(times[::2],rotation=45)

    plt.grid(alpha=0.3)

    plt.tight_layout()

    buf=io.BytesIO()

    plt.savefig(buf,format="png",bbox_inches="tight")

    buf.seek(0)

    plt.close()

    return buf

# ================= TELEGRAM =================

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(

"""
━━━━━━━━━━━━━━━━━━━━
🎣 <b>PREDIKSI MANCING MANIA</b>
━━━━━━━━━━━━━━━━━━━━

⚡ <b>Welcome To Fishing Intelligence</b> ⚡

“Berdoa Agar Tidak Boncos  
& Lenturkan Joran Bersama”

<i>Created By Padlian.NF</i>

🙏 Jika bot ini membantu,
silakan dukung pengembangan
melalui tombol Support Me.

━━━━━━━━━━━━━━━━━━━━

🗺 <b>Pilih Kota Untuk Memulai</b>
""",

        parse_mode="HTML",

        reply_markup=main_menu()
    )

# ================= HELP =================

async def help_menu(update:Update,context:ContextTypes.DEFAULT_TYPE):

    query=update.callback_query

    await query.answer()

    kb=[[InlineKeyboardButton("⬅ Kembali ke Menu",callback_data="back_main")]]

    text="""
📘 <b>PANDUAN BOT</b>

⭐ Strike Score
Menunjukkan peluang ikan aktif.

🏆 Jam Terbaik
Waktu paling potensial ikan makan.

🌊 Grafik Pasang Surut
Perubahan tinggi air laut.

🎣 Rekomendasi Umpan
AI memilih umpan terbaik.

📅 Pilih tanggal untuk melihat prediksi hari tersebut.
"""

    await query.edit_message_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(kb))

# ================= CITY =================

async def city(update:Update,context:ContextTypes.DEFAULT_TYPE):

    query=update.callback_query

    await query.answer()

    if query.data=="help":

        await help_menu(update,context)

        return

    if query.data=="back_main":

        await query.edit_message_text("Menu Utama:",reply_markup=main_menu())

        return

    if query.data=="city_bpp":

        kb=[
            [InlineKeyboardButton("🌊 Laut",callback_data="bpp_laut")],
            [InlineKeyboardButton("🏞 Sungai",callback_data="bpp_sungai")]
        ]

        await query.edit_message_text("Pilih Spot Balikpapan:",reply_markup=InlineKeyboardMarkup(kb))

    if query.data=="city_smr":

        kb=[
            [InlineKeyboardButton("🌊 Laut",callback_data="smr_laut")],
            [InlineKeyboardButton("🏞 Sungai",callback_data="smr_sungai")]
        ]

        await query.edit_message_text("Pilih Spot Samarinda:",reply_markup=InlineKeyboardMarkup(kb))

# ================= SPOT =================

async def spot(update:Update,context:ContextTypes.DEFAULT_TYPE):

    query=update.callback_query

    await query.answer()

    context.user_data["spot"]=query.data

    now=datetime.now(TIMEZONE)

    await query.edit_message_text(
        "Pilih Tanggal:",
        reply_markup=make_calendar(now.year,now.month)
    )

# ================= CALENDAR =================

def make_calendar(year,month):

    kb=[]

    for week in calendar.monthcalendar(year,month):

        row=[]

        for day in week:

            if day==0:

                row.append(InlineKeyboardButton(" ",callback_data="ignore"))

            else:

                row.append(InlineKeyboardButton(str(day),callback_data=f"date_{year}_{month}_{day}"))

        kb.append(row)

    kb.append([
        InlineKeyboardButton("⬅",callback_data=f"prev_{year}_{month}"),
        InlineKeyboardButton(f"{calendar.month_name[month]} {year}",callback_data="ignore"),
        InlineKeyboardButton("➡",callback_data=f"next_{year}_{month}")
    ])

    return InlineKeyboardMarkup(kb)

# ================= CALENDAR HANDLER =================

async def calendar_handler(update:Update,context:ContextTypes.DEFAULT_TYPE):

    query=update.callback_query

    await query.answer()

    data=query.data

    if data.startswith("date_"):

        _,y,m,d=data.split("_")

        date=datetime(int(y),int(m),int(d),tzinfo=TIMEZONE)

        spot=context.user_data.get("spot")

        lat,lon,name=LOCATIONS[spot]

        hours,scores,wind,pressure,weather,temp,sunrise,sunset=predict(lat,lon,date)

        best_score=max(scores)
        best_hour=hours[scores.index(best_score)]

        umpan=rekomendasi_umpan(name,weather,wind,pressure)

        msg=f"""
━━━━━━━━━━━━━━━━━━━━
🎣 <b>{name}</b>
📅 <b>{date.strftime('%d %B %Y')}</b>
━━━━━━━━━━━━━━━━━━━━

⭐ Strike Score : <b>{best_score}%</b>
🏆 Jam Terbaik  : <b>{best_hour}</b>

🌅 Sunrise : {sunrise}:00
🌇 Sunset  : {sunset}:00
💨 Angin   : {int(wind)} km/h
📈 Tekanan : {pressure} hPa
🌤 Cuaca   : {weather}
🌡 Suhu    : {temp}°C

🎣 Rekomendasi Umpan AI
👉 <b>{umpan}</b>

━━━━━━━━━━━━━━━━━━━━
"""

        await context.bot.send_message(query.from_user.id,msg,parse_mode="HTML")

        await context.bot.send_photo(query.from_user.id,strike_chart(lat,lon,date))

        tide_img=tide_chart(get_tide(lat,lon,date),date)

        if tide_img:

            await context.bot.send_photo(query.from_user.id,tide_img)

        # kembali ke menu utama

        await context.bot.send_message(
            query.from_user.id,
            "Silakan pilih menu berikut:",
            reply_markup=main_menu()
        )

    elif data.startswith("prev_") or data.startswith("next_"):

        action,y,m=data.split("_")

        y=int(y)
        m=int(m)

        if action=="next":

            m=m+1 if m<12 else 1
            y=y if m!=1 else y+1

        else:

            m=m-1 if m>1 else 12
            y=y if m!=12 else y-1

        await query.edit_message_reply_markup(reply_markup=make_calendar(y,m))

# ================= MAIN =================
async def set_bot_commands(app):

    commands = [
        BotCommand("start", "Mulai bot"),
     
    ]

    await app.bot.set_my_commands(commands)

# ================= MAIN =================

def main():

    print("Prediksi Mancing Mania FINAL Running...")

    app=ApplicationBuilder().token(BOT_TOKEN).build()

    # aktifkan menu command telegram
    app.post_init = set_bot_commands

    app.add_handler(CommandHandler("start",start))

    app.add_handler(CallbackQueryHandler(city,pattern="city_|help|back_main"))

    app.add_handler(CallbackQueryHandler(spot,pattern="bpp_|smr_"))

    app.add_handler(CallbackQueryHandler(calendar_handler,pattern="date_|prev_|next_|ignore"))

    app.run_polling()

if __name__=="__main__":

    main()