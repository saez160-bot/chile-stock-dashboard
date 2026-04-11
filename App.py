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
    elif last["change_pct"] > 1:
        return "📈 MOMENTUM"
    elif last["change_pct"] < -1:
        return "📉 DISTRIBUTION"
    return "➖ NEUTRAL"

# =========================
# CHART
# =========================

def plot_chart(df, name):
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df["date"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"]
    ))

    fig.update_layout(
        height=520,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis_rangeslider_visible=False,
        title=name
    )

    return fig

# =========================
# SELECTOR
# =========================

selected = st.selectbox("Select Stock", list(TICKERS.keys()))
ticker = TICKERS[selected]

df = get_data(ticker)

# =========================
# SAFE FALLBACK (NO BREAKS)
# =========================

if df is None or df.empty:
    st.error("No data received from API (check key or ticker access)")
    st.stop()

df = indicators(df)
last = df.iloc[-1]

# =========================
# METRICS (COMPACT)
# =========================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Price", round(last["close"], 2))

with col2:
    st.metric("Volume", f"{int(last['volume'])/1000:.1f}K")

with col3:
    st.metric("Rel Vol", round(last["rel_vol"], 2))

with col4:
    st.metric("Z", round(last["zscore"], 2))

st.markdown(
    f"<div style='font-size:13px;'>🧠 Signal: <b>{signal(last)}</b></div>",
    unsafe_allow_html=True
)

# =========================
# CHART
# =========================

st.plotly_chart(
    plot_chart(df, selected),
    use_container_width=True,
    config={"displayModeBar": False}
)

# =========================
# SCREENER
# =========================

st.subheader("📊 Screener")

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
