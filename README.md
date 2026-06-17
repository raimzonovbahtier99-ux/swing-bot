# 🤖 Swing Trading AI Bot — 100% BEPUL

**yfinance** (real narxlar) + **Gemini AI** (tahlil) + **Telegram**

---

## ✅ Nima bepul?

| Narsa | Xizmat | Narxi |
|-------|--------|-------|
| Real narxlar | yfinance (Yahoo Finance) | **BEPUL** |
| AI tahlil | Google Gemini 1.5 Flash | **BEPUL** (1500 req/kun) |
| Telegram bot | Telegram | **BEPUL** |
| Server | Railway.app | **BEPUL** (500 soat/oy) |

---

## 🚀 O'rnatish

### 1. Telegram Bot Token
1. `@BotFather` → `/newbot`
2. Nom va username bering
3. Token oling: `123456:ABC...`

### 2. Gemini API Key (BEPUL)
1. **aistudio.google.com** ga kiring
2. Google akkaunt bilan login
3. **Get API Key** → **Create API key**
4. Key oling: `AIzaSy...`

### 3. O'rnatish
```bash
pip install -r requirements.txt
cp .env.example .env
# .env ga tokenlarni yozing
python bot.py
```

### 4. Avtomatik signal sozlash
1. Botga `/myid` yuboring → Chat ID oling
2. `.env` da `AUTO_SIGNAL_CHAT=CHAT_ID` qiling
3. Botni qayta ishga tushiring
4. Har 4 soatda signal keladi! ⏰

---

## 📱 Buyruqlar

| Buyruq | Vazifasi |
|--------|----------|
| `/analyze AAPL` | To'liq tahlil |
| `/scan` | 15 aksiya skaneri |
| `/watchlist` | Kuzatish ro'yxati |
| `/add NVDA` | Qo'shish |
| `/remove TSLA` | O'chirish |
| `/myid` | Telegram ID |
| `AAPL` (ticker) | Tezkor tahlil |

---

## ☁️ Railway ga deploy

1. GitHub ga yuklang
2. railway.app → New Project → GitHub repo
3. Variables:
   - `TELEGRAM_TOKEN` = token
   - `GEMINI_API_KEY` = key
   - `AUTO_SIGNAL_CHAT` = chat ID
4. Deploy!

---

## ⚠️ Eslatmalar

- Gemini bepul: kuniga **1500 so'rov** (yetarli)
- Tahlil vaqti: **5-15 soniya**
- Scanner (15 aksiya): **~2-3 daqiqa**
- Bu faqat ma'lumot — **moliyaviy maslahat emas**
