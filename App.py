import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Chile CLP Engine v8", layout="wide")
st.title("🇨🇱 Chile Market Engine v8 (REAL CLP DATA)")

st_autorefresh(interval=60000)

# =========================
# 🇨🇱 REAL CHILE TICKERS
# =========================

TICKERS = {
    "ENEL CHILE": "ENELCHILE.SN",
    "SQM-B": "SQM-B.SN",
    "COPEC": "COPEC.SN",
    "BANCO DE CHILE": "CHILE.SN",
    "SANTANDER CHILE": "BSANTANDER.SN"
}

# =========================
# DATA ENGINE (CLP REAL)
# =========================

def get_data(ticker):
    try:
        df = yf.download(ticker, period="6mo", interval="1d", progress=False)

        if df is None or df.empty:
            return None

        df = df.reset_index()
        df.columns = [c.lower().replace(" ", "_") for c in df.columns]

        required = ["open", "high", "low", "close", "volume"]

        if not all(col in df.columns for col in required):
            return None

        return df.dropna()

    except:
        return None

# =========================
# INDICATORS
# =========================

def indicators(df):
    df["vol_avg"] = df["volume"].rolling(20, min_periods=1).mean()
    df["vol_std"] = df["volume"].rolling(20, min_periods=1).std()

    df["rel_vol"] = df["volume"] / df["vol_avg"]
    df["zscore"] = (df["volume"] - df["vol_avg"]) / (df["vol_std"] + 1e-9)

    df["change_pct"] = df["close"].pct_change() * 100
    df["high_5d"] = df["high"].rolling(5, min_periods=1).max()

    return df.fillna(0)

# =========================
# SIGNAL ENGINE
# =========================

def signal(last):
    if last["zscore"] > 3:
        return "🚨 INSTITUTIONAL FLOW"
    elif last["zscore"] > 2:
        return "🔥 ACCUMULATION"
    elif last["rel_vol"] > 1.5:
        return "⚡ VOLUME SPIKE"
    elif last["change_pct"] > 1:
        return "📈 MOMENTUM"
    elif last["change_pct"] < -1:
        return "📉 SELLING PRESSURE"
    return "➖ NEUTRAL"

# =========================
# DASHBOARD
# =========================

cols = st.columns(2)

results = []

for i, (name, ticker) in enumerate(TICKERS.items()):

    df = get_data(ticker)

    if df is None:
        st.warning(f"⚠️ No real CLP data: {name}")
        continue

    df = indicators(df)
    last = df.iloc[-1]

    with cols[i % 2]:
        st.markdown(f"## {name} (CLP)")

        st.metric("Precio CLP", round(last["close"], 2))
        st.metric("Volumen", int(last["volume"]))
        st.metric("Rel Vol", round(last["rel_vol"], 2))
        st.metric("Z-Score", round(last["zscore"], 2))

        st.write("Signal:", signal(last))

    results.append({
        "Stock": name,
        "Precio CLP": round(last["close"], 2),
        "RelVol": round(last["rel_vol"], 2),
        "ZScore": round(last["zscore"], 2),
        "Signal": signal(last)
    })

# =========================
# SCREENER
# =========================

st.subheader("📊 Chile CLP Screener")

df_res = pd.DataFrame(results)

if not df_res.empty:
    st.dataframe(df_res.sort_values("ZScore", ascending=False))
else:
    st.error("No CLP market data available (Yahoo limitation or ticker mismatch)")
