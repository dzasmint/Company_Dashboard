"""
Valuation utilities for Model Forecast tab
Contains RNAV, Multiple Valuation, and Historical Valuation analysis functions
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import os


def render_valuation_analysis(selected_ticker, npatmi_row=None, total_equity_row=None):
    """Render valuation analysis including stock price, RNAV, multiples, and historical metrics
    
    Returns:
        dict: Valuation data for saving to database
    """
    
    # Initialize return data
    valuation_data_return = {}
    
    # Get current stock price
    latest_close_price = render_stock_price_section(selected_ticker)
    valuation_data_return['current_price'] = latest_close_price if latest_close_price else 0
    
    # RNAV Valuation
    st.subheader("RNAV Valuation")
    rnav_data = render_rnav_section(selected_ticker, latest_close_price)
    outstanding_shares = rnav_data['outstanding_shares']
    valuation_data_return['rnav_per_share'] = rnav_data['rnav_per_share']
    valuation_data_return['rnav_details'] = rnav_data['rnav_details']
    
    # Multiple Valuation
    st.subheader("Multiple Valuation")
    multiples_data = None
    if selected_ticker and latest_close_price and outstanding_shares > 0:
        multiples_data = render_multiple_valuation(selected_ticker, latest_close_price, outstanding_shares, npatmi_row, total_equity_row)
        if multiples_data:
            valuation_data_return.update(multiples_data)
    else:
        if not selected_ticker:
            st.info("Please select a company to view multiple valuation")
        elif not latest_close_price:
            st.info("Stock price data unavailable for multiple valuation")
        elif outstanding_shares <= 0:
            st.info("Outstanding shares data unavailable for multiple valuation")
    
    # Historical Valuation Metrics
    st.markdown("---")
    st.subheader("Historical Valuation Metrics")
    valuation_data = load_valuation_data(selected_ticker)
    if valuation_data is not None and not valuation_data.empty:
        render_valuation_charts(valuation_data, selected_ticker)
    else:
        st.info(f"No historical valuation data available for {selected_ticker}")
    
    return valuation_data_return


def render_stock_price_section(ticker):
    """Render current stock price only"""
    from utils.stock_candle import get_cached_stock_data
    
    # Fetch current stock data
    with st.spinner(f"Loading stock data for {ticker}..."):
        df = get_cached_stock_data(ticker, days=30)
    
    if df is not None and not df.empty:
        latest = df.iloc[-1]
        previous = df.iloc[-2] if len(df) > 1 else latest
        
        price_change = latest['close'] - previous['close']
        price_change_pct = (price_change / previous['close'] * 100) if previous['close'] > 0 else 0
        
        st.metric(
            f"Current Price ({ticker})",
            f"{latest['close']:,.0f} VND",
            f"{price_change:+,.0f} ({price_change_pct:+.2f}%)"
        )
        
        return latest['close']
    else:
        st.warning(f"Unable to fetch stock price data for {ticker}")
        return None


def render_rnav_section(selected_ticker, latest_close_price):
    """Render RNAV valuation section and return RNAV data"""
    total_rnav = 0
    outstanding_shares = 0
    rnav_per_share = 0
    rnav_details = []  # Store RNAV table data for return
    
    if st.session_state.project_data is not None and isinstance(st.session_state.project_data, pd.DataFrame) and not st.session_state.project_data.empty:
        if 'rnav_value' in st.session_state.project_data.columns:
            total_rnav = st.session_state.project_data['rnav_value'].sum()
            
            valuation_rows = []
            total_rnav_to_company = 0
            
            for _, project in st.session_state.project_data.iterrows():
                ownership_raw = project.get('project_ownership', 1.0) if 'project_ownership' in project else 1.0
                ownership_pct = ownership_raw * 100
                rnav_value_billions = project['rnav_value'] / 1e9
                rnav_to_company = rnav_value_billions * ownership_raw
                total_rnav_to_company += rnav_to_company
                
                valuation_rows.append({
                    'Item': f"  {project['project_name']}",
                    'RNAV Value (B VND)': rnav_value_billions,
                    'Ownership (%)': ownership_pct,
                    'RNAV to Company (B VND)': rnav_to_company
                })
            
            # Add Sub-total RNAV
            valuation_rows.append({
                'Item': 'SUB-TOTAL RNAV',
                'RNAV Value (B VND)': total_rnav / 1e9,
                'Ownership (%)': None,
                'RNAV to Company (B VND)': total_rnav_to_company
            })
            
            # Load balance sheet items from FA_processed.parquet
            cash_equivalent = 0
            short_term_investment = 0
            short_term_debt = 0
            long_term_debt = 0
            latest_quarter = 'N/A'
            
            if selected_ticker:
                try:
                    fa_path = os.path.join('data', 'FA_processed.parquet')
                    if os.path.exists(fa_path):
                        fa_df = pd.read_parquet(fa_path)
                        ticker_data = fa_df[fa_df['TICKER'] == selected_ticker]
                        
                        if not ticker_data.empty:
                            latest_date = ticker_data['DATE'].max()
                            latest_quarter = latest_date
                            latest_data = ticker_data[ticker_data['DATE'] == latest_date]
                            
                            def get_balance_sheet_value(keycode, default=0):
                                row = latest_data[latest_data['KEYCODE'] == keycode]
                                if not row.empty:
                                    value = row['VALUE'].values[0]
                                    if pd.notna(value):
                                        return value / 1e9
                                return default
                            
                            cash_equivalent = get_balance_sheet_value('Cash_Equivalent', 0)
                            short_term_investment = get_balance_sheet_value('Short_Investment', 0)
                            short_term_debt = get_balance_sheet_value('ST_Debt', 0)
                            long_term_debt = get_balance_sheet_value('LT_Debt', 0)
                            
                            os_row = latest_data[latest_data['KEYCODE'] == 'OS']
                            if not os_row.empty:
                                os_value = os_row['VALUE'].values[0]
                                if pd.notna(os_value):
                                    outstanding_shares = os_value / 1e6
                                else:
                                    outstanding_shares = 0
                            else:
                                outstanding_shares = 0
                except Exception as e:
                    st.warning(f"Could not load balance sheet data: {str(e)}")
            
            # Format quarter display
            quarter_display = 'N/A'
            if latest_quarter != 'N/A' and 'Q' in latest_quarter:
                year_str = latest_quarter[:4]
                quarter_num = latest_quarter[-1]
                year_short = year_str[-2:]
                quarter_display = f'{quarter_num}Q{year_short}'
            
            # Add balance sheet items
            valuation_rows.append({
                'Item': f'Cash & Equivalent ({quarter_display})',
                'RNAV Value (B VND)': None,
                'Ownership (%)': None,
                'RNAV to Company (B VND)': cash_equivalent
            })
            
            valuation_rows.append({
                'Item': f'Short-term Investment ({quarter_display})',
                'RNAV Value (B VND)': None,
                'Ownership (%)': None,
                'RNAV to Company (B VND)': short_term_investment
            })
            
            valuation_rows.append({
                'Item': f'Short-term Debt ({quarter_display})',
                'RNAV Value (B VND)': None,
                'Ownership (%)': None,
                'RNAV to Company (B VND)': -short_term_debt
            })
            
            valuation_rows.append({
                'Item': f'Long-term Debt ({quarter_display})',
                'RNAV Value (B VND)': None,
                'Ownership (%)': None,
                'RNAV to Company (B VND)': -long_term_debt
            })
            
            # Add separator
            valuation_rows.append({
                'Item': '',
                'RNAV Value (B VND)': None,
                'Ownership (%)': None,
                'RNAV to Company (B VND)': None
            })
            
            # Calculate Total Equity
            total_equity = total_rnav_to_company + cash_equivalent + short_term_investment + (-short_term_debt) + (-long_term_debt)
            
            valuation_rows.append({
                'Item': 'TOTAL EQUITY',
                'RNAV Value (B VND)': None,
                'Ownership (%)': None,
                'RNAV to Company (B VND)': total_equity
            })
            
            valuation_rows.append({
                'Item': f'Total Outstanding Shares ({quarter_display}) (millions)',
                'RNAV Value (B VND)': None,
                'Ownership (%)': None,
                'RNAV to Company (B VND)': outstanding_shares
            })
            
            # Calculate RNAV per share (store in outer scope variable)
            rnav_per_share = (total_equity * 1e9 / (outstanding_shares * 1e6)) if outstanding_shares > 0 else 0
            valuation_rows.append({
                'Item': 'RNAV/share (VND)',
                'RNAV Value (B VND)': None,
                'Ownership (%)': None,
                'RNAV to Company (B VND)': rnav_per_share
            })
            
            # Create DataFrame
            valuation_df = pd.DataFrame(valuation_rows)
            
            # Display metrics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("RNAV/share", f"{rnav_per_share:,.0f} VND")
            with col2:
                if latest_close_price and latest_close_price > 0:
                    upside_pct = ((rnav_per_share / latest_close_price) - 1) * 100
                    st.metric("Upside (%)", f"{upside_pct:+.1f}%")
                else:
                    st.metric("Upside (%)", "N/A")
            
            # Store RNAV details for return
            for _, row in valuation_df.iterrows():
                rnav_details.append({
                    'item': row['Item'],
                    'rnav_value': row['RNAV Value (B VND)'],
                    'ownership_pct': row['Ownership (%)'],
                    'rnav_to_company': row['RNAV to Company (B VND)']
                })
            
            # Display table
            display_data = []
            for _, row in valuation_df.iterrows():
                item = row['Item']
                rnav_val = row['RNAV Value (B VND)']
                ownership = row['Ownership (%)']
                rnav_to_company = row['RNAV to Company (B VND)']
                
                formatted_rnav = ''
                if pd.notna(rnav_val):
                    if 'Outstanding Shares' in str(item):
                        formatted_rnav = f'{rnav_val:,.0f}M'
                    elif 'RNAV/share' in str(item):
                        formatted_rnav = f'{rnav_val:,.0f}'
                    else:
                        formatted_rnav = f'{rnav_val:,.0f}B'
                
                formatted_ownership = ''
                if pd.notna(ownership):
                    formatted_ownership = f'{ownership:.1f}%'
                
                formatted_rnav_to_company = ''
                if pd.notna(rnav_to_company):
                    if 'Outstanding Shares' in str(item):
                        formatted_rnav_to_company = f'{rnav_to_company:,.0f}M'
                    elif 'RNAV/share' in str(item):
                        formatted_rnav_to_company = f'{rnav_to_company:,.0f}'
                    else:
                        formatted_rnav_to_company = f'{rnav_to_company:,.0f}B'
                
                display_data.append({
                    'Item': item,
                    'RNAV Value': formatted_rnav,
                    'Ownership (%)': formatted_ownership,
                    'RNAV to Company': formatted_rnav_to_company
                })
            
            display_df = pd.DataFrame(display_data)
            
            def style_important_rows(val):
                if isinstance(val, str):
                    if any(keyword in val for keyword in ['SUB-TOTAL', 'TOTAL EQUITY', 'RNAV/share']):
                        return 'font-weight: bold'
                return ''
            
            st.dataframe(
                display_df.style.applymap(
                    style_important_rows,
                    subset=['Item']
                ),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("RNAV values not available in project data")
    else:
        st.info("Sync project data to calculate RNAV")
    
    # Return RNAV data for saving
    return {
        'outstanding_shares': outstanding_shares,
        'rnav_per_share': rnav_per_share,
        'rnav_details': rnav_details
    }


def render_multiple_valuation(ticker, current_price, outstanding_shares, npatmi_row=None, total_equity_row=None):
    """Render multiple valuation metrics based on model forecast"""
    
    current_year = datetime.now().year
    next_year = current_year + 1
    
    # Check if we have the required data from session state
    if not npatmi_row or not total_equity_row:
        st.warning(f"Forecast data not available in current session. Please complete the Model Forecast calculations above.")
        return
    
    # Initialize values
    pe_values = {'trailing': None, current_year: None, next_year: None}
    pb_values = {'trailing': None, current_year: None, next_year: None}
    
    # Load historical valuation data
    valuation_data = load_valuation_data(ticker)
    pe_mean = None
    pb_mean = None
    
    if valuation_data is not None and not valuation_data.empty:
        latest_val = valuation_data.iloc[-1]
        
        if 'P/E' in valuation_data.columns and pd.notna(latest_val['P/E']):
            pe_values['trailing'] = latest_val['P/E']
        
        if 'P/B' in valuation_data.columns and pd.notna(latest_val['P/B']):
            pb_values['trailing'] = latest_val['P/B']
        
        if 'P/E' in valuation_data.columns:
            pe_series = valuation_data['P/E'].dropna()
            if not pe_series.empty:
                pe_mean = pe_series.mean()
        
        if 'P/B' in valuation_data.columns:
            pb_series = valuation_data['P/B'].dropna()
            if not pb_series.empty:
                pb_mean = pb_series.mean()
    
    # Calculate forward P/E and P/B using passed data
    for year in [current_year, next_year]:
        year_str = str(year)
        
        # Get NPATMI from npatmi_row
        if year_str in npatmi_row:
            npatmi = npatmi_row[year_str]  # Already in billions VND
            
            if npatmi and outstanding_shares > 0:
                eps = (npatmi * 1e9) / (outstanding_shares * 1e6)
                if eps > 0:
                    pe_values[year] = current_price / eps
        
        # Get Total Equity from total_equity_row
        if year_str in total_equity_row:
            total_equity = total_equity_row[year_str]  # Already in billions VND
            
            if total_equity and outstanding_shares > 0:
                bvps = (total_equity * 1e9) / (outstanding_shares * 1e6)
                if bvps > 0:
                    pb_values[year] = current_price / bvps
    
    # Helper function to format metric with mean comparison
    def format_metric_with_mean(value, mean_val):
        if value is None:
            return "N/A", ""
        
        main_text = f"{value:.2f}x"
        
        if mean_val is not None and mean_val > 0:
            vs_mean_pct = ((value / mean_val) - 1) * 100
            if vs_mean_pct >= 0:
                delta_text = f"vs. mean: +{vs_mean_pct:.0f}%"
            else:
                delta_text = f"vs. mean: {vs_mean_pct:.0f}%"
        else:
            delta_text = ""
        
        return main_text, delta_text
    
    # Display P/E metrics
    st.markdown("**P/E Ratios**")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        val, delta = format_metric_with_mean(pe_values['trailing'], pe_mean)
        st.metric("Trailing P/E", val, delta)
    
    with col2:
        val, delta = format_metric_with_mean(pe_values[current_year], pe_mean)
        st.metric(f"{current_year}F P/E", val, delta)
    
    with col3:
        val, delta = format_metric_with_mean(pe_values[next_year], pe_mean)
        st.metric(f"{next_year}F P/E", val, delta)
    
    with col4:
        mean_val = f"{pe_mean:.2f}x" if pe_mean else "N/A"
        st.metric("Mean P/E", mean_val, "Historical Average")
    
    # Display P/B metrics
    st.markdown("**P/B Ratios**")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        val, delta = format_metric_with_mean(pb_values['trailing'], pb_mean)
        st.metric("Trailing P/B", val, delta)
    
    with col2:
        val, delta = format_metric_with_mean(pb_values[current_year], pb_mean)
        st.metric(f"{current_year}F P/B", val, delta)
    
    with col3:
        val, delta = format_metric_with_mean(pb_values[next_year], pb_mean)
        st.metric(f"{next_year}F P/B", val, delta)
    
    with col4:
        mean_val = f"{pb_mean:.2f}x" if pb_mean else "N/A"
        st.metric("Mean P/B", mean_val, "Historical Average")
    
    # Return multiples data for saving
    return {
        'pe_values': pe_values,
        'pb_values': pb_values,
        'pe_mean': pe_mean,
        'pb_mean': pb_mean
    }


def load_valuation_data(ticker):
    """Load valuation data from Val_processed.csv for selected ticker"""
    try:
        csv_path = os.path.join('data', 'Val_processed.csv')
        if not os.path.exists(csv_path):
            return None
        
        df = pd.read_csv(csv_path)
        ticker_data = df[df['TICKER'] == ticker].copy()
        
        if ticker_data.empty:
            return None
        
        ticker_data['TRADE_DATE'] = pd.to_datetime(ticker_data['TRADE_DATE'])
        ticker_data = ticker_data.sort_values('TRADE_DATE')
        
        metrics = ['P/E', 'P/B', 'P/S', 'EV/EBITDA']
        ticker_data = ticker_data.dropna(subset=metrics, how='all')
        
        return ticker_data
        
    except Exception as e:
        st.error(f"Error loading valuation data: {str(e)}")
        return None


def render_valuation_charts(data, ticker):
    """Render valuation metric charts with standard deviation bands"""
    
    metrics = [
        ('P/E', 'Price to Earnings'),
        ('P/B', 'Price to Book'),
        ('P/S', 'Price to Sales'),
        ('EV/EBITDA', 'EV/EBITDA')
    ]
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[title for _, title in metrics],
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )
    
    positions = [(1, 1), (1, 2), (2, 1), (2, 2)]
    
    for (metric, title), (row, col) in zip(metrics, positions):
        if metric not in data.columns:
            continue
        
        metric_data = data[['TRADE_DATE', metric]].dropna()
        
        if metric_data.empty:
            continue
        
        x = metric_data['TRADE_DATE']
        y = metric_data[metric]
        
        mean = y.mean()
        std = y.std()
        
        # Main line
        fig.add_trace(
            go.Scatter(
                x=x,
                y=y,
                mode='lines',
                name=metric,
                line=dict(color='blue', width=2),
                showlegend=False
            ),
            row=row, col=col
        )
        
        # Mean line
        fig.add_trace(
            go.Scatter(
                x=x,
                y=[mean] * len(x),
                mode='lines',
                name=f'Mean',
                line=dict(color='green', width=1, dash='dash'),
                showlegend=False
            ),
            row=row, col=col
        )
        
        # +1 std line
        fig.add_trace(
            go.Scatter(
                x=x,
                y=[mean + std] * len(x),
                mode='lines',
                name='+1σ',
                line=dict(color='orange', width=1, dash='dot'),
                showlegend=False
            ),
            row=row, col=col
        )
        
        # -1 std line
        fig.add_trace(
            go.Scatter(
                x=x,
                y=[mean - std] * len(x),
                mode='lines',
                name='-1σ',
                line=dict(color='orange', width=1, dash='dot'),
                showlegend=False
            ),
            row=row, col=col
        )
        
        # +2 std line
        fig.add_trace(
            go.Scatter(
                x=x,
                y=[mean + 2*std] * len(x),
                mode='lines',
                name='+2σ',
                line=dict(color='red', width=1, dash='dot'),
                showlegend=False
            ),
            row=row, col=col
        )
        
        # -2 std line
        fig.add_trace(
            go.Scatter(
                x=x,
                y=[mean - 2*std] * len(x),
                mode='lines',
                name='-2σ',
                line=dict(color='red', width=1, dash='dot'),
                showlegend=False
            ),
            row=row, col=col
        )
        
        # Add latest value annotation
        if len(y) > 0:
            latest_value = y.iloc[-1]
            latest_date = x.iloc[-1]
            
            fig.add_annotation(
                x=latest_date,
                y=latest_value,
                text=f"{latest_value:.2f}",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=1,
                arrowcolor="black",
                ax=-30,
                ay=-30,
                row=row, col=col
            )
    
    fig.update_layout(
        height=700,
        title_text=f"Valuation Metrics for {ticker}",
        showlegend=True,
        hovermode='x unified'
    )
    
    fig.update_xaxes(title_text="Date", row=2, col=1)
    fig.update_xaxes(title_text="Date", row=2, col=2)
    
    st.plotly_chart(fig, use_container_width=True)