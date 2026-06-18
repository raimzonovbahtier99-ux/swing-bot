"""
analyzer.py — yfinance (real narxlar) + Gemini AI (bepul tahlil)
"""

import os
import json
import time
import logging

log = logging.getLogger(__name__)

# ── yfinance ──────────────────────────────────────────────────────────────────
try:
    import yfinance as yf
    YF_OK = True
except ImportError:
    YF_OK = False
    log.warning("yfinance o'rnatilmagan")

# ── Gemini ────────────────────────────────────────────────────────────────────
try:
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
    model = genai.GenerativeModel("gemini-1.5-flash")
    GEMINI_OK = True
except Exception as e:
    GEMINI_OK = False
    log.warning(f"Gemini yuklanmadi: {e}")


# ─── yfinance market data ─────────────────────────────────────────────────────
def get_market_data(ticker: str) -> dict:
    if not YF_OK:
        raise RuntimeError("yfinance o'rnatilmagan")

    tk   = yf.Ticker(ticker)
    info = tk.info or {}

    price = float(
        info.get("currentPrice") or
        info.get("regularMarketPrice") or
        info.get("previousClose") or 0
    )
    if price == 0:
        raise ValueError(f"{ticker} uchun narx topilmadi")

    prev   = float(info.get("previousClose") or price)
    change = round((price - prev) / prev * 100, 2) if prev else 0.0

    hist = tk.history(period="6mo", interval="1d")

    rsi14    = _calc_rsi(hist["Close"], 14)  if not hist.empty else 50.0
    ma50     = float(hist["Close"].tail(50).mean())  if len(hist) >= 50  else price
    ma200    = float(hist["Close"].tail(200).mean()) if len(hist) >= 200 else price
    atr_pct  = _calc_atr_pct(hist) if not hist.empty else 2.0
    macd_st  = _calc_macd(hist["Close"]) if not hist.empty else "Neytral"

    vol     = info.get("volume") or info.get("regularMarketVolume") or 0
    vol_str = f"{vol/1_000_000:.1f}M" if vol > 1_000_000 else f"{vol:,}"

    return {
        "ticker":        ticker.upper(),
        "companyName":   info.get("longName") or info.get("shortName") or ticker,
        "sector":        info.get("sector") or "—",
        "price":         round(price, 2),
        "change":        change,
        "high52":        round(float(info.get("fiftyTwoWeekHigh") or price * 1.2), 2),
        "low52":         round(float(info.get("fiftyTwoWeekLow")  or price * 0.8), 2),
        "pe":            round(float(info.get("trailingPE") or 0), 1) or None,
        "beta":          round(float(info.get("beta") or 1.0), 2),
        "marketCap":     round(float(info.get("marketCap") or 0) / 1e9, 1),
        "dividendYield": round(float(info.get("dividendYield") or 0) * 100, 2),
        "rsi14":         round(rsi14, 1),
        "ma50":          round(ma50, 2),
        "ma200":         round(ma200, 2),
        "macdStatus":    macd_st,
        "atrPct":        round(atr_pct, 2),
        "volumeStr":     vol_str,
        "priceSource":   "Yahoo Finance",
    }


def _calc_rsi(closes, period=14) -> float:
    delta = closes.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss
    val   = (100 - 100 / (1 + rs)).iloc[-1]
    return float(val) if val == val else 50.0


def _calc_atr_pct(hist) -> float:
    h, l, c = hist["High"], hist["Low"], hist["Close"]
    tr  = (h - l).combine((h - c.shift()).abs(), max).combine((l - c.shift()).abs(), max)
    atr = tr.rolling(14).mean().iloc[-1]
    return float(atr / c.iloc[-1] * 100) if c.iloc[-1] else 2.0


def _calc_macd(closes) -> str:
    e12 = closes.ewm(span=12).mean()
    e26 = closes.ewm(span=26).mean()
    mac = e12 - e26
    sig = mac.ewm(span=9).mean()
    return "Bullish" if mac.iloc[-1] > sig.iloc[-1] else "Bearish"


# ─── Gemini tahlil ────────────────────────────────────────────────────────────
def _gemini(market: dict, short=False) -> dict:
    if not GEMINI_OK:
        raise RuntimeError("Gemini API ishlamayapti")

    if short:
        prompt = f"""Swing trading analitiki sifatida quyidagi ma'lumotlar asosida signal ber.
Aksiya: {market['ticker']} | Narx: ${market['price']} ({market['change']:+.2f}%)
RSI: {market['rsi14']} | MACD: {market['macdStatus']} | Beta: {market['beta']}
MA50: ${market['ma50']} | MA200: ${market['ma200']} | ATR: {market['atrPct']}%

Faqat JSON qaytargil:
{{"signal":"STRONG_BUY|BUY|NEUTRAL|SELL|STRONG_SELL","confidence":0-100,"riskLevel":"LOW|MEDIUM|HIGH","stopLoss":raqam,"takeProfit1":raqam,"rsi14":{market['rsi14']},"summary":"1 jumla o'zbekcha"}}"""
    else:
        prompt = f"""Professional swing trading tahlili qil.
{market['ticker']} — {market['companyName']} ({market['sector']})
Narx: ${market['price']} ({market['change']:+.2f}%) | 52H: ↑${market['high52']} ↓${market['low52']}
P/E: {market['pe']} | Beta: {market['beta']} | MarketCap: ${market['marketCap']}B | Div: {market['dividendYield']}%
RSI: {market['rsi14']} | MACD: {market['macdStatus']} | MA50: ${market['ma50']} | MA200: ${market['ma200']} | ATR: {market['atrPct']}%

Faqat JSON qaytargil:
{{"signal":"STRONG_BUY|BUY|NEUTRAL|SELL|STRONG_SELL","confidence":0-100,"stopLoss":raqam,"takeProfit1":raqam,"takeProfit2":raqam,"takeProfit3":raqam,"riskReward":raqam,"riskLevel":"LOW|MEDIUM|HIGH","riskScore":0-100,"companyHealth":"EXCELLENT|GOOD|FAIR|POOR","healthScore":0-100,"technicalScore":0-100,"fundamentalScore":0-100,"swingTimeframe":"masalan 1-2 hafta","entryZone":"kirish oralig'i","keyLevels":["d1","d2","d3"],"catalysts":["s1","s2"],"risks":["x1","x2"],"summary":"3 jumla o'zbekcha"}}"""

    for attempt in range(3):
        try:
            resp  = model.generate_content(prompt)
            text  = resp.text.replace("```json","").replace("```","").strip()
            s, e  = text.find("{"), text.rfind("}")
            if s == -1: raise ValueError("JSON yo'q")
            return json.loads(text[s:e+1])
        except Exception as ex:
            log.warning(f"Gemini urinish {attempt+1}: {ex}")
            time.sleep(2)
    raise RuntimeError("Gemini 3 marta ham javob bermadi")


# ─── Public API ───────────────────────────────────────────────────────────────
def analyze_stock(ticker: str) -> dict:
    ticker = ticker.upper().strip()
    market = get_market_data(ticker)
    ai     = _gemini(market, short=False)
    return {**market, **ai}


def quick_scan(ticker: str) -> dict:
    ticker = ticker.upper().strip()
    market = get_market_data(ticker)
    ai     = _gemini(market, short=True)
    return {**market, **ai}
