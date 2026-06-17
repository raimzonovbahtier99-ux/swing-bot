"""
analyzer.py — yfinance (real narxlar) + Gemini AI (bepul tahlil)
"""

import os
import json
import yfinance as yf
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")  # Bepul, tez


# ─── yfinance orqali real ma'lumot ───────────────────────────────────────────
def get_market_data(ticker: str) -> dict:
    """yfinance orqali real narx va texnik ma'lumotlar."""
    tk   = yf.Ticker(ticker)
    info = tk.info

    # Narx
    price = (
        info.get("currentPrice") or
        info.get("regularMarketPrice") or
        info.get("previousClose") or 0
    )

    # Kunlik o'zgarish
    prev  = info.get("previousClose") or price
    change = ((price - prev) / prev * 100) if prev else 0

    # Tarixiy narxlar (texnik hisoblash uchun)
    hist = tk.history(period="6mo", interval="1d")

    rsi14  = calc_rsi(hist["Close"], 14)  if not hist.empty else 50
    ma50   = float(hist["Close"].tail(50).mean())  if len(hist) >= 50 else price
    ma200  = float(hist["Close"].tail(200).mean()) if len(hist) >= 200 else price
    atr_pct = calc_atr_pct(hist) if not hist.empty else 2.0

    # MACD
    macd_status = calc_macd_status(hist["Close"]) if not hist.empty else "Neytral"

    # Volume
    vol = info.get("volume") or info.get("regularMarketVolume") or 0
    vol_str = f"{vol/1_000_000:.1f}M" if vol > 1_000_000 else f"{vol:,}"

    return {
        "ticker":        ticker.upper(),
        "companyName":   info.get("longName") or info.get("shortName") or ticker,
        "sector":        info.get("sector") or "—",
        "price":         round(float(price), 2),
        "change":        round(change, 2),
        "high52":        round(float(info.get("fiftyTwoWeekHigh") or price * 1.2), 2),
        "low52":         round(float(info.get("fiftyTwoWeekLow")  or price * 0.8), 2),
        "pe":            round(float(info.get("trailingPE") or 0), 1) or None,
        "beta":          round(float(info.get("beta") or 1.0), 2),
        "marketCap":     round(float(info.get("marketCap") or 0) / 1e9, 1),
        "dividendYield": round(float(info.get("dividendYield") or 0) * 100, 2),
        "rsi14":         round(rsi14, 1),
        "ma50":          round(ma50, 2),
        "ma200":         round(ma200, 2),
        "macdStatus":    macd_status,
        "atrPct":        round(atr_pct, 2),
        "volumeStr":     vol_str,
        "priceSource":   "Yahoo Finance (yfinance)",
    }


# ─── Texnik indikatorlar ──────────────────────────────────────────────────────
def calc_rsi(closes, period=14) -> float:
    delta  = closes.diff()
    gain   = delta.clip(lower=0).rolling(period).mean()
    loss   = (-delta.clip(upper=0)).rolling(period).mean()
    rs     = gain / loss
    rsi    = 100 - (100 / (1 + rs))
    val    = rsi.iloc[-1]
    return float(val) if not (val != val) else 50.0  # NaN check


def calc_atr_pct(hist) -> float:
    high  = hist["High"]
    low   = hist["Low"]
    close = hist["Close"]
    tr    = (high - low).combine(
                (high - close.shift()).abs(),
                max
            ).combine(
                (low  - close.shift()).abs(),
                max
            )
    atr   = tr.rolling(14).mean().iloc[-1]
    price = close.iloc[-1]
    return float(atr / price * 100) if price else 2.0


def calc_macd_status(closes) -> str:
    ema12 = closes.ewm(span=12).mean()
    ema26 = closes.ewm(span=26).mean()
    macd  = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    if macd.iloc[-1] > signal.iloc[-1]:
        return "Bullish"
    elif macd.iloc[-1] < signal.iloc[-1]:
        return "Bearish"
    return "Neytral"


# ─── Gemini AI tahlil ────────────────────────────────────────────────────────
def _gemini_analyze(market: dict, short=False) -> dict:
    """Gemini ga ma'lumot yuborib, signal olish."""

    if short:
        prompt = f"""
Sen swing trading analitikisan. Quyidagi ma'lumotlar asosida signal ber.

Aksiya: {market['ticker']} ({market['companyName']})
Narx: ${market['price']}  Kunlik: {market['change']}%
RSI(14): {market['rsi14']}  MACD: {market['macdStatus']}
MA50: ${market['ma50']}  MA200: ${market['ma200']}  ATR%: {market['atrPct']}
Beta: {market['beta']}  52H: ↑${market['high52']} ↓${market['low52']}

Faqat JSON qaytargil:
{{"signal":"STRONG_BUY yoki BUY yoki NEUTRAL yoki SELL yoki STRONG_SELL","confidence":0-100,"riskLevel":"LOW yoki MEDIUM yoki HIGH","stopLoss":raqam,"takeProfit1":raqam,"rsi14":{market['rsi14']},"summary":"1 jumla o'zbekcha"}}"""
    else:
        prompt = f"""
Sen professional swing trading analitikisan.

AKSIYA MA'LUMOTLARI (REAL, yfinance dan):
Ticker: {market['ticker']} — {market['companyName']}
Sektor: {market['sector']}
Narx: ${market['price']}  ({market['change']:+.2f}% bugun)
52 haftalik: ↑${market['high52']}  ↓${market['low52']}
P/E: {market['pe']}  Beta: {market['beta']}  MarketCap: ${market['marketCap']}B
Dividend: {market['dividendYield']}%

TEXNIK KO'RSATKICHLAR:
RSI(14): {market['rsi14']}
MACD: {market['macdStatus']}
MA50: ${market['ma50']}  MA200: ${market['ma200']}
ATR%: {market['atrPct']}%  Volume: {market['volumeStr']}

Yuqoridagi MA'LUMOTLAR ASOSIDA swing trading tahlili qil.

Faqat JSON qaytargil, boshqa hech narsa yo'q:
{{
  "signal":"STRONG_BUY yoki BUY yoki NEUTRAL yoki SELL yoki STRONG_SELL",
  "confidence":0-100,
  "stopLoss":raqam,
  "takeProfit1":raqam,
  "takeProfit2":raqam,
  "takeProfit3":raqam,
  "riskReward":raqam,
  "riskLevel":"LOW yoki MEDIUM yoki HIGH",
  "riskScore":0-100,
  "companyHealth":"EXCELLENT yoki GOOD yoki FAIR yoki POOR",
  "healthScore":0-100,
  "technicalScore":0-100,
  "fundamentalScore":0-100,
  "swingTimeframe":"masalan 1-2 hafta",
  "entryZone":"kirish narx oralig'i",
  "keyLevels":["daraja1","daraja2","daraja3"],
  "catalysts":["sabab1","sabab2","sabab3"],
  "risks":["xavf1","xavf2"],
  "summary":"3-4 jumlali o'zbekcha xulosa"
}}"""

    resp  = model.generate_content(prompt)
    text  = resp.text.replace("```json","").replace("```","").strip()
    s, e  = text.find("{"), text.rfind("}")
    if s == -1 or e == -1:
        raise ValueError(f"JSON topilmadi: {text[:200]}")
    return json.loads(text[s:e+1])


# ─── Public functions ─────────────────────────────────────────────────────────
def analyze_stock(ticker: str) -> dict:
    """To'liq tahlil: yfinance + Gemini."""
    ticker = ticker.upper().strip()
    market = get_market_data(ticker)
    ai     = _gemini_analyze(market, short=False)
    return {**market, **ai}


def quick_scan(ticker: str) -> dict:
    """Tezkor skaner: yfinance + Gemini (qisqa prompt)."""
    ticker = ticker.upper().strip()
    market = get_market_data(ticker)
    ai     = _gemini_analyze(market, short=True)
    return {**market, **ai}
