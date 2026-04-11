import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# =========================
# CONFIG
# =========================

st.set_page_config(page_title="Chile Broker Engine v6", layout="wide")
st.title("🇨🇱 Chile Broker Engine v6 (Institutional + Safe Mode)")

# =========================
# TRY BROKER CONNECTION
# =========================

USE_BROKER = False
ib = None

try:
    from ib_insync import IB, Stock, util

    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=1)
    USE_BROKER = True
    st.success("✅ Broker connected (Interactive Brokers)")
except:
    st.warning("⚠️ Broker not connected → running SIMULATION MODE")

# =========================
# CHILE UNIVERSE
# =========================

TICKERS = {
    "ENEL": "ENEL",
    "SQM-B": "SQM",
    "COPEC": "COPEC",
    "SANTANDER": "BSANTANDER",
    "CHILE": "BCHILE"
}

# =========================
# DATA ENGINE
# =========================

def get_broker_data(symbol):
    try:
        contract = Stock(symbol, 'SMART', 'USD')

        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',
            durationStr='3 M',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1
        )

        df = util.df(bars)

        if df is None or df.empty:
            return None

        df = df.rename(columns=str.lower)

        return df

    except:
        return None


def get_simulated_data(symbol):
    """
    Safe fallback when broker is not available
    """
    np.random.seed(hash(symbol) % 10000)

    dates = pd.date_range(end=pd.Timestamp.today(), periods=90)

    price = 100 + np.cumsum(np.random.randn(90))

    df = pd.DataFrame({
        "date": dates,
        "open": price,
        "high": price * (1 + np.random.rand(90) * 0.02),
        "low": price * (1 - np.random.rand(90) * 0.02),
        "close": price,
        "volume": np.random.randint(10000, 100000, 90)
    })

    return df


def get_data(symbol):
    if USE_BROKER:
        df = get_broker_data(symbol)
        if df is not None:
            return df

    return get_simulated_data(symbol)

# =========================
# INDICATORS
# =========================

def compute_indicators(df):
    df["vol_avg"] = df["volume"].rolling(20).mean()
    df["vol_std"] = df["volume"].rolling(20).std()

    df["rel_vol"] = df["volume"] / df["vol_avg"]
    df["zscore"] = (df["volume"] - df["vol_avg"]) / df["vol_std"]

    df["change_pct"] = df["close"].pct_change() * 100
    df["high_5d"] = df["high"].rolling(5).max()

    df = df.replace([np.inf, -np.inf], 0).fillna(0)

    return df

# =========================
# SIGNAL ENGINE
# =========================

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

# =========================
# DASHBOARD
# =========================

cols = st.columns(2)

results = []

for i, (name, symbol) in enumerate(TICKERS.items()):

    df = get_data(symbol)

    if df is None or df.empty:
        st.warning(f"No data: {name}")
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

# =========================
# SCREENER TABLE
# =========================

st.subheader("📊 Volume Anomaly Screener")

df_res = pd.DataFrame(results)

if not df_res.empty:
