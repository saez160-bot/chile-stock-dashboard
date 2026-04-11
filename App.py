import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go

# =========================
# PAGE
# =========================

st.set_page_config(page_title="Chile Terminal v13", layout="wide")

st.markdown(
    "<h3 style='margin-bottom:5px;'>🇨🇱 Chile Trading Terminal v13 (Stable Pro)</h3>",
    unsafe_allow_html=True
)

st.caption("Stable engine • EODHD data • Safe fallback handling • Charts + Screener")

# =========================
# API
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
# SAFE DATA ENGINE (ROBUST)
# =========================

def get_data(ticker):
    try:
        url = f"{BASE_URL}/{ticker}?api_token={API_KEY}&fmt=json"
        r = requests.get(url, timeout=12)

        if r.status_code != 200:
            return None

        data = r.json()

        if not isinstance(data, list) or len(data) < 30:
            return None

        df = pd.DataFrame(data)

        required = ["date", "open", "high", "low", "close", "volume"]
        for col in required:
            if col not in df.columns:
                return None

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        df = df.dropna()

        return df

    except:
        return None

# =========================
# INDICATORS
# =========================

def indicators(df):
    df = df.copy()

    df["volume"] = df["volume"].fillna(0)

    df["vol_avg"] = df["volume"].rolling(20, min_periods=5).mean()
    df["vol_std"] = df["volume"].rolling(20, min_periods=5).std()

    df["rel_vol"] = df["volume"] / (df["vol_avg"] + 1e-9)
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
    elif last["change
