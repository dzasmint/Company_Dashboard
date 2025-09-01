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
    render_minority_interest_tab
)
from utils.model_forecast_cashflow_utils import (
    create_detail_cashflow_rows,
    create_consolidated_cashflow_rows,
    render_detail_cf_tab,
    render_consolidated_cf_tab
)


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
        
        # Revenue Forecast from Projects (data preparation)
        revenue_forecast = self.generate_revenue_forecast()
    
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
        base_year = st.session_state.get('base_year', 2024)  # Default to 2024 if not set
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
            years = revenue_forecast['years']
            current_year = datetime.now().year
        
            # Get base year from session state
            base_year = st.session_state.get('base_year', datetime.now().year - 1)
            hist_col = f'{base_year}H'  # Historical column name
        
            # Add historical year to display columns
            display_years = [hist_col] + [str(y) for y in years]
        
            # Initialize data structures
            project_revenue_by_year = {}
            project_cogs_by_year = {}
            other_revenue_by_year = {}
            other_cogs_by_year = {}
        
            # Store individual project details for breakdown
            project_revenue_breakdown = {}
            project_cogs_breakdown = {}
            project_land_breakdown = {}
            project_sga_breakdown = {}
            project_interest_breakdown = {}
            project_pat_breakdown = {}
            project_patmi_breakdown = {}
            project_minority_interest_breakdown = {}
            
            # Initialize P&L rows that will be populated later
            minority_interest_row = {'P&L Item': 'Minority Interest'}
            minority_interest_row[hist_col] = hist_values.get('Minority Interest', 0)  # Historical from CSV
            npatmi_row = {'P&L Item': 'NPATMI (Net Profit After Tax and MI)'}
            npatmi_row[hist_col] = hist_values.get('NPATMI (Net Profit After Tax and MI)', 0)  # Historical
            revenue_row = {'P&L Item': 'Net Revenue'}
            revenue_row[hist_col] = hist_values.get('Net Revenue', 0)  # Historical, will be updated later with forecast values
        
            # Store other business segment revenue breakdown
            other_revenue_breakdown = {}
        
            # Track logged projects for debug output
            logged_projects = set()
        
            # Load project schedules from MongoDB P&L schedule
            for year in years:
                project_revenue_by_year[year] = 0
                project_cogs_by_year[year] = 0
            
                for _, project in df_projects.iterrows():
                    project_name = project.get('project_name', 'Unknown')
                
                    # Initialize project breakdown if not exists
                    if project_name not in project_revenue_breakdown:
                        project_revenue_breakdown[project_name] = {}
                        project_cogs_breakdown[project_name] = {}
                        project_land_breakdown[project_name] = {}
                        project_sga_breakdown[project_name] = {}
                        project_interest_breakdown[project_name] = {}
                        project_pat_breakdown[project_name] = {}
                        project_patmi_breakdown[project_name] = {}
                
                    # Get data from comprehensive_financial_statements only
                    financial_statements = project.get('comprehensive_financial_statements', {})
                
                    # Ensure schedule is a dictionary
                    if not isinstance(financial_statements, dict):
                        financial_statements = {}
                
                    # Add to yearly totals
                    year_str = str(year)
                
                    if year_str in financial_statements:
                        year_data = financial_statements[year_str]
                    
                        # Process data from comprehensive_financial_statements
                        # Values are in raw VND, expenses are already negative in MongoDB
                        
                        # Get revenue (convert to billions)
                        revenue_amount = year_data.get('revenue_recognition', 0) / 1e9
                        project_revenue_by_year[year] += revenue_amount
                        project_revenue_breakdown[project_name][year] = revenue_amount
                    
                        # Get COGS - already negative in MongoDB (convert to billions)
                        project_cogs = year_data.get('cogs', 0) / 1e9  # Already negative in DB
                        project_cogs_breakdown[project_name][year] = project_cogs
                        project_cogs_by_year[year] += project_cogs
                    
                        # Get land cost separately for breakdown (convert to billions)
                        land_cost = year_data.get('land_cost', 0) / 1e9
                        project_land_breakdown[project_name][year] = land_cost
                    
                        # Get SG&A - already negative in MongoDB (convert to billions)
                        sga_amount = year_data.get('sga_expense', 0) / 1e9  # Already negative in DB
                        project_sga_breakdown[project_name][year] = sga_amount
                    
                        # Get Interest expense from P&L - already negative in MongoDB (convert to billions)
                        interest_amount     = year_data.get('interest_expense_cash', 0) / 1e9  # Already negative in DB
                        project_interest_breakdown[project_name][year] = interest_amount
                        
                        # Get PAT directly from database (convert to billions)
                        project_pat = year_data.get('pat', 0) / 1e9
                        project_pat_breakdown[project_name][year] = project_pat
                        
                        # Get project ownership to calculate minority interest and PATMI
                        project_ownership = project.get('project_ownership', 1.0)
                        
                        # Calculate minority interest and PATMI based on ownership
                        #if project_ownership <= 1.0:
                        # Calculate minority interest = PAT * (1 - ownership)
                        minority_stake = 1 - project_ownership
                        minority_interest_value = project_pat * minority_stake
                        
                        # Store minority interest breakdown
                        if project_name not in project_minority_interest_breakdown:
                            project_minority_interest_breakdown[project_name] = {}
                        project_minority_interest_breakdown[project_name][year] = {
                            'ownership': project_ownership,
                            'minority_stake': minority_stake,
                            'project_pat': project_pat,
                            'minority_interest': minority_interest_value
                        }
                        
                        # Calculate PATMI = PAT - Minority Interest
                        project_patmi_value = project_pat - minority_interest_value
                        #else:
                            # 100% ownership - no minority interest
                        #    project_patmi_value = project_pat
                        
                        # Store PATMI
                        project_patmi_breakdown[project_name][year] = project_patmi_value
                    
                        # Debug: Log first project's values for verification
                        if year == years[0] and project_name not in logged_projects:
                            logged_projects.add(project_name)
                    else:
                        # No data for this year
                        project_revenue_breakdown[project_name][year] = 0
                        project_cogs_breakdown[project_name][year] = 0
                        project_land_breakdown[project_name][year] = 0
                        project_sga_breakdown[project_name][year] = 0
                        project_interest_breakdown[project_name][year] = 0
                        project_pat_breakdown[project_name][year] = 0
                        project_patmi_breakdown[project_name][year] = 0
        
            # Calculate other revenue streams and COGS
            for year_idx, year in enumerate(years):
                other_revenue_by_year[year] = 0
                other_cogs_by_year[year] = 0
            
                # Check if base_year_revenues exists and has items
                if 'base_year_revenues' not in st.session_state:
                    st.session_state.base_year_revenues = {}
            
                for segment_name, base_revenue in st.session_state.base_year_revenues.items():
                    # Initialize segment breakdown if not exists
                    if segment_name not in other_revenue_breakdown:
                        other_revenue_breakdown[segment_name] = {}
                
                    # Get metrics from segment_metrics if available
                    if segment_name in segment_metrics:
                        growth_rate = segment_metrics[segment_name]['revenue_growth']
                        gross_margin = segment_metrics[segment_name]['gross_margin']
                    else:
                        # Fallback to defaults
                        growth_rate = 0.0  # Default 0%
                        gross_margin = 0.0  # Default 0%
                
                    # Calculate revenue with growth
                    # Base year is the latest historical year, apply growth from there
                    years_from_base = year - base_year
                    year_revenue = base_revenue * ((1 + growth_rate) ** years_from_base)
                
                    # Store in breakdown by segment
                    other_revenue_breakdown[segment_name][str(year)] = year_revenue
                    other_revenue_by_year[year] += year_revenue
                
                    # Calculate COGS from gross margin
                    year_cogs = year_revenue * (1 - gross_margin)
                    other_cogs_by_year[year] += year_cogs
        
            # Display data source indicator if we have projects
            if not df_projects.empty:
                st.toast(f"✅ {len(df_projects)} project(s) using Comprehensive Financial Statements from DB")
        
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
            cumulative_debt = 0
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
        
            # Calculate Minority Interest with project-level breakdown
            # For forecast years: aggregate from projects based on (1 - ownership) * project PAT
            # For historical: load from CSV
        
            # Continue populating minority interest data (already initialized earlier)
        
            for year in years:
                year_str = str(year)
                total_minority_interest = 0
            
                # Calculate minority interest for each project
                for project_name in project_revenue_breakdown.keys():
                    # Find the project in df_projects to get ownership
                    project_found = False
                    project_ownership = 1.0  # Default to 100% ownership
                
                    for _, project in df_projects.iterrows():
                        if project.get('project_name') == project_name:
                            project_found = True
                            # Get project ownership (default to 1.0 = 100% if not specified)
                            project_ownership = project.get('project_ownership', 1.0)
                            break
                
                    if project_found and project_ownership < 1.0:  # Only process if there's minority ownership
                        # Calculate project PAT for this year
                        # Project PAT = Project Revenue - Project COGS - Project SG&A - Project Interest - Tax
                        project_revenue = project_revenue_breakdown[project_name].get(year, 0)
                        project_cogs = project_cogs_breakdown[project_name].get(year, 0)
                        project_sga = project_sga_breakdown[project_name].get(year, 0)
                        project_interest = project_interest_breakdown[project_name].get(year, 0)
                    
                        # Calculate project PBT
                        project_pbt = project_revenue + project_cogs + project_sga + project_interest
                    
                        # Calculate project tax (using tax rate from assumptions)
                        project_tax = -max(0, project_pbt * tax_rate)
                    
                        # Calculate project PAT
                        project_pat = project_pbt + project_tax
                    
                        # Calculate minority interest for this project
                        # Minority Interest = PAT * (1 - Ownership)
                        # Minority shareholders share in both profits and losses
                        minority_stake = 1 - project_ownership
                        project_minority_interest = project_pat * minority_stake
                        total_minority_interest += project_minority_interest
                    
                        # Store breakdown for display (only if there's minority interest)
                        if project_name not in project_minority_interest_breakdown:
                            project_minority_interest_breakdown[project_name] = {}
                        project_minority_interest_breakdown[project_name][year] = {
                            'ownership': project_ownership,
                            'minority_stake': minority_stake,
                            'project_pat': project_pat,
                            'minority_interest': project_minority_interest
                        }
            
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
        
            # Key metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                avg_revenue_growth = ((total_revenue_row[str(years[-1])] / total_revenue_row[str(years[0])]) ** (1/len(years)) - 1) * 100 if len(years) > 1 else 0
                st.metric("Avg Revenue Growth", f"{avg_revenue_growth:.1f}%")
            with col2:
                # Calculate average gross margin from margin_df
                overall_margins = []
                for year in years:
                    year_str = str(year)
                    revenue = total_revenue_row[year_str]
                    if revenue > 0:
                        gross_profit = total_gp_row[year_str]
                        overall_margins.append((gross_profit / revenue) * 100)
                avg_gross_margin = sum(overall_margins) / len(overall_margins) if overall_margins else 0
                st.metric("Avg Gross Margin", f"{avg_gross_margin:.1f}%")
            with col3:
                # Calculate EBITDA margin
                total_ebitda = sum([ebitda_row[str(y)] for y in years])
                total_revenue = sum([revenue_row[str(y)] for y in years])
                avg_ebitda_margin = (total_ebitda / total_revenue * 100) if total_revenue > 0 else 0
                st.metric("Avg EBITDA Margin", f"{avg_ebitda_margin:.1f}%")
            with col4:
                # Calculate PAT margin
                total_pat = sum([pat_row[str(y)] for y in years])
                avg_pat_margin = (total_pat / total_revenue * 100) if total_revenue > 0 else 0
                st.metric("Avg PAT Margin", f"{avg_pat_margin:.1f}%")
        
            # Pre-calculate cash flows (needed for balance sheet cash calculation)
            # Initialize cash flow aggregates
            operating_cf_by_year = {}
            investing_cf_by_year = {}
            financing_cf_by_year = {}
            net_cf_by_year = {}
            
            # Initialize breakdown components
            other_segment_revenue_cf = {}
            other_segment_cogs_cf = {}
            presales_cf_breakdown = {}
            interest_outflow_breakdown = {}
            sga_outflow_breakdown = {}
            tax_outflow_breakdown = {}
            land_outflow_breakdown = {}
            construction_outflow_breakdown = {}
            investing_cf_breakdown = {}
            financing_cf_breakdown = {}
            
            # Initialize for all years
            for year in years:
                year_str = str(year)
                operating_cf_by_year[year_str] = 0
                investing_cf_by_year[year_str] = 0
                financing_cf_by_year[year_str] = 0
                net_cf_by_year[year_str] = 0
                other_segment_revenue_cf[year_str] = 0
                other_segment_cogs_cf[year_str] = 0
            
            # 1. Calculate revenue and COGS from other business segments (non-real estate)
            if other_revenue_breakdown:
                for segment_name, segment_revenue in other_revenue_breakdown.items():
                    for year in years:
                        year_str = str(year)
                        revenue = segment_revenue.get(year_str, 0)
                        other_segment_revenue_cf[year_str] += revenue
                        operating_cf_by_year[year_str] += revenue
                        
                        # Calculate COGS for this segment
                        if segment_name in segment_metrics:
                            gross_margin = segment_metrics[segment_name]['gross_margin']
                        else:
                            gross_margin = 0.0
                        
                        segment_cogs = revenue * (1 - gross_margin)
                        other_segment_cogs_cf[year_str] += segment_cogs
                        operating_cf_by_year[year_str] -= segment_cogs
            
            # 2. Aggregate cash flows from all projects
            for _, project in df_projects.iterrows():
                project_name = project.get('project_name', 'Unknown')
                financial_statements = project.get('comprehensive_financial_statements', {})
                
                if not isinstance(financial_statements, dict):
                    financial_statements = {}
                
                # Initialize project breakdown
                if project_name not in presales_cf_breakdown:
                    presales_cf_breakdown[project_name] = {}
                    interest_outflow_breakdown[project_name] = {}
                    sga_outflow_breakdown[project_name] = {}
                    tax_outflow_breakdown[project_name] = {}
                    land_outflow_breakdown[project_name] = {}
                    construction_outflow_breakdown[project_name] = {}
                    investing_cf_breakdown[project_name] = {}
                    financing_cf_breakdown[project_name] = {}
                
                for year in years:
                    year_str = str(year)
                    
                    if year_str in financial_statements:
                        year_data = financial_statements[year_str]
                        
                        # Operating Cash Flow Components
                        presales_inflow = year_data.get('cash_inflow_presales', 0) / 1e9
                        presales_cf_breakdown[project_name][year_str] = presales_inflow
                        operating_cf_by_year[year_str] += presales_inflow
                        
                        interest_outflow = year_data.get('cash_outflow_interest', 0) / 1e9
                        interest_outflow_breakdown[project_name][year_str] = interest_outflow
                        operating_cf_by_year[year_str] += interest_outflow
                        
                        sga_outflow = year_data.get('cash_outflow_sga', 0) / 1e9
                        sga_outflow_breakdown[project_name][year_str] = sga_outflow
                        operating_cf_by_year[year_str] += sga_outflow
                        
                        tax_outflow = year_data.get('cash_outflow_tax', 0) / 1e9
                        tax_outflow_breakdown[project_name][year_str] = tax_outflow
                        operating_cf_by_year[year_str] += tax_outflow
                        
                        # Investing Cash Flow
                        land_outflow = year_data.get('cash_outflow_land', 0) / 1e9
                        construction_outflow = year_data.get('cash_outflow_construction', 0) / 1e9
                        
                        land_outflow_breakdown[project_name][year_str] = land_outflow
                        construction_outflow_breakdown[project_name][year_str] = construction_outflow
                        
                        investing_cf = land_outflow + construction_outflow
                        investing_cf_by_year[year_str] += investing_cf
                        investing_cf_breakdown[project_name][year_str] = investing_cf
                        
                        # Financing Cash Flow
                        debt_disbursement = year_data.get('debt_disbursement', 0) / 1e9
                        debt_repayment = year_data.get('debt_repayment', 0) / 1e9
                        financing_cf = debt_disbursement + debt_repayment
                        financing_cf_by_year[year_str] += financing_cf
                        financing_cf_breakdown[project_name][year_str] = financing_cf
                    else:
                        presales_cf_breakdown[project_name][year_str] = 0
                        interest_outflow_breakdown[project_name][year_str] = 0
                        sga_outflow_breakdown[project_name][year_str] = 0
                        tax_outflow_breakdown[project_name][year_str] = 0
                        land_outflow_breakdown[project_name][year_str] = 0
                        construction_outflow_breakdown[project_name][year_str] = 0
                        investing_cf_breakdown[project_name][year_str] = 0
                        financing_cf_breakdown[project_name][year_str] = 0
            
            # Add existing debt interest expense to operating cash flow
            for year in years:
                year_str = str(year)
                existing_debt_interest = existing_debt_interest_row.get(str(year), 0)
                operating_cf_by_year[year_str] += existing_debt_interest
            
            # Add SG&A expense from other segments to operating cash flow
            for year in years:
                year_str = str(year)
                total_sga = 0
                for row in sga_rows:
                    if row['SG&A Source'] == 'TOTAL SG&A':
                        total_sga = row.get(str(year), 0)
                        break
                total_proj_sga = sum(sga_outflow_breakdown.get(proj, {}).get(year_str, 0) for proj in sga_outflow_breakdown.keys())
                other_sga = total_sga - total_proj_sga
                operating_cf_by_year[year_str] += other_sga
            
            # Add total tax expense to operating cash flow
            for year in years:
                year_str = str(year)
                project_taxes = sum(tax_outflow_breakdown.get(proj, {}).get(year_str, 0) for proj in tax_outflow_breakdown.keys())
                operating_cf_by_year[year_str] -= project_taxes
                total_tax_pnl = tax_row.get(year_str, 0)
                operating_cf_by_year[year_str] += total_tax_pnl
            
            # Add interest income to investing cash flow
            for year in years:
                year_str = str(year)
                interest_income_cf = interest_income_by_year.get(year_str, 0)
                investing_cf_by_year[year_str] += interest_income_cf
            
            # Calculate net cash flow for each year
            for year in years:
                year_str = str(year)
                net_cf_by_year[year_str] = (
                    operating_cf_by_year[year_str] + 
                    investing_cf_by_year[year_str] + 
                    financing_cf_by_year[year_str]
                )
            
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
            
            # Initialize aggregated balance sheet data (needed by both tabs)
            total_debt_by_year = {hist_col: 0}
            total_inventory_by_year = {hist_col: 0}
            total_customer_prepayment_by_year = {hist_col: 0}
            total_cash_by_year = {hist_col: 0}
        
            for year in years:
                year_str = str(year)
                total_debt_by_year[year_str] = 0
                total_inventory_by_year[year_str] = 0
                total_customer_prepayment_by_year[year_str] = 0
                total_cash_by_year[year_str] = 0
        
            # Load historical balance sheet data for consolidated balance sheet
            hist_bs_data = {}
            if historical_data is not None and not historical_data.empty and hist_date_idx is not None:
                # Map of display names to column names in FA_A_processed.parquet
                bs_mapping = {
                    'Cash & Equivalents': ['Cash_Equivalent', 'Cash'],
                    'Account Receivable': ['Account_Receivable'],
                    'Inventory': ['Inventory'],
                    'Total Current Assets': ['Current_Asset'],
                    'Tangible Fixed Assets': ['Tangible_Fixed_Asset'],
                    'Total Assets': ['Total_Asset'],
                    'Account Payable': ['Account_Payable'],
                    'Customer Prepayment': ['Advance_From_Custmers'],  # Note the typo in the KEYCODE
                    'Short-term Debt': ['ST_Debt'],
                    'Current Liabilities': ['Current_Liabilities'],
                    'Long-term Debt': ['LT_Debt'],
                    'Total Liabilities': ['Total_Liabilities'],
                    'Retained Earnings': ['Retain_Earning'],
                    'Minority Interest': ['Minority_Interest'],
                    'Total Equity': ['TOTAL_Equity']
                }
                
                # Extract historical values
                for display_name, col_names in bs_mapping.items():
                    value = 0
                    for col_name in col_names:
                        if col_name in historical_data.columns:
                            try:
                                raw_value = historical_data.loc[hist_date_idx, col_name]
                                if not pd.isna(raw_value):
                                    value += raw_value
                            except:
                                pass
                    hist_bs_data[display_name] = value / 1e9  # Convert to billions
            
            # Use consolidated balance sheet historical values for consistency
            hist_debt = hist_bs_data.get('Short-term Debt', 0) + hist_bs_data.get('Long-term Debt', 0)
            hist_inventory = hist_bs_data.get('Inventory', 0)
            hist_cash = hist_bs_data.get('Cash & Equivalents', 0)
            hist_customer_prepayment = hist_bs_data.get('Customer Prepayment', 0)
            hist_retained_earnings = hist_bs_data.get('Retained Earnings', 0)
            hist_minority_interest = hist_bs_data.get('Minority Interest', 0)
        
            # First, initialize with historical values as starting point
            # These will be the base for cumulative calculations
            cumulative_debt = hist_debt
            cumulative_inventory = hist_inventory
            cumulative_prepayment = hist_customer_prepayment
            cumulative_cash = hist_cash
        
            # Store year-over-year changes for each project
            debt_changes_by_year = {year_str: 0 for year_str in [str(y) for y in years]}
            inventory_changes_by_year = {year_str: 0 for year_str in [str(y) for y in years]}
            prepayment_changes_by_year = {year_str: 0 for year_str in [str(y) for y in years]}
            cash_changes_by_year = {year_str: 0 for year_str in [str(y) for y in years]}
        
            # Aggregate changes from all projects
            for _, project in df_projects.iterrows():
                financial_statements = project.get('comprehensive_financial_statements', {})
                project_name = project.get('project_name', 'Unknown')
                
                # Ensure financial_statements is a dictionary
                if not isinstance(financial_statements, dict):
                    financial_statements = {}
            
                # Track previous year values for this project to calculate changes
                # Check if project has historical data (base year) for proper initialization
                base_year_str = str(base_year)
                prev_debt = 0
                prev_inventory = 0
                prev_prepayment = 0
                prev_cash = 0
                
                # If project has historical year data, use it as starting point
                if base_year_str in financial_statements:
                    hist_data = financial_statements[base_year_str]
                    
                    # Get historical inventory
                    if 'inventory_balance' in hist_data:
                        prev_inventory = hist_data.get('inventory_balance', 0) / 1e9
                    elif 'Inventory_Balance' in hist_data:
                        prev_inventory = hist_data.get('Inventory_Balance', 0) / 1e9
                    
                    # Get historical debt
                    if 'debt_balance' in hist_data:
                        prev_debt = hist_data.get('debt_balance', 0) / 1e9
                    elif 'Debt_Balance' in hist_data:
                        prev_debt = hist_data.get('Debt_Balance', 0) / 1e9
                    
                    # Get historical prepayment
                    if 'customer_prepayment_balance' in hist_data:
                        prev_prepayment = hist_data.get('customer_prepayment_balance', 0) / 1e9
                    elif 'Customer_Prepayment_Balance' in hist_data:
                        prev_prepayment = hist_data.get('Customer_Prepayment_Balance', 0) / 1e9
                    
                    # Note: prev_cash typically stays at 0 as cash is cumulative from project start
            
                for year in years:
                    year_str = str(year)
                
                    if year_str in financial_statements:
                        year_data = financial_statements[year_str]
                    
                        # Get current year debt balance
                        current_debt = 0
                        if 'debt_balance' in year_data:
                            current_debt = year_data.get('debt_balance', 0) / 1e9
                        elif 'Debt_Balance' in year_data:
                            current_debt = year_data.get('Debt_Balance', 0) / 1e9
                        # Calculate net change and add to total changes
                        debt_changes_by_year[year_str] += (current_debt - prev_debt)
                        prev_debt = current_debt
                    
                        # Get current year inventory balance
                        current_inventory = 0
                        if 'inventory_balance' in year_data:
                            current_inventory = year_data.get('inventory_balance', 0) / 1e9
                        elif 'Inventory_Balance' in year_data:
                            current_inventory = year_data.get('Inventory_Balance', 0) / 1e9
                        
                        # Calculate net change (current year - previous year)
                        inventory_change = current_inventory - prev_inventory
                        inventory_changes_by_year[year_str] += inventory_change
                        
                        # Update prev_inventory for next year's calculation
                        prev_inventory = current_inventory
                    
                        # Get current year customer prepayment balance
                        current_prepayment = 0
                        if 'customer_prepayment_balance' in year_data:
                            current_prepayment = year_data.get('customer_prepayment_balance', 0) / 1e9
                        elif 'Customer_Prepayment_Balance' in year_data:
                            current_prepayment = year_data.get('Customer_Prepayment_Balance', 0) / 1e9
                        # Calculate net change and add to total changes
                        prepayment_changes_by_year[year_str] += (current_prepayment - prev_prepayment)
                        prev_prepayment = current_prepayment
                    
                        # For cash, we can use cash_balance_change directly if available
                        if 'cash_balance_change' in year_data:
                            cash_changes_by_year[year_str] += year_data.get('cash_balance_change', 0) / 1e9
                        elif 'Cash_Balance_Change' in year_data:
                            cash_changes_by_year[year_str] += year_data.get('Cash_Balance_Change', 0) / 1e9
                        else:
                            # Calculate from cumulative balance if available
                            current_cash = 0
                            if 'cumulative_cash_balance' in year_data:
                                current_cash = year_data.get('cumulative_cash_balance', 0) / 1e9
                            elif 'Cumulative_Cash_Balance' in year_data:
                                current_cash = year_data.get('Cumulative_Cash_Balance', 0) / 1e9
                            # Calculate net change
                            cash_changes_by_year[year_str] += (current_cash - prev_cash)
                            prev_cash = current_cash
        
            # Recalculate interest income with more accurate cash balances
            # (This refines the preliminary calculation done before P&L)
            interest_income_by_year_refined = {}
            
            # First pass: calculate cumulative totals WITHOUT interest income
            for year_str in [str(y) for y in years]:
                # Add the year's changes to the cumulative totals
                cumulative_debt += debt_changes_by_year[year_str]
                cumulative_inventory += inventory_changes_by_year[year_str]
                cumulative_prepayment += prepayment_changes_by_year[year_str]
                cumulative_cash += cash_changes_by_year[year_str]
                
                # Store the base totals (before interest income)
                total_debt_by_year[year_str] = cumulative_debt
                total_inventory_by_year[year_str] = cumulative_inventory
                total_customer_prepayment_by_year[year_str] = cumulative_prepayment
                total_cash_by_year[year_str] = cumulative_cash
            
            # Second pass: use the interest income already calculated iteratively in P&L section
            # This ensures consistency across all financial statements
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
            
            # Track breakdown by project for debugging
            debt_breakdown = {}
            inventory_breakdown = {}
            prepayment_breakdown = {}
            cash_breakdown = {}
            
            # Initialize change breakdown variables at broader scope for save function
            debt_change_breakdown = {}
            inventory_change_breakdown = {}
            prepayment_change_breakdown = {}
            cash_change_breakdown = {}
        
            # Populate breakdown data from the aggregation loop above
            # All detail balance sheet code has been moved inside tab_detail_bs above
            
            # Format function to handle NaN values (used by both tabs)
            def format_bs_value(x):
                if pd.isna(x) or x is None:
                    return "-"
                try:
                    return f"{int(x):,}"
                except (ValueError, OverflowError):
                    return f"{x:,.0f}"
            
            with tab_detail_bs:
                # Detail Project Breakdown Balance Sheet content
                bs_rows = []
                
                # Build Detail Project Breakdown Balance Sheet
                for _, project in df_projects.iterrows():
                    project_name = project.get('project_name', 'Unknown')
                    financial_statements = project.get('comprehensive_financial_statements', {})
                    
                    # Ensure financial_statements is a dictionary
                    if not isinstance(financial_statements, dict):
                        financial_statements = {}
                
                    # Initialize project breakdown
                    debt_breakdown[project_name] = {hist_col: 0}
                    inventory_breakdown[project_name] = {hist_col: 0}
                    prepayment_breakdown[project_name] = {hist_col: 0}
                    cash_breakdown[project_name] = {hist_col: 0}
                
                    # Track cumulative cash for this project
                    project_cumulative_cash = 0
                
                    for year in years:
                        year_str = str(year)
                        debt_breakdown[project_name][year_str] = 0
                        inventory_breakdown[project_name][year_str] = 0
                        prepayment_breakdown[project_name][year_str] = 0
                        cash_breakdown[project_name][year_str] = 0
                    
                        if year_str in financial_statements:
                            year_data = financial_statements[year_str]
                        
                            # Get debt for this project
                            if 'debt_balance' in year_data:
                                debt_breakdown[project_name][year_str] = year_data.get('debt_balance', 0) / 1e9
                            elif 'Debt_Balance' in year_data:
                                debt_breakdown[project_name][year_str] = year_data.get('Debt_Balance', 0) / 1e9
                        
                            # Get inventory for this project
                            if 'inventory_balance' in year_data:
                                inventory_breakdown[project_name][year_str] = year_data.get('inventory_balance', 0) / 1e9
                            elif 'Inventory_Balance' in year_data:
                                inventory_breakdown[project_name][year_str] = year_data.get('Inventory_Balance', 0) / 1e9
                        
                            # Get customer prepayment for this project
                            if 'customer_prepayment_balance' in year_data:
                                prepayment_breakdown[project_name][year_str] = year_data.get('customer_prepayment_balance', 0) / 1e9
                            elif 'Customer_Prepayment_Balance' in year_data:
                                prepayment_breakdown[project_name][year_str] = year_data.get('Customer_Prepayment_Balance', 0) / 1e9
                        
                            # Get cash for this project
                            if 'cumulative_cash_balance' in year_data:
                                cash_breakdown[project_name][year_str] = year_data.get('cumulative_cash_balance', 0) / 1e9
                            elif 'Cumulative_Cash_Balance' in year_data:
                                cash_breakdown[project_name][year_str] = year_data.get('Cumulative_Cash_Balance', 0) / 1e9
                            elif 'cash_balance_change' in year_data or 'Cash_Balance_Change' in year_data:
                                cash_change = year_data.get('cash_balance_change', year_data.get('Cash_Balance_Change', 0)) / 1e9
                                project_cumulative_cash += cash_change
                                cash_breakdown[project_name][year_str] = project_cumulative_cash
            
                # Create balance sheet rows with breakdown
                # Note: Individual project rows show the project's balance at each year
                # Total rows show cumulative company-wide balance (historical + all project changes)
            
                # DEBT SECTION - Show changes for each project
                # Calculate debt changes for each project (use broader scope variable)
                for project_name in debt_breakdown.keys():
                    debt_change_breakdown[project_name] = {}
                    prev_value = 0  # Projects start with 0 debt in historical year
                    
                    # Check if project has historical debt
                    financial_statements = None
                    for _, project in df_projects.iterrows():
                        if project.get('project_name', 'Unknown') == project_name:
                            financial_statements = project.get('comprehensive_financial_statements', {})
                            break
                    
                    if financial_statements and base_year_str in financial_statements:
                        hist_data = financial_statements[base_year_str]
                        if 'debt_balance' in hist_data:
                            prev_value = hist_data.get('debt_balance', 0) / 1e9
                        elif 'Debt_Balance' in hist_data:
                            prev_value = hist_data.get('Debt_Balance', 0) / 1e9
                    
                    for year in years:
                        year_str = str(year)
                        current_value = debt_breakdown[project_name].get(year_str, 0)
                        change = current_value - prev_value
                        debt_change_breakdown[project_name][year_str] = change
                        prev_value = current_value
                
                # Add individual project debt change rows
                for project_name in debt_change_breakdown.keys():
                    project_debt_row = {'Balance Sheet Item': f'  {project_name} Debt Change'}
                    project_debt_row[hist_col] = 0  # No historical changes
                    for year in years:
                        project_debt_row[str(year)] = debt_change_breakdown[project_name][str(year)]
                    bs_rows.append(project_debt_row)
            
                # Total Debt row (previous year + sum of changes)
                debt_row = {'Balance Sheet Item': 'TOTAL DEBT'}
                debt_row[hist_col] = hist_debt
                for year in years:
                    debt_row[str(year)] = total_debt_by_year[str(year)]
                bs_rows.append(debt_row)
            
                # INVENTORY SECTION - Show changes for each project
                # Calculate inventory changes for each project (use broader scope variable)
                for project_name in inventory_breakdown.keys():
                    inventory_change_breakdown[project_name] = {}
                    prev_value = 0  # Projects start with 0 inventory in historical year
                    
                    # Check if project has historical inventory
                    financial_statements = None
                    for _, project in df_projects.iterrows():
                        if project.get('project_name', 'Unknown') == project_name:
                            financial_statements = project.get('comprehensive_financial_statements', {})
                            break
                    
                    if financial_statements and base_year_str in financial_statements:
                        hist_data = financial_statements[base_year_str]
                        if 'inventory_balance' in hist_data:
                            prev_value = hist_data.get('inventory_balance', 0) / 1e9
                        elif 'Inventory_Balance' in hist_data:
                            prev_value = hist_data.get('Inventory_Balance', 0) / 1e9
                    
                    for year in years:
                        year_str = str(year)
                        current_value = inventory_breakdown[project_name].get(year_str, 0)
                        change = current_value - prev_value
                        inventory_change_breakdown[project_name][year_str] = change
                        prev_value = current_value
                
                # Add individual project inventory change rows
                for project_name in inventory_change_breakdown.keys():
                    project_inv_row = {'Balance Sheet Item': f'  {project_name} Inventory Change'}
                    project_inv_row[hist_col] = 0  # No historical changes
                    for year in years:
                        project_inv_row[str(year)] = inventory_change_breakdown[project_name][str(year)]
                    bs_rows.append(project_inv_row)
            
                # Total Inventory row (previous year + sum of changes)
                inventory_row = {'Balance Sheet Item': 'TOTAL INVENTORY'}
                inventory_row[hist_col] = hist_inventory
                for year in years:
                    inventory_row[str(year)] = total_inventory_by_year[str(year)]
                bs_rows.append(inventory_row)
            
                # CUSTOMER PREPAYMENT SECTION - Show changes for each project
                # Calculate prepayment changes for each project (use broader scope variable)
                for project_name in prepayment_breakdown.keys():
                    prepayment_change_breakdown[project_name] = {}
                    prev_value = 0  # Projects start with 0 prepayment in historical year
                    
                    # Check if project has historical prepayment
                    financial_statements = None
                    for _, project in df_projects.iterrows():
                        if project.get('project_name', 'Unknown') == project_name:
                            financial_statements = project.get('comprehensive_financial_statements', {})
                            break
                    
                    if financial_statements and base_year_str in financial_statements:
                        hist_data = financial_statements[base_year_str]
                        if 'customer_prepayment_balance' in hist_data:
                            prev_value = hist_data.get('customer_prepayment_balance', 0) / 1e9
                        elif 'Customer_Prepayment_Balance' in hist_data:
                            prev_value = hist_data.get('Customer_Prepayment_Balance', 0) / 1e9
                    
                    for year in years:
                        year_str = str(year)
                        current_value = prepayment_breakdown[project_name].get(year_str, 0)
                        change = current_value - prev_value
                        prepayment_change_breakdown[project_name][year_str] = change
                        prev_value = current_value
                
                # Add individual project prepayment change rows
                for project_name in prepayment_change_breakdown.keys():
                    project_prep_row = {'Balance Sheet Item': f'  {project_name} Prepayment Change'}
                    project_prep_row[hist_col] = 0  # No historical changes
                    for year in years:
                        project_prep_row[str(year)] = prepayment_change_breakdown[project_name][str(year)]
                    bs_rows.append(project_prep_row)
            
                # Total Customer Prepayment row (previous year + sum of changes)
                prepayment_row = {'Balance Sheet Item': 'TOTAL CUSTOMER PREPAYMENT'}
                prepayment_row[hist_col] = hist_customer_prepayment
                for year in years:
                    prepayment_row[str(year)] = total_customer_prepayment_by_year[str(year)]
                bs_rows.append(prepayment_row)
            
                # CASH SECTION - Show changes for each project
                # Calculate cash changes for each project (use broader scope variable)
                for project_name in cash_breakdown.keys():
                    cash_change_breakdown[project_name] = {}
                    prev_value = 0  # Projects start with 0 cash in historical year
                    
                    # Check if project has historical cash
                    financial_statements = None
                    for _, project in df_projects.iterrows():
                        if project.get('project_name', 'Unknown') == project_name:
                            financial_statements = project.get('comprehensive_financial_statements', {})
                            break
                    
                    if financial_statements and base_year_str in financial_statements:
                        hist_data = financial_statements[base_year_str]
                        if 'cumulative_cash_balance' in hist_data:
                            prev_value = hist_data.get('cumulative_cash_balance', 0) / 1e9
                        elif 'Cumulative_Cash_Balance' in hist_data:
                            prev_value = hist_data.get('Cumulative_Cash_Balance', 0) / 1e9
                    
                    for year in years:
                        year_str = str(year)
                        current_value = cash_breakdown[project_name].get(year_str, 0)
                        change = current_value - prev_value
                        cash_change_breakdown[project_name][year_str] = change
                        prev_value = current_value
                
                # Add individual project cash change rows
                for project_name in cash_change_breakdown.keys():
                    project_cash_row = {'Balance Sheet Item': f'  {project_name} Cash Change'}
                    project_cash_row[hist_col] = 0  # No historical changes
                    for year in years:
                        project_cash_row[str(year)] = cash_change_breakdown[project_name][str(year)]
                    bs_rows.append(project_cash_row)
            
                # Removed net cash from other segments - only show project cash
            
                # Total Cash row (previous year + sum of changes)
                cash_row = {'Balance Sheet Item': 'TOTAL CASH'}
                cash_row[hist_col] = 0  # Start with 0 for project cash (no historical project breakdown)
                cumulative_cash = 0  # Start from 0 for projects
                for year in years:
                    year_str = str(year)
                    # Sum cash changes from all projects for this year
                    total_cash_change = sum(
                        cash_change_breakdown[project_name].get(year_str, 0) 
                        for project_name in cash_change_breakdown.keys()
                    )
                    cumulative_cash += total_cash_change
                    cash_row[year_str] = cumulative_cash
                bs_rows.append(cash_row)
            
                # Removed separator, net debt, working capital, retained earnings, and total equity rows
                # Keep only the essential project-related balance sheet items
            
                # Create DataFrame
                bs_df = pd.DataFrame(bs_rows)
            
                st.write("**Detailed Project Breakdown Balance Sheet Items (Billion VND)**")
            
                # Style function to highlight key rows and color code changes
                def style_bs_table(row):
                    item = str(row['Balance Sheet Item'])
                    # Total rows - bold with background
                    if item in ['TOTAL DEBT', 'TOTAL INVENTORY', 'TOTAL CUSTOMER PREPAYMENT', 'TOTAL CASH']:
                        return ['font-weight: bold; background-color: #e6f2ff'] * len(row)
                    # Debt change rows - color code based on value
                    elif 'Debt Change' in item:
                        styles = ['padding-left: 20px']  # First column (item name)
                        styles.append('')  # Historical column
                        # Color code each year's value
                        for year in years:
                            val = row.get(str(year), 0)
                            if pd.notna(val) and val != 0:
                                if val > 0:
                                    styles.append('color: #28a745; font-weight: 600')  # Green for increase
                                elif val < 0:
                                    styles.append('color: #dc3545; font-weight: 600')  # Red for decrease
                                else:
                                    styles.append('color: #666')
                            else:
                                styles.append('color: #666')
                        return styles
                    # Inventory change rows - color code based on value
                    elif 'Inventory Change' in item:
                        styles = ['padding-left: 20px']  # First column (item name)
                        styles.append('')  # Historical column
                        # Color code each year's value
                        for year in years:
                            val = row.get(str(year), 0)
                            if pd.notna(val) and val != 0:
                                if val > 0:
                                    styles.append('color: #28a745; font-weight: 600')  # Green for increase
                                elif val < 0:
                                    styles.append('color: #dc3545; font-weight: 600')  # Red for decrease
                                else:
                                    styles.append('color: #666')
                            else:
                                styles.append('color: #666')
                        return styles
                    # Customer prepayment change rows - color code based on value
                    elif 'Prepayment Change' in item:
                        styles = ['padding-left: 20px']  # First column (item name)
                        styles.append('')  # Historical column
                        # Color code each year's value
                        for year in years:
                            val = row.get(str(year), 0)
                            if pd.notna(val) and val != 0:
                                if val > 0:
                                    styles.append('color: #28a745; font-weight: 600')  # Green for increase
                                elif val < 0:
                                    styles.append('color: #dc3545; font-weight: 600')  # Red for decrease
                                else:
                                    styles.append('color: #666')
                            else:
                                styles.append('color: #666')
                        return styles
                    # Cash change rows - color code based on value
                    elif 'Cash Change' in item:
                        styles = ['padding-left: 20px']  # First column (item name)
                        styles.append('')  # Historical column
                        # Color code each year's value
                        for year in years:
                            val = row.get(str(year), 0)
                            if pd.notna(val) and val != 0:
                                if val > 0:
                                    styles.append('color: #28a745; font-weight: 600')  # Green for increase
                                elif val < 0:
                                    styles.append('color: #dc3545; font-weight: 600')  # Red for decrease
                                else:
                                    styles.append('color: #666')
                            else:
                                styles.append('color: #666')
                        return styles
                    # Other project details - indented with lighter font
                    elif item.startswith('  '):
                        return ['padding-left: 20px; color: #666'] * len(row)
                    return [''] * len(row)
            
                # Define column configuration
                bs_column_config = {
                    'Balance Sheet Item': st.column_config.TextColumn('Balance Sheet Item', width='medium'),
                }
                for col in [hist_col] + [str(y) for y in years]:
                    bs_column_config[col] = st.column_config.NumberColumn(col, width='small')
                
                # Display the detail balance sheet
                st.dataframe(
                    bs_df.style
                    .format(format_bs_value, subset=[hist_col] + [str(y) for y in years])
                    .apply(style_bs_table, axis=1),
                    use_container_width=True,
                    column_config=bs_column_config,
                    hide_index=True
                )
            
            with tab_consolidated_bs:
                # Consolidated Balance Sheet content
                
                # Create consolidated balance sheet with typical items
                consolidated_bs_rows = []
                
                # hist_bs_data was already loaded earlier before accumulation calculations
                # No need to reload it here
                
                # Assets Section
                # Cash & Equivalents
                cash_row = {
                    'Item': 'Cash & Equivalents',
                    hist_col: hist_bs_data.get('Cash & Equivalents', 0)
                }
                # Calculate cash based on cumulative net cash flow from cash flow statement
                cumulative_cash_balance = hist_bs_data.get('Cash & Equivalents', 0)
                for year in years:
                    year_str = str(year)
                    # Add the net cash flow for this year to cumulative balance
                    net_cf = net_cf_by_year.get(year_str, 0)
                    cumulative_cash_balance += net_cf
                    cash_row[year_str] = cumulative_cash_balance
                consolidated_bs_rows.append(cash_row)
                
                # Account Receivable
                hist_ar = hist_bs_data.get('Account Receivable', 0)
                ar_row = {
                    'Item': 'Account Receivable',
                    hist_col: hist_ar
                }
                for year in years:
                    year_str = str(year)
                    # Keep AR constant at historical level
                    ar_row[year_str] = hist_ar
                consolidated_bs_rows.append(ar_row)
                
                # Inventory
                inventory_row = {
                    'Item': 'Inventory',
                    hist_col: hist_bs_data.get('Inventory', 0)
                }
                for year in years:
                    year_str = str(year)
                    inventory_row[year_str] = total_inventory_by_year.get(year_str, 0)
                consolidated_bs_rows.append(inventory_row)
                
                # Other Assets
                # For historical year: Other Assets = Total Assets - Cash & Equivalent - Account Receivable - Inventory
                hist_total_assets = hist_bs_data.get('Total Assets', 0)
                hist_cash_equiv = hist_bs_data.get('Cash & Equivalents', 0)
                hist_acc_receivable = hist_bs_data.get('Account Receivable', 0)
                hist_inventory_bs = hist_bs_data.get('Inventory', 0)
                hist_other_assets = hist_total_assets - hist_cash_equiv - hist_acc_receivable - hist_inventory_bs
                
                other_assets_row = {
                    'Item': 'Other Assets',
                    hist_col: hist_other_assets
                }
                # For forecast years, keep Other Assets constant at historical level
                for year in years:
                    year_str = str(year)
                    other_assets_row[year_str] = hist_other_assets
                consolidated_bs_rows.append(other_assets_row)
                
                # Total Assets
                total_assets_row = {
                    'Item': 'Total Assets',
                    hist_col: hist_bs_data.get('Total Assets', 0)
                }
                for year in years:
                    year_str = str(year)
                    # Total Assets = Cash + AR + Inventory + Other Assets
                    total_assets_row[year_str] = (
                        cash_row[year_str] + 
                        ar_row[year_str] + 
                        inventory_row[year_str] +
                        other_assets_row[year_str]
                    )
                consolidated_bs_rows.append(total_assets_row)
                
                # Liabilities Section
                # Account Payable
                hist_ap = hist_bs_data.get('Account Payable', 0)
                ap_row = {
                    'Item': 'Account Payable',
                    hist_col: hist_ap
                }
                for year in years:
                    year_str = str(year)
                    # Keep AP constant at historical level
                    ap_row[year_str] = hist_ap
                consolidated_bs_rows.append(ap_row)
                
                # Customer Prepayment
                customer_prepayment_row = {
                    'Item': 'Customer Prepayment',
                    hist_col: hist_bs_data.get('Customer Prepayment', hist_customer_prepayment)  # Use hist_customer_prepayment if not in mapping
                }
                for year in years:
                    year_str = str(year)
                    customer_prepayment_row[year_str] = total_customer_prepayment_by_year.get(year_str, 0)
                consolidated_bs_rows.append(customer_prepayment_row)
                
                # Calculate historical ST/LT debt ratio
                hist_st_debt = hist_bs_data.get('Short-term Debt', 0)
                hist_lt_debt = hist_bs_data.get('Long-term Debt', 0)
                hist_total_debt = hist_st_debt + hist_lt_debt
                
                # Calculate ratios, with fallback to 30/70 if no historical debt
                if hist_total_debt > 0:
                    st_debt_ratio = hist_st_debt / hist_total_debt
                    lt_debt_ratio = hist_lt_debt / hist_total_debt
                else:
                    # Default ratios if no historical debt
                    st_debt_ratio = 0.3  # 30% short-term
                    lt_debt_ratio = 0.7  # 70% long-term
                
                # Short-term Debt
                st_debt_row = {
                    'Item': 'Short-term Debt',
                    hist_col: hist_st_debt
                }
                for year in years:
                    year_str = str(year)
                    # Use historical ratio for forecast
                    st_debt_row[year_str] = total_debt_by_year.get(year_str, 0) * st_debt_ratio
                consolidated_bs_rows.append(st_debt_row)
                
                # Long-term Debt
                lt_debt_row = {
                    'Item': 'Long-term Debt',
                    hist_col: hist_lt_debt
                }
                for year in years:
                    year_str = str(year)
                    # Use historical ratio for forecast
                    lt_debt_row[year_str] = total_debt_by_year.get(year_str, 0) * lt_debt_ratio
                consolidated_bs_rows.append(lt_debt_row)
                
                # Other Liabilities
                # For historical year: Other Liabilities = Total Liabilities - Account Payable - Customer Prepayment - Short-term debt - Long-term debt
                hist_total_liabilities = hist_bs_data.get('Total Liabilities', 0)
                hist_acc_payable = hist_bs_data.get('Account Payable', 0)
                hist_cust_prepayment = hist_bs_data.get('Customer Prepayment', hist_customer_prepayment)
                hist_other_liabilities = hist_total_liabilities - hist_acc_payable - hist_cust_prepayment - hist_st_debt - hist_lt_debt
                
                other_liab_row = {
                    'Item': 'Other Liabilities',
                    hist_col: hist_other_liabilities
                }
                # For forecast years, keep Other Liabilities constant at historical level
                for year in years:
                    year_str = str(year)
                    other_liab_row[year_str] = hist_other_liabilities
                consolidated_bs_rows.append(other_liab_row)
                
                # Total Liabilities
                total_liab_row = {
                    'Item': 'Total Liabilities',
                    hist_col: hist_bs_data.get('Total Liabilities', 0)
                }
                for year in years:
                    year_str = str(year)
                    # Total Liabilities = AP + Customer Prepayment + ST Debt + LT Debt + Other Liabilities
                    total_liab_row[year_str] = (
                        ap_row[year_str] + 
                        customer_prepayment_row[year_str] +
                        st_debt_row[year_str] +
                        lt_debt_row[year_str] +
                        other_liab_row[year_str]
                    )
                consolidated_bs_rows.append(total_liab_row)
                
                # Equity Section
                # Retained Earnings
                retained_earnings_row = {
                    'Item': 'Retained Earnings',
                    hist_col: hist_bs_data.get('Retained Earnings', 0)
                }
                # Calculate cumulative retained earnings from NPATMI
                cumulative_earnings = retained_earnings_row[hist_col]
                for year in years:
                    year_str = str(year)
                    # Add current year NPATMI to retained earnings
                    if npatmi_row and year_str in npatmi_row:
                        cumulative_earnings += npatmi_row[year_str]
                    retained_earnings_row[year_str] = cumulative_earnings
                consolidated_bs_rows.append(retained_earnings_row)
                
                # Minority Interest
                minority_interest_bs_row = {
                    'Item': 'Minority Interest',
                    hist_col: hist_bs_data.get('Minority Interest', 0)
                }
                # Calculate cumulative minority interest from P&L
                cumulative_minority = minority_interest_bs_row[hist_col]
                for year in years:
                    year_str = str(year)
                    # Add current year minority interest from P&L to cumulative
                    if minority_interest_row and year_str in minority_interest_row:
                        cumulative_minority += minority_interest_row[year_str]
                    minority_interest_bs_row[year_str] = cumulative_minority
                consolidated_bs_rows.append(minority_interest_bs_row)
                
                # Other Equity (Charter Capital, Treasury shares etc.)
                # For historical: Other Equity = Total Equity - Retained Earnings - Minority Interest
                hist_total_equity = hist_bs_data.get('Total Equity', 0)
                hist_retained_earnings = hist_bs_data.get('Retained Earnings', 0)
                hist_minority_interest = hist_bs_data.get('Minority Interest', 0)
                hist_other_equity = hist_total_equity - hist_retained_earnings - hist_minority_interest
                
                other_equity_row = {
                    'Item': 'Other Equity (Charter Capital, Treasury shares etc.)',
                    hist_col: hist_other_equity
                }
                # For forecast years, keep Other Equity constant at historical level
                for year in years:
                    year_str = str(year)
                    other_equity_row[year_str] = hist_other_equity
                consolidated_bs_rows.append(other_equity_row)
                
                # Total Equity
                total_equity_row = {
                    'Item': 'Total Equity',
                    hist_col: hist_bs_data.get('Total Equity', 0)
                }
                for year in years:
                    year_str = str(year)
                    # Total Equity = Retained Earnings + Minority Interest + Other Equity
                    total_equity_row[year_str] = (
                        retained_earnings_row[year_str] + 
                        minority_interest_bs_row[year_str] +
                        other_equity_row[year_str]
                    )
                consolidated_bs_rows.append(total_equity_row)
                
                # Check row (Total Assets - Total Liabilities - Total Equity)
                check_row = {
                    'Item': 'Check (A - L - E)',
                    hist_col: 0  # Historical should balance
                }
                # Calculate check for historical year
                hist_check = hist_bs_data.get('Total Assets', 0) - hist_bs_data.get('Total Liabilities', 0) - hist_bs_data.get('Total Equity', 0)
                check_row[hist_col] = hist_check
                
                for year in years:
                    year_str = str(year)
                    # Check = Total Assets - Total Liabilities - Total Equity (should be 0)
                    check_value = (
                        total_assets_row[year_str] - 
                        total_liab_row[year_str] - 
                        total_equity_row[year_str]
                    )
                    check_row[year_str] = check_value
                consolidated_bs_rows.append(check_row)
                
                # Create DataFrame
                consolidated_bs_df = pd.DataFrame(consolidated_bs_rows)
                
                # Format function for balance sheet values
                def format_consolidated_bs(val):
                    if val is None or pd.isna(val):
                        return ""
                    elif val == 0:
                        return "-"
                    else:
                        return f"{val:,.0f}"
                
                # Style function for the consolidated balance sheet
                def style_consolidated_bs(row):
                    if row['Item'] == 'Total Assets':
                        return ['background-color: #e8f4f8; font-weight: bold'] * len(row)
                    elif row['Item'] == 'Total Liabilities':
                        return ['background-color: #ffe8e8; font-weight: bold'] * len(row)
                    elif row['Item'] == 'Total Equity':
                        return ['background-color: #e8f8e8; font-weight: bold'] * len(row)
                    elif row['Item'] in ['Other Assets', 'Other Liabilities']:
                        return ['font-weight: 600'] * len(row)
                    elif row['Item'] == 'Check (A - L - E)':
                        # Check if any value is non-zero and highlight in red
                        styles = []
                        for col in row.index:
                            if col == 'Item':
                                styles.append('font-weight: bold')
                            else:
                                val = row[col]
                                if val is not None and not pd.isna(val) and abs(val) > 0.01:  # Allow small rounding errors
                                    styles.append('color: red; font-weight: bold')
                                else:
                                    styles.append('color: green')
                        return styles
                    return [''] * len(row)
                
                # Display the consolidated balance sheet
                st.dataframe(
                    consolidated_bs_df.style
                    .format(format_consolidated_bs, subset=[hist_col] + [str(y) for y in years])
                    .apply(style_consolidated_bs, axis=1),
                    use_container_width=True,
                    column_config={
                        'Item': st.column_config.TextColumn('Balance Sheet Item', width=200),
                        hist_col: st.column_config.NumberColumn(hist_col, width=120),
                        **{str(year): st.column_config.NumberColumn(str(year), width=120) for year in years}
                    },
                    hide_index=True
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
        
            # Create tabs for cash flow statements
            tab_detail_cf, tab_consolidated_cf = st.tabs([
                "Detail Project Breakdown",
                "Consolidated Cash Flow"
            ])
            
            with tab_detail_cf:
                # Render the detail cash flow tab using the utility function
                render_detail_cf_tab(cf_rows, hist_col, years)
            
            with tab_consolidated_cf:
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
                
                # Render the consolidated cash flow tab using the utility function
                render_consolidated_cf_tab(consol_cf_rows, hist_col, years)
            
        
        
            # Save Consolidated Financial Statements to MongoDB
            st.markdown("---")
            st.subheader("Save Consolidated Financial Statements")
        
            col_save1, col_save2, col_save3 = st.columns([1, 2, 1])
            with col_save2:
                if st.button("Save All Consolidated Statements to Database", type="primary", use_container_width=True):
                    # Helper function to convert numpy types to Python native types
                    def convert_to_native(obj):
                        """Convert numpy types to native Python types for MongoDB"""
                        import numpy as np
                        if isinstance(obj, np.integer):
                            return int(obj)
                        elif isinstance(obj, np.floating):
                            return float(obj)
                        elif isinstance(obj, np.ndarray):
                            return obj.tolist()
                        elif isinstance(obj, dict):
                            # Recursively convert dictionary values
                            return {k: convert_to_native(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            # Recursively convert list items
                            return [convert_to_native(item) for item in obj]
                        elif pd.isna(obj):
                            return 0
                        else:
                            return obj
                
                    # Prepare consolidated financial data for MongoDB
                    consolidated_data = {
                        'ticker': selected_ticker,
                        'base_year': int(base_year),
                        'forecast_years': [str(y) for y in years],
                        'timestamp': pd.Timestamp.now().isoformat(),
                        'financial_statements': {}
                    }
                
                    for year in years:
                        year_str = str(year)
                    
                        # Complete Consolidated P&L Statement (including interest income)
                        # Convert from billions to raw VND values for database storage
                        pnl_data = {
                            'real_estate_revenue': convert_to_native(re_revenue_row.get(year_str, 0) * 1e9),
                            'other_revenue': convert_to_native((revenue_row.get(year_str, 0) - re_revenue_row.get(year_str, 0)) * 1e9),
                            'net_revenue': convert_to_native(revenue_row.get(year_str, 0) * 1e9),
                            'real_estate_cogs': convert_to_native(re_cogs_row.get(year_str, 0) * 1e9),
                            'other_cogs': convert_to_native((total_cogs_pnl_row.get(year_str, 0) - re_cogs_row.get(year_str, 0)) * 1e9),
                            'total_cogs': convert_to_native(total_cogs_pnl_row.get(year_str, 0) * 1e9),
                            'gross_profit': convert_to_native(gp_row.get(year_str, 0) * 1e9),
                            'sga': convert_to_native(sga_row.get(year_str, 0) * 1e9),
                            'ebitda': convert_to_native(ebitda_row.get(year_str, 0) * 1e9),
                            'interest_income': convert_to_native(interest_income_row.get(year_str, 0) * 1e9),  # Added interest income
                            'project_interest_expense': convert_to_native(project_interest_pnl_row.get(year_str, 0) * 1e9),
                            'existing_debt_interest_expense': convert_to_native(existing_interest_pnl_row.get(year_str, 0) * 1e9),
                            'interest_expense': convert_to_native(interest_row.get(year_str, 0) * 1e9),
                            'pbt': convert_to_native(pbt_row.get(year_str, 0) * 1e9),
                            'tax': convert_to_native(tax_row.get(year_str, 0) * 1e9),
                            'pat': convert_to_native(pat_row.get(year_str, 0) * 1e9),
                            'minority_interest': convert_to_native(minority_interest_row.get(year_str, 0) * 1e9),
                            'npatmi': convert_to_native(npatmi_row.get(year_str, 0) * 1e9)
                        }
                    
                        # Complete Consolidated Balance Sheet (all line items)
                        # Convert from billions to raw VND values for database storage
                        balance_sheet_data = {
                            'assets': {
                                'cash_and_equivalents': convert_to_native(cash_row.get(year_str, 0) * 1e9),
                                'account_receivable': convert_to_native(ar_row.get(year_str, 0) * 1e9),
                                'inventory': convert_to_native(inventory_row.get(year_str, 0) * 1e9),
                                'other_assets': convert_to_native(other_assets_row.get(year_str, 0) * 1e9),
                                'total_assets': convert_to_native(total_assets_row.get(year_str, 0) * 1e9)
                            },
                            'liabilities': {
                                'account_payable': convert_to_native(ap_row.get(year_str, 0) * 1e9),
                                'customer_prepayment': convert_to_native(customer_prepayment_row.get(year_str, 0) * 1e9),
                                'short_term_debt': convert_to_native(st_debt_row.get(year_str, 0) * 1e9),
                                'long_term_debt': convert_to_native(lt_debt_row.get(year_str, 0) * 1e9),
                                'total_debt': convert_to_native(total_debt_by_year.get(year_str, 0) * 1e9),
                                'other_liabilities': convert_to_native(other_liab_row.get(year_str, 0) * 1e9),
                                'total_liabilities': convert_to_native(total_liab_row.get(year_str, 0) * 1e9)
                            },
                            'equity': {
                                'retained_earnings': convert_to_native(retained_earnings_row.get(year_str, 0) * 1e9),
                                'minority_interest': convert_to_native(minority_interest_bs_row.get(year_str, 0) * 1e9),
                                'other_equity': convert_to_native(other_equity_row.get(year_str, 0) * 1e9),
                                'total_equity': convert_to_native(total_equity_row.get(year_str, 0) * 1e9)
                            },
                            # Derived metrics
                            'net_debt': convert_to_native((total_debt_by_year.get(year_str, 0) - cash_row.get(year_str, 0)) * 1e9),
                            'working_capital': convert_to_native((inventory_row.get(year_str, 0) + cash_row.get(year_str, 0) - customer_prepayment_row.get(year_str, 0)) * 1e9)
                        }
                    
                        # Complete Consolidated Cash Flow Statement
                        # Convert from billions to raw VND values for database storage
                        cash_flow_data = {
                            'operating': {
                                'presales_inflow': convert_to_native(sum(presales_cf_breakdown.get(p, {}).get(year_str, 0) for p in presales_cf_breakdown) * 1e9),
                                'other_segment_revenue': convert_to_native(other_segment_revenue_cf.get(year_str, 0) * 1e9),
                                'other_segment_cogs': convert_to_native(other_segment_cogs_cf.get(year_str, 0) * 1e9),
                                'project_interest_expense': convert_to_native(sum(interest_outflow_breakdown.get(p, {}).get(year_str, 0) for p in interest_outflow_breakdown) * 1e9),
                                'existing_debt_interest': convert_to_native(existing_debt_interest_row.get(year_str, 0) * 1e9),
                                'project_sga': convert_to_native(sum(sga_outflow_breakdown.get(p, {}).get(year_str, 0) for p in sga_outflow_breakdown) * 1e9),
                                'other_segment_sga': convert_to_native(other_sga_cf_row.get(year_str, 0) * 1e9),
                                'tax': convert_to_native(sum(tax_outflow_breakdown.get(p, {}).get(year_str, 0) for p in tax_outflow_breakdown) * 1e9),
                                'total_operating': convert_to_native(operating_cf_by_year.get(year_str, 0) * 1e9)
                            },
                            'investing': {
                                'land_outflow': convert_to_native(sum(land_outflow_breakdown.get(p, {}).get(year_str, 0) for p in land_outflow_breakdown) * 1e9),
                                'construction_outflow': convert_to_native(sum(construction_outflow_breakdown.get(p, {}).get(year_str, 0) for p in construction_outflow_breakdown) * 1e9),
                                'interest_income': convert_to_native(interest_income_row.get(year_str, 0) * 1e9),  # Interest income in investing
                                'total_investing': convert_to_native(investing_cf_by_year.get(year_str, 0) * 1e9)
                            },
                            'financing': {
                                'debt_changes': convert_to_native(sum(financing_cf_breakdown.get(p, {}).get(year_str, 0) for p in financing_cf_breakdown) * 1e9),
                                'total_financing': convert_to_native(financing_cf_by_year.get(year_str, 0) * 1e9)
                            },
                            'net_cash_flow': convert_to_native(net_cf_by_year.get(year_str, 0) * 1e9)
                        }
                    
                        # Business segments detail
                        # Convert from billions to raw VND values for database storage
                        business_segments_data = {}
                        for segment_name in st.session_state.base_year_revenues.keys():
                            if segment_name in segment_revenue_data:
                                business_segments_data[segment_name] = {
                                    'revenue': convert_to_native(segment_revenue_data[segment_name].get(year_str, 0) * 1e9),
                                    'cogs': convert_to_native(segment_cogs_data[segment_name].get(year_str, 0) * 1e9),
                                    'gross_profit': convert_to_native((segment_revenue_data[segment_name].get(year_str, 0) + segment_cogs_data[segment_name].get(year_str, 0)) * 1e9)
                                }
                    
                        # NEW: Detail Project Breakdown Balance Sheet (changes)
                        # Convert from billions to raw VND values for database storage
                        balance_sheet_detail_data = {
                            'debt_changes': {p: convert_to_native(debt_change_breakdown.get(p, {}).get(year_str, 0) * 1e9) for p in debt_change_breakdown},
                            'inventory_changes': {p: convert_to_native(inventory_change_breakdown.get(p, {}).get(year_str, 0) * 1e9) for p in inventory_change_breakdown},
                            'prepayment_changes': {p: convert_to_native(prepayment_change_breakdown.get(p, {}).get(year_str, 0) * 1e9) for p in prepayment_change_breakdown},
                            'cash_changes': {p: convert_to_native(cash_change_breakdown.get(p, {}).get(year_str, 0) * 1e9) for p in cash_change_breakdown}
                        }
                    
                        # NEW: Detail Project Breakdown Cash Flow
                        cash_flow_detail_data = {
                            'by_project': {}
                        }
                        
                        # Extract project-level cash flow data from cf_rows
                        # Convert from billions to raw VND values for database storage
                        for project_name in presales_cf_breakdown.keys():
                            cash_flow_detail_data['by_project'][project_name] = {
                                'presales_inflow': convert_to_native(presales_cf_breakdown.get(project_name, {}).get(year_str, 0) * 1e9),
                                'land_outflow': convert_to_native(land_outflow_breakdown.get(project_name, {}).get(year_str, 0) * 1e9),
                                'construction_outflow': convert_to_native(construction_outflow_breakdown.get(project_name, {}).get(year_str, 0) * 1e9),
                                'interest_outflow': convert_to_native(interest_outflow_breakdown.get(project_name, {}).get(year_str, 0) * 1e9),
                                'sga_outflow': convert_to_native(sga_outflow_breakdown.get(project_name, {}).get(year_str, 0) * 1e9),
                                'tax_outflow': convert_to_native(tax_outflow_breakdown.get(project_name, {}).get(year_str, 0) * 1e9),
                                'debt_changes': convert_to_native(financing_cf_breakdown.get(project_name, {}).get(year_str, 0) * 1e9),
                                'net_cash_flow': convert_to_native(
                                    (presales_cf_breakdown.get(project_name, {}).get(year_str, 0) +
                                    land_outflow_breakdown.get(project_name, {}).get(year_str, 0) +
                                    construction_outflow_breakdown.get(project_name, {}).get(year_str, 0) +
                                    interest_outflow_breakdown.get(project_name, {}).get(year_str, 0) +
                                    sga_outflow_breakdown.get(project_name, {}).get(year_str, 0) +
                                    tax_outflow_breakdown.get(project_name, {}).get(year_str, 0) +
                                    financing_cf_breakdown.get(project_name, {}).get(year_str, 0)) * 1e9
                                )
                            }
                        
                        # Combine all statements for this year
                        consolidated_data['financial_statements'][year_str] = {
                            'pnl': pnl_data,
                            'balance_sheet': balance_sheet_data,
                            'balance_sheet_detail': balance_sheet_detail_data,  # NEW
                            'cash_flow': cash_flow_data,
                            'cash_flow_detail': cash_flow_detail_data,  # NEW
                            'business_segments': business_segments_data,
                            'project_breakdown': {
                                'revenue': {p: convert_to_native(project_revenue_breakdown.get(p, {}).get(year, 0) * 1e9) for p in project_revenue_breakdown},
                                'cogs': {p: convert_to_native(project_cogs_breakdown.get(p, {}).get(year, 0) * 1e9) for p in project_cogs_breakdown},
                                'gross_profit': {p: convert_to_native((project_revenue_breakdown.get(p, {}).get(year, 0) + project_cogs_breakdown.get(p, {}).get(year, 0)) * 1e9) for p in project_revenue_breakdown},
                                'sga': {p: convert_to_native(project_sga_breakdown.get(p, {}).get(year, 0) * 1e9) for p in project_sga_breakdown},
                                'interest': {p: convert_to_native(project_interest_breakdown.get(p, {}).get(year, 0) * 1e9) for p in project_interest_breakdown},
                                'pbt': {p: convert_to_native(project_pbt_breakdown.get(p, {}).get(year, 0) * 1e9) for p in project_pbt_breakdown if p in project_pbt_breakdown},
                                'pat': {p: convert_to_native(project_pat_breakdown.get(p, {}).get(year, 0) * 1e9) for p in project_pat_breakdown},
                                'patmi': {p: convert_to_native(project_patmi_breakdown.get(p, {}).get(year, 0) * 1e9) for p in project_patmi_breakdown},
                                'minority_interest': {p: convert_to_native(project_minority_interest_breakdown.get(p, {}).get(year, {}).get('minority_interest', 0) * 1e9) for p in project_minority_interest_breakdown if year in project_minority_interest_breakdown.get(p, {})}
                            },
                            'profitability_metrics': {
                                'project_margins': {
                                    p: {
                                        # All margins are percentages, calculated from billion VND values in breakdowns
                                        'gross_margin': convert_to_native((project_revenue_breakdown.get(p, {}).get(year, 0) + project_cogs_breakdown.get(p, {}).get(year, 0)) / project_revenue_breakdown.get(p, {}).get(year, 0) * 100) if project_revenue_breakdown.get(p, {}).get(year, 0) > 0 else 0,
                                        'sga_margin': convert_to_native(-project_sga_breakdown.get(p, {}).get(year, 0) / project_revenue_breakdown.get(p, {}).get(year, 0) * 100) if project_revenue_breakdown.get(p, {}).get(year, 0) > 0 else 0,
                                        'pbt_margin': convert_to_native(project_pbt_breakdown.get(p, {}).get(year, 0) / project_revenue_breakdown.get(p, {}).get(year, 0) * 100) if project_revenue_breakdown.get(p, {}).get(year, 0) > 0 and p in project_pbt_breakdown else 0,
                                        'pat_margin': convert_to_native(project_pat_breakdown.get(p, {}).get(year, 0) / project_revenue_breakdown.get(p, {}).get(year, 0) * 100) if project_revenue_breakdown.get(p, {}).get(year, 0) > 0 else 0,
                                        'patmi_margin': convert_to_native(project_patmi_breakdown.get(p, {}).get(year, 0) / project_revenue_breakdown.get(p, {}).get(year, 0) * 100) if project_revenue_breakdown.get(p, {}).get(year, 0) > 0 else 0
                                    } for p in project_revenue_breakdown if project_revenue_breakdown.get(p, {}).get(year, 0) > 0
                                },
                                'aggregated_project_margins': {
                                    # Total project margins (all projects combined)
                                    'total_projects_revenue': convert_to_native(project_revenue_by_year.get(year, 0) * 1e9),
                                    'total_projects_gross_profit': convert_to_native((project_revenue_by_year.get(year, 0) + project_cogs_by_year.get(year, 0)) * 1e9),
                                    'total_projects_gross_margin': convert_to_native((project_revenue_by_year.get(year, 0) + project_cogs_by_year.get(year, 0)) / project_revenue_by_year.get(year, 0) * 100) if project_revenue_by_year.get(year, 0) > 0 else 0,
                                    'total_projects_sga_margin': convert_to_native(-sum(project_sga_breakdown.get(p, {}).get(year, 0) for p in project_sga_breakdown) / project_revenue_by_year.get(year, 0) * 100) if project_revenue_by_year.get(year, 0) > 0 else 0,
                                    'total_projects_pbt_margin': convert_to_native(sum(project_pbt_breakdown.get(p, {}).get(year, 0) for p in project_pbt_breakdown) / project_revenue_by_year.get(year, 0) * 100) if project_revenue_by_year.get(year, 0) > 0 else 0,
                                    'total_projects_pat_margin': convert_to_native(sum(project_pat_breakdown.get(p, {}).get(year, 0) for p in project_pat_breakdown) / project_revenue_by_year.get(year, 0) * 100) if project_revenue_by_year.get(year, 0) > 0 else 0,
                                    'total_projects_patmi_margin': convert_to_native(sum(project_patmi_breakdown.get(p, {}).get(year, 0) for p in project_patmi_breakdown) / project_revenue_by_year.get(year, 0) * 100) if project_revenue_by_year.get(year, 0) > 0 else 0
                                },
                                'consolidated_margins': {
                                    # Company-wide margins (projects + other segments)
                                    'gross_margin': convert_to_native((pnl_data['gross_profit'] / pnl_data['net_revenue'] * 100)) if pnl_data.get('net_revenue', 0) > 0 else 0,
                                    'ebitda_margin': convert_to_native((pnl_data['ebitda'] / pnl_data['net_revenue'] * 100)) if pnl_data.get('net_revenue', 0) > 0 else 0,
                                    'pbt_margin': convert_to_native((pnl_data['pbt'] / pnl_data['net_revenue'] * 100)) if pnl_data.get('net_revenue', 0) > 0 else 0,
                                    'pat_margin': convert_to_native((pnl_data['pat'] / pnl_data['net_revenue'] * 100)) if pnl_data.get('net_revenue', 0) > 0 else 0,
                                    'patmi_margin': convert_to_native((pnl_data['npatmi'] / pnl_data['net_revenue'] * 100)) if pnl_data.get('net_revenue', 0) > 0 else 0
                                }
                            }
                        }
                
                    # No historical data saved - only forecast data
                
                    # Save to MongoDB with new collection structure
                    # Apply deep conversion to entire consolidated_data to ensure all numpy types are converted
                    consolidated_data = convert_to_native(consolidated_data)
                    
                    # Save all financial statements to CompanyForecast collection
                    from utils.mongodb_utils import save_company_forecast
                    
                    # Extract all financial statements data for CompanyForecast collection
                    forecast_data = {}
                    for year_str, year_data in consolidated_data['financial_statements'].items():
                        forecast_data[year_str] = {
                            'pnl': year_data.get('pnl', {}),
                            'balance_sheet': year_data.get('balance_sheet', {}),
                            'balance_sheet_detail': year_data.get('balance_sheet_detail', {}),  # NEW
                            'cash_flow': year_data.get('cash_flow', {}),
                            'cash_flow_detail': year_data.get('cash_flow_detail', {}),  # NEW
                            'business_segments': year_data.get('business_segments', {}),
                            'project_breakdown': year_data.get('project_breakdown', {}),
                            'profitability_metrics': year_data.get('profitability_metrics', {})
                        }
                    
                    # Debug: Check if interest_income is present in the data
                    has_interest_income = False
                    for year_str in forecast_data.keys():
                        if 'pnl' in forecast_data[year_str] and 'interest_income' in forecast_data[year_str]['pnl']:
                            interest_val = forecast_data[year_str]['pnl']['interest_income']
                            if interest_val != 0:
                                # Values are now in raw VND, convert to billions for display
                                st.info(f"💡 Interest Income for {year_str}: {interest_val/1e9:,.2f}B VND")
                                has_interest_income = True
                        else:
                            st.warning(f"⚠️ Interest Income missing or zero for {year_str}")
                    
                    if not has_interest_income:
                        st.warning("⚠️ No interest income values found in any year. Check if cash balances are positive.")
                    
                    # Save to CompanyForecast collection
                    result = save_company_forecast(selected_ticker, forecast_data)
                    if result['success']:
                        st.success(f"✅ {result['message']}")
                        # Store in session state for reference
                        st.session_state[f'saved_consolidated_{selected_ticker}'] = consolidated_data
                    else:
                        st.error(f"❌ {result['message']}")
        
            st.info("💡 This saves all three consolidated financial statements (P&L, Balance Sheet, Cash Flow) to the CompanyForecast collection in MongoDB for reporting and analysis.")
        
        else:
            st.info("No project data available. Please add projects in the Project Pipeline tab.")
    
    def generate_revenue_forecast(self):
        """Generate revenue forecast from project pipeline"""
        current_year = datetime.now().year
        forecast_years = st.session_state.forecast_years
    
        # Initialize forecast structure
        years = list(range(current_year, current_year + forecast_years + 1))
        forecast = {
            'years': years,
            'presales': [0] * len(years),
            'handover': [0] * len(years),
            'recurring': [0] * len(years),
            'total': [0] * len(years),
            'project_details': {},  # Store project-level breakdown
            'revenue_by_project': {},  # Store revenue schedules by project
            'construction_by_project': {},  # Store construction schedules by project
            'land_by_project': {},  # Store land schedules by project
            'sga_by_project': {}  # Store SG&A schedules by project
        }
    
        # If we have project data, calculate revenue from projects
        if st.session_state.project_data is not None and isinstance(st.session_state.project_data, pd.DataFrame) and not st.session_state.project_data.empty:
            forecast = self.calculate_project_based_revenue(forecast)
        # If no project data, forecast remains with zero values
    
        return forecast
    
    def calculate_project_based_revenue(self, forecast):
        """Calculate revenue forecast based on actual project details"""
        df_projects = st.session_state.project_data
        current_year = datetime.now().year
    
        # Initialize project details dictionary and schedule dictionaries
        for year in forecast['years']:
            forecast['project_details'][year] = []
            if year not in forecast['revenue_by_project']:
                forecast['revenue_by_project'][year] = {}
            if year not in forecast['construction_by_project']:
                forecast['construction_by_project'][year] = {}
            if year not in forecast['land_by_project']:
                forecast['land_by_project'][year] = {}
            if year not in forecast['sga_by_project']:
                forecast['sga_by_project'][year] = {}
    
        # Process each project
        for _, project in df_projects.iterrows():
            project_name = project.get('project_name', 'Unknown Project')
        
            # First check if project has saved schedules
            revenue_schedule = project.get('revenue_schedule', {})
            construction_schedule = project.get('construction_schedule', {})
            land_schedule = project.get('land_schedule', {})
            sga_schedule = project.get('sga_schedule', {})
        
            # Ensure schedules are dictionaries
            if not isinstance(revenue_schedule, dict):
                revenue_schedule = {}
            if not isinstance(construction_schedule, dict):
                construction_schedule = {}
            if not isinstance(land_schedule, dict):
                land_schedule = {}
            if not isinstance(sga_schedule, dict):
                sga_schedule = {}
        
            # If we have saved schedules, use them preferentially
            if revenue_schedule:
                for year in forecast['years']:
                    year_str = str(year)
                    if year_str in revenue_schedule:
                        year_revenue = revenue_schedule[year_str]  # Already in billions
                        if year_revenue > 0:
                            year_idx = forecast['years'].index(year)
                            # For simplicity, split between presales (40%) and handover (60%)
                            forecast['presales'][year_idx] += year_revenue * 0.4
                            forecast['handover'][year_idx] += year_revenue * 0.6
                            forecast['revenue_by_project'][year][project_name] = year_revenue
                        
                            forecast['project_details'][year].append({
                                'project': project_name,
                                'type': 'Revenue',
                                'amount': year_revenue
                            })
                
                    # Add cost schedules
                    if year_str in construction_schedule:
                        forecast['construction_by_project'][year][project_name] = construction_schedule[year_str]
                    if year_str in land_schedule:
                        forecast['land_by_project'][year][project_name] = land_schedule[year_str]
                    if year_str in sga_schedule:
                        forecast['sga_by_project'][year][project_name] = sga_schedule[year_str]
            
                continue  # Skip to next project since we used saved schedules
        
            # Get project timeline parameters
            construction_start = int(project.get('construction_start_year', current_year))
            completion_year = int(project.get('project_completion_year', current_year + 3))
            revenue_start = int(project.get('revenue_booking_start_year', construction_start + 1))
        
            # Calculate total project revenue
            total_revenue = 0
            if 'total_revenue' in project and pd.notna(project['total_revenue']) and project['total_revenue'] > 0:
                total_revenue = project['total_revenue'] / 1e9  # Convert to billions
            else:
                # Calculate from components
                total_units = project.get('total_units', 0)
                nsa = project.get('net_sellable_area', 0)
                avg_price = project.get('average_selling_price', 0)  # Price per sqm in millions VND
            
                if nsa > 0 and avg_price > 0:
                    # Total revenue = NSA * Price per sqm
                    total_revenue = (nsa * avg_price) / 1e3  # Convert from millions to billions
                elif total_units > 0 and avg_price > 0:
                    # If we have units but not NSA, estimate average unit size
                    avg_unit_size = project.get('average_unit_size', 70)  # Default 70 sqm
                    total_revenue = (total_units * avg_unit_size * avg_price) / 1e3
        
            if total_revenue <= 0:
                continue  # Skip projects with no revenue data
        
            # Get distribution schedules (always use them now)
            revenue_distribution = project.get('revenue_distribution', {})
            presales_distribution = project.get('presales_distribution', {})
        
            # Calculate presales revenue with custom or default distribution
            sales_start = int(project.get('sale_start_year', current_year))
            sales_years = int(project.get('sales_years', 3))
            sales_end = sales_start + sales_years - 1
        
            if presales_distribution:
                # Use custom presales distribution
                for year in forecast['years']:
                    if sales_start <= year <= sales_end:
                        year_pct = presales_distribution.get(str(year), 0) / 100.0
                        year_presales = total_revenue * 0.4 * year_pct  # 40% of total as presales
                    
                        if year_presales > 0:
                            year_idx = forecast['years'].index(year)
                            forecast['presales'][year_idx] += year_presales
                            forecast['project_details'][year].append({
                                'project': project_name,
                                'type': 'Presales',
                                'amount': year_presales
                            })
            else:
                # Default presales distribution (even across sales years)
                presales_revenue = total_revenue * 0.4  # 40% as presales
                for year in forecast['years']:
                    if sales_start <= year <= sales_end:
                        annual_presales = presales_revenue / sales_years
                    
                        year_idx = forecast['years'].index(year)
                        forecast['presales'][year_idx] += annual_presales
                        forecast['project_details'][year].append({
                            'project': project_name,
                            'type': 'Presales',
                            'amount': annual_presales
                        })
        
            # Calculate handover revenue with custom or default distribution
            if revenue_distribution:
                # Use custom revenue distribution for handover
                for year in forecast['years']:
                    if revenue_start <= year <= completion_year:
                        year_pct = revenue_distribution.get(str(year), 0) / 100.0
                        year_handover = total_revenue * 0.6 * year_pct  # 60% of total as handover
                    
                        if year_handover > 0:
                            year_idx = forecast['years'].index(year)
                            forecast['handover'][year_idx] += year_handover
                            forecast['project_details'][year].append({
                                'project': project_name,
                                'type': 'Handover',
                                'amount': year_handover
                            })
            else:
                # Default handover distribution (even across revenue booking years)
                handover_revenue = total_revenue * 0.6  # 60% as handover revenue
                for year in forecast['years']:
                    if revenue_start <= year <= completion_year:
                        handover_years = max(completion_year - revenue_start + 1, 1)
                        annual_handover = handover_revenue / handover_years
                    
                        year_idx = forecast['years'].index(year)
                        forecast['handover'][year_idx] += annual_handover
                        forecast['project_details'][year].append({
                            'project': project_name,
                            'type': 'Handover',
                            'amount': annual_handover
                        })
    
        # Add recurring revenue (property management, rental income)
        # Estimate as 5% of cumulative delivered projects
        cumulative_delivered = 0
        for i, year in enumerate(forecast['years']):
            cumulative_delivered += forecast['handover'][i]
            forecast['recurring'][i] = cumulative_delivered * 0.05  # 5% recurring revenue
    
        # Calculate total revenue
        for i in range(len(forecast['years'])):
            forecast['total'][i] = forecast['presales'][i] + forecast['handover'][i] + forecast['recurring'][i]
    
        return forecast

