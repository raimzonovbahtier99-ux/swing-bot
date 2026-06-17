"""
🤖 Swing Trading AI Bot — 100% BEPUL
- yfinance: real narxlar
- Gemini: AI tahlil
- Har 4 soatda avtomatik signal
"""

import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from analyzer import analyze_stock, quick_scan
from apscheduler.schedulers.asyncio import AsyncIOScheduler

load_dotenv()

TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")
ALLOWED_USERS   = os.getenv("ALLOWED_USERS", "")
AUTO_SIGNAL_CHAT = os.getenv("AUTO_SIGNAL_CHAT", "")  # Kanal yoki chat ID

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ─── Default scanner tickers ──────────────────────────────────────────────────
DEFAULT_TICKERS = [
    "AAPL", "MSFT", "NVDA", "TSLA", "AMZN",
    "META", "GOOGL", "JPM",  "AMD",  "NFLX",
    "CRM",  "COIN",  "PLTR", "UBER", "SOFI",
]

# ─── Auth ─────────────────────────────────────────────────────────────────────
def is_allowed(uid: int) -> bool:
    if not ALLOWED_USERS.strip():
        return True
    return str(uid) in [u.strip() for u in ALLOWED_USERS.split(",")]

# ─── Formatters ───────────────────────────────────────────────────────────────
SIGNAL_EMOJI = {
    "STRONG_BUY":  "💚", "BUY": "🟢",
    "NEUTRAL":     "🟡",
    "SELL":        "🟠", "STRONG_SELL": "🔴",
}
SIGNAL_UZ = {
    "STRONG_BUY":  "KUCHLI SOTIB OL", "BUY": "SOTIB OL",
    "NEUTRAL":     "KUTIB TUR",
    "SELL":        "SOTISH",          "STRONG_SELL": "KUCHLI SOTISH",
}
RISK_EMOJI  = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}
HEALTH_UZ   = {"EXCELLENT":"⭐ A'lo","GOOD":"✅ Yaxshi","FAIR":"⚡ O'rtacha","POOR":"⚠ Yomon"}

def fmtU(v):
    try:    return f"${float(v):,.2f}"
    except: return "—"

def fmtP(v):
    try:
        f = float(v)
        return f"+{f:.2f}%" if f >= 0 else f"{f:.2f}%"
    except: return "—"

def fmt(v, d=2):
    try:    return f"{float(v):.{d}f}"
    except: return "—"

def bar(score):
    s = int(score) // 10
    return "█" * s + "░" * (10 - s)

# ─── Message builders ─────────────────────────────────────────────────────────
def build_detail(d: dict) -> str:
    sig = d.get("signal", "NEUTRAL")
    risk = d.get("riskLevel", "MEDIUM")
    return "\n".join([
        f"{'='*30}",
        f"📊 *{d.get('ticker')} — {d.get('companyName','?')}*",
        f"🏭 {d.get('sector','—')}",
        f"{'='*30}",
        f"",
        f"💰 *Narx:* {fmtU(d.get('price'))}  {fmtP(d.get('change'))}",
        f"📡 52H: ↑{fmtU(d.get('high52'))}  ↓{fmtU(d.get('low52'))}",
        f"",
        f"{'─'*26}",
        f"🚦 *SIGNAL: {SIGNAL_EMOJI.get(sig,'')} {SIGNAL_UZ.get(sig,sig)}*",
        f"📊 Ishonch: *{d.get('confidence','—')}%*   ⏱ {d.get('swingTimeframe','—')}",
        f"🎯 Kirish: _{d.get('entryZone','—')}_",
        f"{'─'*26}",
        f"",
        f"🎯 *NARX DARAJALARI*",
        f"🔴 Stop Loss:      {fmtU(d.get('stopLoss'))}",
        f"🟢 Take Profit 1:  {fmtU(d.get('takeProfit1'))}",
        f"🟢 Take Profit 2:  {fmtU(d.get('takeProfit2'))}",
        f"💜 Take Profit 3:  {fmtU(d.get('takeProfit3'))}",
        f"⚖️  Risk/Reward:   1 : {fmt(d.get('riskReward'))}",
        f"",
        f"{'─'*26}",
        f"📈 *TEXNIK*",
        f"RSI(14): {fmt(d.get('rsi14'),1)}  MACD: {d.get('macdStatus','—')}",
        f"MA50: {fmtU(d.get('ma50'))}   MA200: {fmtU(d.get('ma200'))}",
        f"ATR: {fmt(d.get('atrPct'))}%   Volume: {d.get('volumeStr','—')}",
        f"",
        f"📊 Texnik:      {bar(d.get('technicalScore',0))} {d.get('technicalScore','—')}/100",
        f"📊 Fundamental: {bar(d.get('fundamentalScore',0))} {d.get('fundamentalScore','—')}/100",
        f"",
        f"{'─'*26}",
        f"🛡 Risk: {RISK_EMOJI.get(risk,'')} {risk} ({d.get('riskScore','—')}/100)",
        f"🏢 Kompaniya: {HEALTH_UZ.get(d.get('companyHealth','FAIR'),'—')} ({d.get('healthScore','—')}/100)",
        f"",
        f"📋 P/E: {fmt(d.get('pe',0),1)}x  Beta: {fmt(d.get('beta'))}  Div: {fmt(d.get('dividendYield'))}%",
        f"",
        f"{'─'*26}",
        f"🚀 *Sabablar:* " + " · ".join(d.get("catalysts", [])[:2]),
        f"⚠️ *Xavflar:* "  + " · ".join(d.get("risks", [])[:2]),
        f"",
        f"💡 _{d.get('summary','—')}_",
        f"",
        f"{'─'*26}",
        f"⚠️ _Moliyaviy maslahat emas. DYOR._",
        f"🕐 _{datetime.now().strftime('%Y-%m-%d %H:%M')} UTC_",
    ])


def build_scan_line(d: dict) -> str:
    sig = d.get("signal", "NEUTRAL")
    e   = SIGNAL_EMOJI.get(sig, "🟡")
    r   = RISK_EMOJI.get(d.get("riskLevel","MEDIUM"), "🟡")
    return (
        f"{e} *{d.get('ticker','?'):5s}* {fmtU(d.get('price'))} ({fmtP(d.get('change'))})"
        f"  RSI:{fmt(d.get('rsi14'),0)}"
        f"  SL:{fmtU(d.get('stopLoss'))}"
        f"  TP:{fmtU(d.get('takeProfit1'))}"
        f"  {r}{d.get('confidence','—')}%"
    )


def build_scanner_msg(results: list, errors: list, title="📡 BOZOR SKANERI") -> str:
    buys  = [r for r in results if r.get("signal") in ("STRONG_BUY","BUY")]
    sells = [r for r in results if r.get("signal") in ("STRONG_SELL","SELL")]
    neut  = [r for r in results if r.get("signal") == "NEUTRAL"]

    lines = [
        f"{'='*30}",
        f"📡 *{title}*",
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')} UTC",
        f"{'='*30}",
        f"✅ BUY: {len(buys)}   🔴 SELL: {len(sells)}   🟡 Neytral: {len(neut)}",
        f"",
    ]

    if buys:
        lines.append("💚 *SOTIB OLISH SIGNALLARI:*")
        for r in buys[:8]:
            lines.append(build_scan_line(r))
        lines.append("")

    if sells:
        lines.append("🔴 *SOTISH SIGNALLARI:*")
        for r in sells[:5]:
            lines.append(build_scan_line(r))
        lines.append("")

    if errors:
        lines.append(f"⚠️ Xato: {', '.join(errors)}")

    lines += [
        "─" * 26,
        "👆 Batafsil: `/analyze TICKER`",
        "⚠️ _Moliyaviy maslahat emas._",
    ]
    return "\n".join(lines)


# ─── Auto signal job ──────────────────────────────────────────────────────────
async def auto_signal_job(app: Application):
    """Har 4 soatda avtomatik signal yuboradi."""
    chat_id = AUTO_SIGNAL_CHAT
    if not chat_id:
        log.info("AUTO_SIGNAL_CHAT sozlanmagan — avtomatik signal o'chirilgan.")
        return

    log.info("Avtomatik signal boshlanmoqda...")
    results, errors = [], []

    for ticker in DEFAULT_TICKERS:
        try:
            r = await asyncio.get_event_loop().run_in_executor(None, quick_scan, ticker)
            results.append(r)
        except Exception as e:
            log.warning(f"auto scan xato {ticker}: {e}")
            errors.append(ticker)
        await asyncio.sleep(1)

    order = {"STRONG_BUY":0,"BUY":1,"NEUTRAL":2,"SELL":3,"STRONG_SELL":4}
    results.sort(key=lambda x: (order.get(x.get("signal","NEUTRAL"),2), -x.get("confidence",0)))

    msg = build_scanner_msg(results, errors, title="⏰ AVTOMATIK SIGNAL")
    try:
        await app.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
        log.info(f"Avtomatik signal yuborildi → {chat_id}")
    except Exception as e:
        log.error(f"Signal yuborishda xato: {e}")


# ─── /start ───────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return

    uid = update.effective_user.id
    kb = [
        [InlineKeyboardButton("📡 Bozor Skaneri",  callback_data="scan")],
        [InlineKeyboardButton("⏰ Mening ID im",   callback_data="myid")],
        [InlineKeyboardButton("ℹ️ Yordam",          callback_data="help")],
    ]
    await update.message.reply_text(
        f"🤖 *Swing Trading AI Bot*\n\n"
        f"100% bepul — yfinance + Gemini AI\n\n"
        f"📌 *Buyruqlar:*\n"
        f"/analyze AAPL — tahlil\n"
        f"/scan — bozor skaneri\n"
        f"/watchlist — kuzatish ro'yxati\n"
        f"/myid — Telegram ID ingiz\n"
        f"/help — yordam\n\n"
        f"🆔 Sizning ID: `{uid}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb)
    )


# ─── /myid ────────────────────────────────────────────────────────────────────
async def cmd_myid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    await update.message.reply_text(
        f"🆔 *Sizning ma'lumotlaringiz:*\n\n"
        f"User ID: `{uid}`\n"
        f"Chat ID: `{cid}`\n\n"
        f"`.env` faylda `AUTO_SIGNAL_CHAT={cid}` qiling — signal shu chatga keladi.",
        parse_mode="Markdown"
    )


# ─── /help ────────────────────────────────────────────────────────────────────
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Yordam*\n\n"
        "*/analyze TICKER* — to'liq tahlil\n"
        "  Misol: `/analyze AAPL`\n\n"
        "*/scan* — 15 aksiya skaneri\n\n"
        "*/watchlist* — kuzatish ro'yxati\n"
        "*/add TICKER* — qo'shish\n"
        "*/remove TICKER* — o'chirish\n\n"
        "*/myid* — Telegram ID ingiz\n\n"
        "📊 *Signallar:*\n"
        "💚 STRONG BUY · 🟢 BUY · 🟡 HOLD · 🟠 SELL · 🔴 STRONG SELL\n\n"
        "⏰ *Avtomatik signal:* har 4 soatda\n"
        "`.env` da `AUTO_SIGNAL_CHAT` ni sozlang\n\n"
        "⚠️ _Moliyaviy maslahat emas._",
        parse_mode="Markdown"
    )


# ─── /analyze ────────────────────────────────────────────────────────────────
async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    if not ctx.args:
        await update.message.reply_text("❓ Misol: `/analyze AAPL`", parse_mode="Markdown")
        return

    ticker = ctx.args[0].upper().strip()
    msg = await update.message.reply_text(
        f"⚙️ *{ticker}* tahlil qilinmoqda...",
        parse_mode="Markdown"
    )
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, analyze_stock, ticker)
        text = build_detail(data)
        kb = [[
            InlineKeyboardButton("🔄 Yangilash", callback_data=f"refresh_{ticker}"),
            InlineKeyboardButton("📡 Skaner",    callback_data="scan"),
        ]]
        await msg.edit_text(text, parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        log.error(f"analyze xato {ticker}: {e}")
        await msg.edit_text(f"❌ Xatolik: {e}\n\nTicker to'g'rimi? Misol: AAPL, TSLA, NVDA")


# ─── /scan ────────────────────────────────────────────────────────────────────
async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    wl      = ctx.user_data.get("watchlist")
    tickers = wl if wl else DEFAULT_TICKERS

    msg = await update.message.reply_text(
        f"📡 *{len(tickers)} ta aksiya skanerlanyapti...*\n▓░░░░░░░░░ 0%",
        parse_mode="Markdown"
    )

    results, errors = [], []
    order = {"STRONG_BUY":0,"BUY":1,"NEUTRAL":2,"SELL":3,"STRONG_SELL":4}

    for i, ticker in enumerate(tickers):
        try:
            r = await asyncio.get_event_loop().run_in_executor(None, quick_scan, ticker)
            results.append(r)
            results.sort(key=lambda x: (order.get(x.get("signal","NEUTRAL"),2),
                                         -x.get("confidence",0)))
        except Exception as e:
            log.warning(f"scan xato {ticker}: {e}")
            errors.append(ticker)

        pct  = int(((i+1)/len(tickers))*100)
        bars = "▓"*(pct//10) + "░"*(10-pct//10)
        if (i+1) % 3 == 0 or i+1 == len(tickers):
            try:
                await msg.edit_text(
                    f"📡 *Skanerlanyapti...*\n{bars} {pct}%\n"
                    f"✅ {i+1}/{len(tickers)} · Signal: {len(results)}",
                    parse_mode="Markdown"
                )
            except:
                pass
        await asyncio.sleep(0.5)

    text = build_scanner_msg(results, errors)
    kb   = [[InlineKeyboardButton("🔄 Qayta", callback_data="scan")]]
    await msg.edit_text(text, parse_mode="Markdown",
                        reply_markup=InlineKeyboardMarkup(kb))


# ─── /watchlist, /add, /remove ───────────────────────────────────────────────
async def cmd_watchlist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    wl = ctx.user_data.get("watchlist", [])
    if not wl:
        await update.message.reply_text(
            "📋 Ro'yxat bo'sh.\n\nQo'shish: `/add AAPL`", parse_mode="Markdown")
        return
    kb = [[InlineKeyboardButton("📡 Ro'yxatni Skanerlash", callback_data="scan")]]
    await update.message.reply_text(
        "📋 *Kuzatish ro'yxati:*\n\n" + "\n".join(f"• {t}" for t in wl),
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb)
    )

async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("❓ Misol: `/add AAPL`", parse_mode="Markdown")
        return
    t  = ctx.args[0].upper().strip()
    wl = ctx.user_data.setdefault("watchlist", [])
    if t in wl:
        await update.message.reply_text(f"ℹ️ {t} allaqachon ro'yxatda.")
        return
    wl.append(t)
    await update.message.reply_text(
        f"✅ *{t}* qo'shildi! Jami: {len(wl)} ta", parse_mode="Markdown")

async def cmd_remove(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("❓ Misol: `/remove AAPL`", parse_mode="Markdown")
        return
    t  = ctx.args[0].upper().strip()
    wl = ctx.user_data.get("watchlist", [])
    if t not in wl:
        await update.message.reply_text(f"ℹ️ {t} ro'yxatda yo'q.")
        return
    wl.remove(t)
    await update.message.reply_text(f"🗑 *{t}* o'chirildi.", parse_mode="Markdown")


# ─── Text shortcut ────────────────────────────────────────────────────────────
async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return
    t = update.message.text.strip().upper()
    if t.isalpha() and 1 <= len(t) <= 5:
        ctx.args = [t]
        await cmd_analyze(update, ctx)
    else:
        await update.message.reply_text(
            "❓ Ticker yuboring (masalan: `AAPL`) yoki /help", parse_mode="Markdown")


# ─── Callbacks ────────────────────────────────────────────────────────────────
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "scan":
        ctx.args = []
        update.message = q.message
        await cmd_scan(update, ctx)

    elif q.data == "myid":
        uid = update.effective_user.id
        cid = update.effective_chat.id
        await q.message.reply_text(
            f"🆔 User ID: `{uid}`\nChat ID: `{cid}`", parse_mode="Markdown")

    elif q.data == "help":
        update.message = q.message
        await cmd_help(update, ctx)

    elif q.data.startswith("refresh_"):
        ticker = q.data.split("_", 1)[1]
        ctx.args = [ticker]
        update.message = q.message
        await cmd_analyze(update, ctx)


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("❌ TELEGRAM_TOKEN topilmadi!")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("analyze",   cmd_analyze))
    app.add_handler(CommandHandler("scan",      cmd_scan))
    app.add_handler(CommandHandler("watchlist", cmd_watchlist))
    app.add_handler(CommandHandler("add",       cmd_add))
    app.add_handler(CommandHandler("remove",    cmd_remove))
    app.add_handler(CommandHandler("myid",      cmd_myid))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # ⏰ Avtomatik signal scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        auto_signal_job,
        trigger="interval",
        hours=4,
        args=[app],
        id="auto_signal",
        next_run_time=None,  # darhol emas, 4 soatdan keyin
    )
    scheduler.start()
    log.info("✅ Scheduler ishga tushdi — har 4 soatda signal yuboriladi")

    log.info("🤖 Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
