import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go

# =========================
# PAGE CONFIG
# =========================

st.set_page_config(page_title="Chile Terminal v12", layout="wide")

st.markdown(
    "<h3 style='margin-bottom:5px;'>🇨🇱 Chile Trading Terminal v12</h3>",
    unsafe_allow_html=True
)

st.caption("CLP Market Engine • EODHD Data • Volume Anomalies • Charts")

# =========================
# API KEY
# =========================

API_KEY = st.secrets.get("EODHD_API_KEY", "69d99e2d2c54f0.76165177")
BASE_URL = "https://eodhd.com/api/eod"

# =========================
# UNIVERSE
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
        height=500,
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=30, b=10)
    )

    return fig

# =========================
# SELECTOR
# =========================

selected = st.selectbox("Select Stock", list(TICKERS.keys()))
ticker = TICKERS[selected]

df = get_data(ticker)

# =========================
