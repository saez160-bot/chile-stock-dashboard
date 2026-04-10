import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import requests
from streamlit_autorefresh import st_autorefresh

# 🔄 Auto refresh every 60 sec
st_autorefresh(interval=60000)

st.title("🇨🇱 Chile Stock Screener Dashboard")

# 🔔 TELEGRAM CONFIG (optional)
TELEGRAM_TOKEN = ""  # put your token
CHAT_ID = ""         # put your chat id

def send_alert(msg):
    if TELEGRAM_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})

# 📊 Chilean tickers
TICKERS = {
    "ENEL": "ENELCHILE.SN",
    "SQM-B": "SQM-B.SN",
    "COPEC": "COPEC.SN",
    "BSANTANDER": "BSANTANDER.SN",
    "CHILE": "CHILE.SN"
}

# 📥 Get data (no API key)
def get_data(ticker):
    try:
        df = yf.download(ticker, period="3mo",
