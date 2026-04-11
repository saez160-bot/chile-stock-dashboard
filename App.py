import streamlit as st
import pandas as pd
import requests
import numpy as np

st.set_page_config(page_title="Chile CLP Engine v10", layout="wide")
st.title("🇨🇱 Chile CLP Engine v10 (EODHD Live)")

# =========================
# 🔑 API KEY (DO NOT HARD-CODE PUBLICLY)
# =========================

API_KEY = st.secrets.get("EODHD_API_KEY", "69d99e2d2c54f0.76165177")

BASE_URL = "https://eodhd.com/api/eod"

# =========================
# 🇨🇱 CHILE TICKERS
# =========================

TICKERS = {
    "ENEL CHILE": "ENELCHILE.SN",
    "SQM-B": "SQM-B.SN",
    "COPEC": "COPEC.SN",
    "BANCO DE CHILE": "CHILE.SN",
    "SANTANDER CHILE": "BSANTANDER.SN"
}

# =========================
# 📡 DATA FETCH
# =========================

def get_data(ticker):
    try:
        url = f"{BASE_URL}/{ticker}?api_token={API_KEY}&fmt=json&period=d"
        r = requests.get(url, timeout=10)

        if r.status_code != 200:
            return None

        data = r.json()

        if not isinstance(data, list) or len(data) == 0:
            return None

        df = pd.DataFrame(data)

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        return df

    except:
        return None

# =========================
# 📊 INDICATORS
# =========================

def indicators(df):
    df = df.copy()

    df["volume"] = df["volume"].fillna(0)

    df["vol_avg"] = df["volume"].rolling(20).mean()
    df["vol_std"] = df["volume"].rolling(20).std()

    df["rel_vol"] = df["volume"] / df["vol_avg"]
    df["zscore"] = (df["volume"] - df["vol_avg"]) / (df["vol_std"] + 1e-9)

    df["change_pct"] = df["close"].pct_change() * 100

    return df.fillna(0)

# =========================
# 🧠 SIGNAL ENGINE
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
        return "📉 DISTRIBUTION"
    return "➖ NEUTRAL"

# =========================
# 📊 DASHBOARD
# =========================

results = []

for name, ticker in TICKERS.items():

    df = get_data(ticker)

    if df is None or df.empty:
        st.warning(f"No data: {name}")
        continue

    df = indicators(df)
    last = df.iloc[-1]

    st.markdown(f"## {name} (CLP)")

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

st.subheader("📊 Chile CLP Screener")

if results:
    st.dataframe(pd.DataFrame(results))
else:
    st.error("No data received (check API key or ticker access)")
