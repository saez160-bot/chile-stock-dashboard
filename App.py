import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

st_autorefresh(interval=60000)

st.title("🇨🇱 Chile Proxy Institutional Scanner v2")

# -----------------------------
# 🇨🇱 PROXY TICKERS (REAL DATA)
# -----------------------------
TICKERS = {
    "SQM": "SQM",       # lithium giant (Chile exposure)
    "ENEL CHILE": "ENIC",
    "SANTANDER CHILE": "BSAC",
    "LATAM BASKET": "EEM"   # optional emerging markets flow proxy
}

# -----------------------------
# 📥 DATA LOADER (STABLE)
# -----------------------------
def get_data(ticker):
    try:
        df = yf.download(ticker, period="6mo", interval="1d")

        if df is None or df.empty:
            return None

        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]

        df = df.replace([np.inf, -np.inf], 0).fillna(0)

        return df

    except:
        return None

# -----------------------------
# 📊 INDICATORS
# -----------------------------
def compute_indicators(df):
    df["vol_avg"] = df["volume"].rolling(20).mean()
    df["vol_std"] = df["volume"].rolling(20).std()

    df["rel_vol"] = df["volume"] / df["vol_avg"]
    df["zscore"] = (df["volume"] - df["vol_avg"]) / df["vol_std"]

    df["change_pct"] = df["close"].pct_change() * 100
    df["high_5d"] = df["high"].rolling(5).max()

    df = df.replace([np.inf, -np.inf], 0).fillna(0)

    return df

# -----------------------------
# 🧠 SIGNAL ENGINE
# -----------------------------
def signal(last):
    if last["zscore"] > 3:
        return "🚨 INSTITUTIONAL FLOW"
    elif last["zscore"] > 2:
        return "🔥 STRONG ACCUMULATION"
    elif last["rel_vol"] > 1.5:
        return "⚡ VOLUME ANOMALY"
    elif last["change_pct"] > 1:
        return "📈 MOMENTUM"
    elif last["change_pct"] < -1:
        return "📉 WEAKNESS"
    return "➖ NEUTRAL"

# -----------------------------
# 📊 DASHBOARD
# -----------------------------
cols = st.columns(2)

results = []

for i, (name, ticker) in enumerate(TICKERS.items()):

    df = get_data(ticker)

    if df is None or df.empty:
        st.warning(f"⚠️ No data: {name}")
        continue

    df = compute_indicators(df)
    last = df.iloc[-1]

    with cols[i % 2]:
        st.markdown(f"## {name}")

        st.metric("Price", round(last["close"], 2))
        st.metric("Volume", int(last["volume"]))
        st.metric("Rel Vol", round(last["rel_vol"], 2))
        st.metric("Z-Score", round(last["zscore"], 2))

        st.write("Signal:", signal(last))

    results.append({
        "Stock": name,
        "Price": round(last["close"], 2),
        "RelVol": round(last["rel_vol"], 2),
        "ZScore": round(last["zscore"], 2),
        "Signal": signal(last)
    })

# -----------------------------
# 📋 SCREENER
# -----------------------------
st.subheader("📊 Anomaly Screener")

df_res = pd.DataFrame(results)

if not df_res.empty:
    df_res = df_res.sort_values("ZScore", ascending=False)
    st.dataframe(df_res, use_container_width=True)
else:
    st.error("No data available")
