import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
import os
from utils.mongodb_utils import load_assumptions_from_mongodb
from utils.model_forecast_project_breakdown_utils import (
    render_revenue_forecast_tab,
    render_cogs_forecast_tab,
    render_gross_profit_tab,
    render_sga_tab,
    render_pbt_tab,
    render_pat_tab,
    render_patmi_tab,
    render_minority_interest_tab,
    load_project_financial_data
)
from utils.model_forecast_cashflow_utils import (
    create_detail_cashflow_rows,
    create_consolidated_cashflow_rows,
    render_detail_cf_tab,
    render_consolidated_cf_tab,
    prepare_cashflow_data
)
from utils.model_forecast_save_to_db import render_save_section
from utils.model_forecast_bs_utils import (
    render_detail_bs_tab, 
    render_consolidated_bs_tab,
    prepare_balance_sheet_data
)
from utils.model_forecast_valuation_utils import render_valuation_analysis


class ModelForecastTab:
    """Model Forecast Tab for Revenue & COGS Forecasting"""
    
    def __init__(self, parent_model=None):
        """Initialize the Model Forecast tab"""
        self.parent_model = parent_model
    
    def load_historical_data_from_csv(self, ticker):
        """Load historical data from FA_A_processed.parquet"""
        try:
            fa_path = 'data/FA_A_processed.parquet'
            if os.path.exists(fa_path):
                df = pd.read_parquet(fa_path)
                # Filter for selected ticker
                ticker_data = df[df['TICKER'] == ticker].copy()
                if not ticker_data.empty:
                    # Pivot data to create time series
                    pivot_data = ticker_data.pivot_table(
                        index='DATE',
                        columns='KEYCODE',
                        values='VALUE',
                        aggfunc='first'
                    )
                    pivot_data.sort_index(inplace=True)
                    return pivot_data
        except Exception as e:
            st.error(f"Error loading historical data: {str(e)}")
        return pd.DataFrame()
    
    def render(self):
        """Main render method - entry point for the tab"""
        self.render_revenue_forecast()
    
    def _convert_assumptions_to_dict(self, assumptions_list):
        """Convert assumptions list format to dictionary format"""
        if not assumptions_list:
            return {}
        
        result = {
            'revenue_streams': [],
            'wacc': 0.0,  # Default to 0 to show missing assumptions
            'debt_financing_pct': 0.0,  # Default to 0 to show missing assumptions
            'tax_rate': 0.0,  # Default to 0 to show missing assumptions
            'cost_of_debts': 0.0,  # Default to 0 to show missing assumptions
            'custom_assumptions': []
        }
    
        # Group business segments by name
        business_segments = {}
    
        for assumption in assumptions_list:
            category = assumption.get('Category', '')
            item = assumption.get('Item', '')
            value = assumption.get('Value', 0)
            type_field = assumption.get('Type', '')
        
            if category == 'Business Segment':
                # Group by segment name
                if item not in business_segments:
                    business_segments[item] = {
                        'segment_name': item,
                        'revenue_growth': 0.0,
                        'gross_margin': 0.0,
                        'sga_percentage': 0.0,
                        'base_year_revenue': 0
                    }
            
                # Map Type to the appropriate field
                if type_field == 'Revenue Growth':
                    business_segments[item]['revenue_growth'] = value / 100  # Convert from percentage
                elif type_field == 'Gross Margin':
                    business_segments[item]['gross_margin'] = value / 100
                elif type_field == 'SG&A % of Revenue':
                    business_segments[item]['sga_percentage'] = value / 100
                elif type_field == 'Base Year Revenue':
                    business_segments[item]['base_year_revenue'] = value
        
            elif category == 'Financial':
                # Map financial assumptions
                if item == 'WACC':
                    result['wacc'] = value / 100
                elif item == 'Debt Financing %':
                    result['debt_financing_pct'] = value / 100
                elif item == 'Tax Rate':
                    result['tax_rate'] = value / 100
                elif item == 'Cost of Debts':
                    result['cost_of_debts'] = value / 100
            else:
                # Store other assumptions
                result['custom_assumptions'].append(assumption)
    
        # Convert business segments dictionary to list
        result['revenue_streams'] = list(business_segments.values())
    
        return result

    def render_revenue_forecast(self):
        """Render comprehensive revenue forecast including projects and other revenue streams"""
        #st.header("Revenue & COGS Forecast")
    
        # Get selected ticker
        selected_ticker = st.session_state.get('selected_company', None)
        if not selected_ticker:
            st.info("Please select a company from the sidebar")
            return
    
        # Import MongoDB utilities
        from utils.mongodb_utils import load_assumptions_from_mongodb
    
        # Load assumptions from MongoDB - use the same method as Assumptions tab
        assumptions_list = load_assumptions_from_mongodb(selected_ticker)
    
        # Convert assumptions list to the expected format for revenue forecast
        company_assumptions = self._convert_assumptions_to_dict(assumptions_list) if assumptions_list else {}
        custom_assumptions = company_assumptions.get('custom_assumptions', [])
        
        # Check if critical financial assumptions are missing and show warnings
        tax_rate = company_assumptions.get('tax_rate', 0.0)
        wacc = company_assumptions.get('wacc', 0.0)
        cost_of_debts = company_assumptions.get('cost_of_debts', 0.0)
        debt_financing_pct = company_assumptions.get('debt_financing_pct', 0.0)
        
        missing_assumptions = []
        if tax_rate == 0.0:
            missing_assumptions.append("Tax Rate")
        if wacc == 0.0:
            missing_assumptions.append("WACC")
        if cost_of_debts == 0.0:
            missing_assumptions.append("Cost of Debts")
        if debt_financing_pct == 0.0:
            missing_assumptions.append("Debt Financing %")
            
        if missing_assumptions:
            st.warning(f"⚠️ Missing assumptions: {', '.join(missing_assumptions)}. Please save these in the Assumptions tab first.")
    
        # Initialize session state for base year revenues (ticker-specific)
        revenue_key = f'base_year_revenues_{selected_ticker}'
        if revenue_key not in st.session_state:
            st.session_state[revenue_key] = {}
    
        # For backward compatibility, sync with general base_year_revenues
        st.session_state.base_year_revenues = st.session_state[revenue_key]
    
        # Extract business segments from revenue_streams and load base year revenue from assumptions
        revenue_streams = company_assumptions.get('revenue_streams', [])
        business_segments = []
        segment_metrics = {}
    
        # Clear old segments that no longer exist in assumptions
        current_segments = []
        for stream in revenue_streams:
            segment_name = stream.get('segment_name', '')
            if segment_name and 'real estate' not in segment_name.lower():
                current_segments.append(segment_name)
    
        # Remove segments from base_year_revenues that are no longer in assumptions
        segments_to_remove = []
        for segment_name in st.session_state.base_year_revenues.keys():
            if segment_name not in current_segments:
                segments_to_remove.append(segment_name)
    
        for segment_name in segments_to_remove:
            del st.session_state.base_year_revenues[segment_name]
    
        # Load base year revenues directly from assumptions (silently in background)
        for stream in revenue_streams:
            segment_name = stream.get('segment_name', '')
            if segment_name and 'real estate' not in segment_name.lower():
                business_segments.append(segment_name)
            
                # Get base year revenue from assumptions (if stored there)
                base_year_revenue = stream.get('base_year_revenue', 0)
            
                # If base year revenue is 0, check if it was saved in assumptions
                if base_year_revenue == 0:
                    # Look for Base Year Revenue in the assumptions list
                    for assumption in assumptions_list or []:
                        if (assumption.get('Category') == 'Business Segment' and 
                            assumption.get('Item') == segment_name and 
                            assumption.get('Type') == 'Base Year Revenue'):
                            base_year_revenue = assumption.get('Value', 0)
                            break
            
                # Store in session state for use in tables
                st.session_state.base_year_revenues[segment_name] = base_year_revenue
            
                segment_metrics[segment_name] = {
                    'revenue_growth': stream.get('revenue_growth', 0.0),
                    'gross_margin': stream.get('gross_margin', 0.0),
                    'sga_percentage': stream.get('sga_percentage', 0.0),
                    'base_year_revenue': base_year_revenue
                }
    
        # If no business segments, show a simple message
        if not business_segments:
            st.info("No business segments defined. Add business segment assumptions in the Assumptions tab.")
        
        # Calculate forecast years directly
        current_year = datetime.now().year
        forecast_years = st.session_state.forecast_years
        years = list(range(current_year, current_year + forecast_years + 1))
    
        # Get historical data for 2024
        # First ensure historical data is loaded
        if st.session_state.get('historical_data') is None and selected_ticker:
            with st.spinner(f"Loading historical data for {selected_ticker}..."):
                historical_data = self.load_historical_data_from_csv(selected_ticker)
                if not historical_data.empty:
                    st.session_state.historical_data = historical_data
                    st.toast(f"✅ Loaded historical data with {len(historical_data)} records")
                else:
                    st.warning(f"No historical data found for {selected_ticker}")
    
        historical_data = st.session_state.get('historical_data')
    
        # Dynamically determine the latest historical year
        current_year = datetime.now().year
        base_year = st.session_state.get('base_year', current_year - 1)  # Default to current year - 1 if not set
        hist_values = {}
    
        if historical_data is not None and not historical_data.empty:
            # Find the latest year in the historical data
            # Convert index to integers and find the maximum
            try:
                years_in_data = [int(idx) for idx in historical_data.index if str(idx).isdigit()]
                if years_in_data:
                    base_year = max(years_in_data)
                else:
                    # Fallback: try to convert directly
                    base_year = int(max(historical_data.index))
            except:
                # If all else fails, default to current year - 1
                base_year = datetime.now().year - 1
        
            # Store base_year in session state for use throughout the app
            st.session_state.base_year = base_year
        
            # Find data for the base year
            hist_date_idx = None
        
            # Check if base_year exists in the index
            if base_year in historical_data.index:
                hist_date_idx = base_year
            else:
                # Try to find it with different types
                for idx in historical_data.index:
                    if str(idx) == str(base_year) or (isinstance(idx, (int, float)) and int(idx) == base_year):
                        hist_date_idx = idx
                        break
        
            if hist_date_idx is not None:
                # Extract key financial metrics for 2024 - using underscored column names
            
                # Net Revenue
                if 'Net_Revenue' in historical_data.columns:
                    try:
                        raw_value = historical_data.loc[hist_date_idx, 'Net_Revenue']
                        hist_values['Net Revenue'] = raw_value / 1e9 if not pd.isna(raw_value) else 0
                    except:
                        hist_values['Net Revenue'] = 0
                else:
                    hist_values['Net Revenue'] = 0
            
                # Gross Profit
                if 'Gross_Profit' in historical_data.columns:
                    try:
                        raw_value = historical_data.loc[hist_date_idx, 'Gross_Profit']
                        hist_values['Gross profit'] = raw_value / 1e9 if not pd.isna(raw_value) else 0
                    except:
                        hist_values['Gross profit'] = 0
                else:
                    hist_values['Gross profit'] = 0
            
                # COGS - Calculate from Revenue - Gross Profit
                if hist_values['Net Revenue'] > 0 and hist_values['Gross profit'] >= 0:
                    hist_values['COGS'] = hist_values['Net Revenue'] - hist_values['Gross profit']
                else:
                    hist_values['COGS'] = 0
            
                # EBIT
                if 'EBIT' in historical_data.columns:
                    try:
                        raw_value = historical_data.loc[hist_date_idx, 'EBIT']
                        hist_values['EBIT'] = raw_value / 1e9 if not pd.isna(raw_value) else 0
                    except:
                        hist_values['EBIT'] = 0
                else:
                    hist_values['EBIT'] = 0
            
                # NPATMI
                if 'NPATMI' in historical_data.columns:
                    try:
                        raw_value = historical_data.loc[hist_date_idx, 'NPATMI']
                        hist_values['NPATMI'] = raw_value / 1e9 if not pd.isna(raw_value) else 0
                    except:
                        hist_values['NPATMI'] = 0
                else:
                    hist_values['NPATMI'] = 0
            
                # Minority Interest
                if 'Minority_Interest_In_Earning' in historical_data.columns:
                    try:
                        raw_value = historical_data.loc[hist_date_idx, 'Minority_Interest_In_Earning']
                        # Minority interest is usually negative in the CSV (as it reduces NPAT to get NPATMI)
                        # We want to display it as positive in the P&L
                        hist_values['Minority Interest'] = abs(raw_value / 1e9) if not pd.isna(raw_value) else 0
                    except:
                        hist_values['Minority Interest'] = 0
                else:
                    hist_values['Minority Interest'] = 0
            
                # Interest expense - Load from Financial_Expense in CSV
                if 'Financial_Expense' in historical_data.columns:
                    try:
                        raw_value = historical_data.loc[hist_date_idx, 'Financial_Expense']
                        # Financial_Expense is already negative in the CSV, so we make it negative for P&L
                        hist_values['Interest expense'] = raw_value / 1e9 if not pd.isna(raw_value) else 0
                    except:
                        hist_values['Interest expense'] = 0
                else:
                    hist_values['Interest expense'] = 0
            
                # Clean up values
                for key in hist_values:
                    if pd.isna(hist_values[key]):
                        hist_values[key] = 0
    
        # Get project revenue data
        if st.session_state.project_data is not None and not st.session_state.project_data.empty:
            df_projects = st.session_state.project_data
            # Years were already calculated above at line 235
            
            # Get base year from session state
            base_year = st.session_state.get('base_year', datetime.now().year - 1)
            
            # Load project financial data using utility function
            project_data = load_project_financial_data(
                df_projects=df_projects,
                years=years,
                base_year=base_year,
                hist_values=hist_values,
                segment_metrics=segment_metrics
            )
            
            # Unpack all the returned values
            project_revenue_by_year = project_data['project_revenue_by_year']
            project_cogs_by_year = project_data['project_cogs_by_year']
            other_revenue_by_year = project_data['other_revenue_by_year']
            other_cogs_by_year = project_data['other_cogs_by_year']
            project_revenue_breakdown = project_data['project_revenue_breakdown']
            project_cogs_breakdown = project_data['project_cogs_breakdown']
            project_land_breakdown = project_data['project_land_breakdown']
            project_sga_breakdown = project_data['project_sga_breakdown']
            project_interest_breakdown = project_data['project_interest_breakdown']
            project_pat_breakdown = project_data['project_pat_breakdown']
            project_patmi_breakdown = project_data['project_patmi_breakdown']
            project_minority_interest_breakdown = project_data['project_minority_interest_breakdown']
            other_revenue_breakdown = project_data['other_revenue_breakdown']
            minority_interest_row = project_data['minority_interest_row']
            npatmi_row = project_data['npatmi_row']
            revenue_row = project_data['revenue_row']
            hist_col = project_data['hist_col']
            display_years = project_data['display_years']
        
            # Project breakdown data is now incorporated into Total Revenue Forecast table
        
            # Create tabs for Revenue, COGS, Gross Profit, and Minority Interest sections
            st.markdown("---")
            
            # Apply custom CSS for colored tabs with teal theme
            st.markdown("""
            <style>
            /* Custom tab styling for financial sections - Teal Theme */
            div[data-testid="stTabs"][data-baseweb="tabs"] {
                background: linear-gradient(135deg, #2E7D7B 0%, #3A9B98 50%, #2E7D7B 100%);
                padding: 15px;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(46, 125, 123, 0.2);
            }
            
            /* Tab list container */
            div[role="tablist"] {
                gap: 8px;
                background-color: rgba(255, 255, 255, 0.1);
                padding: 8px;
                border-radius: 8px;
            }
            
            /* Individual tab button styling - variations of teal */
            div[role="tablist"] button:nth-of-type(1) {
                background-color: #173F35 !important;  /* Revenue Forecast */
                color: #FFFFFF !important;
                border-radius: 6px;
            }
            div[role="tablist"] button:nth-of-type(2) {
                background-color: #173F35 !important;  /* Cost of Goods Sold */
                color: #FFFFFF !important;
                border-radius: 6px;
            }
            div[role="tablist"] button:nth-of-type(3) {
                background-color: #173F35 !important;  /* Gross Profit */
                color: #FFFFFF !important;
                border-radius: 6px;
            }
            div[role="tablist"] button:nth-of-type(4) {
                background-color: #173F35 !important;  /* SG&A */
                color: #FFFFFF !important;
                border-radius: 6px;
            }
            div[role="tablist"] button:nth-of-type(5) {
                background-color: #173F35 !important;  /* Profit Before Tax */
                color: #FFFFFF !important;
                border-radius: 6px;
            }
            div[role="tablist"] button:nth-of-type(6) {
                background-color: #173F35 !important;  /* Profit After Tax */
                color: #FFFFFF !important;
                border-radius: 6px;
            }
            div[role="tablist"] button:nth-of-type(7) {
                background-color: #173F35 !important;  /* Minority Interest */
                color: #FFFFFF !important;
                border-radius: 6px;
            }
            div[role="tablist"] button:nth-of-type(8) {
                background-color: #173F35 !important;  /* PATMI */
                color: #FFFFFF !important;
                border-radius: 6px;
            }
            
            /* Hover effects */
            div[role="tablist"] button:hover {
                opacity: 0.85;
                transform: translateY(-2px);
                transition: all 0.3s ease;
                box-shadow: 0 4px 8px rgba(46, 125, 123, 0.3);
            }
            
            /* Active tab styling */
            div[role="tablist"] button[aria-selected="true"] {
                background: #08C179 !important;
                border-bottom: none !important;
                font-weight: bold !important;
                box-shadow: 0 6px 12px rgba(46, 125, 123, 0.4);
                transform: translateY(-2px);
                position: relative;
            }
            
            /* Black underline for active tab */
            div[role="tablist"] button[aria-selected="true"]::after {
                content: "";
                display: none;
            }
            
            /* Override any default red coloring */
            .stTabs [data-baseweb="tab-highlight"] {
                background-color: transparent !important;
            }
            
            .stTabs [aria-selected="true"] {
                border-color: transparent !important;
            }
            
            
            /* Additional styling for better contrast */
            div[role="tablist"] button {
                font-weight: 500;
                padding: 10px 20px;
                transition: all 0.3s ease;
            }
            </style>
            """, unsafe_allow_html=True)
            
            tab_revenue, tab_cogs, tab_gp, tab_sga, tab_pbt, tab_pat, tab_minority, tab_patmi = st.tabs([
                "Revenue Forecast", 
                "Cost of Goods Sold", 
                "Gross Profit",
                "SG&A",
                "Profit Before Tax",
                "Profit After Tax",
                "Minority Interest",
                "PATMI"
            ])
            
            with tab_revenue:
                revenue_df = render_revenue_forecast_tab(
                    project_revenue_breakdown,
                    project_revenue_by_year,
                    hist_col,
                    years,
                    base_year,
                    segment_metrics,
                    hist_values
                )
        
            with tab_cogs:
                cogs_df = render_cogs_forecast_tab(
                    project_cogs_breakdown,
                    project_cogs_by_year,
                    hist_col,
                    years,
                    base_year,
                    segment_metrics,
                    hist_values
                )
        
            with tab_gp:
                gross_profit_df, margin_df, projects_gp_total_by_year = render_gross_profit_tab(
                    project_revenue_breakdown,
                    project_cogs_breakdown,
                    project_revenue_by_year,
                    revenue_df,
                    cogs_df,
                    hist_col,
                    years,
                    base_year,
                    segment_metrics,
                    hist_values
                )
            
            with tab_sga:
                sga_df, project_sga_total_by_year = render_sga_tab(
                    project_sga_breakdown,
                    project_revenue_breakdown,
                    project_revenue_by_year,
                    hist_col,
                    years,
                    base_year,
                    segment_metrics,
                    hist_values
                )
                # Convert DataFrame back to list of dicts for P&L calculations
                sga_rows = sga_df.to_dict('records')
        
            # Display PBT Breakdown in the PBT tab
            with tab_pbt:
                project_pbt_breakdown, project_pbt_total_by_year = render_pbt_tab(
                    df_projects,
                    project_revenue_breakdown,
                    project_revenue_by_year,
                    hist_col,
                    years
                )
        
            # Display Profit After Tax Breakdown in the PAT tab
            with tab_pat:
                pat_breakdown_df, project_pat_total_by_year = render_pat_tab(
                    project_pat_breakdown,
                    project_revenue_breakdown,
                    project_revenue_by_year,
                    hist_col,
                    years
                )
        
            # Display Minority Interest Breakdown in the minority tab
            with tab_minority:
                mi_breakdown_df = render_minority_interest_tab(
                    project_minority_interest_breakdown=project_minority_interest_breakdown,
                    df_projects=df_projects,
                    minority_interest_row=minority_interest_row,
                    hist_col=hist_col,
                    years=years
                )
        
            # Display PATMI (PAT Minus Minority Interest) in the PATMI tab
            with tab_patmi:
                patmi_df, project_patmi_breakdown, project_patmi_total_by_year = render_patmi_tab(
                    df_projects=df_projects,
                    hist_col=hist_col,
                    years=years,
                    hist_values=hist_values,
                    project_pat_breakdown=project_pat_breakdown,
                    project_minority_interest_breakdown=project_minority_interest_breakdown,
                    npatmi_row=npatmi_row,
                    project_revenue_breakdown=project_revenue_breakdown,
                    project_revenue_by_year=project_revenue_by_year
                )
            
            # Pre-calculate cash balances and interest income for P&L
            # Using cost_of_debts already retrieved at line 141
            # This is needed because P&L section comes before Balance Sheet section
            # We'll do a simplified calculation here that will be refined later in Balance Sheet
            
            # Initialize historical cash (will be properly loaded in Balance Sheet section)
            hist_cash_preliminary = 0
            
            # Try to load historical cash early for interest income calculation
            try:
                fa_annual_path = 'data/FA_A_processed.parquet'
                if os.path.exists(fa_annual_path):
                    fa_annual_df = pd.read_parquet(fa_annual_path)
                    ticker_data = fa_annual_df[(fa_annual_df['TICKER'] == selected_ticker) & 
                                               (fa_annual_df['DATE'] == base_year)]
                    if not ticker_data.empty:
                        cash_data = ticker_data[ticker_data['KEYCODE'] == 'Cash']
                        if not cash_data.empty:
                            hist_cash_preliminary += cash_data['VALUE'].iloc[0] / 1e9 if not pd.isna(cash_data['VALUE'].iloc[0]) else 0
                        cash_equiv_data = ticker_data[ticker_data['KEYCODE'] == 'Cash_Equivalent']
                        if not cash_equiv_data.empty:
                            hist_cash_preliminary += cash_equiv_data['VALUE'].iloc[0] / 1e9 if not pd.isna(cash_equiv_data['VALUE'].iloc[0]) else 0
            except:
                hist_cash_preliminary = 0
            
            # Calculate preliminary cash flows from projects to estimate cash balances
            preliminary_cash_by_year = {}
            cumulative_cash_prelim = hist_cash_preliminary
            
            for year in years:
                year_str = str(year)
                year_cash_change = 0
                
                # Add cash changes from projects
                for _, project in df_projects.iterrows():
                    financial_statements = project.get('comprehensive_financial_statements', {})
                    if isinstance(financial_statements, dict) and year_str in financial_statements:
                        year_data = financial_statements[year_str]
                        if 'cash_balance_change' in year_data:
                            year_cash_change += year_data.get('cash_balance_change', 0) / 1e9
                        elif 'Cash_Balance_Change' in year_data:
                            year_cash_change += year_data.get('Cash_Balance_Change', 0) / 1e9
                
                # Add cash from other segments (simplified)
                if year_str in other_revenue_breakdown:
                    for segment_name, segment_revenue in other_revenue_breakdown.items():
                        revenue = segment_revenue.get(year_str, 0)
                        if segment_name in segment_metrics:
                            gross_margin = segment_metrics[segment_name]['gross_margin']
                        else:
                            gross_margin = 0.0
                        # Simplified cash = revenue * gross margin
                        year_cash_change += revenue * gross_margin
                
                cumulative_cash_prelim += year_cash_change
                preliminary_cash_by_year[year_str] = cumulative_cash_prelim
            
            # Calculate interest income with iterative approach to handle circular reference
            # Maximum 10 iterations to avoid infinite loops
            MAX_ITERATIONS = 10
            CONVERGENCE_THRESHOLD = 0.001  # Stop if change is less than 0.1%
            
            interest_income_by_year = {str(year): 0 for year in years}
            
            for iteration in range(MAX_ITERATIONS):
                previous_interest_income = interest_income_by_year.copy()
                
                # Recalculate cash balances with current interest income
                cumulative_cash_with_interest = hist_cash_preliminary
                cash_balance_with_interest = {}
                
                for year in years:
                    year_str = str(year)
                    
                    # Start with preliminary cash change (without interest income)
                    year_cash_change = 0
                    
                    # Add operating cash flow components
                    if hasattr(st.session_state, 'project_forecasts'):
                        for project_name, project_data in st.session_state.project_forecasts.items():
                            if year_str in project_data:
                                year_data = project_data[year_str]
                                presales_cf = year_data.get('cash_inflow_presales', 0) / 1e9
                                interest_cf = year_data.get('cash_outflow_interest', 0) / 1e9
                                sga_cf = year_data.get('cash_outflow_sga', 0) / 1e9
                                tax_cf = year_data.get('cash_outflow_tax', 0) / 1e9
                                year_cash_change += presales_cf + interest_cf + sga_cf + tax_cf
                    
                    # Add existing debt interest (negative cash flow)
                    if 'existing_debt' in company_assumptions:
                        existing_debt = company_assumptions['existing_debt']
                        existing_interest_rate = company_assumptions.get('existing_interest_rate', 0.08)
                        existing_debt_interest = existing_debt * existing_interest_rate
                        year_cash_change -= existing_debt_interest
                    
                    # Add other segment SG&A (negative cash flow)
                    if hasattr(st.session_state, 'base_year_revenues'):
                        for segment_name in st.session_state.base_year_revenues.keys():
                            if segment_name in segment_metrics:
                                sga_pct = segment_metrics[segment_name]['sga_percentage']
                            else:
                                sga_pct = 0.0
                            
                            base_revenue = st.session_state.base_year_revenues[segment_name]
                            if segment_name in segment_metrics:
                                growth_rate = segment_metrics[segment_name]['revenue_growth']
                            else:
                                growth_rate = 0.0
                            
                            years_from_base = year - base_year
                            segment_revenue = base_revenue * ((1 + growth_rate) ** years_from_base)
                            segment_sga = -segment_revenue * sga_pct  # Negative for cash outflow
                            year_cash_change += segment_sga
                    
                    # Add other revenue/COGS
                    if other_revenue_breakdown:
                        for segment_name in other_revenue_breakdown.keys():
                            segment_revenue = other_revenue_breakdown[segment_name].get(year, 0)
                            year_cash_change += segment_revenue
                            # Calculate and subtract COGS for this segment
                            if segment_name in segment_metrics:
                                gross_margin = segment_metrics[segment_name]['gross_margin']
                                segment_cogs = segment_revenue * (1 - gross_margin)  # COGS = Revenue * (1 - Gross Margin)
                                year_cash_change -= segment_cogs
                    
                    # Add investing cash flows
                    if hasattr(st.session_state, 'project_forecasts'):
                        for project_name, project_data in st.session_state.project_forecasts.items():
                            if year_str in project_data:
                                year_data = project_data[year_str]
                                land_cf = year_data.get('cash_outflow_land', 0) / 1e9
                                construction_cf = year_data.get('cash_outflow_construction', 0) / 1e9
                                year_cash_change += land_cf + construction_cf
                    
                    # Add financing cash flows
                    if hasattr(st.session_state, 'project_forecasts'):
                        for project_name, project_data in st.session_state.project_forecasts.items():
                            if year_str in project_data:
                                year_data = project_data[year_str]
                                debt_drawdown = year_data.get('debt_drawdown', 0) / 1e9
                                debt_repayment = year_data.get('debt_repayment', 0) / 1e9
                                year_cash_change += debt_drawdown - debt_repayment
                    
                    # Add interest income from previous iteration
                    year_cash_change += interest_income_by_year[year_str]
                    
                    # Update cumulative cash
                    cumulative_cash_with_interest += year_cash_change
                    cash_balance_with_interest[year_str] = cumulative_cash_with_interest
                
                # Calculate new interest income based on updated cash balances
                prev_cash = hist_cash_preliminary
                for year in years:
                    year_str = str(year)
                    current_cash = cash_balance_with_interest[year_str]
                    avg_cash = (prev_cash + current_cash) / 2
                    interest_income = max(0, avg_cash * cost_of_debts) if avg_cash > 0 else 0
                    interest_income_by_year[year_str] = interest_income
                    prev_cash = current_cash
                
                # Check for convergence
                converged = True
                for year_str in interest_income_by_year:
                    if previous_interest_income[year_str] != 0:
                        change_pct = abs((interest_income_by_year[year_str] - previous_interest_income[year_str]) / previous_interest_income[year_str])
                        if change_pct > CONVERGENCE_THRESHOLD:
                            converged = False
                            break
                    elif interest_income_by_year[year_str] != 0:
                        converged = False
                        break
                
                if converged:
                    break
            
            # Update preliminary cash balances to include final interest income
            cumulative_cash_prelim = hist_cash_preliminary
            for year in years:
                year_str = str(year)
                # Get the original preliminary cash change
                year_cash_change = preliminary_cash_by_year[year_str] - (cumulative_cash_prelim if year == years[0] else preliminary_cash_by_year[str(year-1)])
                # Add the final interest income
                year_cash_change += interest_income_by_year[year_str]
                cumulative_cash_prelim += year_cash_change
                preliminary_cash_by_year[year_str] = cumulative_cash_prelim
        
            # Section 5: Consolidated P&L with Interest Expense
            st.markdown("---")
            
            # Add toggle for comparison mode
            col_header, col_toggle = st.columns([3, 1])
            with col_header:
                st.subheader("Consolidated P&L Statement")
            with col_toggle:
                compare_mode = st.toggle("Compare with previous forecast", value=False, key="pnl_compare_toggle")
        
            # Calculate interest expense for all projects
            project_interest_by_year = {}
            debt_financing_pct = company_assumptions.get('debt_financing_pct', 0.0)  # Default 30%
        
            for year in years:
                year_str = str(year)
                total_interest = 0
            
                # Aggregate interest from all projects
                for _, project in df_projects.iterrows():
                    # Check if project has saved interest schedule
                    interest_schedule = project.get('interest_schedule', {})
                    if isinstance(interest_schedule, dict) and year_str in interest_schedule:
                        total_interest += interest_schedule[year_str]
            
                project_interest_by_year[year] = total_interest
        
            # Calculate SG&A expenses
            sga_by_year = {}
            for year in years:
                # SG&A for projects - should come from project data, not hardcoded
                # Use the actual SG&A from project breakdown if available
                project_sga = sum(project_sga_breakdown.get(project, {}).get(year, 0) 
                                for project in project_sga_breakdown.keys())
            
                # SG&A for other segments
                other_sga = 0
                for segment_name in st.session_state.base_year_revenues.keys():
                    if segment_name in segment_metrics:
                        sga_pct = segment_metrics[segment_name]['sga_percentage']
                    else:
                        sga_pct = 0.0  # Default 0%
                
                    # Calculate segment revenue for the year
                    base_revenue = st.session_state.base_year_revenues[segment_name]
                    if segment_name in segment_metrics:
                        growth_rate = segment_metrics[segment_name]['revenue_growth']
                    else:
                        growth_rate = 0.0
                
                    # Base year is the latest historical year, apply growth from there
                    years_from_base = year - base_year
                    segment_revenue = base_revenue * ((1 + growth_rate) ** years_from_base)
                
                    other_sga += segment_revenue * sga_pct
            
                sga_by_year[year] = project_sga + other_sga
        
            # Create comprehensive P&L (rows = P&L items, columns = years including historical)
            # Get totals from the DataFrames
            total_revenue_row = revenue_df[revenue_df['Revenue Source'] == 'TOTAL REVENUE'].iloc[0]
            total_cogs_row = cogs_df[cogs_df['COGS Source'] == 'TOTAL COGS'].iloc[0]
            total_gp_row = gross_profit_df[gross_profit_df['Gross Profit Source'] == 'TOTAL GROSS PROFIT'].iloc[0]
            total_sga_row = sga_df[sga_df['SG&A Source'] == 'TOTAL SG&A'].iloc[0]
        
            # First, load historical debt balance to calculate existing debt interest
            hist_debt = 0
            try:
                # Load FA_A_processed.parquet to get debt balance
                fa_annual_path = 'data/FA_A_processed.parquet'
                if os.path.exists(fa_annual_path):
                    fa_annual_df = pd.read_parquet(fa_annual_path)
                
                    # Filter for selected ticker and base year
                    ticker_data = fa_annual_df[(fa_annual_df['TICKER'] == selected_ticker) & 
                                               (fa_annual_df['DATE'] == base_year)]
                
                    if not ticker_data.empty:
                        # Get historical debt (ST + LT debt)
                        st_debt_data = ticker_data[ticker_data['KEYCODE'] == 'ST_Debt']
                        if not st_debt_data.empty:
                            hist_debt += st_debt_data['VALUE'].iloc[0] / 1e9 if not pd.isna(st_debt_data['VALUE'].iloc[0]) else 0
                    
                        lt_debt_data = ticker_data[ticker_data['KEYCODE'] == 'LT_Debt']
                        if not lt_debt_data.empty:
                            hist_debt += lt_debt_data['VALUE'].iloc[0] / 1e9 if not pd.isna(lt_debt_data['VALUE'].iloc[0]) else 0
            except:
                pass  # Silent fail, hist_debt remains 0
        
            # Cost of debt already loaded from company_assumptions at the beginning
            # No need to reload it here
        
            # Calculate interest expense from projects and existing debt separately
            # 1. Project interest from project_interest_breakdown
            project_interest_row = {hist_col: 0}  # No historical project breakdown
            for year in years:
                total_project_interest = 0
                for project_name in project_interest_breakdown.keys():
                    total_project_interest += project_interest_breakdown[project_name].get(year, 0)
                project_interest_row[str(year)] = total_project_interest
        
            # 2. Interest on existing debt balance
            # For historical, use the actual Financial_Expense from CSV
            # For forecast, calculate as Debt Balance * Cost of Debts
            existing_debt_interest_row = {hist_col: hist_values.get('Interest expense', 0)}  # Historical from Financial_Expense
        
            for year in years:
                # Calculate interest on existing debt for forecast years
                # Interest = Debt Balance * Cost of Debts (negative for expense)
                existing_debt_interest = -abs(hist_debt * cost_of_debts) if hist_debt > 0 else 0
                existing_debt_interest_row[str(year)] = existing_debt_interest
        
            # Total interest combines both sources
            total_interest_row = {hist_col: hist_values.get('Interest expense', 0)}
            for year in years:
                total_interest_row[str(year)] = project_interest_row[str(year)] + existing_debt_interest_row[str(year)]
        
            # Create P&L rows
            pnl_rows = []
        
            # Store segment data for saving
            segment_revenue_data = {}
            segment_cogs_data = {}
        
            # Revenue breakdown
            # Real Estate Revenue (from projects)
            re_revenue_row = {'P&L Item': '  Real Estate Revenue'}
            re_revenue_row[hist_col] = 0  # No historical breakdown
            for year in years:
                re_revenue_row[str(year)] = project_revenue_by_year[year]
            pnl_rows.append(re_revenue_row)
        
            # Individual Business Segments Revenue
            for segment_name in st.session_state.base_year_revenues.keys():
                segment_row = {'P&L Item': f'  {segment_name}'}
                segment_row[hist_col] = st.session_state.base_year_revenues[segment_name]  # Base year revenue
            
                # Initialize segment data storage
                if segment_name not in segment_revenue_data:
                    segment_revenue_data[segment_name] = {}
            
                for year in years:
                    year_str = str(year)
                    base_revenue = st.session_state.base_year_revenues[segment_name]
                    if segment_name in segment_metrics:
                        growth_rate = segment_metrics[segment_name]['revenue_growth']
                    else:
                        growth_rate = 0.1
                    years_from_base = year - base_year
                    segment_revenue = base_revenue * ((1 + growth_rate) ** years_from_base)
                    segment_row[year_str] = segment_revenue
                    segment_revenue_data[segment_name][year_str] = segment_revenue
            
                pnl_rows.append(segment_row)
        
            # Update revenue_row with forecast values (already initialized earlier)
            revenue_row[hist_col] = total_revenue_row[hist_col]  # Update historical
            for year in years:
                revenue_row[str(year)] = total_revenue_row[str(year)]
            pnl_rows.append(revenue_row)
        
            # COGS breakdown
            # Real Estate COGS
            re_cogs_row = {'P&L Item': '  Real Estate COGS'}
            re_cogs_row[hist_col] = 0  # No historical breakdown
            for year in years:
                re_cogs_row[str(year)] = project_cogs_by_year[year]  # Already negative
            pnl_rows.append(re_cogs_row)
        
            # Individual Business Segments COGS
            for segment_name in st.session_state.base_year_revenues.keys():
                cogs_row = {'P&L Item': f'  {segment_name} COGS'}
            
                # Initialize segment COGS data storage
                if segment_name not in segment_cogs_data:
                    segment_cogs_data[segment_name] = {}
            
                # Get metrics
                if segment_name in segment_metrics:
                    gross_margin = segment_metrics[segment_name]['gross_margin']
                else:
                    gross_margin = 0.0
            
                # Historical COGS
                base_revenue = st.session_state.base_year_revenues[segment_name]
                cogs_row[hist_col] = -base_revenue * (1 - gross_margin)  # Negative
            
                # Forecast COGS
                for year in years:
                    year_str = str(year)
                    # Get revenue for this year (already calculated above)
                    segment_revenue = segment_revenue_data[segment_name][year_str]
                    segment_cogs = -segment_revenue * (1 - gross_margin)  # Negative
                    cogs_row[year_str] = segment_cogs
                    segment_cogs_data[segment_name][year_str] = segment_cogs
            
                pnl_rows.append(cogs_row)
        
            # Total COGS row (negative values)
            total_cogs_pnl_row = {'P&L Item': 'Total COGS'}
            total_cogs_pnl_row[hist_col] = total_cogs_row[hist_col]  # Add historical
            for year in years:
                total_cogs_pnl_row[str(year)] = total_cogs_row[str(year)]
            pnl_rows.append(total_cogs_pnl_row)
        
            # Gross Profit row
            gp_row = {'P&L Item': 'Gross Profit'}
            gp_row[hist_col] = total_gp_row[hist_col]  # Add historical
            for year in years:
                gp_row[str(year)] = total_gp_row[str(year)]
            pnl_rows.append(gp_row)
        
            # SG&A row (negative values)
            sga_row = {'P&L Item': 'SG&A'}
            sga_row[hist_col] = total_sga_row[hist_col]  # Add historical
            for year in years:
                sga_row[str(year)] = total_sga_row[str(year)]
            pnl_rows.append(sga_row)
        
            # EBITDA row (GP + SG&A where SG&A is negative)
            ebitda_row = {'P&L Item': 'EBITDA'}
            ebitda_row[hist_col] = total_gp_row[hist_col] + total_sga_row[hist_col]  # Add historical
            for year in years:
                year_str = str(year)
                # Since SG&A is negative, we add it (not subtract)
                ebitda_row[year_str] = total_gp_row[year_str] + total_sga_row[year_str]
            pnl_rows.append(ebitda_row)
            
            # Interest Income from Cash (positive values)
            # Calculate based on average cash balance * cost of debt
            interest_income_row = {'P&L Item': 'Interest Income'}
            interest_income_row[hist_col] = 0  # No historical interest income
            
            # Use the pre-calculated interest income values
            for year in years:
                year_str = str(year)
                interest_income_row[year_str] = interest_income_by_year.get(year_str, 0)
            
            pnl_rows.append(interest_income_row)
        
            # Interest Expense from Projects (negative values)
            project_interest_pnl_row = {'P&L Item': '  Interest Expense - Projects'}
            project_interest_pnl_row[hist_col] = 0  # No historical breakdown
            for year in years:
                project_interest_pnl_row[str(year)] = project_interest_row[str(year)]
            pnl_rows.append(project_interest_pnl_row)
        
            # Interest Expense from Existing Debt (negative values)
            existing_interest_pnl_row = {'P&L Item': '  Interest Expense - Existing Debt'}
            existing_interest_pnl_row[hist_col] = existing_debt_interest_row[hist_col]  # Historical from Financial_Expense
            for year in years:
                existing_interest_pnl_row[str(year)] = existing_debt_interest_row[str(year)]
            pnl_rows.append(existing_interest_pnl_row)
        
            # Total Interest Expense row (negative values)
            interest_row = {'P&L Item': 'Total Interest Expense'}
            interest_row[hist_col] = total_interest_row[hist_col]  # Add historical
            for year in years:
                interest_row[str(year)] = total_interest_row[str(year)]
            pnl_rows.append(interest_row)
        
            # PBT row (EBITDA + Interest Income + Interest Expense where Interest Expense is negative)
            pbt_row = {'P&L Item': 'Profit Before Tax'}
            pbt_row[hist_col] = ebitda_row[hist_col] + total_interest_row[hist_col]  # Add historical (no interest income historically)
            for year in years:
                year_str = str(year)
                # PBT = EBITDA + Interest Income + Interest Expense (where Interest Expense is negative)
                pbt_row[year_str] = ebitda_row[year_str] + interest_income_row[year_str] + total_interest_row[year_str]
            pnl_rows.append(pbt_row)
        
            # Tax row
            tax_label = f'Tax ({tax_rate * 100:.0f}%)' if tax_rate > 0 else 'Tax (0% - Not Set)'
            tax_row = {'P&L Item': tax_label}
            tax_row[hist_col] = -max(0, pbt_row[hist_col] * tax_rate)  # Add historical as negative
            for year in years:
                year_str = str(year)
                pbt_value = pbt_row[year_str]
                tax_row[year_str] = -max(0, pbt_value * tax_rate)  # Tax as negative (expense)
            pnl_rows.append(tax_row)
        
            # PAT row (PBT + Tax where Tax is negative)
            pat_row = {'P&L Item': 'Profit After Tax'}
            pat_row[hist_col] = pbt_row[hist_col] + tax_row[hist_col]  # Add historical
            for year in years:
                year_str = str(year)
                # Since Tax is negative, we add it (not subtract)
                pat_row[year_str] = pbt_row[year_str] + tax_row[year_str]
            pnl_rows.append(pat_row)
        
            # Aggregate minority interest from already calculated project breakdown
            # The minority interest was already calculated in load_project_financial_data
            # based on project PAT from MongoDB and ownership percentages
            
            for year in years:
                year_str = str(year)
                total_minority_interest = 0
                
                # Sum up minority interest from all projects
                for project_name, project_mi_data in project_minority_interest_breakdown.items():
                    if year in project_mi_data:
                        total_minority_interest += project_mi_data[year]['minority_interest']
                
                minority_interest_row[year_str] = total_minority_interest
        
            pnl_rows.append(minority_interest_row)
        
            # NPATMI row 
            # For historical: NPATMI = PAT + Minority Interest (since MI represents profit from minority-owned subsidiaries)
            # For forecast: NPATMI = PAT - Minority Interest (since MI represents profit going to minority shareholders)
            # Continue populating NPATMI data (already initialized earlier)
            # Update historical value to use the correct calculation
            npatmi_row[hist_col] = hist_values.get('NPATMI', pat_row[hist_col] - minority_interest_row[hist_col])
            for year in years:
                year_str = str(year)
                # For forecast years: NPATMI = PAT - Minority Interest
                npatmi_row[year_str] = pat_row[year_str] - minority_interest_row[year_str]
            pnl_rows.append(npatmi_row)
        
            # Create DataFrame
            pnl_df = pd.DataFrame(pnl_rows)
        
            # Load saved forecast for comparison BEFORE displaying table (only if compare mode is on)
            from utils.mongodb_utils import load_company_forecast
            saved_forecast = load_company_forecast(selected_ticker) if compare_mode else {}
        
            # Create a mapping of P&L items to their saved values
            saved_values_map = {}
            if saved_forecast and compare_mode:
                for year_str in saved_forecast.keys():
                    if year_str not in saved_values_map:
                        saved_values_map[year_str] = {}
                
                    saved_year = saved_forecast[year_str]
                    
                    # Check if this is the P&L data directly or nested
                    if 'pnl' in saved_year:
                        # P&L data is nested under 'pnl' key
                        saved_pnl = saved_year['pnl']
                    else:
                        # P&L data is at the root level
                        saved_pnl = saved_year
                
                    # Map saved values to P&L row items
                    # Convert from raw VND values back to billions for comparison
                    saved_values_map[year_str]['  Real Estate Revenue'] = saved_pnl.get('real_estate_revenue', 0) / 1e9 if saved_pnl.get('real_estate_revenue') else None
                    saved_values_map[year_str]['Net Revenue'] = saved_pnl.get('net_revenue', 0) / 1e9 if saved_pnl.get('net_revenue') else None
                    saved_values_map[year_str]['  Real Estate COGS'] = saved_pnl.get('real_estate_cogs', 0) / 1e9 if saved_pnl.get('real_estate_cogs') else None
                    saved_values_map[year_str]['Total COGS'] = saved_pnl.get('total_cogs', 0) / 1e9 if saved_pnl.get('total_cogs') else None
                    saved_values_map[year_str]['Gross Profit'] = saved_pnl.get('gross_profit', 0) / 1e9 if saved_pnl.get('gross_profit') else None
                    saved_values_map[year_str]['SG&A'] = saved_pnl.get('sga', 0) / 1e9 if saved_pnl.get('sga') else None
                    saved_values_map[year_str]['EBITDA'] = saved_pnl.get('ebitda', 0) / 1e9 if saved_pnl.get('ebitda') else None
                    saved_values_map[year_str]['Interest Income'] = saved_pnl.get('interest_income', 0) / 1e9 if saved_pnl.get('interest_income') else None
                    saved_values_map[year_str]['  Interest Expense - Projects'] = saved_pnl.get('project_interest_expense', 0) / 1e9 if saved_pnl.get('project_interest_expense') else None
                    saved_values_map[year_str]['  Interest Expense - Existing Debt'] = saved_pnl.get('existing_debt_interest_expense', 0) / 1e9 if saved_pnl.get('existing_debt_interest_expense') else None
                    saved_values_map[year_str]['Total Interest Expense'] = saved_pnl.get('interest_expense', 0) / 1e9 if saved_pnl.get('interest_expense') else None
                    saved_values_map[year_str]['Profit Before Tax'] = saved_pnl.get('pbt', 0) / 1e9 if saved_pnl.get('pbt') else None
                    
                    # Handle Tax row with dynamic label
                    tax_value = saved_pnl.get('tax', 0) / 1e9 if saved_pnl.get('tax') else None
                    # Try to map to any tax row (could be "Tax (20%)" or "Tax (0% - Not Set)" etc.)
                    for item in pnl_df['P&L Item'].values:
                        if item.startswith('Tax'):
                            saved_values_map[year_str][item] = tax_value
                            break
                    
                    saved_values_map[year_str]['Profit After Tax'] = saved_pnl.get('pat', 0) / 1e9 if saved_pnl.get('pat') else None
                    saved_values_map[year_str]['Minority Interest'] = saved_pnl.get('minority_interest', 0) / 1e9 if saved_pnl.get('minority_interest') else None
                    saved_values_map[year_str]['NPATMI (Net Profit After Tax and MI)'] = saved_pnl.get('npatmi', 0) / 1e9 if saved_pnl.get('npatmi') else None
                
                    # Map business segments
                    if 'business_segments' in saved_pnl:
                        for segment_name, segment_data in saved_pnl['business_segments'].items():
                            saved_values_map[year_str][f'  {segment_name}'] = segment_data.get('revenue', 0) / 1e9 if segment_data.get('revenue') else None
                            saved_values_map[year_str][f'  {segment_name} COGS'] = segment_data.get('cogs', 0) / 1e9 if segment_data.get('cogs') else None
        
            # Create display DataFrame with change indicators
            display_df = pnl_df.copy()
            changed_cells = []  # Track cells that have changed for styling
        
            # Add change indicators to values (only if compare_mode is on)
            if compare_mode:
                for idx, row in pnl_df.iterrows():
                    item = row['P&L Item']
                    for year in years:
                        year_str = str(year)
                        if year_str in saved_values_map and item in saved_values_map[year_str]:
                            current_val = row[year_str]
                            saved_val = saved_values_map[year_str][item]
                        
                            if saved_val is not None and abs(current_val - saved_val) > 0.01:
                                # Format as "new (old)" for changed values with thousand comma separation
                                display_df.at[idx, year_str] = f"{current_val:,.0f}\n({saved_val:,.0f})"
                                changed_cells.append((idx, year_str))
        
            # Style function to highlight key rows and changed cells
            def style_pnl_table(df_style):
                # Create style DataFrame
                styles = pd.DataFrame('', index=df_style.index, columns=df_style.columns)
            
                # Apply row-level styles with enhanced formatting (no background colors)
                for idx, row in df_style.iterrows():
                    item = pnl_df.iloc[idx]['P&L Item']
                
                    # Major totals - bold
                    if item in ['Net Revenue', 'NPATMI (Net Profit After Tax and MI)']:
                        styles.iloc[idx] = 'font-weight: bold; color: #155724'  # Bold with green text
                    # Important subtotals - bold
                    elif item in ['Total COGS', 'Gross Profit', 'EBITDA', 'Profit Before Tax', 'Profit After Tax']:
                        styles.iloc[idx] = 'font-weight: bold'  # Bold only
                    # Other totals - just bold
                    elif item in ['Total Interest Expense', 'SG&A']:
                        styles.iloc[idx] = 'font-weight: bold'  # Bold only
                    # Minority Interest - special formatting
                    elif item == 'Minority Interest':
                        styles.iloc[idx] = 'font-style: italic; color: #856404'  # Italic with brown text
                    # Tax row - red text
                    elif item == 'Tax' or 'Tax (' in item:
                        styles.iloc[idx] = 'color: #dc3545'  # Red text for expense
                    # Sub-items (indented)
                    elif item.startswith('  '):
                        styles.iloc[idx] = 'padding-left: 20px; color: #6c757d'  # Gray text for sub-items
            
                # Apply cell-level highlighting for changes
                for idx, col in changed_cells:
                    current_style = styles.at[idx, col]
                    styles.at[idx, col] = f"{current_style}; background-color: #E8F5E9"  # Very light green (same as RNAV)
            
                return styles
        
            # Format function for proper display with integer formatting
            def format_pnl_values(val):
                if isinstance(val, str) and '\n' in val:
                    return val  # Already formatted with old value
                elif pd.isna(val) or val is None:
                    return "-"
                else:
                    try:
                        # Format as integer with comma thousand separator
                        return f"{int(val):,}"
                    except (ValueError, OverflowError):
                        return f"{val:,.0f}"
        
            st.write("**Consolidated P&L Statement (Billion VND)**")
            #if compare_mode and changed_cells:
            #    st.caption("🟢 Green cells indicate changes from saved forecast (showing: current value / saved value)")
        
            # Define column configuration for consistent width
            pnl_column_config = {
                'P&L Item': st.column_config.TextColumn('P&L Item', width='medium'),
            }
            for col in [hist_col] + [str(y) for y in years]:
                pnl_column_config[col] = st.column_config.TextColumn(col, width='small')
        
            # Apply styling
            styled_df = display_df.style.apply(lambda x: style_pnl_table(display_df), axis=None)
        
            # Format numeric columns
            for col in [hist_col] + [str(y) for y in years]:
                styled_df = styled_df.format(format_pnl_values, subset=[col])
        
            st.dataframe(
                styled_df,
                use_container_width=True,
                column_config=pnl_column_config,
                hide_index=True
            )
        
            # Check for changes compared to saved data
            has_changes = False
            changed_items = {}  # Track which items have changed for the summary
        
            if saved_forecast:
                # Compare current values with saved values
                for year in years:
                    year_str = str(year)
                    if year_str in saved_forecast:
                        saved_year = saved_forecast[year_str]
                    
                        # Check main P&L items
                        checks = [
                            ('real_estate_revenue', re_revenue_row[year_str]),
                            ('net_revenue', revenue_row[year_str]),
                            ('real_estate_cogs', re_cogs_row[year_str]),
                            ('total_cogs', total_cogs_pnl_row[year_str]),
                            ('gross_profit', gp_row[year_str]),
                            ('sga', sga_row[year_str]),
                            ('ebitda', ebitda_row[year_str]),
                            ('project_interest_expense', project_interest_pnl_row[year_str]),
                            ('existing_debt_interest_expense', existing_interest_pnl_row[year_str]),
                            ('interest_expense', interest_row[year_str]),
                            ('pbt', pbt_row[year_str]),
                            ('tax', tax_row[year_str]),
                            ('pat', pat_row[year_str])
                        ]
                    
                        for key, current_val in checks:
                            if key in saved_year:
                                if abs(current_val - saved_year[key]) > 0.01:  # Tolerance for float comparison
                                    has_changes = True
                                    if year_str not in changed_items:
                                        changed_items[year_str] = []
                                    changed_items[year_str].append(key)
                    
                        # Check business segments
                        if 'business_segments' in saved_year:
                            for segment_name in st.session_state.base_year_revenues.keys():
                                if segment_name in saved_year['business_segments']:
                                    saved_segment = saved_year['business_segments'][segment_name]
                                    current_revenue = segment_revenue_data[segment_name][year_str]
                                    current_cogs = segment_cogs_data[segment_name][year_str]
                                
                                    if abs(current_revenue - saved_segment.get('revenue', 0)) > 0.01:
                                        has_changes = True
                                        if year_str not in changed_items:
                                            changed_items[year_str] = []
                                        changed_items[year_str].append(f'{segment_name}_revenue')
                                
                                    if abs(current_cogs - saved_segment.get('cogs', 0)) > 0.01:
                                        has_changes = True
                                        if year_str not in changed_items:
                                            changed_items[year_str] = []
                                        changed_items[year_str].append(f'{segment_name}_cogs')
        
            # Display change indicator (keep for P&L tracking)
            if has_changes:
                st.info("ℹ️ Changes detected in the P&L forecast compared to the database")
        
            
            # Pre-calculate cash flows (needed for balance sheet cash calculation)
            cf_data = prepare_cashflow_data(
                df_projects=df_projects,
                years=years,
                other_revenue_breakdown=other_revenue_breakdown,
                segment_metrics=segment_metrics,
                existing_debt_interest_row=existing_debt_interest_row,
                sga_rows=sga_rows,
                tax_row=tax_row,
                interest_income_by_year=interest_income_by_year
            )
            
            # Unpack the returned values
            operating_cf_by_year = cf_data['operating_cf_by_year']
            investing_cf_by_year = cf_data['investing_cf_by_year']
            financing_cf_by_year = cf_data['financing_cf_by_year']
            net_cf_by_year = cf_data['net_cf_by_year']
            other_segment_revenue_cf = cf_data['other_segment_revenue_cf']
            other_segment_cogs_cf = cf_data['other_segment_cogs_cf']
            presales_cf_breakdown = cf_data['presales_cf_breakdown']
            interest_outflow_breakdown = cf_data['interest_outflow_breakdown']
            sga_outflow_breakdown = cf_data['sga_outflow_breakdown']
            tax_outflow_breakdown = cf_data['tax_outflow_breakdown']
            land_outflow_breakdown = cf_data['land_outflow_breakdown']
            construction_outflow_breakdown = cf_data['construction_outflow_breakdown']
            financing_cf_breakdown = cf_data['financing_cf_breakdown']
            
            # Section 6: Balance Sheet Statements
            st.markdown("---")
            st.subheader("Balance Sheet Statements")
            
            # Apply custom CSS for balance sheet tabs (similar to revenue tabs)
            st.markdown("""
            <style>
            /* Custom tab styling for balance sheet tabs */
            div[role="tablist"] {
                gap: 8px;
                background-color: rgba(255, 255, 255, 0.1);
                padding: 8px;
                border-radius: 8px;
            }
            
            /* Individual tab button styling - teal theme */
            div[role="tablist"] button {
                background-color: #173F35 !important;
                color: #FFFFFF !important;
                border-radius: 6px;
                font-weight: 500;
                padding: 10px 20px;
                transition: all 0.3s ease;
            }
            
            /* Hover effects */
            div[role="tablist"] button:hover {
                opacity: 0.85;
                transform: translateY(-2px);
                transition: all 0.3s ease;
                box-shadow: 0 4px 8px rgba(46, 125, 123, 0.3);
            }
            
            /* Active tab styling */
            div[role="tablist"] button[aria-selected="true"] {
                background: #08C179 !important;
                border-bottom: none !important;
                font-weight: bold !important;
                box-shadow: 0 6px 12px rgba(46, 125, 123, 0.4);
                transform: translateY(-2px);
                position: relative;
            }
            
            /* Override any default red coloring */
            .stTabs [data-baseweb="tab-highlight"] {
                background-color: transparent !important;
            }
            
            .stTabs [aria-selected="true"] {
                border-color: transparent !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Create tabs for the two balance sheet views
            tab_detail_bs, tab_consolidated_bs = st.tabs([
                "Detail Project Breakdown",
                "Consolidated Balance Sheet"
            ])
            
            # Prepare balance sheet data using utility function
            base_year_str = str(base_year)  # Define base_year_str for use in render_detail_bs_tab
            bs_data_result = prepare_balance_sheet_data(
                df_projects=df_projects,
                hist_col=hist_col,
                years=years,
                base_year=base_year,
                historical_data=historical_data,
                hist_date_idx=hist_date_idx
            )
            
            # Unpack only the values that are actually used
            total_debt_by_year = bs_data_result['total_debt_by_year']
            total_inventory_by_year = bs_data_result['total_inventory_by_year']
            total_customer_prepayment_by_year = bs_data_result['total_customer_prepayment_by_year']
            total_cash_by_year = bs_data_result['total_cash_by_year']
            hist_bs_data = bs_data_result['hist_bs_data']
            hist_debt = bs_data_result['hist_debt']
            hist_inventory = bs_data_result['hist_inventory']
            hist_customer_prepayment = bs_data_result['hist_customer_prepayment']
            debt_breakdown = bs_data_result['debt_breakdown']
            inventory_breakdown = bs_data_result['inventory_breakdown']
            prepayment_breakdown = bs_data_result['prepayment_breakdown']
            cash_breakdown = bs_data_result['cash_breakdown']
            debt_change_breakdown = bs_data_result['debt_change_breakdown']
            inventory_change_breakdown = bs_data_result['inventory_change_breakdown']
            prepayment_change_breakdown = bs_data_result['prepayment_change_breakdown']
            cash_change_breakdown = bs_data_result['cash_change_breakdown']
        
            # Refine cash balances with interest income
            # The interest income was already calculated iteratively in P&L section
            interest_income_by_year_refined = {}
            cumulative_interest = 0
            
            for year_str in [str(y) for y in years]:
                # Use the interest income from the iterative calculation (already in interest_income_by_year)
                interest_income = interest_income_by_year.get(year_str, 0)
                interest_income_by_year_refined[year_str] = interest_income
                cumulative_interest += interest_income
                
                # Add cumulative interest to cash balance
                total_cash_by_year[year_str] += cumulative_interest
        
            # Now update the P&L interest income row with calculated values
            for year in years:
                year_str = str(year)
                if year_str in interest_income_by_year:
                    interest_income_row[year_str] = interest_income_by_year[year_str]
        
            # Populate breakdown data from the aggregation loop above
            # All detail balance sheet code has been moved inside tab_detail_bs above
            
            with tab_detail_bs:
                # Render detail balance sheet tab using utility function
                render_detail_bs_tab(
                    df_projects=df_projects,
                    hist_col=hist_col,
                    years=years,
                    base_year_str=base_year_str,
                    hist_debt=hist_debt,
                    hist_inventory=hist_inventory,
                    hist_customer_prepayment=hist_customer_prepayment,
                    debt_breakdown=debt_breakdown,
                    inventory_breakdown=inventory_breakdown,
                    prepayment_breakdown=prepayment_breakdown,
                    cash_breakdown=cash_breakdown,
                    debt_change_breakdown=debt_change_breakdown,
                    inventory_change_breakdown=inventory_change_breakdown,
                    prepayment_change_breakdown=prepayment_change_breakdown,
                    cash_change_breakdown=cash_change_breakdown,
                    total_debt_by_year=total_debt_by_year,
                    total_inventory_by_year=total_inventory_by_year,
                    total_customer_prepayment_by_year=total_customer_prepayment_by_year
                )
            
            with tab_consolidated_bs:
                # Initialize row dictionaries for consolidated BS
                cash_row = {}
                ar_row = {}
                inventory_row = {}
                other_assets_row = {}
                total_assets_row = {}
                ap_row = {}
                customer_prepayment_row = {}
                st_debt_row = {}
                lt_debt_row = {}
                other_liab_row = {}
                total_liab_row = {}
                retained_earnings_row = {}
                minority_interest_bs_row = {}
                other_equity_row = {}
                total_equity_row = {}
                
                # Render consolidated balance sheet tab using utility function
                render_consolidated_bs_tab(
                    hist_col=hist_col,
                    years=years,
                    hist_bs_data=hist_bs_data,
                    net_cf_by_year=net_cf_by_year,
                    total_inventory_by_year=total_inventory_by_year,
                    total_customer_prepayment_by_year=total_customer_prepayment_by_year,
                    total_debt_by_year=total_debt_by_year,
                    hist_customer_prepayment=hist_customer_prepayment,
                    npatmi_row=npatmi_row,
                    minority_interest_row=minority_interest_row,
                    cash_row=cash_row,
                    ar_row=ar_row,
                    inventory_row=inventory_row,
                    other_assets_row=other_assets_row,
                    total_assets_row=total_assets_row,
                    ap_row=ap_row,
                    customer_prepayment_row=customer_prepayment_row,
                    st_debt_row=st_debt_row,
                    lt_debt_row=lt_debt_row,
                    other_liab_row=other_liab_row,
                    total_liab_row=total_liab_row,
                    retained_earnings_row=retained_earnings_row,
                    minority_interest_bs_row=minority_interest_bs_row,
                    other_equity_row=other_equity_row,
                    total_equity_row=total_equity_row
                )
    
            # Section 7: Cash Flow Statements
            st.markdown("---")
            st.subheader("Cash Flow Statements")
            
            # Apply custom CSS for cash flow tabs (similar to balance sheet tabs)
            st.markdown("""
            <style>
            /* Custom tab styling for cash flow tabs */
            div[role="tablist"] {
                gap: 8px;
                background-color: rgba(255, 255, 255, 0.1);
                padding: 8px;
                border-radius: 8px;
            }
            
            /* Individual tab button styling - teal theme */
            div[role="tablist"] button {
                background-color: #173F35 !important;
                color: #FFFFFF !important;
                border-radius: 6px;
                font-weight: 500;
                padding: 10px 20px;
                transition: all 0.3s ease;
            }
            
            /* Hover effects */
            div[role="tablist"] button:hover {
                opacity: 0.85;
                transform: translateY(-2px);
                transition: all 0.3s ease;
                box-shadow: 0 4px 8px rgba(46, 125, 123, 0.3);
            }
            
            /* Active tab styling */
            div[role="tablist"] button[aria-selected="true"] {
                background: #08C179 !important;
                border-bottom: none !important;
                font-weight: bold !important;
                box-shadow: 0 6px 12px rgba(46, 125, 123, 0.4);
                transform: translateY(-2px);
                position: relative;
            }
            
            /* Override any default red coloring */
            .stTabs [data-baseweb="tab-highlight"] {
                background-color: transparent !important;
            }
            
            .stTabs [aria-selected="true"] {
                border-color: transparent !important;
            }
            </style>
            """, unsafe_allow_html=True)
        
            # Create cash flow rows using the utility function
            cf_rows, hist_operating_cf_detail, hist_investing_cf_detail, hist_financing_cf_detail = create_detail_cashflow_rows(
                years=years,
                hist_col=hist_col,
                historical_data=historical_data,
                hist_date_idx=hist_date_idx,
                operating_cf_by_year=operating_cf_by_year,
                investing_cf_by_year=investing_cf_by_year,
                financing_cf_by_year=financing_cf_by_year,
                net_cf_by_year=net_cf_by_year,
                presales_cf_breakdown=presales_cf_breakdown,
                interest_outflow_breakdown=interest_outflow_breakdown,
                sga_outflow_breakdown=sga_outflow_breakdown,
                tax_outflow_breakdown=tax_outflow_breakdown,
                land_outflow_breakdown=land_outflow_breakdown,
                construction_outflow_breakdown=construction_outflow_breakdown,
                financing_cf_breakdown=financing_cf_breakdown,
                other_segment_revenue_cf=other_segment_revenue_cf,
                other_segment_cogs_cf=other_segment_cogs_cf,
                existing_debt_interest_row=existing_debt_interest_row,
                sga_rows=sga_rows,
                interest_income_by_year=interest_income_by_year
            )

            # Create consolidated cash flow rows using the utility function
            consol_cf_rows, other_sga_cf_row = create_consolidated_cashflow_rows(
                years=years,
                hist_col=hist_col,
                hist_operating_cf=hist_operating_cf_detail,
                hist_investing_cf=hist_investing_cf_detail,
                hist_financing_cf=hist_financing_cf_detail,
                operating_cf_by_year=operating_cf_by_year,
                investing_cf_by_year=investing_cf_by_year,
                financing_cf_by_year=financing_cf_by_year,
                net_cf_by_year=net_cf_by_year,
                presales_cf_breakdown=presales_cf_breakdown,
                interest_outflow_breakdown=interest_outflow_breakdown,
                sga_outflow_breakdown=sga_outflow_breakdown,
                land_outflow_breakdown=land_outflow_breakdown,
                construction_outflow_breakdown=construction_outflow_breakdown,
                other_segment_revenue_cf=other_segment_revenue_cf,
                other_segment_cogs_cf=other_segment_cogs_cf,
                existing_debt_interest_row=existing_debt_interest_row,
                sga_rows=sga_rows,
                tax_row=tax_row,
                interest_income_by_year=interest_income_by_year,
                df_projects=df_projects
            )
            
            # Create tabs for cash flow statements
            tab_detail_cf, tab_consolidated_cf = st.tabs([
                "Detail Project Breakdown",
                "Consolidated Cash Flow"
            ])
            
            with tab_detail_cf:
                # Render the detail cash flow tab using the utility function
                render_detail_cf_tab(cf_rows, hist_col, years)
            
            with tab_consolidated_cf:
                # Render the consolidated cash flow tab using the utility function
                render_consolidated_cf_tab(consol_cf_rows, hist_col, years)
            
            # Add Valuation Section
            st.markdown("---")
            st.header("Valuation Analysis")
            
            # Render valuation sections (pass current forecast data and capture return data)
            valuation_data_raw = render_valuation_analysis(selected_ticker, npatmi_row, total_equity_row)
            
            # Process valuation data for saving
            from utils.model_forecast_save_to_db import prepare_valuation_data
            
            current_year = datetime.now().year
            next_year = current_year + 1
            
            # Prepare valuation data if we have the raw data
            valuation_data = None
            if valuation_data_raw:
                valuation_data = prepare_valuation_data(
                    current_price=valuation_data_raw.get('current_price', 0),
                    rnav_per_share=valuation_data_raw.get('rnav_per_share', 0),
                    rnav_details=valuation_data_raw.get('rnav_details', []),
                    pe_values=valuation_data_raw.get('pe_values', {}),
                    pb_values=valuation_data_raw.get('pb_values', {}),
                    pe_mean=valuation_data_raw.get('pe_mean'),
                    pb_mean=valuation_data_raw.get('pb_mean'),
                    current_year=current_year,
                    next_year=next_year
                )
            
            # Save Consolidated Financial Statements to MongoDB
            # Prepare all required parameters for the save function
            pnl_rows = {
                're_revenue_row': re_revenue_row,
                'revenue_row': revenue_row,
                're_cogs_row': re_cogs_row,
                'total_cogs_pnl_row': total_cogs_pnl_row,
                'gp_row': gp_row,
                'sga_row': sga_row,
                'ebitda_row': ebitda_row,
                'interest_income_row': interest_income_row,
                'project_interest_pnl_row': project_interest_pnl_row,
                'existing_interest_pnl_row': existing_interest_pnl_row,
                'interest_row': interest_row,
                'pbt_row': pbt_row,
                'tax_row': tax_row,
                'pat_row': pat_row,
                'minority_interest_row': minority_interest_row,
                'npatmi_row': npatmi_row
            }
            
            balance_sheet_rows = {
                'cash_row': cash_row,
                'ar_row': ar_row,
                'inventory_row': inventory_row,
                'other_assets_row': other_assets_row,
                'total_assets_row': total_assets_row,
                'ap_row': ap_row,
                'customer_prepayment_row': customer_prepayment_row,
                'st_debt_row': st_debt_row,
                'lt_debt_row': lt_debt_row,
                'total_debt_by_year': total_debt_by_year,
                'other_liab_row': other_liab_row,
                'total_liab_row': total_liab_row,
                'retained_earnings_row': retained_earnings_row,
                'minority_interest_bs_row': minority_interest_bs_row,
                'other_equity_row': other_equity_row,
                'total_equity_row': total_equity_row
            }
            
            cash_flow_aggregates = {
                'operating_cf_by_year': operating_cf_by_year,
                'investing_cf_by_year': investing_cf_by_year,
                'financing_cf_by_year': financing_cf_by_year,
                'net_cf_by_year': net_cf_by_year,
                'other_segment_revenue_cf': other_segment_revenue_cf,
                'other_segment_cogs_cf': other_segment_cogs_cf,
                'existing_debt_interest_row': existing_debt_interest_row,
                'other_sga_cf_row': other_sga_cf_row,
                'interest_income_row': interest_income_row
            }
            
            cash_flow_breakdowns = {
                'presales_cf_breakdown': presales_cf_breakdown,
                'interest_outflow_breakdown': interest_outflow_breakdown,
                'sga_outflow_breakdown': sga_outflow_breakdown,
                'tax_outflow_breakdown': tax_outflow_breakdown,
                'land_outflow_breakdown': land_outflow_breakdown,
                'construction_outflow_breakdown': construction_outflow_breakdown,
                'financing_cf_breakdown': financing_cf_breakdown
            }
            
            project_breakdowns = {
                'project_revenue_breakdown': project_revenue_breakdown,
                'project_cogs_breakdown': project_cogs_breakdown,
                'project_sga_breakdown': project_sga_breakdown,
                'project_interest_breakdown': project_interest_breakdown,
                'project_pbt_breakdown': project_pbt_breakdown,
                'project_pat_breakdown': project_pat_breakdown,
                'project_patmi_breakdown': project_patmi_breakdown,
                'project_minority_interest_breakdown': project_minority_interest_breakdown,
                'project_revenue_by_year': project_revenue_by_year,
                'project_cogs_by_year': project_cogs_by_year
            }
            
            segment_data = {
                'segment_revenue_data': segment_revenue_data,
                'segment_cogs_data': segment_cogs_data
            }
            
            balance_sheet_details = {
                'debt_change_breakdown': debt_change_breakdown,
                'inventory_change_breakdown': inventory_change_breakdown,
                'prepayment_change_breakdown': prepayment_change_breakdown,
                'cash_change_breakdown': cash_change_breakdown
            }
            
            session_state_data = {
                'base_year_revenues': st.session_state.base_year_revenues
            }
            
            # Render the save section using the utility function
            render_save_section(
                selected_ticker,
                base_year,
                years,
                pnl_rows,
                balance_sheet_rows,
                cash_flow_aggregates,
                cash_flow_breakdowns,
                project_breakdowns,
                segment_data,
                balance_sheet_details,
                session_state_data,
                valuation_data
            )
        
        else:
            st.info("No project data available. Please add projects in the Project Pipeline tab.")
    

