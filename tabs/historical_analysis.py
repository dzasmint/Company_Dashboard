import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import DC database connection
from utils.dc_database_connection import get_dc_database, load_quarterly_data, load_annual_data


class HistoricalAnalysisTab:
    """Historical Analysis Tab with Annual and Quarterly views"""
    
    def __init__(self, parent=None):
        """Initialize the Historical Analysis tab
        
        Args:
            parent: Parent model instance (RealEstateFinancialModel)
        """
        self.parent = parent
        
    def render(self):
        """Render historical financial analysis with Annual/Quarterly tabs"""
        
        # Check if company is selected
        if not st.session_state.get('selected_company'):
            st.info("👈 Select a company to view historical data")
            return
        
        # Create tabs for Annual and Quarterly views
        annual_tab, quarterly_tab = st.tabs(["Annual", "Quarterly"])
        
        with annual_tab:
            self.render_annual_view()
            
        with quarterly_tab:
            self.render_quarterly_view()
    
    @st.cache_data(ttl=600)  # Cache for 10 minutes
    def load_annual_data(_self, ticker):
        """Load annual financial data from Dragon Capital database."""
        # Get DC database connection
        db = get_dc_database()
        
        if not db.is_connected():
            st.error("❌ Dragon Capital database not connected. Please configure DC_DB_STRING in secrets or environment.")
            st.info("Set DC_DB_STRING with: Server=host;Database=db;User Id=user;Password=pass")
            return pd.DataFrame()
        
        try:
            # Load from database
            st.info("📡 Loading annual data from Dragon Capital database...")
            df = db.get_annual_financials(ticker)
            
            if df.empty:
                st.warning(f"No annual data found for {ticker} in FA_Annual table")
                return pd.DataFrame()
            
            # Pivot data to create time series (KEYCODE as columns, DATE as rows)
            pivot_data = df.pivot_table(
                index='DATE',
                columns='KEYCODE',
                values='VALUE',
                aggfunc='first'
            )
            
            # Sort by date
            pivot_data.sort_index(inplace=True)
            
            st.success(f"✅ Loaded {len(pivot_data)} years of annual data from DC database")
            
            return pivot_data
            
        except Exception as e:
            st.error(f"❌ Error loading annual data from database: {str(e)}")
            return pd.DataFrame()
    
    @st.cache_data(ttl=600)  # Cache for 10 minutes
    def load_quarterly_data(_self, ticker):
        """Load quarterly financial data from Dragon Capital database."""
        # Get DC database connection
        db = get_dc_database()
        
        if not db.is_connected():
            st.error("❌ Dragon Capital database not connected. Please configure DC_DB_STRING in secrets or environment.")
            st.info("Set DC_DB_STRING with: Server=host;Database=db;User Id=user;Password=pass")
            return pd.DataFrame()
        
        try:
            # Load from database
            st.info("📡 Loading quarterly data from Dragon Capital database...")
            df = db.get_quarterly_financials(ticker)
            
            if df.empty:
                st.warning(f"No quarterly data found for {ticker} in FA_Quarterly table")
                return pd.DataFrame()
            
            # Pivot data to create time series with quarters as columns
            pivot_data = df.pivot_table(
                index='KEYCODE',
                columns='DATE',
                values='VALUE',
                aggfunc='first'
            )
            
            # Sort columns (quarters) chronologically
            sorted_columns = sorted(pivot_data.columns, 
                                  key=lambda x: (int(x[:4]), int(x[5])))
            pivot_data = pivot_data[sorted_columns]
            
            st.success(f"✅ Loaded {len(pivot_data.columns)} quarters of data from DC database")
            
            return pivot_data
            
        except Exception as e:
            st.error(f"❌ Error loading quarterly data from database: {str(e)}")
            return pd.DataFrame()
    
    def render_annual_view(self):
        """Render annual financial analysis - P&L, Balance Sheet, Cash Flow"""
        
        # Load annual data
        ticker = st.session_state.selected_company
        df = self.load_annual_data(ticker)
        
        if df.empty:
            st.warning("No annual data available for this company")
            return
        
        # Get current year to filter out future data
        current_year = datetime.now().year
        
        # Filter to only show historical years (no future data)
        if df.index.dtype in ['int64', 'int32']:
            df = df[df.index <= current_year]
        
        if df.empty:
            st.warning("No historical annual data available")
            return
        
        # Create P&L table
        st.subheader("Annual Income Statement")
        st.markdown("*All values in Billion VND*")
        
        # Define P&L line items mapping
        pnl_mapping = {
            'Net Revenue': 'Net_Revenue',
            'Cost of Goods Sold': 'COGS',
            'Gross Profit': 'Gross_Profit',
            'SG&A Expenses': 'GA_Expense',
            'EBITDA': 'EBITDA',
            'Depreciation & Amortization': 'Dep_Expense',
            'EBIT': 'EBIT',
            'Financial Income': 'Financial_Income',
            'Financial Expense': 'Financial_Expense',
            'Profit Before Tax': 'PBT',
            'Tax Expense': 'Tax',
            'Profit After Tax': 'NPAT',
            'Minority Interest': 'Minority_Interest_In_Earning',
            'NPATMI': 'NPATMI'
        }
        
        # Create the P&L dataframe
        pnl_data = {}
        years = sorted(df.index.tolist())
        
        for display_name, column_name in pnl_mapping.items():
            row_data = []
            for year in years:
                if column_name in df.columns:
                    value = df.loc[year, column_name] if year in df.index else 0
                    # Convert to billions
                    row_data.append(value / 1e9 if pd.notna(value) else 0)
                else:
                    row_data.append(0)
            pnl_data[display_name] = row_data
        
        # Create DataFrame with years as columns
        pnl_df = pd.DataFrame(pnl_data, index=years).T
        
        # Format the P&L dataframe for display
        def format_pnl_value(val):
            if pd.isna(val) or val == 0:
                return "-"
            return f"{val:,.1f}"
        
        # Apply formatting
        styled_pnl = pnl_df.style.format(format_pnl_value)
        
        # Highlight important rows
        def highlight_rows(row):
            if row.name in ['Net Revenue', 'Gross Profit', 'EBITDA', 'NPATMI']:
                return ['background-color: #f0f2f6'] * len(row)
            return [''] * len(row)
        
        styled_pnl = styled_pnl.apply(highlight_rows, axis=1)
        
        # Display the P&L table
        st.dataframe(styled_pnl, use_container_width=True, height=500)
        
        # Add Balance Sheet section
        st.subheader("Annual Balance Sheet")
        st.markdown("*All values in Billion VND*")
        
        # Define Balance Sheet line items (order matters for display)
        bs_mapping = {
            'Cash & Equivalents': 'Cash_Equivalent',
            'Account Receivable': 'Account_Receivable',
            'Inventory': 'Inventory',
            'Total Current Assets': 'Current_Asset',
            'Tangible Fixed Assets': 'Tangible_Fixed_Asset',
            'Total Assets': 'Total_Asset',
            'Account Payable': 'Account_Payable',
            'Short-term Debt': 'ST_Debt',
            'Current Liabilities': 'Current_Liabilities',
            'Long-term Debt': 'LT_Debt',
            'Total Liabilities': 'Total_Liabilities',
            'Retained Earnings': 'Retain_Earning',
            'Minority Interest': 'Minority_Interest',
            'Total Equity': 'TOTAL_Equity'
        }
        
        # Create Balance Sheet dataframe
        bs_data = {}
        for display_name, column_name in bs_mapping.items():
            row_data = []
            for year in years:
                if column_name in df.columns:
                    value = df.loc[year, column_name] if year in df.index else 0
                    row_data.append(value / 1e9 if pd.notna(value) else 0)
                else:
                    row_data.append(0)
            bs_data[display_name] = row_data
        
        bs_df = pd.DataFrame(bs_data, index=years).T
        styled_bs = bs_df.style.format(format_pnl_value)
        
        # Highlight important rows
        def highlight_bs_rows(row):
            if row.name == 'Total Assets':
                return ['background-color: #e8f4f8; font-weight: bold'] * len(row)
            elif row.name == 'Total Liabilities':
                return ['background-color: #ffe8e8; font-weight: bold'] * len(row)
            elif row.name == 'Total Equity':
                return ['background-color: #e8f8e8; font-weight: bold'] * len(row)
            elif row.name in ['Total Current Assets', 'Current Liabilities', 'Retained Earnings', 'Minority Interest']:
                return ['background-color: #f0f2f6'] * len(row)
            return [''] * len(row)
        
        styled_bs = styled_bs.apply(highlight_bs_rows, axis=1)
        st.dataframe(styled_bs, use_container_width=True, height=400)
        
        # Add Cash Flow section
        st.subheader("Annual Cash Flow Statement")
        st.markdown("*All values in Billion VND*")
        
        # Define Cash Flow line items
        cf_mapping = {
            'Operating Cash Flow': 'Operating_CF',
            'Capital Expenditure': 'Capex',
            'Free Cash Flow': 'FCF',
            'Investing Cash Flow': 'Inv_CF',
            'Financing Cash Flow': 'Fin_CF'
        }
        
        # Create Cash Flow dataframe
        cf_data = {}
        for display_name, column_name in cf_mapping.items():
            row_data = []
            for year in years:
                if column_name in df.columns:
                    value = df.loc[year, column_name] if year in df.index else 0
                    row_data.append(value / 1e9 if pd.notna(value) else 0)
                else:
                    row_data.append(0)
            cf_data[display_name] = row_data
        
        cf_df = pd.DataFrame(cf_data, index=years).T
        styled_cf = cf_df.style.format(format_pnl_value)
        
        # Highlight important rows
        def highlight_cf_rows(row):
            if row.name in ['Operating Cash Flow', 'Free Cash Flow']:
                return ['background-color: #f0f2f6'] * len(row)
            return [''] * len(row)
        
        styled_cf = styled_cf.apply(highlight_cf_rows, axis=1)
        st.dataframe(styled_cf, use_container_width=True, height=250)
        
        # Add margin analysis
        st.subheader("Profitability Margins")
        margin_data = {}
        for year in years:
            if pnl_df.loc['Net Revenue', year] != 0:
                margin_data[year] = {
                    'Gross Margin %': (pnl_df.loc['Gross Profit', year] / pnl_df.loc['Net Revenue', year] * 100) if pnl_df.loc['Net Revenue', year] != 0 else 0,
                    'EBITDA Margin %': (pnl_df.loc['EBITDA', year] / pnl_df.loc['Net Revenue', year] * 100) if pnl_df.loc['Net Revenue', year] != 0 else 0,
                    'Net Margin %': (pnl_df.loc['NPATMI', year] / pnl_df.loc['Net Revenue', year] * 100) if pnl_df.loc['Net Revenue', year] != 0 else 0
                }
        
        if margin_data:
            margin_df = pd.DataFrame(margin_data)
            styled_margins = margin_df.style.format(lambda x: f"{x:.1f}%")
            st.dataframe(styled_margins, use_container_width=True)
        
        # Add year-over-year growth rates
        st.subheader("Year-over-Year Growth Rates")
        growth_data = {}
        
        for metric in ['Net Revenue', 'Gross Profit', 'EBITDA', 'NPATMI']:
            growth_row = []
            for i, year in enumerate(years):
                if i == 0:
                    growth_row.append(None)  # No growth rate for first year
                else:
                    prev_val = pnl_df.loc[metric, years[i-1]]
                    curr_val = pnl_df.loc[metric, year]
                    if prev_val != 0 and not pd.isna(prev_val) and not pd.isna(curr_val):
                        growth = ((curr_val - prev_val) / abs(prev_val)) * 100
                        growth_row.append(growth)
                    else:
                        growth_row.append(None)
            growth_data[metric] = growth_row
        
        growth_df = pd.DataFrame(growth_data, index=years).T
        
        # Format growth rates
        def format_growth(val):
            if pd.isna(val) or val is None:
                return "-"
            color = 'green' if val > 0 else 'red' if val < 0 else 'black'
            return f"<span style='color: {color}'>{val:+.1f}%</span>"
        
        # Display growth rates with HTML formatting
        growth_html = growth_df.to_html(escape=False, 
                                       float_format=lambda x: format_growth(x) if not pd.isna(x) else "-")
        st.markdown(growth_html, unsafe_allow_html=True)
    
    def render_quarterly_view(self):
        """Render quarterly financial analysis"""
        
        # Load quarterly data
        ticker = st.session_state.selected_company
        df = self.load_quarterly_data(ticker)
        
        if df.empty:
            st.warning("No quarterly data available for this company")
            return
        
        # Get current quarter
        current_date = datetime.now()
        current_year = current_date.year
        current_quarter = (current_date.month - 1) // 3 + 1
        current_quarter_str = f"{current_year}Q{current_quarter}"
        
        # Filter to show only historical quarters (no future data)
        historical_quarters = []
        for col in df.columns:
            try:
                year = int(col[:4])
                quarter = int(col[5])
                if year < current_year or (year == current_year and quarter <= current_quarter):
                    historical_quarters.append(col)
            except:
                continue
        
        # Limit to last 12 quarters (3 years)
        if len(historical_quarters) > 12:
            historical_quarters = historical_quarters[-12:]
        
        df = df[historical_quarters]
        
        if df.empty:
            st.warning("No historical quarterly data available")
            return
        
        # Create Quarterly P&L table
        st.subheader("Quarterly Income Statement")
        st.markdown("*All values in Billion VND*")
        
        # Define P&L line items mapping (using KEYCODE as index)
        pnl_keycodes = [
            'Net_Revenue', 'COGS', 'Gross_Profit', 'GA_Expense',
            'EBITDA', 'Dep_Expense', 'EBIT',
            'Financial_Income', 'Financial_Expense',
            'PBT', 'Tax', 'NPAT', 'Minority_Interest_In_Earning', 'NPATMI'
        ]
        
        # Display names for the keycodes
        pnl_display_names = {
            'Net_Revenue': 'Net Revenue',
            'COGS': 'Cost of Goods Sold',
            'Gross_Profit': 'Gross Profit',
            'GA_Expense': 'SG&A Expenses',
            'EBITDA': 'EBITDA',
            'Dep_Expense': 'Depreciation & Amortization',
            'EBIT': 'EBIT',
            'Financial_Income': 'Financial Income',
            'Financial_Expense': 'Financial Expense',
            'PBT': 'Profit Before Tax',
            'Tax': 'Tax Expense',
            'NPAT': 'Profit After Tax',
            'Minority_Interest_In_Earning': 'Minority Interest',
            'NPATMI': 'NPATMI'
        }
        
        # Filter and create P&L dataframe
        pnl_data = {}
        for keycode in pnl_keycodes:
            if keycode in df.index:
                # Convert to billions
                row_values = df.loc[keycode] / 1e9
                pnl_data[pnl_display_names.get(keycode, keycode)] = row_values
        
        pnl_df = pd.DataFrame(pnl_data).T
        
        # Format for display
        def format_quarterly_value(val):
            if pd.isna(val) or val == 0:
                return "-"
            return f"{val:,.1f}"
        
        styled_pnl = pnl_df.style.format(format_quarterly_value)
        
        # Highlight important rows
        def highlight_rows(row):
            if row.name in ['Net Revenue', 'Gross Profit', 'EBITDA', 'NPATMI']:
                return ['background-color: #f0f2f6'] * len(row)
            return [''] * len(row)
        
        styled_pnl = styled_pnl.apply(highlight_rows, axis=1)
        st.dataframe(styled_pnl, use_container_width=True, height=500)
        
        # Add Quarterly Balance Sheet
        st.subheader("Quarterly Balance Sheet")
        st.markdown("*All values in Billion VND*")
        
        # Define Balance Sheet keycodes (order matters for display)
        bs_keycodes = [
            'Cash_Equivalent', 'Account_Receivable', 'Inventory',
            'Current_Asset', 'Tangible_Fixed_Asset', 'Total_Asset',
            'Account_Payable', 'ST_Debt', 'Current_Liabilities',
            'LT_Debt', 'Total_Liabilities', 'Retain_Earning', 
            'Minority_Interest', 'TOTAL_Equity'
        ]
        
        bs_display_names = {
            'Cash_Equivalent': 'Cash & Equivalents',
            'Account_Receivable': 'Account Receivable',
            'Inventory': 'Inventory',
            'Current_Asset': 'Total Current Assets',
            'Tangible_Fixed_Asset': 'Tangible Fixed Assets',
            'Total_Asset': 'Total Assets',
            'Account_Payable': 'Account Payable',
            'ST_Debt': 'Short-term Debt',
            'Current_Liabilities': 'Current Liabilities',
            'LT_Debt': 'Long-term Debt',
            'Total_Liabilities': 'Total Liabilities',
            'Retain_Earning': 'Retained Earnings',
            'Minority_Interest': 'Minority Interest',
            'TOTAL_Equity': 'Total Equity'
        }
        
        # Filter and create Balance Sheet dataframe
        bs_data = {}
        for keycode in bs_keycodes:
            if keycode in df.index:
                row_values = df.loc[keycode] / 1e9
                bs_data[bs_display_names.get(keycode, keycode)] = row_values
        
        if bs_data:
            bs_df = pd.DataFrame(bs_data).T
            styled_bs = bs_df.style.format(format_quarterly_value)
            
            def highlight_bs_rows(row):
                if row.name == 'Total Assets':
                    return ['background-color: #e8f4f8; font-weight: bold'] * len(row)
                elif row.name == 'Total Liabilities':
                    return ['background-color: #ffe8e8; font-weight: bold'] * len(row)
                elif row.name == 'Total Equity':
                    return ['background-color: #e8f8e8; font-weight: bold'] * len(row)
                elif row.name in ['Total Current Assets', 'Current Liabilities', 'Retained Earnings', 'Minority Interest']:
                    return ['background-color: #f0f2f6'] * len(row)
                return [''] * len(row)
            
            styled_bs = styled_bs.apply(highlight_bs_rows, axis=1)
            st.dataframe(styled_bs, use_container_width=True, height=400)
        
        # Add Quarterly Cash Flow
        st.subheader("Quarterly Cash Flow Statement")
        st.markdown("*All values in Billion VND*")
        
        # Define Cash Flow keycodes
        cf_keycodes = ['Operating_CF', 'Capex', 'FCF', 'Inv_CF', 'Fin_CF']
        
        cf_display_names = {
            'Operating_CF': 'Operating Cash Flow',
            'Capex': 'Capital Expenditure',
            'FCF': 'Free Cash Flow',
            'Inv_CF': 'Investing Cash Flow',
            'Fin_CF': 'Financing Cash Flow'
        }
        
        # Filter and create Cash Flow dataframe
        cf_data = {}
        for keycode in cf_keycodes:
            if keycode in df.index:
                row_values = df.loc[keycode] / 1e9
                cf_data[cf_display_names.get(keycode, keycode)] = row_values
        
        if cf_data:
            cf_df = pd.DataFrame(cf_data).T
            styled_cf = cf_df.style.format(format_quarterly_value)
            
            def highlight_cf_rows(row):
                if row.name in ['Operating Cash Flow', 'Free Cash Flow']:
                    return ['background-color: #f0f2f6'] * len(row)
                return [''] * len(row)
            
            styled_cf = styled_cf.apply(highlight_cf_rows, axis=1)
            st.dataframe(styled_cf, use_container_width=True, height=250)
        
        # Add Quarter-over-Quarter growth rates
        st.subheader("Quarter-over-Quarter Growth Rates")
        
        if 'Net Revenue' in pnl_df.index:
            growth_metrics = ['Net Revenue', 'Gross Profit', 'EBITDA', 'NPATMI']
            growth_data = {}
            
            for metric in growth_metrics:
                if metric in pnl_df.index:
                    growth_row = []
                    values = pnl_df.loc[metric]
                    for i in range(len(values)):
                        if i == 0:
                            growth_row.append(None)
                        else:
                            prev_val = values.iloc[i-1]
                            curr_val = values.iloc[i]
                            if prev_val != 0 and not pd.isna(prev_val) and not pd.isna(curr_val):
                                growth = ((curr_val - prev_val) / abs(prev_val)) * 100
                                growth_row.append(growth)
                            else:
                                growth_row.append(None)
                    growth_data[metric] = growth_row
            
            if growth_data:
                growth_df = pd.DataFrame(growth_data, index=pnl_df.columns).T
                
                # Format growth rates
                def format_growth(val):
                    if pd.isna(val) or val is None:
                        return "-"
                    color = 'green' if val > 0 else 'red' if val < 0 else 'black'
                    return f"<span style='color: {color}'>{val:+.1f}%</span>"
                
                # Display growth rates with HTML formatting
                growth_html = growth_df.to_html(escape=False, 
                                               float_format=lambda x: format_growth(x) if not pd.isna(x) else "-")
                st.markdown(growth_html, unsafe_allow_html=True)
        
        # Add TTM (Trailing Twelve Months) metrics
        st.subheader("Trailing Twelve Months (TTM) Metrics")
        st.markdown("*Sum of last 4 quarters for flow items*")
        
        # Calculate TTM for flow items (sum of last 4 quarters)
        if len(pnl_df.columns) >= 4:
            ttm_metrics = ['Net Revenue', 'EBITDA', 'NPATMI']
            ttm_data = {}
            
            for metric in ttm_metrics:
                if metric in pnl_df.index:
                    # Sum last 4 quarters
                    ttm_value = pnl_df.loc[metric].iloc[-4:].sum()
                    ttm_data[metric] = ttm_value
            
            if ttm_data:
                ttm_df = pd.DataFrame([ttm_data], index=['TTM'])
                styled_ttm = ttm_df.style.format(lambda x: f"{x:,.1f}B VND")
                st.dataframe(styled_ttm, use_container_width=True)