import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os
import sys

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import stock price functions
from utils.stock_candle import get_cached_stock_data
from utils.mongodb_utils import load_company_forecast
from datetime import datetime


class ValuationTab:
    """Valuation Analysis Tab"""
    
    def __init__(self):
        pass
    
    def render(self):
        """Render simplified valuation analysis based on RNAV and revenue forecasts"""
        #st.header("Valuation Analysis")
        
        # Get selected ticker
        selected_ticker = st.session_state.get('selected_company', None)
        
        # Display current stock price and chart if ticker is selected
        latest_close_price = None
        if selected_ticker:
            latest_close_price = self.render_stock_price_section(selected_ticker)
        
        # RNAV Valuation
        st.subheader("RNAV Valuation")
        
        total_rnav = 0  # Initialize total_rnav
        outstanding_shares = 0  # Initialize outstanding_shares for use in multiple valuation
        if st.session_state.project_data is not None and isinstance(st.session_state.project_data, pd.DataFrame) and not st.session_state.project_data.empty:
            if 'rnav_value' in st.session_state.project_data.columns:
                total_rnav = st.session_state.project_data['rnav_value'].sum()
                
                # Create comprehensive valuation table
                valuation_rows = []
                
                # Add individual project rows
                total_rnav_to_company = 0  # Track RNAV attributable to company
                for _, project in st.session_state.project_data.iterrows():
                    # Get ownership as raw value (0.5 = 50%), default to 1.0 (100%)
                    ownership_raw = project.get('project_ownership', 1.0) if 'project_ownership' in project else 1.0
                    ownership_pct = ownership_raw * 100  # Convert to percentage for display
                    rnav_value_billions = project['rnav_value'] / 1e9
                    rnav_to_company = rnav_value_billions * ownership_raw
                    total_rnav_to_company += rnav_to_company
                    
                    valuation_rows.append({
                        'Item': f"  {project['project_name']}",
                        'RNAV Value (B VND)': rnav_value_billions,
                        'Ownership (%)': ownership_pct,
                        'RNAV to Company (B VND)': rnav_to_company
                    })
                
                # Add Sub-total row for RNAV (using RNAV to Company values)
                valuation_rows.append({
                    'Item': 'SUB-TOTAL RNAV',
                    'RNAV Value (B VND)': total_rnav / 1e9,
                    'Ownership (%)': None,  # No ownership % for subtotal
                    'RNAV to Company (B VND)': total_rnav_to_company
                })
                
                # Load balance sheet items from FA_processed.parquet (quarterly data)
                cash_equivalent = 0
                short_term_investment = 0
                short_term_debt = 0
                long_term_debt = 0
                outstanding_shares = 0
                latest_quarter = 'N/A'  # Track which quarter is being used
                
                # Get selected ticker
                selected_ticker = st.session_state.get('selected_company', None)
                
                if selected_ticker:
                    try:
                        # Load financial data from quarterly parquet file
                        import os
                        fa_path = os.path.join('data', 'FA_processed.parquet')
                        if os.path.exists(fa_path):
                            fa_df = pd.read_parquet(fa_path)
                            
                            # Filter for selected ticker
                            ticker_data = fa_df[fa_df['TICKER'] == selected_ticker]
                            
                            if not ticker_data.empty:
                                # Get the latest quarter available for this ticker
                                latest_date = ticker_data['DATE'].max()
                                latest_quarter = latest_date  # Store the quarter (e.g., '2025Q2')
                                
                                # Filter for latest quarter data
                                latest_data = ticker_data[ticker_data['DATE'] == latest_date]
                                
                                # Helper function to get value for a specific keycode
                                def get_balance_sheet_value(keycode, default=0):
                                    row = latest_data[latest_data['KEYCODE'] == keycode]
                                    if not row.empty:
                                        value = row['VALUE'].values[0]
                                        # Convert to billions if value exists and is not NaN
                                        if pd.notna(value):
                                            return value / 1e9  # Convert from VND to billions VND
                                    return default
                                
                                # Load balance sheet items using correct keycodes from FA_A_processed.parquet
                                # Only load Cash_Equivalent field as requested
                                cash_equivalent = get_balance_sheet_value('Cash_Equivalent', 0)
                                
                                # Load short-term investment using the correct keycode
                                short_term_investment = get_balance_sheet_value('Short_Investment', 0)
                                
                                # Use the correct keycodes: ST_Debt and LT_Debt
                                short_term_debt = get_balance_sheet_value('ST_Debt', 0)
                                long_term_debt = get_balance_sheet_value('LT_Debt', 0)
                                
                                # Load Outstanding Shares (OS) - the value in parquet is actual number of shares
                                # get_balance_sheet_value divides by 1e9, but OS is already in shares not VND
                                # So we need to get the raw value differently
                                os_row = latest_data[latest_data['KEYCODE'] == 'OS']
                                if not os_row.empty:
                                    os_value = os_row['VALUE'].values[0]
                                    if pd.notna(os_value):
                                        outstanding_shares = os_value / 1e6  # Convert to millions for display
                                    else:
                                        outstanding_shares = 0
                                else:
                                    outstanding_shares = 0
                    
                    except Exception as e:
                        st.warning(f"Could not load balance sheet data: {str(e)}")
                        # Keep default values of 0
                
                # Format quarter display (e.g., '2025Q2' -> '2Q25')
                quarter_display = 'N/A'
                if latest_quarter != 'N/A':
                    # Extract year and quarter from format like '2025Q2'
                    if 'Q' in latest_quarter:
                        year_str = latest_quarter[:4]
                        quarter_num = latest_quarter[-1]
                        year_short = year_str[-2:]  # Get last 2 digits of year
                        quarter_display = f'{quarter_num}Q{year_short}'  # Format as '2Q25'
                
                valuation_rows.append({
                    'Item': f'Cash & Equivalent ({quarter_display})',
                    'RNAV Value (B VND)': None,  # Empty for balance sheet items
                    'Ownership (%)': None,
                    'RNAV to Company (B VND)': cash_equivalent
                })
                
                valuation_rows.append({
                    'Item': f'Short-term Investment ({quarter_display})',
                    'RNAV Value (B VND)': None,  # Empty for balance sheet items
                    'Ownership (%)': None,
                    'RNAV to Company (B VND)': short_term_investment
                })
                
                valuation_rows.append({
                    'Item': f'Short-term Debt ({quarter_display})',
                    'RNAV Value (B VND)': None,  # Empty for balance sheet items
                    'Ownership (%)': None,
                    'RNAV to Company (B VND)': -short_term_debt
                })
                
                valuation_rows.append({
                    'Item': f'Long-term Debt ({quarter_display})',
                    'RNAV Value (B VND)': None,  # Empty for balance sheet items
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
                
                # Calculate Total Equity (using RNAV to Company values)
                # Since debt values are already negative, we add them directly
                total_equity = total_rnav_to_company + cash_equivalent + short_term_investment + (-short_term_debt) + (-long_term_debt)
                
                valuation_rows.append({
                    'Item': 'TOTAL EQUITY',
                    'RNAV Value (B VND)': None,  # Empty for summary rows
                    'Ownership (%)': None,
                    'RNAV to Company (B VND)': total_equity
                })
                
                # Add Outstanding Shares row with quarter display
                valuation_rows.append({
                    'Item': f'Total Outstanding Shares ({quarter_display}) (millions)',
                    'RNAV Value (B VND)': None,  # Empty for summary rows
                    'Ownership (%)': None,
                    'RNAV to Company (B VND)': outstanding_shares
                })
                
                # Calculate and add RNAV per share
                rnav_per_share = (total_equity * 1e9 / (outstanding_shares * 1e6)) if outstanding_shares > 0 else 0
                valuation_rows.append({
                    'Item': 'RNAV/share (VND)',
                    'RNAV Value (B VND)': None,  # Empty for summary rows
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
                    # Calculate upside percentage if we have latest close price
                    if latest_close_price and latest_close_price > 0:
                        upside_pct = ((rnav_per_share / latest_close_price) - 1) * 100
                        st.metric("Upside (%)", f"{upside_pct:+.1f}%")
                    else:
                        st.metric("Upside (%)", "N/A")
                
                # Create formatted columns for display
                display_data = []
                for idx, row in valuation_df.iterrows():
                    item = row['Item']
                    rnav_val = row['RNAV Value (B VND)']
                    ownership = row['Ownership (%)']
                    rnav_to_company = row['RNAV to Company (B VND)']
                    
                    # Format RNAV Value
                    if pd.isna(rnav_val):
                        formatted_rnav = ''
                    elif 'Outstanding Shares' in str(item):
                        formatted_rnav = f'{rnav_val:,.0f}M'
                    elif 'RNAV/share' in str(item):
                        formatted_rnav = f'{rnav_val:,.0f}'
                    else:
                        formatted_rnav = f'{rnav_val:,.0f}B'
                    
                    # Format Ownership
                    if pd.isna(ownership):
                        formatted_ownership = ''
                    else:
                        formatted_ownership = f'{ownership:.1f}%'
                    
                    # Format RNAV to Company
                    if pd.isna(rnav_to_company):
                        formatted_rnav_to_company = ''
                    elif 'Outstanding Shares' in str(item):
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
                
                # Create display DataFrame
                display_df = pd.DataFrame(display_data)
                
                # Apply styling with bold for important rows
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
        
        # Add separator
        st.markdown("---")
        
        # Multiple Valuation Section
        st.subheader("Multiple Valuation")
        
        # Get selected ticker (already defined above)
        if selected_ticker and latest_close_price and outstanding_shares > 0:
            self.render_multiple_valuation(selected_ticker, latest_close_price, outstanding_shares)
        else:
            if not selected_ticker:
                st.info("Please select a company from the sidebar to view multiple valuation")
            elif not latest_close_price:
                st.info("Stock price data unavailable for multiple valuation")
            elif outstanding_shares <= 0:
                st.info("Outstanding shares data unavailable for multiple valuation")
        
        # Add separator
        st.markdown("---")
        
        # Historical Valuation Metrics Section
        st.subheader("Historical Valuation Metrics")
        
        # Reuse the selected ticker from above
        selected_ticker = st.session_state.get('selected_company', None)
        
        if selected_ticker:
            # Load valuation data
            valuation_data = self.load_valuation_data(selected_ticker)
            
            if valuation_data is not None and not valuation_data.empty:
                self.render_valuation_charts(valuation_data, selected_ticker)
            else:
                st.info(f"No valuation data available for {selected_ticker}")
        else:
            st.info("Please select a company from the sidebar to view valuation metrics")
    
    def load_valuation_data(self, ticker):
        """Load valuation data from Val_processed.csv for selected ticker"""
        try:
            # Load the CSV file
            csv_path = os.path.join('data', 'Val_processed.csv')
            if not os.path.exists(csv_path):
                st.error(f"Valuation data file not found: {csv_path}")
                return None
            
            # Read CSV
            df = pd.read_csv(csv_path)
            
            # Filter for selected ticker
            ticker_data = df[df['TICKER'] == ticker].copy()
            
            if ticker_data.empty:
                return None
            
            # Convert TRADE_DATE to datetime
            ticker_data['TRADE_DATE'] = pd.to_datetime(ticker_data['TRADE_DATE'])
            
            # Sort by date
            ticker_data = ticker_data.sort_values('TRADE_DATE')
            
            # Remove rows where all metrics are NaN
            metrics = ['P/E', 'P/B', 'P/S', 'EV/EBITDA']
            ticker_data = ticker_data.dropna(subset=metrics, how='all')
            
            return ticker_data
            
        except Exception as e:
            st.error(f"Error loading valuation data: {str(e)}")
            return None
    
    def render_valuation_charts(self, data, ticker):
        """Render valuation metric charts with standard deviation bands"""
        
        # Define metrics to plot
        metrics = [
            ('P/E', 'Price to Earnings'),
            ('P/B', 'Price to Book'),
            ('P/S', 'Price to Sales'),
            ('EV/EBITDA', 'EV/EBITDA')
        ]
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=[title for _, title in metrics],
            vertical_spacing=0.12,
            horizontal_spacing=0.1
        )
        
        # Define positions for subplots
        positions = [(1, 1), (1, 2), (2, 1), (2, 2)]
        
        for (metric, title), (row, col) in zip(metrics, positions):
            if metric not in data.columns:
                continue
            
            # Get metric data
            metric_data = data[['TRADE_DATE', metric]].dropna()
            
            if metric_data.empty:
                continue
            
            x = metric_data['TRADE_DATE']
            y = metric_data[metric]
            
            # Calculate statistics
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
        
        # Update layout
        fig.update_layout(
            height=700,
            title_text=f"Valuation Metrics for {ticker}",
            showlegend=True,
            hovermode='x unified'
        )
        
        # Update x and y axes
        fig.update_xaxes(title_text="Date", row=2, col=1)
        fig.update_xaxes(title_text="Date", row=2, col=2)
        
        # Display the figure
        st.plotly_chart(fig, use_container_width=True)
        
        # Add statistics summary
        st.subheader("Valuation Statistics")
        
        stats_data = []
        for metric, title in metrics:
            if metric in data.columns:
                metric_data = data[metric].dropna()
                if not metric_data.empty:
                    stats_data.append({
                        'Metric': title,
                        'Current': metric_data.iloc[-1] if len(metric_data) > 0 else np.nan,
                        'Mean': metric_data.mean(),
                        'Std Dev': metric_data.std(),
                        'Min': metric_data.min(),
                        'Max': metric_data.max(),
                        'Current vs Mean': f"{((metric_data.iloc[-1] / metric_data.mean() - 1) * 100):.1f}%" if len(metric_data) > 0 else "N/A"
                    })
        
        if stats_data:
            stats_df = pd.DataFrame(stats_data)
            st.dataframe(
                stats_df.style.format({
                    'Current': '{:.2f}',
                    'Mean': '{:.2f}',
                    'Std Dev': '{:.2f}',
                    'Min': '{:.2f}',
                    'Max': '{:.2f}'
                }),
                use_container_width=True
            )
    
    def render_stock_price_section(self, ticker):
        """Render current stock price only"""
        # Fetch current stock data
        with st.spinner(f"Loading stock data for {ticker}..."):
            df = get_cached_stock_data(ticker, days=30)  # Get 30 days of data
        
        if df is not None and not df.empty:
            # Get latest price data
            latest = df.iloc[-1]
            previous = df.iloc[-2] if len(df) > 1 else latest
            
            # Calculate changes
            price_change = latest['close'] - previous['close']
            price_change_pct = (price_change / previous['close'] * 100) if previous['close'] > 0 else 0
            
            # Display current price as a simple metric
            st.metric(
                f"Current Price ({ticker})",
                f"{latest['close']:,.0f} VND",
                f"{price_change:+,.0f} ({price_change_pct:+.2f}%)"
            )
            
            # Return the latest close price for upside calculation
            return latest['close']
        else:
            st.warning(f"Unable to fetch stock price data for {ticker}")
            return None
    
    def render_multiple_valuation(self, ticker, current_price, outstanding_shares):
        """Render multiple valuation metrics based on model forecast"""
        
        # Get current year dynamically
        current_year = datetime.now().year
        next_year = current_year + 1
        
        # Load forecast data from MongoDB
        forecast_doc = load_company_forecast(ticker)
        
        if not forecast_doc or 'forecast_data' not in forecast_doc:
            st.warning(f"No forecast data available for {ticker}. Please complete the Model Forecast first.")
            return
        
        # Extract forecast data
        forecast = forecast_doc.get('forecast_data', {})
        
        # Initialize metrics
        metrics = {
            f'{current_year} P/E': 'N/A',
            f'{next_year} P/E': 'N/A',
            f'{current_year} P/B': 'N/A',
            f'{next_year} P/B': 'N/A'
        }
        
        # Calculate P/E ratios
        for year in [current_year, next_year]:
            year_str = str(year)
            if year_str in forecast:
                year_data = forecast[year_str]
                
                # Get NPATMI - check both old format (direct) and new format (nested)
                npatmi = 0
                if 'NPATMI' in year_data:
                    # Old format: direct field in billions
                    npatmi = year_data.get('NPATMI', 0)
                elif 'pnl' in year_data and 'npatmi' in year_data['pnl']:
                    # New format: nested in pnl, value in VND
                    npatmi = year_data['pnl']['npatmi'] / 1e9  # Convert VND to billions
                
                if npatmi and outstanding_shares > 0:
                    # Calculate EPS (Earnings Per Share)
                    # NPATMI is in billions, outstanding_shares is in millions
                    # Convert both to actual values for calculation
                    eps = (npatmi * 1e9) / (outstanding_shares * 1e6)
                    
                    # Calculate P/E ratio
                    if eps > 0:
                        pe_ratio = current_price / eps
                        metrics[f'{year} P/E'] = f"{pe_ratio:.2f}x"
                
                # Get Total Equity - check both old format (direct) and new format (nested)
                total_equity = 0
                if 'Total_Equity' in year_data:
                    # Old format: direct field in billions
                    total_equity = year_data.get('Total_Equity', 0)
                elif 'balance_sheet' in year_data:
                    # New format: nested in balance_sheet
                    bs = year_data['balance_sheet']
                    if 'equity' in bs and isinstance(bs['equity'], dict):
                        # Nested structure with total_equity
                        total_equity = bs['equity'].get('total_equity', 0) / 1e9  # Convert VND to billions
                    elif 'total_equity' in bs:
                        # Direct field in balance_sheet
                        total_equity = bs.get('total_equity', 0) / 1e9  # Convert VND to billions
                
                if total_equity and outstanding_shares > 0:
                    # Calculate Book Value Per Share
                    # Total_Equity is in billions, outstanding_shares is in millions
                    bvps = (total_equity * 1e9) / (outstanding_shares * 1e6)
                    
                    # Calculate P/B ratio
                    if bvps > 0:
                        pb_ratio = current_price / bvps
                        metrics[f'{year} P/B'] = f"{pb_ratio:.2f}x"
        
        # Display metrics in columns
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(f"{current_year} P/E", metrics[f'{current_year} P/E'])
        
        with col2:
            st.metric(f"{next_year} P/E", metrics[f'{next_year} P/E'])
        
        with col3:
            st.metric(f"{current_year} P/B", metrics[f'{current_year} P/B'])
        
        with col4:
            st.metric(f"{next_year} P/B", metrics[f'{next_year} P/B'])
        
        # Add detailed breakdown in expander
        with st.expander("View Calculation Details"):
            details = []
            
            for year in [current_year, next_year]:
                year_str = str(year)
                if year_str in forecast:
                    year_data = forecast[year_str]
                    
                    # Get NPATMI - check both formats
                    npatmi = 0
                    if 'NPATMI' in year_data:
                        npatmi = year_data.get('NPATMI', 0)
                    elif 'pnl' in year_data and 'npatmi' in year_data['pnl']:
                        npatmi = year_data['pnl']['npatmi'] / 1e9  # Convert VND to billions
                    
                    # Get Total Equity - check both formats
                    total_equity = 0
                    if 'Total_Equity' in year_data:
                        total_equity = year_data.get('Total_Equity', 0)
                    elif 'balance_sheet' in year_data:
                        bs = year_data['balance_sheet']
                        if 'equity' in bs and isinstance(bs['equity'], dict):
                            total_equity = bs['equity'].get('total_equity', 0) / 1e9
                        elif 'total_equity' in bs:
                            total_equity = bs.get('total_equity', 0) / 1e9
                    
                    if npatmi:
                        eps = (npatmi * 1e9) / (outstanding_shares * 1e6) if outstanding_shares > 0 else 0
                        details.append({
                            'Year': year,
                            'Metric': 'EPS',
                            'Value': f"{eps:,.0f} VND",
                            'Formula': f"NPATMI ({npatmi:,.1f}B) / Shares ({outstanding_shares:,.0f}M)"
                        })
                    
                    if total_equity:
                        bvps = (total_equity * 1e9) / (outstanding_shares * 1e6) if outstanding_shares > 0 else 0
                        details.append({
                            'Year': year,
                            'Metric': 'BVPS',
                            'Value': f"{bvps:,.0f} VND",
                            'Formula': f"Equity ({total_equity:,.1f}B) / Shares ({outstanding_shares:,.0f}M)"
                        })
            
            if details:
                details_df = pd.DataFrame(details)
                st.dataframe(details_df, use_container_width=True, hide_index=True)
            
            st.info(f"Current Stock Price: {current_price:,.0f} VND")