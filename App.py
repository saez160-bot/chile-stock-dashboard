import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go

# =========================
# CONFIG
# =========================

st.set_page_config(page_title="Chile Trading Terminal v11", layout="wide")
st.title("🇨🇱 Chile Trading Terminal v11 (CLP + Charts + Signals)")

# 🔑 API KEY (use secrets in production)
API_KEY = st.secrets.get("EODHD_API_KEY", "69d99e2d2c54f0.76165177")
BASE_URL = "https://eodhd.com/api/eod"

# =========================
# 🇨🇱 UNIVERSE
# =========================

TICKERS = {
    "ENEL CHILE": "ENELCHILE.SN",
    "SQM-B": "SQM-B.SN",
    "COPEC": "COPEC.SN",
    "BANCO DE CHILE": "CHILE.SN",
    "SANTANDER CHILE": "BSANTANDER.SN"
}

# =========================
# DATA ENGINE
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
# INDICATORS
# =========================

def indicators(df):
    df = df.copy()

    df["volume"] = df["volume"].fillna(0)

    df["vol_avg"] = df["volume"].rolling(20).mean()
    df["vol_std"] = df["volume"].rolling(20).std()

    df["rel_vol"] = df["volume"] / df["vol_avg"]
    df["zscore"] = (df["volume"] - df["vol_avg"]) / (df["vol_std"] + 1e-9)

    df["change_pct"] = df["close"].pct_change() * 100

    df = df.replace([np.inf, -np.inf], 0).fillna(0)

    return df

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
        return "📉 DISTRIBUTION"
    return "➖ NEUTRAL"

# =========================
# CHART ENGINE
# =========================

def plot_chart(df, name):
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df["date"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name=name
    ))

    fig.update_layout(
        title=f"{name} - CLP Chart",
        height=550,
        xaxis_rangeslider_visible=False
    )

    return fig

# =========================
# STOCK SELECTOR
# =========================

selected = st.selectbox("📊 Select Chile Stock", list(TICKERS.keys()))
ticker = TICKERS[selected]

df = get_data(ticker)

# =========================
# MAIN VIEW
# =========================

if df is None or df.empty:
    st.error("No CLP data available (check API key or ticker)")
    st.stop()

df = indicators(df)
last = df.iloc[-1]

# =========================
# METRICS
# =========================

col1, col2, col3, col4 = st.columns(4)

col1.metric("Price (CLP)", round(last["close"], 2))
col2.metric("Volume", int(last["volume"]))
col3.metric("Rel Vol", round(last["rel_vol"], 2))
col4.metric("Z-Score", round(last["zscore"], 2))

st.subheader("🧠 Signal")
st.write(signal(last))

# =========================
# CHART
# =========================

st.subheader("📈 Price Chart")

st.plotly_chart(plot_chart(df, selected), use_container_width=True)

# =========================
# SCREENER (ALL STOCKS)
# =========================

st.subheader("📊 Chile Screener")

results = []

for name, ticker in TICKERS.items():

    df_temp = get_data(ticker)

    if df_temp is None or df_temp.empty:
        continue

    df_temp = indicators(df_temp)
    last_temp = df_temp.iloc[-1]

    results.append({
        "Stock": name,
        "Price": round(last_temp["close"], 2),
        "RelVol": round(last_temp["rel_vol"], 2),
        "ZScore": round(last_temp["zscore"], 2),
        "Signal": signal(last_temp)
    })

if results:
    df_res = pd.DataFrame(results).sort_values("ZScore", ascending=False)
    st.dataframe(df_res, use_container_width=True)
else:
    st.warning("No screener data available")
