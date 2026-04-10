import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go

API_KEY = "YOUR_API_KEY"

# Chilean tickers
TICKERS = {
    "ENELCHILE": "ENELCHILE.SN",
    "SQM-B": "SQM-B.SN",
    "COPEC": "COPEC.SN",
    "BSANTANDER": "BSANTANDER.SN",
    "CHILE": "CHILE.SN"
}

# Fetch data
def get_data(ticker):
    url = f"https://eodhd.com/api/eod/{ticker}?api_token={API_KEY}&fmt=json"
    data = requests.get(url).json()
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    return df

# Indicators
def compute_indicators(df):
    df['vol_avg'] = df['volume'].rolling(20).mean()
    df['rel_vol'] = df['volume'] / df['vol_avg']
    df['change_pct'] = df['close'].pct_change() * 100
    df['high_5d'] = df['high'].rolling(5).max()
    return df

# Chart
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

    fig.update_layout(title=name, xaxis_rangeslider_visible=False)
    return fig

# App UI
st.title("🇨🇱 Chile Stock Screener Dashboard")

selected = st.selectbox("Select Stock", list(TICKERS.keys()))

df = get_data(TICKERS[selected])
df = compute_indicators(df)

st.plotly_chart(plot_chart(df, selected), use_container_width=True)

latest = df.iloc[-1]

# Signals
st.subheader("📊 Signals")

st.write(f"Price: {latest['close']:.2f}")
st.write(f"Rel Volume: {latest['rel_vol']:.2f}")
st.write(f"Change %: {latest['change_pct']:.2f}")

if latest['rel_vol'] > 1.8:
    st.success("🔥 High Volume Detected")

if latest['close'] >= latest['high_5d']:
    st.success("🚀 Breakout (5-day high)")

if 1.5 < latest['change_pct'] < 4:
    st.info("⚡ Momentum Zone")

# Screener Table
st.subheader("📋 Screener Results")

results = []

for name, ticker in TICKERS.items():
    d = get_data(ticker)
    d = compute_indicators(d)
    last = d.iloc[-1]

    if (
        last['rel_vol'] > 1.5 and
        1 < last['change_pct'] < 5
    ):
        results.append({
            "Stock": name,
            "Price": last['close'],
            "RelVol": round(last['rel_vol'], 2),
            "Change%": round(last['change_pct'], 2)
        })

st.dataframe(pd.DataFrame(results))
