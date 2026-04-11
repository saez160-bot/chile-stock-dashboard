import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import requests
from streamlit_autorefresh import st_autorefresh

# 🔄 Auto refresh
st_autorefresh(interval=60000)

st.title("🇨🇱 Chile Stock Screener Dashboard v5 (Hybrid Data Fix)")

# 🔔 Telegram (optional)
TELEGRAM_TOKEN = ""
CHAT_ID = ""

def send_alert(msg):
    if TELEGRAM_TOKEN and CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
        except:
            pass

# 📊 Chile stocks
TICKERS = {
    "ENEL": "ENELCHILE.SN",
    "SQM-B": "SQM-B.SN",
    "COPEC": "COPEC.SN",
    "BSANTANDER": "BSANTANDER.SN",
    "CHILE": "CHILE.SN"
}

# 📥 HYBRID DATA LOADER (FIXED FOR CHILE)
def get_data(ticker):
    alternatives = [
        ticker,
        ticker.replace(".SN", ".BS")
    ]

    for t in alternatives:
        try:
            df = yf.download(t, period="6mo", interval="1d")

            if df is not None and not df.empty:
                df = df.reset_index()

                # normalize columns (CRITICAL FIX)
                df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]

                required = ["open", "high", "low", "close", "volume"]
                if not all(col in df.columns for col in required):
                    continue

                df = df.fillna(0)
                df = df.replace([float("inf"), -float("inf")], 0)

                return df

        except:
            continue

    return None

# 📈 INDICATORS (Chile-safe)
def compute_indicators(df):
    df["volume"] = df["volume"].fillna(0)

    df["vol_avg"] = df["volume"].rolling(20).mean()
    df["rel_vol"] = df["volume"] / df["vol_avg"]

    df["change_pct"] = df["close"].pct_change() * 100
    df["high_5d"] = df["high"].rolling(5).max()

    df = df.fillna(0)
    return df

# 🧠 SIGNAL ENGINE (Chile adapted)
def classify_signal(last):
    if last["rel_vol"] > 1.8 and last["close"] >= last["high_5d"]:
        return "🚀 BREAKOUT"
    elif last["rel_vol"] > 1.2 and last["change_pct"] > 0.3:
        return "⚡ ACCUMULATION"
    elif abs(last["change_pct"]) > 1.2:
        return "⚡ VOL SPIKE"
    elif last["change_pct"] < 0:
        return "🔻 PULLBACK"
    return "➖ NEUTRAL"

# 📊 DASHBOARD
st.subheader("📊 Market Overview")

cols = st.columns(2)
i = 0

valid_count = 0

for name, ticker in TICKERS.items():
    df = get_data(ticker)

    if df is None or df.empty:
        st.warning(f"⚠️ No data for {name}")
        continue

    df = compute_indicators(df)

    if len(df) < 5:
        st.warning(f"⚠️ Not enough history: {name}")
        continue

    last = df.iloc[-1]
    valid_count += 1

    with cols[i % 2]:
        st.markdown(f"### {name}")

        st.write(f"💰 Price: {round(last['close'],2)}")
        st.write(f"🔊 Rel Vol: {round(last['rel_vol'],2)}")
        st.write(f"⚡ Change: {round(last['change_pct'],2)}%")

        signal = classify_signal(last)
        st.write(f"Signal: {signal}")

        if last["rel_vol"] > 1.8 and last["close"] >= last["high_5d"]:
            send_alert(f"🚀 BREAKOUT: {name} @ {last['close']}")

    i += 1

# 📋 SCREENER
st.subheader("📋 Screener Results")

results = []

for name, ticker in TICKERS.items():
    df = get_data(ticker)

    if df is None or df.empty:
        continue

    df = compute_indicators(df)
    last = df.iloc[-1]

    # 🧠 CHILE ADAPTED FILTER (balanced)
    if (
        (last["rel_vol"] > 0.8 and last["change_pct"] > 0.3) or
        (last["rel_vol"] > 1.2) or
        (abs(last["change_pct"]) > 1.2)
    ):
        results.append({
            "Stock": name,
            "Price": round(last["close"], 2),
            "RelVol": round(last["rel_vol"], 2),
            "Change%": round(last["change_pct"], 2),
            "Signal": classify_signal(last)
        })

# 📊 OUTPUT HANDLING
if results:
    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values(by="RelVol", ascending=False)
    st.dataframe(df_results)

else:
    st.warning("⚠️ No signals — showing fallback market view")

    fallback = []

    for name, ticker in TICKERS.items():
        df = get_data(ticker)

        if df is None:
            continue

        df = compute_indicators(df)
        last = df.iloc[-1]

        fallback.append({
            "Stock": name,
            "Price": round(last["close"], 2),
            "RelVol": round(last["rel_vol"], 2),
            "Change%": round(last["change_pct"], 2),
            "Signal": classify_signal(last)
        })

    if fallback:
        st.dataframe(pd.DataFrame(fallback))
    else:
        st.error("❌ No data available from Yahoo Finance (Chile feed issue)")
