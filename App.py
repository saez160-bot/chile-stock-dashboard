import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go

# =========================
# PAGE SETUP
# =========================

st.set_page_config(page_title="Chile Terminal v16", layout="wide")

st.markdown(
    "<h3 style='margin-bottom:5px;'>🇨🇱 Chile Trading Terminal v16 (Pro + Volume + Controls)</h3>",
    unsafe_allow_html=True
)

st.caption("CLP Engine • EODHD • AI Breakout • Volume + Chart Controls")

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
    "COPEC": "COPEC.SN",
    "BANCO DE CHILE": "CHILE.SN",
    "SANTANDER CHILE": "BSANTANDER.SN",
    "SOCOVESA": "SOCOVESA.SN",
    "COLBUN": "COLBUN.SN",
    "LATAM": "LTM.SN"
}

# =========================
# DATA ENGINE (SAFE)
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
# AI BREAKOUT ENGINE
# =========================

def breakout_score(df):
    trend = 0
    if df["ma20"].iloc[-1] > df["ma50"].iloc[-1]:
        trend = 25
    elif df["ma20"].iloc[-1] < df["ma50"].iloc[-1]:
        trend = -10

    vol_score = min(df["rel_vol"].iloc[-1] * 20, 35)
    momentum = min(abs(df["change_pct"].iloc[-1]) * 10, 20)

    recent_range = (df["high"] - df["low"]).iloc[-5:].mean()
    full_range = (df["high"] - df["low"]).mean()

    volatility = 20 if recent_range > full_range else 5

    score = trend + vol_score + momentum + volatility

    return max(0, min(100, score))


def breakout_status(score):
    if score >= 75:
        return "🚀 BREAKOUT READY"
    elif score >= 55:
        return "⚡ BUILDING PRESSURE"
    elif score >= 35:
        return "🟡 ACCUMULATION"
    return "🔵 NO SETUP"

# =========================
# CONTROLS
# =========================

st.subheader("📊 Chart Controls")

chart_type = st.selectbox("Chart Type", ["Candlestick", "Line", "OHLC"])
show_ma = st.checkbox("Show MA20 / MA50", value=True)
show_volume = st.checkbox("Show Volume", value=True)

# =========================
# CHART ENGINE (FULL)
# =========================

def plot_chart(df, name):

    fig = go.Figure()

    # PRICE
    if chart_type == "Candlestick":
        fig.add_trace(go.Candlestick(
            x=df["date"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"]
        ))

    elif chart_type == "Line":
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df["close"],
            mode="lines",
            name="Price"
        ))

    elif chart_type == "OHLC":
        fig.add_trace(go.Ohlc(
            x=df["date"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"]
        ))

    # MOVING AVERAGES
    if show_ma:
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df["ma20"],
            mode="lines",
            name="MA20"
        ))

        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df["ma50"],
            mode="lines",
            name="MA50"
        ))

    # VOLUME
    if show_volume:
        colors = np.where(df["close"] >= df["open"], "green", "red")

        fig.add_trace(go.Bar(
            x=df["date"],
            y=df["volume"],
            marker_color=colors,
            opacity=0.3,
            name="Volume",
            yaxis="y2"
        ))

    fig.update_layout(
        title=name,
        height=650,
        template="plotly_dark",
        hovermode="x unified",
        margin=dict(l=10, r=10, t=30, b=10),

        xaxis=dict(rangeslider=dict(visible=False)),

        yaxis=dict(title="Price"),

        yaxis2=dict(
            title="Volume",
            overlaying="y",
            side="right",
            showgrid=False
        ),

        legend=dict(orientation="h")
    )

    return fig

# =========================
# STOCK SELECTOR
# =========================

selected = st.selectbox("Select Stock", list(TICKERS.keys()))
ticker = TICKERS[selected]

df = get_data(ticker)

if df is None or df.empty:
    st.error("No data available")
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
    st.metric("Vol (K)", f"{last['volume']/1000:.1f}")

with col3:
    st.metric("Rel Vol", round(last["rel_vol"], 2))

with col4:
    st.metric("Z", round(last["zscore"], 2))

# =========================
# SIGNAL + AI BREAKOUT
# =========================

score = breakout_score(df)
status = breakout_status(score)

st.markdown(
    f"<div style='font-size:12px; opacity:0.85;'>"
    f"🧠 Signal: <b>{signal(last)}</b> | "
    f"🚀 Breakout Score: <b>{score:.0f}/100</b> ({status})"
    f"</div>",
    unsafe_allow_html=True
)

# =========================
# CHART
# =========================

st.plotly_chart(
    plot_chart(df, selected),
    use_container_width=True,
    config={"displayModeBar": True, "scrollZoom": True}
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
    score_temp = breakout_score(df_temp)

    results.append({
        "Stock": name,
        "Price": round(last_temp["close"], 2),
        "RelVol": round(last_temp["rel_vol"], 2),
        "ZScore": round(last_temp["zscore"], 2),
        "BreakoutScore": score_temp,
        "Signal": signal(last_temp)
    })

if results:
    df_res = pd.DataFrame(results).sort_values("BreakoutScore", ascending=False)
    st.dataframe(df_res, use_container_width=True)
else:
    st.warning("No screener data available")
