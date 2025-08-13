#%%
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime


class HistoricalAnalysisTab:
    """Historical financial analysis tab with vectorized calculations"""
    
    def __init__(self, parent):
        self.parent = parent
    
    def render(self):
        """Render historical financial analysis - Simple P&L Table"""
        selected_ticker = st.session_state.get('selected_company', '')
        if selected_ticker:
            st.header(f"Historical Financial Analysis - {selected_ticker}")
        else:
            st.header("Historical Financial Analysis")
        
        # Load data if not already loaded
        if st.session_state.historical_data is None and st.session_state.selected_company:
            with st.spinner(f"Loading data for {st.session_state.selected_company}..."):
                data = self.parent.load_historical_data_from_csv(st.session_state.selected_company)
                if not data.empty:
                    st.session_state.historical_data = data
                else:
                    st.warning(f"No historical data found for {st.session_state.selected_company}")
                    return
        
        if st.session_state.historical_data is None:
            st.info("👈 Select a company to view historical data")
            return
        
        # Double-check we have the right ticker's data
        if not st.session_state.selected_company:
            st.info("👈 Select a company to view historical data")
            return
            
        df = st.session_state.historical_data
        
        # Get current year to filter out future data
        current_year = datetime.now().year
        
        # Filter to only show historical years (no future data)
        if df.index.dtype in ['int64', 'int32']:
            df = df[df.index <= current_year]
        
        if df.empty:
            st.warning("No historical data available for this company")
            return
        
        # Create P&L table with years as columns
        st.subheader("Historical Profit & Loss Statement")
        st.markdown("*All values in Billion VND*")
        
        # Define P&L line items and their corresponding column names in FA_A_processed.csv
        pnl_mapping = {
            'Net Revenue': 'Net_Revenue',
            'Cost of Goods Sold': 'COGS',
            'Gross Profit': 'Gross_Profit',
            'Operating Expenses': 'Operating_Expense',
            'EBITDA': 'EBITDA',
            'Depreciation & Amortization': 'D&A',
            'EBIT': 'EBIT',
            'Interest Income': 'Interest_Income',
            'Interest Expense': 'Interest_Expense',
            'Profit Before Tax': 'Profit_Before_Tax',
            'Tax': 'Corporate_Tax',
            'Profit After Tax': 'NPAT',
            'Minority Interest': 'Minority_Interest',
            'NPATMI': 'NPATMI'
        }
        
        # Vectorized P&L data creation
        years = sorted(df.index.tolist())
        pnl_data = self._create_pnl_data_vectorized(df, pnl_mapping, years)
        
        # Create DataFrame with years as columns
        pnl_df = pd.DataFrame(pnl_data, index=years).T
        
        # Vectorized margin calculations
        margin_df = self._calculate_margins_vectorized(pnl_df, years)
        
        # Display P&L table
        self._display_pnl_table(pnl_df)
        
        # Display margins
        if not margin_df.empty:
            self._display_margins(margin_df)
        
        # Display growth rates
        self._display_growth_rates(pnl_df, years)
    
    def _create_pnl_data_vectorized(self, df, pnl_mapping, years):
        """Vectorized P&L data creation"""
        pnl_data = {}
        
        # Convert all relevant columns to billions at once
        available_columns = [col for col in pnl_mapping.values() if col in df.columns]
        if available_columns:
            # Vectorized conversion to billions
            df_billions = df[available_columns] / 1e9
            df_billions = df_billions.fillna(0)
            
            # Map display names to data
            for display_name, column_name in pnl_mapping.items():
                if column_name in df_billions.columns:
                    pnl_data[display_name] = df_billions[column_name].reindex(years, fill_value=0).tolist()
                else:
                    pnl_data[display_name] = [0] * len(years)
        else:
            # Fallback if no columns available
            for display_name in pnl_mapping.keys():
                pnl_data[display_name] = [0] * len(years)
        
        return pnl_data
    
    def _calculate_margins_vectorized(self, pnl_df, years):
        """Vectorized margin calculations"""
        if 'Net Revenue' not in pnl_df.index:
            return pd.DataFrame()
        
        # Get revenue row as Series
        revenue = pnl_df.loc['Net Revenue']
        
        # Calculate margins only where revenue is not zero
        mask = revenue != 0
        
        margin_data = {}
        
        if 'Gross Profit' in pnl_df.index:
            gross_margins = np.where(mask, (pnl_df.loc['Gross Profit'] / revenue * 100), 0)
            margin_data['Gross Profit Margin %'] = gross_margins
        
        if 'EBITDA' in pnl_df.index:
            ebitda_margins = np.where(mask, (pnl_df.loc['EBITDA'] / revenue * 100), 0)
            margin_data['EBITDA Margin %'] = ebitda_margins
        
        if 'NPATMI' in pnl_df.index:
            net_margins = np.where(mask, (pnl_df.loc['NPATMI'] / revenue * 100), 0)
            margin_data['Net Margin %'] = net_margins
        
        if margin_data:
            return pd.DataFrame(margin_data, index=years)
        return pd.DataFrame()
    
    def _display_pnl_table(self, pnl_df):
        """Display formatted P&L table"""
        # Format the P&L dataframe for display
        def format_pnl_value(val):
            if pd.isna(val) or val == 0:
                return "-"
            elif abs(val) < 1:
                return f"{val:.2f}"
            else:
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
    
    def _display_margins(self, margin_df):
        """Display margin analysis"""
        st.subheader("Profitability Margins")
        
        # Format margin percentages
        def format_margin(val):
            if pd.isna(val) or val == 0:
                return "-"
            return f"{val:.1f}%"
        
        styled_margins = margin_df.T.style.format(format_margin)
        st.dataframe(styled_margins, use_container_width=True)
    
    def _display_growth_rates(self, pnl_df, years):
        """Display growth rates with vectorized calculations"""
        st.subheader("Year-over-Year Growth Rates")
        
        metrics = ['Net Revenue', 'Gross Profit', 'EBITDA', 'NPATMI']
        available_metrics = [m for m in metrics if m in pnl_df.index]
        
        if not available_metrics:
            st.info("No metrics available for growth calculation")
            return
        
        # Vectorized growth calculation
        growth_data = {}
        
        for metric in available_metrics:
            metric_data = pnl_df.loc[metric]
            
            # Calculate growth rates using vectorized operations
            growth_rates = []
            for i in range(len(years)):
                if i == 0:
                    growth_rates.append(None)  # No growth rate for first year
                else:
                    prev_val = metric_data.iloc[i-1]
                    curr_val = metric_data.iloc[i]
                    
                    if prev_val != 0 and not pd.isna(prev_val) and not pd.isna(curr_val):
                        growth = ((curr_val - prev_val) / abs(prev_val)) * 100
                        growth_rates.append(growth)
                    else:
                        growth_rates.append(None)
            
            growth_data[metric] = growth_rates
        
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