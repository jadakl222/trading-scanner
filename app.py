import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import pytz
from datetime import datetime
from ta.momentum import RSIIndicator
from streamlit_autorefresh import st_autorefresh

# =========================
# UNIVERSE
# =========================
UNIVERSE = [
    "SNDL","NOK","BB","PLUG","SOFI","RIOT","MARA","CLSK","FUBO","OPEN",
    "WISH","ATER","CEI","IDEX","XELA","BBIG","AMC","GME","TLRY","HOOD",
    "NIO","LCID","RIVN","SPCE","KOSS","PROG","TRKA","SAVA","AI","NKLA"
]

# =========================
# UI SETUP
# =========================
st.set_page_config(page_title="Penny Stock Scanner", layout="wide")

st.markdown("""
<style>
.stApp { background-color:#0e1117; color:white; }
h1,h2,h3 { color:#00ffcc; }
</style>
""", unsafe_allow_html=True)

st.title("📊 Penny Stock Momentum Scanner (≤ $10)")

st_autorefresh(interval=60000, key="refresh")

# =========================
# SESSION
# =========================
def session_state():
    now = datetime.now(pytz.timezone("US/Eastern")).time()

    if now < datetime.strptime("09:30","%H:%M").time():
        return "PREMARKET"
    elif now < datetime.strptime("16:00","%H:%M").time():
        return "OPEN"
    return "AFTERMARKET"

st.info(f"🕒 Market Session: {session_state()}")

# =========================
# DATA
# =========================
def get_data(ticker):
    try:
        df = yf.download(ticker, period="2d", interval="5m", prepost=True, progress=False)
        if df is None or df.empty:
            return None
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
        return df
    except:
        return None

# =========================
# PRICE FILTER
# =========================
def price_ok(df):
    try:
        return df["Close"].iloc[-1] <= 10
    except:
        return False

# =========================
# COMPANY NAME FIX (IMPORTANT)
# =========================
def get_name(ticker):
    try:
        info = yf.Ticker(ticker).info
        return info.get("shortName") or info.get("longName") or ticker
    except:
        return ticker

# =========================
# INDICATORS
# =========================
def indicators(df):
    df = df.copy()
    close = df["Close"].squeeze()
    df["RSI"] = RSIIndicator(close=close).rsi()
    return df

# =========================
# GAP
# =========================
def gap_percent(df):
    try:
        prev = df["Close"].iloc[0]
        last = df["Close"].iloc[-1]
        return ((last - prev) / prev) * 100
    except:
        return 0

# =========================
# VOLUME
# =========================
def volume_surge(df):
    try:
        return df["Volume"].iloc[-1] > df["Volume"].mean() * 2
    except:
        return False

# =========================
# LIQUIDITY
# =========================
def liquidity_ok(df):
    try:
        return df["Volume"].mean() > 250000
    except:
        return False

# =========================
# SCORE ENGINE
# =========================
def score_engine(df):
    last = df.iloc[-1]

    score = 0
    reasons = []

    gap = gap_percent(df)

    if gap > 5:
        score += 3
        reasons.append(f"Strong gap {gap:.2f}%")

    if last["Close"] > df["Close"].rolling(20).max().iloc[-2]:
        score += 3
        reasons.append("Breakout structure")

    if volume_surge(df):
        score += 3
        reasons.append("Volume surge")

    if 50 < last["RSI"] < 70:
        score += 2
        reasons.append("Healthy RSI momentum")

    if liquidity_ok(df):
        score += 2
    else:
        score -= 3
        reasons.append("Low liquidity risk")

    return score, reasons

# =========================
# TRADE LEVELS
# =========================
def trade_levels(df):
    entry = df["Close"].iloc[-1]
    stop = df["Low"].rolling(10).min().iloc[-1]
    target = entry + (2 * (entry - stop))
    pct = ((target - entry) / entry) * 100
    return entry, stop, target, pct

# =========================
# MAIN LOOP
# =========================
results = []

for t in UNIVERSE:

    df = get_data(t)
    if df is None:
        continue

    if not price_ok(df):
        continue

    if not liquidity_ok(df):
        continue

    try:
        df = indicators(df)
    except:
        continue

    score, reasons = score_engine(df)

    if score < 5:
        continue

    name = get_name(t)
    entry, stop, target, pct = trade_levels(df)

    results.append({
        "ticker": t,
        "name": name,
        "score": score,
        "entry": entry,
        "stop": stop,
        "target": target,
        "pct": pct,
        "reasons": reasons
    })

# =========================
# SORT
# =========================
results = sorted(results, key=lambda x: x["score"], reverse=True)

# =========================
# UI
# =========================
st.subheader("🔥 High-Probability Setups")

for r in results:

    st.markdown(f"""
    ## 📌 {r['ticker']} — {r['name']}

    **Score: {r['score']}**

    Entry: {round(r['entry'],2)}  
    Target: {round(r['target'],2)}  
    Stop: {round(r['stop'],2)}  

    💰 Potential Gain: +{round(r['pct'],2)}%
    """)

    st.write("📊 Setup reasons:")
    for x in r["reasons"]:
        st.write("-", x)

    st.divider()
