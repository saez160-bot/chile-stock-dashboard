import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

st_autorefresh(interval=60000)

st.title("🇨🇱 Chile Real Data Engine v1")

# 🇨🇱 Chile universe
TICKERS = {
    "ENEL": "enelchile",
    "SQM-B": "sqm",
    "COPEC": "copec",
    "SANTANDER": "bsantander",
    "CHILE": "bchile"
}

# -----------------------------
# 📡 DATA ENGINE (REAL FIX)
# -----------------------------

def fetch_stooq(symbol):
    """
    Stooq free daily data (works for many global + some LATAM)
    """
    try:
        url = f"https://stooq.com/q/d/l/?s={symbol}.cl&i=d"
        df = pd.read_csv(url)

        if df is None or df.empty:
            return None

        df.columns = [c.lower() for c in df.columns]
        df.rename(columns={
            "date": "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "volume": "volume"
        }, inplace=True)

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        return df

    except:
        return None


def get_data(symbol):
    """
    Multi-source Chile data engine
    """
    df = fetch_stooq(symbol)

    if df is not None:
        return df

    return None

# -----------------------------
# 📊 INDICATORS
# -----------------------------

def compute_indicators(df):
    df["volume"] = df["volume"].fillna(0)

    df["vol_avg"] = df["volume"].rolling(20).mean()
    df["rel_vol"] = df["volume"] / df["vol_avg"]

    df["change_pct"] = df["close"].pct_change() * 100
    df["high_5d"] = df["high"].rolling(5).max()

    df = df.fillna(0)
    return df

# -----------------------------
# 🧠 SIGNAL ENGINE
# -----------------------------

def signal(last):
    if last["rel_vol"] > 1.8 and last["close"] >= last["high_5d"]:
        return "🚀 BREAKOUT"
    elif last["rel_vol"] > 1.2:
        return "⚡ ACCUMULATION"
    elif abs(last["change_pct"]) > 1.5:
        return "⚡ VOL SPIKE"
    return "➖ NEUTRAL"

# -----------------------------
# 📊 DASHBOARD
# -----------------------------

st.subheader("📊 Chile Market Overview")

cols = st.columns(2)
i = 0

results = []

for name, symbol in TICKERS.items():

    df = get_data(symbol)

    if df is None or df.empty:
        st.warning(f"⚠️ No data: {name}")
        continue

    df = compute_indicators(df)
    last = df.iloc[-1]

    with cols[i % 2]:
        st.markdown(f"### {name}")

        st.write(f"💰 Price: {round(last['close'],2)}")
        st.write(f"🔊 Rel Vol: {round(last['rel_vol'],2)}")
        st.write(f"⚡ Change: {round(last['change_pct'],2)}%")
        st.write(f"Signal: {signal(last)}")

    results.append({
        "Stock": name,
        "Price": round(last["close"], 2),
        "RelVol": round(last["rel_vol"], 2),
        "Change%": round(last["change_pct"], 2),
        "Signal": signal(last)
    })

    i += 1

# -----------------------------
# 📋 SCREENER
# -----------------------------

st.subheader("📋 Screener")

df_res = pd.DataFrame(results)

if not df_res.empty:
    df_res = df_res.sort_values("RelVol", ascending=False)
    st.dataframe(df_res)
else:
    st.error("No Chile data available from current free sources")
