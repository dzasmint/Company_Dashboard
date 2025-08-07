#%% Data pull from SSI
import requests
import pandas as pd
import time
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import sys
import streamlit as st

# Add parent directory to path for config imports
sys.path.append(str(Path(__file__).parent.parent))
from config.constants import API_ENDPOINTS, PLOTLY_CONFIG

#%% Helper functions
def get_unix_timestamp(date_str):
    # Input format: 'YYYY-MM-DD'
    return int(time.mktime(datetime.strptime(date_str, "%Y-%m-%d").timetuple()))

def fetch_ohlcv(symbol, start_date="2020-01-01", end_date=None):
    if end_date is None:
        end_date = datetime.today().strftime('%Y-%m-%d')
    from_unix = get_unix_timestamp(start_date)
    to_unix = get_unix_timestamp(end_date)

    url = (
        f"{API_ENDPOINTS['ssi_base']}/statistics/charts/history"
        f"?resolution=1D&symbol={symbol}&from={from_unix}&to={to_unix}"
    )

    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()

    # Safety checks
    if data['code'] != "SUCCESS":
        raise Exception("API returned error: " + str(data))

    # Extract OHLCV and time
    d = data["data"]
    # Ensure d['t'] is not empty and is a list of timestamps
    if not d['t']:
        raise Exception("No data returned from API for the given date range.")

    # # Convert to Vietnam time (GMT+7)
    date_series = pd.to_datetime(d['t'], unit='s')
    # # If you want naive datetime (no tz info), uncomment the next line:
    # date_series = date_series.tz_localize(None)

    df = pd.DataFrame({
        'date': date_series,
        'open': d['o'],
        'high': d['h'],
        'low': d['l'],
        'close': d['c'],
        'volume': d['v']
    })

    return df


def plot_ohlcv_candlestick(df, symbol, start_date = '2024-12-31'):
    df_temp = df[df['date'] >= start_date].copy()
    df_temp['date'] = df_temp['date'].dt.strftime('%Y-%m-%d')
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3],
        subplot_titles=[f"{symbol} Price Chart", "Volume"]
    )
    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df_temp['date'],
            open=df_temp['open'],
            high=df_temp['high'],
            low=df_temp['low'],
            close=df_temp['close'],
            name='OHLC',
            opacity=1.0
        ), row=1, col=1
    )
    # Color volume bars by up/down
    colors = ['green' if c >= o else 'red' for c, o in zip(df_temp['close'], df_temp['open'])]
    fig.add_trace(
        go.Bar(
            x=df_temp['date'],
            y=df_temp['volume'],
            marker_color=colors,
            name='Volume',
            opacity=0.5
        ), row=2, col=1
    )
    # Layout
    fig.update_layout(
        template='plotly_white',
        title=f"{symbol} Price Chart",
        xaxis2_title="Date",
        yaxis_title="Price",
        yaxis2_title="Volume",
        xaxis_rangeslider_visible=False,  
        xaxis2_rangeslider_visible=False,
        height=600,
        showlegend=False
    )
    fig.update_xaxes(
        showgrid=False,
        type='category',
    )

    return fig

#%% Putting it together
ytd = datetime(datetime.today().year, 1, 1)
two_years_ago = datetime.today() - pd.DateOffset(years=2)
three_years_ago = datetime.today() - pd.DateOffset(years=3)
five_years_ago = datetime.today() - pd.DateOffset(years=5)

def load_ticker_price(ticker, start_date, end_date=None):
    """
    Load OHLCV data for a specific ticker.
    """
    df = fetch_ohlcv(ticker, start_date, end_date)
    fig = plot_ohlcv_candlestick(df, ticker, start_date)
    return fig


#%% Streamlit
# import streamlit as st 

# st.header("Stock Price Dashboard")
# ticker = st.text_input("Enter ticker symbol (e.g., 'VNINDEX')", value='VNINDEX')
# start_date = st.date_input("Start Date (Default: YTD)", value=ytd)
# if st.button("Load Data"):
#     try:
#         fig = load_ticker_price(ticker, start_date=start_date.strftime('%Y-%m-%d'))
#         st.plotly_chart(fig)
#     except Exception as e:
#         st.error(f"Error loading data: {e}")