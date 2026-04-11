import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import requests
from streamlit_autorefresh import st_autorefresh

# 🔄 Auto refresh (60 sec)
st_autorefresh(interval=60000)

st.title("🇨🇱 Chile Stock Screener Dashboard")

# 🔔 TELEGRAM (optional)
TELEGRAM_TOKEN = ""
CHAT_ID = ""

def send_alert(msg):
    if TELEGRAM_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# 📊 Chile stocks
TICKERS = {
    "ENEL": "ENELCHILE.SN",
    "SQM-B": "SQM-B.SN",
    "COPEC": "COPEC.SN",
    "BSANTANDER": "BSANTANDER.SN",
    "CHILE": "CHILE.SN"
}

# 📥 DATA (no API key)
def get_data(ticker):
    try:
        df = yf.download(ticker, period="3mo", interval="1d")

        if df.empty:
            return None

        df = df.reset_index()
        df.columns = [col.lower() for col in df.columns]

        return df

    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return None

# 📈 Indicators
def compute_indicators(df):
    df['vol_avg'] = df['volume'].rolling(20).mean()
    df['rel_vol'] = df['volume'] / df['vol_avg']
    df['change_pct'] = df['close'].pct_change() * 100
    df['high_5d'] = df['high'].rolling(5).max()
    return df

# 📊 Chart
def plot_chart(df, name):
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df['date'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name=name
    ))

    fig.update_layout(
        title=name,
        xaxis_rangeslider_visible=False,
        height=300
    )

    return fig

# 🧠 Signal engine
def classify_signal(last):
    if last['rel_vol'] > 2 and last['close'] >= last['high_5d']:
        return "🚀 BREAKOUT"
    elif last['rel_vol'] > 1.5 and last['change_pct'] > 1:
        return "⚡ EARLY MOMENTUM"
    elif last['change_pct'] < 0:
        return "🔻 PULLBACK"
    return "➖ NEUTRAL"

# 📊 DASHBOARD VIEW
st.subheader("📊 Multi-Stock Overview")

cols = st.columns(2)
i = 0

for name, ticker in TICKERS.items():
    df = get_data(ticker)

    if df is None or df.empty:
        continue

    df = compute_indicators(df)
    last = df.iloc[-1]

    with cols[i % 2]:
        st.markdown(f"### {name}")

        st.write(f"💰 Price: {round(last['close'],2)}")
        st.write(f"🔊 Rel Vol: {round(last['rel_vol'],2)}")
        st.write(f"⚡ Change: {round(last['change_pct'],2)}%")

        signal = classify_signal(last)
        st.write(f"Signal: {signal}")

        # 🔔 ALERT
        if last['rel_vol'] > 2 and last['close'] >= last['high_5d']:
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

    signal = classify_signal(last)

    # 🧠 IMPROVED FILTER (adaptive)
    if (
        last['rel_vol'] > 1.2 and last['change_pct'] > 0.5
    ) or (
        last['rel_vol'] > 1.5
    ) or (
        last['change_pct'] > 2
    ):
        results.append({
            "Stock": name,
            "Price": round(last['close'], 2),
            "RelVol": round(last['rel_vol'], 2),
            "Change%": round(last['change_pct'], 2),
            "Signal": signal
        })

# 📊 DISPLAY RESULTS
if results:
    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values(by="RelVol", ascending=False)
    st.dataframe(df_results)
else:
    st.warning("⚠️ No strong setups — showing full watchlist")

    fallback = []

    for name, ticker in TICKERS.items():
        df = get_data(ticker)

        if df is None or df.empty:
            continue

        df = compute_indicators(df)
        last = df.iloc[-1]

        fallback.append({
            "Stock": name,
            "Price": round(last['close'], 2),
            "RelVol": round(last['rel_vol'], 2),
            "Change%": round(last['change_pct'], 2),
            "Signal": classify_signal(last)
        })

    st.dataframe(pd.DataFrame(fallback))
