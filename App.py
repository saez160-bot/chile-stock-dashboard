import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go

# =========================
# PAGE CONFIG
# =========================

st.set_page_config(page_title="Chile Terminal v14", layout="wide")

st.markdown(
    "<h3 style='margin-bottom:5px;'>🇨🇱 Chile Trading Terminal v14</h3>",
    unsafe_allow_html=True
)

st.caption("CLP Engine • EODHD Data • Volume Anomalies • MA Trend System")

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
# DATA ENGINE (STABLE)
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
        if not all(col in df.columns for col in required):
            return None

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        return df.dropna()

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

    df["rel_vol"] = df["volume"] / (df["vol_avg"] + 1e-9)
    df["zscore"] = (df["volume"] - df["vol_avg"]) / (df["vol_std"] + 1e-9)

    df["change_pct"] = df["close"].pct_change() * 100

    # MOVING AVERAGES
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma50"] = df["close"].rolling(50).mean()

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
# CHART ENGINE (PRO)
# =========================

def plot_chart(df, name):
    fig = go.Figure()

    # Candles
    fig.add_trace(go.Candlestick(
        x=df["date"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Price"
    ))

    # MA20
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["ma20"],
        mode="lines",
        name="MA20"
    ))

    # MA50
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["ma50"],
        mode="lines",
        name="MA50"
    ))

    fig.update_layout(
        title=name,
        height=600,
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(
            rangeslider=dict(visible=True),
            showspikes=True
        ),
        yaxis=dict(fixedrange=False),
        hovermode="x unified",
        template="plotly_dark"
    )

    return fig

# =========================
# SELECTOR
# =========================

selected = st.selectbox("Select Stock", list(TICKERS.keys()))
ticker = TICKERS[selected]

df = get_data(ticker)

if df is None or df.empty:
    st.error("No data available (check API key or ticker)")
    st.stop()

df = indicators(df)
last = df.iloc[-1]

# =========================
# COMPACT METRICS (FIXED UI)
# =========================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Price", round(last["close"], 2))

with col2:
    st.metric("Vol (K)", f"{last['volume']/1000:.1f}")

with col3:
    st.metric("Rel Vol", round(last["rel_vol"], 2))

with col4:
    st.metric("Z", round(last["zscore"], 2))

# =========================
# SIGNAL (SMALL FONT)
# =========================

st.markdown(
    f"<div style='font-size:12px; opacity:0.85;'>🧠 Signal: <b>{signal(last)}</b></div>",
    unsafe_allow_html=True
)

# =========================
# CHART
# =========================

st.plotly_chart(
    plot_chart(df, selected),
    use_container_width=True,
    config={
        "displayModeBar": True,
        "scrollZoom": True
    }
)

# =========================
# SCREENER
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
    st.dataframe(
        pd.DataFrame(results).sort_values("ZScore", ascending=False),
        use_container_width=True
    )
else:
    st.warning("No screener data available")
