import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import json
import os
from utils.mongodb_utils import load_assumptions_from_mongodb
from tabs.balance_sheet_analysis import BalanceSheetAnalysisTab


class ModelForecastTab:
    """Model Forecast Tab for Revenue & COGS Forecasting"""
    
    def __init__(self, parent_model=None):
        """Initialize the Model Forecast tab"""
        self.parent_model = parent_model
    
    def load_historical_data_from_csv(self, ticker):
        """Load historical data from parent model if available"""
        if self.parent_model and hasattr(self.parent_model, 'load_historical_data_from_csv'):
            return self.parent_model.load_historical_data_from_csv(ticker)
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
        st.header("Revenue & COGS Forecast")
    
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
                    st.success(f"Loaded historical data with {len(historical_data)} records")
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
                # If all else fails, default to 2024
                base_year = 2024
        
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
            base_year = st.session_state.get('base_year', 2024)
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
                        interest_amount = year_data.get('interest_expense_cash', 0) / 1e9  # Already negative in DB
                        project_interest_breakdown[project_name][year] = interest_amount
                    
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
                st.success(f"✅ {len(df_projects)} project(s) using Comprehensive Financial Statements from MongoDB (values converted to Billion VND)")
        
            # Project breakdown data is now incorporated into Total Revenue Forecast table
        
            # Section 2: Total Revenue Forecast
            st.subheader("Total Revenue Forecast")
        
            # Create revenue table with rows as revenue sources and columns as years
            revenue_rows = []
        
            # Add individual project revenues
            for project_name in project_revenue_breakdown.keys():
                row_data = {'Revenue Source': f"{project_name}"}
                row_data[hist_col] = 0  # No historical breakdown by project
                for year in years:
                    row_data[str(year)] = project_revenue_breakdown[project_name].get(year, 0)
                revenue_rows.append(row_data)
        
            # Add separator row for projects total
            if revenue_rows:
                total_projects_row = {'Revenue Source': 'Subtotal: Projects'}
                total_projects_row[hist_col] = 0  # No historical breakdown
                for year in years:
                    total_projects_row[str(year)] = project_revenue_by_year[year]
                revenue_rows.append(total_projects_row)
        
            # Add other revenue streams
            for segment_name in st.session_state.base_year_revenues.keys():
                row_data = {'Revenue Source': f"{segment_name}"}
                # Base year revenue goes in the historical column
                row_data[hist_col] = st.session_state.base_year_revenues[segment_name]
                base_revenue = st.session_state.base_year_revenues[segment_name]
            
                # Get growth rate from segment_metrics
                if segment_name in segment_metrics:
                    growth_rate = segment_metrics[segment_name]['revenue_growth']
                else:
                    growth_rate = 0.0  # Default 0%
            
                # Apply growth for forecast years
                for year in years:
                    # Base year is the latest historical year, apply growth from there
                    years_from_base = year - base_year
                    row_data[str(year)] = base_revenue * ((1 + growth_rate) ** years_from_base)
                revenue_rows.append(row_data)
        
            # Add total row
            total_row = {'Revenue Source': 'TOTAL REVENUE'}
            total_row[hist_col] = hist_values.get('Net Revenue', 0)  # Historical Net Revenue
            for year in years:
                total_revenue = project_revenue_by_year[year]
                for segment_name in st.session_state.base_year_revenues.keys():
                    base_revenue = st.session_state.base_year_revenues[segment_name]
                    if segment_name in segment_metrics:
                        growth_rate = segment_metrics[segment_name]['revenue_growth']
                    else:
                        growth_rate = 0.0
                
                    # Base year is the latest historical year, apply growth from there
                    years_from_base = year - base_year
                    total_revenue += base_revenue * ((1 + growth_rate) ** years_from_base)
                total_row[str(year)] = total_revenue
            revenue_rows.append(total_row)
        
            # Create DataFrame
            revenue_df = pd.DataFrame(revenue_rows)
        
            # Style the dataframe - highlight subtotal and total rows
            def highlight_special_rows(row):
                if 'TOTAL' in str(row['Revenue Source']) or 'Subtotal' in str(row['Revenue Source']):
                    return ['font-weight: bold'] * len(row)
                return [''] * len(row)
        
            st.write("**Revenue by Source (Billion VND)**")
        
            # Define column configuration for consistent width
            column_config = {
                'Revenue Source': st.column_config.TextColumn('Revenue Source', width='medium'),
            }
            for col in [hist_col] + [str(y) for y in years]:
                column_config[col] = st.column_config.NumberColumn(col, width='small')
        
            st.dataframe(
                revenue_df.style
                .format("{:,.0f}", subset=[hist_col] + [str(y) for y in years])
                .apply(highlight_special_rows, axis=1),
                use_container_width=True,
                column_config=column_config,
                hide_index=True
            )
        
            # Section 3: COGS Table
            st.markdown("---")
            st.subheader("Cost of Goods Sold (COGS)")
        
            # Create COGS table with rows as cost sources and columns as years
            cogs_rows = []
        
            # Add individual project COGS
            for project_name in project_cogs_breakdown.keys():
                row_data = {'COGS Source': f"{project_name}"}
                row_data[hist_col] = 0  # No historical breakdown by project
                for year in years:
                    row_data[str(year)] = project_cogs_breakdown[project_name].get(year, 0)
                cogs_rows.append(row_data)
        
            # Add separator row for projects total
            if cogs_rows:
                total_projects_row = {'COGS Source': 'Subtotal: Project COGS'}
                total_projects_row[hist_col] = 0  # No historical breakdown
                for year in years:
                    total_projects_row[str(year)] = project_cogs_by_year[year]
                cogs_rows.append(total_projects_row)
        
            # Add COGS for other revenue streams
            for segment_name in st.session_state.base_year_revenues.keys():
                row_data = {'COGS Source': f"{segment_name} COGS"}
                base_revenue = st.session_state.base_year_revenues[segment_name]
            
                # Get metrics from segment_metrics
                if segment_name in segment_metrics:
                    growth_rate = segment_metrics[segment_name]['revenue_growth']
                    gross_margin = segment_metrics[segment_name]['gross_margin']
                else:
                    growth_rate = 0.0  # Default 0%
                    gross_margin = 0.0  # Default 0%
            
                # Base year COGS in historical column (negative)
                row_data[hist_col] = -base_revenue * (1 - gross_margin)
            
                # Calculate COGS for forecast years (negative)
                for year in years:
                    # Base year is the latest historical year, apply growth from there
                    years_from_base = year - base_year
                    year_revenue = base_revenue * ((1 + growth_rate) ** years_from_base)
                
                    row_data[str(year)] = -year_revenue * (1 - gross_margin)
                cogs_rows.append(row_data)
        
            # Add total row
            total_row = {'COGS Source': 'TOTAL COGS'}
            total_row[hist_col] = -abs(hist_values.get('COGS', 0))  # Historical COGS as negative
            for year in years:
                total_cogs = project_cogs_by_year[year]  # Already negative from projects
                for segment_name in st.session_state.base_year_revenues.keys():
                    base_revenue = st.session_state.base_year_revenues[segment_name]
                
                    if segment_name in segment_metrics:
                        growth_rate = segment_metrics[segment_name]['revenue_growth']
                        gross_margin = segment_metrics[segment_name]['gross_margin']
                    else:
                        growth_rate = 0.0
                        gross_margin = 0.0
                
                    # Base year is the latest historical year, apply growth from there
                    years_from_base = year - base_year
                    year_revenue = base_revenue * ((1 + growth_rate) ** years_from_base)
                
                    # Add negative COGS for other segments
                    total_cogs -= year_revenue * (1 - gross_margin)
                total_row[str(year)] = total_cogs
            cogs_rows.append(total_row)
        
            # Create DataFrame
            cogs_df = pd.DataFrame(cogs_rows)
        
            # Style the dataframe - highlight subtotal and total rows
            def highlight_special_rows_cogs(row):
                if 'TOTAL' in str(row['COGS Source']) or 'Subtotal' in str(row['COGS Source']):
                    return ['font-weight: bold'] * len(row)
                return [''] * len(row)
        
            st.write("**COGS by Source (Billion VND)**")
        
            # Define column configuration for consistent width
            cogs_column_config = {
                'COGS Source': st.column_config.TextColumn('COGS Source', width='medium'),
            }
            for col in [hist_col] + [str(y) for y in years]:
                cogs_column_config[col] = st.column_config.NumberColumn(col, width='small')
        
            st.dataframe(
                cogs_df.style
                .format("{:,.0f}", subset=[hist_col] + [str(y) for y in years])
                .apply(highlight_special_rows_cogs, axis=1),
                use_container_width=True,
                column_config=cogs_column_config,
                hide_index=True
            )
        
            # Section 4: Gross Profit
            st.markdown("---")
            st.subheader("Gross Profit")
        
            # Get total revenue and COGS from the last row of each DataFrame
            total_revenue_row = revenue_df[revenue_df['Revenue Source'] == 'TOTAL REVENUE'].iloc[0]
            total_cogs_row = cogs_df[cogs_df['COGS Source'] == 'TOTAL COGS'].iloc[0]
        
            # Create gross profit breakdown by segment (rows = segments, columns = years)
            gross_profit_rows = []
        
            # Calculate gross profit for Projects (aggregate all projects)
            projects_gp_row = {'Gross Profit Source': 'Projects'}
            projects_gp_row['2024H'] = 0  # No historical breakdown
            for year in years:
                year_str = str(year)
                projects_revenue = project_revenue_by_year[year]
                projects_cogs = project_cogs_by_year[year]  # This is already negative
                projects_gp_row[year_str] = projects_revenue + projects_cogs  # Add negative COGS
            gross_profit_rows.append(projects_gp_row)
        
            # Calculate gross profit for each other segment
            for segment_name in st.session_state.base_year_revenues.keys():
                gp_row = {'Gross Profit Source': segment_name}
                gp_row['2024H'] = 0  # No historical breakdown
                base_revenue = st.session_state.base_year_revenues[segment_name]
            
                # Get metrics from segment_metrics
                if segment_name in segment_metrics:
                    growth_rate = segment_metrics[segment_name]['revenue_growth']
                    gross_margin = segment_metrics[segment_name]['gross_margin']
                else:
                    growth_rate = 0.0  # Default 0%
                    gross_margin = 0.0  # Default 0%
            
                for year in years:
                    year_str = str(year)
                    # Base year is the latest historical year, apply growth from there
                    years_from_base = year - base_year
                    year_revenue = base_revenue * ((1 + growth_rate) ** years_from_base)
                
                    year_cogs = year_revenue * (1 - gross_margin)
                    gp_row[year_str] = year_revenue - year_cogs
                gross_profit_rows.append(gp_row)
        
            # Add total gross profit row
            total_gp_row = {'Gross Profit Source': 'TOTAL GROSS PROFIT'}
            total_gp_row['2024H'] = hist_values.get('Gross profit', 0)  # Historical Gross Profit
            for year in years:
                year_str = str(year)
                revenue = total_revenue_row[year_str]
                cogs = total_cogs_row[year_str]  # Already negative
                total_gp_row[year_str] = revenue + cogs  # Add negative COGS to revenue
            gross_profit_rows.append(total_gp_row)
        
            # Create DataFrame for gross profit
            gross_profit_df = pd.DataFrame(gross_profit_rows)
        
            # Style function to highlight total row
            def highlight_total_row(row):
                if 'TOTAL' in str(row['Gross Profit Source']):
                    return ['font-weight: bold'] * len(row)
                return [''] * len(row)
        
            st.write("**Gross Profit Summary by Segment (Billion VND)**")
        
            # Define column configuration for consistent width
            gp_column_config = {
                'Gross Profit Source': st.column_config.TextColumn('Gross Profit Source', width='medium'),
            }
            for col in [hist_col] + [str(y) for y in years]:
                gp_column_config[col] = st.column_config.NumberColumn(col, width='small')
        
            st.dataframe(
                gross_profit_df.style
                .format("{:,.0f}", subset=[hist_col] + [str(y) for y in years])
                .apply(highlight_total_row, axis=1),
                use_container_width=True,
                column_config=gp_column_config,
                hide_index=True
            )
        
            # Create Gross Profit Margin table
            margin_rows = []
        
            # Calculate margin for Projects
            projects_margin_row = {'Segment': 'Projects'}
            projects_margin_row['2024H'] = 0  # Will calculate if historical data exists
            for year in years:
                year_str = str(year)
                projects_revenue = project_revenue_by_year[year]
                if projects_revenue > 0:
                    projects_gp = gross_profit_df[gross_profit_df['Gross Profit Source'] == 'Projects'].iloc[0][year_str]
                    projects_margin_row[year_str] = (projects_gp / projects_revenue) * 100
                else:
                    projects_margin_row[year_str] = 0
            margin_rows.append(projects_margin_row)
        
            # Calculate margin for each other segment
            for segment_name in st.session_state.base_year_revenues.keys():
                margin_row = {'Segment': segment_name}
                margin_row['2024H'] = 0  # Will calculate if historical data exists
            
                # Get gross margin from segment_metrics
                if segment_name in segment_metrics:
                    gross_margin = segment_metrics[segment_name]['gross_margin'] * 100
                else:
                    gross_margin = 0.0  # Default 0%
            
                for year in years:
                    year_str = str(year)
                    margin_row[year_str] = gross_margin
                margin_rows.append(margin_row)
        
            # Add overall margin row
            overall_margin_row = {'Segment': 'OVERALL MARGIN'}
            # Calculate historical margin if data exists
            if hist_values.get('Net Revenue', 0) > 0 and hist_values.get('Gross profit', 0) > 0:
                overall_margin_row['2024H'] = (hist_values['Gross profit'] / hist_values['Net Revenue']) * 100
            else:
                overall_margin_row['2024H'] = 0
            for year in years:
                year_str = str(year)
                revenue = total_revenue_row[year_str]
                if revenue > 0:
                    gross_profit = total_gp_row[year_str]
                    overall_margin_row[year_str] = (gross_profit / revenue) * 100
                else:
                    overall_margin_row[year_str] = 0
            margin_rows.append(overall_margin_row)
        
            # Create DataFrame for margins
            margin_df = pd.DataFrame(margin_rows)
        
            st.write("**Gross Profit Margin by Segment (%)**")
        
            # Define column configuration for consistent width
            margin_column_config = {
                'Segment': st.column_config.TextColumn('Segment', width='medium'),
            }
            for col in [hist_col] + [str(y) for y in years]:
                margin_column_config[col] = st.column_config.NumberColumn(col, width='small', format='%.1f%%')
        
            st.dataframe(
                margin_df.style
                .format("{:.1f}%", subset=[hist_col] + [str(y) for y in years])
                .apply(lambda row: ['font-weight: bold'] * len(row) if 'OVERALL' in str(row['Segment']) else [''] * len(row), axis=1),
                use_container_width=True,
                column_config=margin_column_config,
                hide_index=True
            )
        
            # Initialize SG&A data for later use in comprehensive P&L
            sga_rows = []
            project_sga_total_by_year = {year: 0 for year in years}
        
            # Collect SG&A data from projects (for comprehensive P&L calculation)
            for project_name in project_sga_breakdown.keys():
                row_data = {'SG&A Source': f"{project_name}"}
                row_data[hist_col] = 0  # No historical breakdown
            
                for year in years:
                    project_sga = project_sga_breakdown[project_name].get(year, 0)
                    row_data[str(year)] = project_sga
                    project_sga_total_by_year[year] += project_sga
            
                sga_rows.append(row_data)
        
            # Add subtotal for all projects
            if project_revenue_breakdown:
                projects_total_row = {'SG&A Source': 'Total Projects SG&A'}
                projects_total_row[hist_col] = 0
                for year in years:
                    projects_total_row[str(year)] = project_sga_total_by_year[year]
                sga_rows.append(projects_total_row)
        
            # SG&A for other business segments
            for segment_name in st.session_state.base_year_revenues.keys():
                row_data = {'SG&A Source': f"{segment_name} SG&A"}
                base_revenue = st.session_state.base_year_revenues[segment_name]
            
                # Get SG&A percentage from segment_metrics
                if segment_name in segment_metrics:
                    sga_pct = segment_metrics[segment_name]['sga_percentage']
                else:
                    sga_pct = 0.0  # Default 0%
            
                # Historical SG&A (negative)
                row_data[hist_col] = -base_revenue * sga_pct
            
                for year in years:
                    # Calculate segment revenue for the year
                    if segment_name in segment_metrics:
                        growth_rate = segment_metrics[segment_name]['revenue_growth']
                    else:
                        growth_rate = 0.0  # Default 0%
                
                    # Base year is the latest historical year, apply growth from there
                    years_from_base = year - base_year
                    segment_revenue = base_revenue * ((1 + growth_rate) ** years_from_base)
                    segment_sga = -segment_revenue * sga_pct  # Negative value for expense
                    row_data[str(year)] = segment_sga
            
                sga_rows.append(row_data)
        
            # Total SG&A row
            total_sga_row = {'SG&A Source': 'TOTAL SG&A'}
            # Calculate historical SG&A by summing all segments (exclude subtotals)
            hist_sga_total = sum(row[hist_col] for row in sga_rows 
                               if row['SG&A Source'] not in ['TOTAL SG&A', 'Total Projects SG&A'])
            total_sga_row[hist_col] = hist_sga_total
            for year in years:
                # Exclude both TOTAL and subtotal rows from the sum
                total_sga = sum(row[str(year)] for row in sga_rows 
                              if row['SG&A Source'] not in ['TOTAL SG&A', 'Total Projects SG&A'])
                total_sga_row[str(year)] = total_sga
            sga_rows.append(total_sga_row)
        
            # Create DataFrame for SG&A (for internal use only, not displayed)
            sga_df = pd.DataFrame(sga_rows)
        
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
                # Load FA_A_processed.csv to get debt balance
                fa_annual_path = 'data/FA_A_processed.csv'
                if os.path.exists(fa_annual_path):
                    fa_annual_df = pd.read_csv(fa_annual_path)
                
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
        
            # Get cost of debt from assumptions (default 7% if not found)
            cost_of_debt = 0.0  # Default 0%
            try:
                # Load assumptions from MongoDB to get cost of debt
                from utils.mongodb_utils import load_assumptions_from_mongodb
                assumptions_list = load_assumptions_from_mongodb(selected_ticker)
                if assumptions_list:
                    for assumption in assumptions_list:
                        if assumption.get('Item') == 'Cost of Debt':
                            # Convert percentage to decimal
                            cost_of_debt = assumption.get('Value', 0.0) / 100
                            break
            except:
                pass  # Use default if error
        
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
            # For forecast, calculate as Debt Balance * Cost of Debt
            existing_debt_interest_row = {hist_col: hist_values.get('Interest expense', 0)}  # Historical from Financial_Expense
        
            for year in years:
                # Calculate interest on existing debt for forecast years
                # Interest = Debt Balance * Cost of Debt (negative for expense)
                existing_debt_interest = -abs(hist_debt * cost_of_debt) if hist_debt > 0 else 0
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
        
            # Total Revenue row
            revenue_row = {'P&L Item': 'Net Revenue'}
            revenue_row[hist_col] = total_revenue_row[hist_col]  # Add historical
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
        
            # PBT row (EBITDA + Interest where Interest is negative)
            pbt_row = {'P&L Item': 'Profit Before Tax'}
            pbt_row[hist_col] = ebitda_row[hist_col] + total_interest_row[hist_col]  # Add historical
            for year in years:
                year_str = str(year)
                # Since Interest is negative, we add it (not subtract)
                pbt_row[year_str] = ebitda_row[year_str] + total_interest_row[year_str]
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
        
            # Store project-level minority interest for breakdown display
            project_minority_interest_breakdown = {}
        
            minority_interest_row = {'P&L Item': 'Minority Interest'}
            minority_interest_row[hist_col] = hist_values.get('Minority Interest', 0)  # Historical from CSV (positive)
        
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
                
                    if project_found:
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
                    
                        # Store breakdown for display
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
            npatmi_row = {'P&L Item': 'NPATMI (Net Profit After Tax and MI)'}
            # Use actual NPATMI from historical data if available
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
                
                    # Map saved values to P&L row items
                    saved_values_map[year_str]['  Real Estate Revenue'] = saved_year.get('real_estate_revenue', None)
                    saved_values_map[year_str]['Net Revenue'] = saved_year.get('net_revenue', None)
                    saved_values_map[year_str]['  Real Estate COGS'] = saved_year.get('real_estate_cogs', None)
                    saved_values_map[year_str]['Total COGS'] = saved_year.get('total_cogs', None)
                    saved_values_map[year_str]['Gross Profit'] = saved_year.get('gross_profit', None)
                    saved_values_map[year_str]['SG&A'] = saved_year.get('sga', None)
                    saved_values_map[year_str]['EBITDA'] = saved_year.get('ebitda', None)
                    saved_values_map[year_str]['  Interest Expense - Projects'] = saved_year.get('project_interest_expense', None)
                    saved_values_map[year_str]['  Interest Expense - Existing Debt'] = saved_year.get('existing_debt_interest_expense', None)
                    saved_values_map[year_str]['Total Interest Expense'] = saved_year.get('interest_expense', None)
                    saved_values_map[year_str]['Profit Before Tax'] = saved_year.get('pbt', None)
                    saved_values_map[year_str]['Tax'] = saved_year.get('tax', None)
                    saved_values_map[year_str]['Profit After Tax'] = saved_year.get('pat', None)
                    saved_values_map[year_str]['Minority Interest'] = saved_year.get('minority_interest', None)
                    saved_values_map[year_str]['NPATMI (Net Profit After Tax and MI)'] = saved_year.get('npatmi', None)
                
                    # Map business segments
                    if 'business_segments' in saved_year:
                        for segment_name, segment_data in saved_year['business_segments'].items():
                            saved_values_map[year_str][f'  {segment_name}'] = segment_data.get('revenue', None)
                            saved_values_map[year_str][f'  {segment_name} COGS'] = segment_data.get('cogs', None)
        
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
            
                # Apply row-level styles with enhanced formatting
                for idx, row in df_style.iterrows():
                    item = pnl_df.iloc[idx]['P&L Item']
                
                    # Major totals - bold with dark background
                    if item in ['Net Revenue', 'NPATMI (Net Profit After Tax and MI)']:
                        styles.iloc[idx] = 'font-weight: bold; background-color: #d4edda; color: #155724'  # Green highlight
                    # Important subtotals - bold with light background
                    elif item in ['Total COGS', 'Gross Profit', 'EBITDA', 'Profit Before Tax', 'Profit After Tax']:
                        styles.iloc[idx] = 'font-weight: bold; background-color: #f0f2f6'  # Light gray
                    # Other totals - just bold
                    elif item in ['Total Interest Expense', 'SG&A']:
                        styles.iloc[idx] = 'font-weight: bold; background-color: #f8f9fa'  # Very light gray
                    # Minority Interest - special formatting
                    elif item == 'Minority Interest':
                        styles.iloc[idx] = 'font-style: italic; background-color: #fff3cd; color: #856404'  # Yellow highlight
                    # Tax row - red text
                    elif item == 'Tax' or 'Tax (' in item:
                        styles.iloc[idx] = 'color: #dc3545'  # Red text for expense
                    # Sub-items (indented)
                    elif item.startswith('  '):
                        styles.iloc[idx] = 'padding-left: 20px; color: #6c757d'  # Gray text for sub-items
            
                # Apply cell-level highlighting for changes
                for idx, col in changed_cells:
                    current_style = styles.at[idx, col]
                    styles.at[idx, col] = f"{current_style}; background-color: #90EE90"  # Light green
            
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
            if compare_mode and changed_cells:
                st.caption("🟢 Green cells indicate changes from saved forecast (showing: current value / saved value)")
        
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
        
            # Display Minority Interest Breakdown if there are projects with minority stakes
            if project_minority_interest_breakdown:
                st.markdown("---")
                st.subheader("Minority Interest Breakdown by Project")
                st.write("**Minority Interest Calculation Details (Billion VND)**")
            
                # Create breakdown table
                mi_breakdown_rows = []
            
                for project_name in project_minority_interest_breakdown.keys():
                    project_row = {'Project': project_name}
                    project_row[hist_col] = 0  # No historical breakdown
                
                    # Get project ownership for display
                    project_ownership = 1.0
                    for _, project in df_projects.iterrows():
                        if project.get('project_name') == project_name:
                            project_ownership = project.get('project_ownership', 1.0)
                            break
                
                    ownership_pct = project_ownership * 100
                    minority_pct = (1 - project_ownership) * 100
                
                    project_row['Ownership %'] = f"{ownership_pct:.1f}%"
                    project_row['Minority %'] = f"{minority_pct:.1f}%"
                
                    for year in years:
                        if year in project_minority_interest_breakdown[project_name]:
                            year_data = project_minority_interest_breakdown[project_name][year]
                            project_row[str(year)] = year_data['minority_interest']
                        else:
                            project_row[str(year)] = 0
                
                    mi_breakdown_rows.append(project_row)
            
                # Add total row
                total_row = {'Project': 'TOTAL MINORITY INTEREST'}
                total_row[hist_col] = minority_interest_row[hist_col]
                total_row['Ownership %'] = ''
                total_row['Minority %'] = ''
                for year in years:
                    total_row[str(year)] = minority_interest_row[str(year)]
                mi_breakdown_rows.append(total_row)
            
                # Create DataFrame
                mi_breakdown_df = pd.DataFrame(mi_breakdown_rows)
            
                # Style function for the breakdown table
                def style_mi_table(row):
                    if 'TOTAL' in str(row['Project']):
                        return ['font-weight: bold; background-color: #f0f0f0'] * len(row)
                    return [''] * len(row)
            
                # Display the breakdown table
                st.dataframe(
                    mi_breakdown_df.style
                    .format("{:,.0f}", subset=[hist_col] + [str(y) for y in years])
                    .apply(style_mi_table, axis=1),
                    use_container_width=True,
                    hide_index=True
                )
            
                st.caption("Note: Minority Interest = Project PAT × (1 - Ownership %). Only shown for profitable projects.")
        
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
        
            # Section 6: Consolidated Balance Sheet Statement
            st.markdown("---")
            st.subheader("Consolidated Balance Sheet Statement")
        
            # Initialize balance sheet items
            bs_rows = []
        
            # Initialize aggregated balance sheet data
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
        
            # Load historical balance sheet data from FA_A_processed.csv
            hist_debt = 0
            hist_inventory = 0
            hist_cash = 0
            hist_customer_prepayment = 0  # Usually not available in standard financials
            hist_retained_earnings = 0
            hist_minority_interest = 0
        
            try:
                # Load FA_A_processed.csv directly
                fa_annual_path = 'data/FA_A_processed.csv'
                if os.path.exists(fa_annual_path):
                    fa_annual_df = pd.read_csv(fa_annual_path)
                
                    # Filter for selected ticker and base year (DATE column is the year)
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
                    
                        # Get historical inventory
                        inventory_data = ticker_data[ticker_data['KEYCODE'] == 'Inventory']
                        if not inventory_data.empty:
                            hist_inventory = inventory_data['VALUE'].iloc[0] / 1e9 if not pd.isna(inventory_data['VALUE'].iloc[0]) else 0
                    
                        # Get historical cash (Cash + Cash_Equivalent)
                        cash_data = ticker_data[ticker_data['KEYCODE'] == 'Cash']
                        if not cash_data.empty:
                            hist_cash += cash_data['VALUE'].iloc[0] / 1e9 if not pd.isna(cash_data['VALUE'].iloc[0]) else 0
                    
                        cash_equiv_data = ticker_data[ticker_data['KEYCODE'] == 'Cash_Equivalent']
                        if not cash_equiv_data.empty:
                            hist_cash += cash_equiv_data['VALUE'].iloc[0] / 1e9 if not pd.isna(cash_equiv_data['VALUE'].iloc[0]) else 0
                    
                        # Customer prepayment - Load from Advance_From_Custmers (note the typo in the KEYCODE)
                        customer_advance_data = ticker_data[ticker_data['KEYCODE'] == 'Advance_From_Custmers']
                        if not customer_advance_data.empty:
                            hist_customer_prepayment = customer_advance_data['VALUE'].iloc[0] / 1e9 if not pd.isna(customer_advance_data['VALUE'].iloc[0]) else 0
                        else:
                            hist_customer_prepayment = 0
                    
                        # Get historical retained earnings
                        retained_earnings_data = ticker_data[ticker_data['KEYCODE'] == 'Retain_Earning']
                        if not retained_earnings_data.empty:
                            hist_retained_earnings = retained_earnings_data['VALUE'].iloc[0] / 1e9 if not pd.isna(retained_earnings_data['VALUE'].iloc[0]) else 0
                    
                        # Get historical minority interest (balance sheet item, not earnings)
                        minority_interest_data = ticker_data[ticker_data['KEYCODE'] == 'Minority_Interest']
                        if not minority_interest_data.empty:
                            hist_minority_interest = minority_interest_data['VALUE'].iloc[0] / 1e9 if not pd.isna(minority_interest_data['VALUE'].iloc[0]) else 0
                    else:
                        st.info(f"No historical data found for {selected_ticker} in year {base_year}")
                else:
                    st.warning(f"Historical data file not found: {fa_annual_path}")
            except Exception as e:
                st.warning(f"Could not load historical balance sheet data: {str(e)}")
        
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
                prev_debt = 0
                prev_inventory = 0
                prev_prepayment = 0
                prev_cash = 0
            
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
                        # Calculate net change and add to total changes
                        inventory_changes_by_year[year_str] += (current_inventory - prev_inventory)
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
        
            # Now calculate cumulative totals for each year
            for year_str in [str(y) for y in years]:
                # Add the year's changes to the cumulative totals
                cumulative_debt += debt_changes_by_year[year_str]
                cumulative_inventory += inventory_changes_by_year[year_str]
                cumulative_prepayment += prepayment_changes_by_year[year_str]
                cumulative_cash += cash_changes_by_year[year_str]
            
                # Store the cumulative totals
                total_debt_by_year[year_str] = cumulative_debt
                total_inventory_by_year[year_str] = cumulative_inventory
                total_customer_prepayment_by_year[year_str] = cumulative_prepayment
                total_cash_by_year[year_str] = cumulative_cash
        
            # Track breakdown by project for debugging
            debt_breakdown = {}
            inventory_breakdown = {}
            prepayment_breakdown = {}
            cash_breakdown = {}
        
            # Populate breakdown data from the aggregation loop above
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
        
            # DEBT SECTION
            # Add individual project debt rows (showing each project's balance)
            for project_name in debt_breakdown.keys():
                project_debt_row = {'Balance Sheet Item': f'  {project_name} Debt'}
                project_debt_row[hist_col] = 0  # No historical breakdown by project
                for year in years:
                    project_debt_row[str(year)] = debt_breakdown[project_name][str(year)]
                bs_rows.append(project_debt_row)
        
            # Total Debt row
            debt_row = {'Balance Sheet Item': 'TOTAL DEBT'}
            debt_row[hist_col] = hist_debt
            for year in years:
                debt_row[str(year)] = total_debt_by_year[str(year)]
            bs_rows.append(debt_row)
        
            # INVENTORY SECTION
            # Add individual project inventory rows
            for project_name in inventory_breakdown.keys():
                project_inv_row = {'Balance Sheet Item': f'  {project_name} Inventory'}
                project_inv_row[hist_col] = 0  # No historical breakdown by project
                for year in years:
                    project_inv_row[str(year)] = inventory_breakdown[project_name][str(year)]
                bs_rows.append(project_inv_row)
        
            # Total Inventory row
            inventory_row = {'Balance Sheet Item': 'TOTAL INVENTORY'}
            inventory_row[hist_col] = hist_inventory
            for year in years:
                inventory_row[str(year)] = total_inventory_by_year[str(year)]
            bs_rows.append(inventory_row)
        
            # CUSTOMER PREPAYMENT SECTION
            # Add individual project prepayment rows
            for project_name in prepayment_breakdown.keys():
                project_prep_row = {'Balance Sheet Item': f'  {project_name} Prepayment'}
                project_prep_row[hist_col] = 0  # No historical breakdown by project
                for year in years:
                    project_prep_row[str(year)] = prepayment_breakdown[project_name][str(year)]
                bs_rows.append(project_prep_row)
        
            # Total Customer Prepayment row
            prepayment_row = {'Balance Sheet Item': 'TOTAL CUSTOMER PREPAYMENT'}
            prepayment_row[hist_col] = hist_customer_prepayment
            for year in years:
                prepayment_row[str(year)] = total_customer_prepayment_by_year[str(year)]
            bs_rows.append(prepayment_row)
        
            # CASH SECTION
            # Add individual project cash rows
            for project_name in cash_breakdown.keys():
                project_cash_row = {'Balance Sheet Item': f'  {project_name} Cash'}
                project_cash_row[hist_col] = 0  # No historical breakdown by project
                for year in years:
                    project_cash_row[str(year)] = cash_breakdown[project_name][str(year)]
                bs_rows.append(project_cash_row)
        
            # Add net cash change from other business segments
            # Calculate as cumulative revenue - COGS from other segments
            other_segment_cash_row = {'Balance Sheet Item': '  Net Cash from Other Segments'}
            other_segment_cash_row[hist_col] = 0  # No historical breakdown
            cumulative_other_cash = 0
            for year in years:
                # Net cash = Revenue - COGS from other business segments
                other_revenue = other_revenue_by_year.get(year, 0)
                other_cogs = other_cogs_by_year.get(year, 0)
                net_cash_from_other = other_revenue - other_cogs
                cumulative_other_cash += net_cash_from_other
                other_segment_cash_row[str(year)] = cumulative_other_cash
            bs_rows.append(other_segment_cash_row)
        
            # Total Cash row (includes historical + project cash + other segment cash)
            cash_row = {'Balance Sheet Item': 'TOTAL CASH'}
            cash_row[hist_col] = hist_cash
            for year in years:
                # Total cash = project cash + cumulative cash from other segments
                year_str = str(year)
                # Get cumulative cash from other segments up to this year
                cumulative_other = 0
                for y in years:
                    if y <= year:
                        other_revenue = other_revenue_by_year.get(y, 0)
                        other_cogs = other_cogs_by_year.get(y, 0)
                        cumulative_other += (other_revenue - other_cogs)
                    else:
                        break
                cash_row[year_str] = total_cash_by_year[year_str] + cumulative_other
            bs_rows.append(cash_row)
        
            # Add separator row
            separator_row = {'Balance Sheet Item': '─' * 30}
            for col in [hist_col] + [str(y) for y in years]:
                separator_row[col] = None
            bs_rows.append(separator_row)
        
            # CALCULATED METRICS
            # Net Debt (Debt - Cash)
            net_debt_row = {'Balance Sheet Item': 'NET DEBT (Debt - Cash)'}
            net_debt_row[hist_col] = hist_debt - hist_cash
            for year in years:
                year_str = str(year)
                # Use the updated total cash that includes other segments
                total_cash_with_other = cash_row[year_str]
                net_debt_row[year_str] = total_debt_by_year[year_str] - total_cash_with_other
            bs_rows.append(net_debt_row)
        
            # Working Capital (Inventory + Cash - Customer Prepayment)
            working_capital_row = {'Balance Sheet Item': 'WORKING CAPITAL'}
            working_capital_row[hist_col] = hist_inventory + hist_cash - hist_customer_prepayment
            for year in years:
                year_str = str(year)
                # Use the updated total cash that includes other segments
                total_cash_with_other = cash_row[year_str]
                working_capital_row[year_str] = (total_inventory_by_year[year_str] + 
                                                 total_cash_with_other - 
                                                 total_customer_prepayment_by_year[year_str])
            bs_rows.append(working_capital_row)
        
            # Add another separator row
            separator_row2 = {'Balance Sheet Item': '─' * 30}
            for col in [hist_col] + [str(y) for y in years]:
                separator_row2[col] = None
            bs_rows.append(separator_row2)
        
            # EQUITY SECTION
            # Retained Earnings
            retained_earnings_row_bs = {'Balance Sheet Item': 'Retained Earnings'}
            retained_earnings_row_bs[hist_col] = hist_retained_earnings
        
            # Calculate cumulative retained earnings for forecast years
            cumulative_retained_earnings = hist_retained_earnings
            for year in years:
                year_str = str(year)
                # Get NPATMI for this year from consolidated P&L (already calculated above)
                npatmi_for_year = npatmi_row.get(year_str, 0) if 'npatmi_row' in locals() else 0
            
                # Add NPATMI to cumulative retained earnings
                cumulative_retained_earnings += npatmi_for_year
                retained_earnings_row_bs[year_str] = cumulative_retained_earnings
            bs_rows.append(retained_earnings_row_bs)
        
            # Minority Interest
            minority_interest_row_bs = {'Balance Sheet Item': 'Minority Interest'}
            minority_interest_row_bs[hist_col] = hist_minority_interest
        
            # Calculate cumulative minority interest for forecast years
            cumulative_minority_interest = hist_minority_interest
            for year in years:
                year_str = str(year)
                # Get minority interest for this year from consolidated P&L (already calculated above)
                minority_for_year = minority_interest_row.get(year_str, 0) if 'minority_interest_row' in locals() else 0
            
                # Add to cumulative minority interest
                cumulative_minority_interest += minority_for_year
                minority_interest_row_bs[year_str] = cumulative_minority_interest
            bs_rows.append(minority_interest_row_bs)
        
            # Total Equity
            total_equity_row = {'Balance Sheet Item': 'TOTAL EQUITY'}
            total_equity_row[hist_col] = hist_retained_earnings + hist_minority_interest
            for year in years:
                year_str = str(year)
                total_equity_row[year_str] = retained_earnings_row_bs[year_str] + minority_interest_row_bs[year_str]
            bs_rows.append(total_equity_row)
        
            # Create DataFrame
            bs_df = pd.DataFrame(bs_rows)
        
            st.write("**Consolidated Balance Sheet Items (Billion VND)**")
        
            # Style function to highlight key rows
            def style_bs_table(row):
                item = str(row['Balance Sheet Item'])
                # Total rows - bold with background
                if item in ['TOTAL DEBT', 'TOTAL INVENTORY', 'TOTAL CUSTOMER PREPAYMENT', 'TOTAL CASH', 'TOTAL EQUITY']:
                    return ['font-weight: bold; background-color: #e6f2ff'] * len(row)
                # Calculated metrics - bold with different background
                elif item in ['NET DEBT (Debt - Cash)', 'WORKING CAPITAL']:
                    return ['font-weight: bold; background-color: #f0f0f0'] * len(row)
                # Equity components - with light green background
                elif item in ['Retained Earnings', 'Minority Interest']:
                    return ['background-color: #e8f5e9'] * len(row)
                # Project details - indented with lighter font
                elif item.startswith('  '):
                    return ['padding-left: 20px; color: #666'] * len(row)
                # Separator row
                elif '─' in item:
                    return ['border-top: 2px solid #ccc'] * len(row)
                return [''] * len(row)
        
            # Define column configuration
            bs_column_config = {
                'Balance Sheet Item': st.column_config.TextColumn('Balance Sheet Item', width='medium'),
            }
            for col in [hist_col] + [str(y) for y in years]:
                bs_column_config[col] = st.column_config.NumberColumn(col, width='small')
        
            # Format function to handle NaN values
            def format_bs_value(x):
                if pd.isna(x) or x is None:
                    return "-"
                try:
                    return f"{int(x):,}"
                except (ValueError, OverflowError):
                    return f"{x:,.0f}"
            
            st.dataframe(
                bs_df.style
                .format(format_bs_value, subset=[hist_col] + [str(y) for y in years])
                .apply(style_bs_table, axis=1),
                use_container_width=True,
                column_config=bs_column_config,
                hide_index=True
            )
    
            # Section 7: Consolidated Cash Flow Statement
            st.markdown("---")
            st.subheader("Consolidated Cash Flow Statement")
        
            # Initialize cash flow items
            cf_rows = []
        
            # Initialize aggregated cash flow data by year
            operating_cf_by_year = {}
            investing_cf_by_year = {}
            financing_cf_by_year = {}
            net_cf_by_year = {}
        
            # Initialize breakdown components for operating cash flow
            other_segment_revenue_cf = {}  # Revenue from non-real estate segments
            other_segment_cogs_cf = {}  # COGS from non-real estate segments
            presales_cf_breakdown = {}  # Cash inflow from project presales
            interest_outflow_breakdown = {}  # Interest expense outflow
            sga_outflow_breakdown = {}  # SG&A expense outflow
            tax_outflow_breakdown = {}  # Tax expense outflow
        
            # Initialize breakdown for investing and financing
            land_outflow_breakdown = {}  # Land payment breakdown by project
            construction_outflow_breakdown = {}  # Construction cost breakdown by project
            investing_cf_breakdown = {}  # Total investing CF (land + construction)
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
            # Revenue comes from other_revenue_breakdown, COGS calculated from gross margin
            if other_revenue_breakdown:  # Only if there are other business segments
                for segment_name, segment_revenue in other_revenue_breakdown.items():
                    for year in years:
                        year_str = str(year)
                        revenue = segment_revenue.get(year_str, 0)
                        other_segment_revenue_cf[year_str] += revenue
                        operating_cf_by_year[year_str] += revenue
                    
                        # Calculate COGS for this segment
                        # Get gross margin from segment_metrics
                        if segment_name in segment_metrics:
                            gross_margin = segment_metrics[segment_name]['gross_margin']
                        else:
                            gross_margin = 0.0  # Default 30%
                    
                        # COGS = Revenue * (1 - Gross Margin)
                        segment_cogs = revenue * (1 - gross_margin)
                        other_segment_cogs_cf[year_str] += segment_cogs
                        # Subtract COGS from operating CF (it's an outflow)
                        operating_cf_by_year[year_str] -= segment_cogs
        
            # 2. Aggregate cash flows from all projects
            for _, project in df_projects.iterrows():
                project_name = project.get('project_name', 'Unknown')
                financial_statements = project.get('comprehensive_financial_statements', {})
                
                # Ensure financial_statements is a dictionary
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
                        cashflow_data = year_data.get('cashflow', {})
                        pnl_data = year_data.get('pnl', {})
                    
                        # Operating Cash Flow Components:
                        # Cash inflow from presales (customer deposits) - directly from MongoDB
                        presales_inflow = year_data.get('cash_inflow_presales', 0) / 1e9
                        presales_cf_breakdown[project_name][year_str] = presales_inflow
                        operating_cf_by_year[year_str] += presales_inflow
                    
                        # Cash outflow from interest expense (already negative in MongoDB)
                        interest_outflow = year_data.get('cash_outflow_interest', 0) / 1e9
                        interest_outflow_breakdown[project_name][year_str] = interest_outflow
                        operating_cf_by_year[year_str] += interest_outflow
                    
                        # Cash outflow from SG&A expense (already negative in MongoDB)
                        sga_outflow = year_data.get('cash_outflow_sga', 0) / 1e9
                        sga_outflow_breakdown[project_name][year_str] = sga_outflow
                        operating_cf_by_year[year_str] += sga_outflow
                    
                        # Cash outflow from tax expense (already negative in MongoDB)
                        tax_outflow = year_data.get('cash_outflow_tax', 0) / 1e9
                        tax_outflow_breakdown[project_name][year_str] = tax_outflow
                        operating_cf_by_year[year_str] += tax_outflow
                    
                        # Investing Cash Flow (land and construction cash outflows)
                        # Both are already negative in MongoDB
                        land_outflow = year_data.get('cash_outflow_land', 0) / 1e9
                        construction_outflow = year_data.get('cash_outflow_construction', 0) / 1e9
                    
                        # Store separate breakdowns
                        land_outflow_breakdown[project_name][year_str] = land_outflow
                        construction_outflow_breakdown[project_name][year_str] = construction_outflow
                    
                        # Total investing CF
                        investing_cf = land_outflow + construction_outflow
                        investing_cf_by_year[year_str] += investing_cf
                        investing_cf_breakdown[project_name][year_str] = investing_cf
                    
                        # Financing Cash Flow (debt disbursement and repayment)
                        debt_disbursement = year_data.get('debt_disbursement', 0) / 1e9
                        debt_repayment = year_data.get('debt_repayment', 0) / 1e9  # Already negative in MongoDB
                        financing_cf = debt_disbursement + debt_repayment
                        financing_cf_by_year[year_str] += financing_cf
                        financing_cf_breakdown[project_name][year_str] = financing_cf
                    else:
                        # No data for this year
                        presales_cf_breakdown[project_name][year_str] = 0
                        interest_outflow_breakdown[project_name][year_str] = 0
                        sga_outflow_breakdown[project_name][year_str] = 0
                        tax_outflow_breakdown[project_name][year_str] = 0
                        land_outflow_breakdown[project_name][year_str] = 0
                        construction_outflow_breakdown[project_name][year_str] = 0
                        investing_cf_breakdown[project_name][year_str] = 0
                        financing_cf_breakdown[project_name][year_str] = 0
        
            # Calculate net cash flow for each year
            for year in years:
                year_str = str(year)
                net_cf_by_year[year_str] = (operating_cf_by_year[year_str] + 
                                           investing_cf_by_year[year_str] + 
                                           financing_cf_by_year[year_str])
        
            # Build the cash flow table rows
            # Operating Cash Flow Section
            cf_rows.append({'Cash Flow Item': 'OPERATING ACTIVITIES', **{str(y): None for y in years}})
        
            # Operating Cash Inflows
            cf_rows.append({'Cash Flow Item': '  Cash Inflows:', **{str(y): None for y in years}})
        
            # Revenue from other business segments
            if any(other_segment_revenue_cf[str(y)] != 0 for y in years):
                other_revenue_row = {'Cash Flow Item': '    Revenue from Other Segments'}
                for year in years:
                    other_revenue_row[str(year)] = other_segment_revenue_cf[str(year)]
                cf_rows.append(other_revenue_row)
        
            # Presales cash inflow by project
            for project_name in sorted(presales_cf_breakdown.keys()):
                if any(presales_cf_breakdown[project_name].get(str(y), 0) != 0 for y in years):
                    project_row = {'Cash Flow Item': f'    Presales - {project_name}'}
                    for year in years:
                        year_str = str(year)
                        project_row[year_str] = presales_cf_breakdown[project_name].get(year_str, 0)
                    cf_rows.append(project_row)
        
            # Operating Cash Outflows
            cf_rows.append({'Cash Flow Item': '  Cash Outflows:', **{str(y): None for y in years}})
        
            # COGS from other business segments
            if any(other_segment_cogs_cf[str(y)] != 0 for y in years):
                cogs_row = {'Cash Flow Item': '    COGS - Other Business Segments'}
                for year in years:
                    cogs_row[str(year)] = -other_segment_cogs_cf[str(year)]  # Show as negative
                cf_rows.append(cogs_row)
        
            # Interest expense outflow by project
            for project_name in sorted(interest_outflow_breakdown.keys()):
                if any(interest_outflow_breakdown[project_name].get(str(y), 0) != 0 for y in years):
                    project_row = {'Cash Flow Item': f'    Interest Expense - {project_name}'}
                    for year in years:
                        year_str = str(year)
                        project_row[year_str] = interest_outflow_breakdown[project_name].get(year_str, 0)
                    cf_rows.append(project_row)
        
            # SG&A expense outflow by project
            for project_name in sorted(sga_outflow_breakdown.keys()):
                if any(sga_outflow_breakdown[project_name].get(str(y), 0) != 0 for y in years):
                    project_row = {'Cash Flow Item': f'    SG&A Expense - {project_name}'}
                    for year in years:
                        year_str = str(year)
                        project_row[year_str] = sga_outflow_breakdown[project_name].get(year_str, 0)
                    cf_rows.append(project_row)
        
            # Tax expense outflow by project
            for project_name in sorted(tax_outflow_breakdown.keys()):
                if any(tax_outflow_breakdown[project_name].get(str(y), 0) != 0 for y in years):
                    project_row = {'Cash Flow Item': f'    Tax Expense - {project_name}'}
                    for year in years:
                        year_str = str(year)
                        project_row[year_str] = tax_outflow_breakdown[project_name].get(year_str, 0)
                    cf_rows.append(project_row)
        
            # Total Operating CF
            operating_total_row = {'Cash Flow Item': 'TOTAL OPERATING CASH FLOW'}
            for year in years:
                operating_total_row[str(year)] = operating_cf_by_year[str(year)]
            cf_rows.append(operating_total_row)
        
            # Add separator
            cf_rows.append({'Cash Flow Item': '', **{str(y): None for y in years}})
        
            # Investing Cash Flow Section
            cf_rows.append({'Cash Flow Item': 'INVESTING ACTIVITIES', **{str(y): None for y in years}})
        
            # Land Payment Outflows
            cf_rows.append({'Cash Flow Item': '  Land Payments:', **{str(y): None for y in years}})
            for project_name in sorted(land_outflow_breakdown.keys()):
                if any(land_outflow_breakdown[project_name].get(str(y), 0) != 0 for y in years):
                    project_row = {'Cash Flow Item': f'    Land Payment - {project_name}'}
                    for year in years:
                        year_str = str(year)
                        project_row[year_str] = land_outflow_breakdown[project_name].get(year_str, 0)
                    cf_rows.append(project_row)
        
            # Construction Cost Outflows
            cf_rows.append({'Cash Flow Item': '  Construction Costs:', **{str(y): None for y in years}})
            for project_name in sorted(construction_outflow_breakdown.keys()):
                if any(construction_outflow_breakdown[project_name].get(str(y), 0) != 0 for y in years):
                    project_row = {'Cash Flow Item': f'    Construction - {project_name}'}
                    for year in years:
                        year_str = str(year)
                        project_row[year_str] = construction_outflow_breakdown[project_name].get(year_str, 0)
                    cf_rows.append(project_row)
        
            # Total Investing CF
            investing_total_row = {'Cash Flow Item': 'TOTAL INVESTING CASH FLOW'}
            for year in years:
                investing_total_row[str(year)] = investing_cf_by_year[str(year)]
            cf_rows.append(investing_total_row)
        
            # Add separator
            cf_rows.append({'Cash Flow Item': '', **{str(y): None for y in years}})
        
            # Financing Cash Flow Section
            cf_rows.append({'Cash Flow Item': 'FINANCING ACTIVITIES', **{str(y): None for y in years}})
        
            # Add breakdown by project for financing CF
            for project_name in sorted(financing_cf_breakdown.keys()):
                project_row = {'Cash Flow Item': f'  └─ {project_name}'}
                for year in years:
                    year_str = str(year)
                    project_row[year_str] = financing_cf_breakdown[project_name].get(year_str, 0)
                cf_rows.append(project_row)
        
            # Total Financing CF
            financing_total_row = {'Cash Flow Item': 'TOTAL FINANCING CASH FLOW'}
            for year in years:
                financing_total_row[str(year)] = financing_cf_by_year[str(year)]
            cf_rows.append(financing_total_row)
        
            # Add separator with line
            cf_rows.append({'Cash Flow Item': '─' * 30, **{str(y): None for y in years}})
        
            # Net Cash Flow
            net_cf_row = {'Cash Flow Item': 'NET CASH FLOW'}
            for year in years:
                net_cf_row[str(year)] = net_cf_by_year[str(year)]
            cf_rows.append(net_cf_row)
        
            # Create DataFrame
            cf_df = pd.DataFrame(cf_rows)
        
            st.write("**Consolidated Cash Flow Statement (Billion VND)**")
        
            # Define style function for formatting
            def style_cf_table(val):
                if pd.isna(val) or val is None:
                    return ''
                if isinstance(val, str):
                    return ''
                # Color code: positive cash flow green, negative red
                color = '#28a745' if val >= 0 else '#dc3545'
                return f'color: {color}'
        
            # Apply styling to numeric columns
            styled_cf_df = cf_df.style.applymap(
                style_cf_table,
                subset=[str(y) for y in years]
            ).format(
                {str(y): lambda x: f"{int(x):,}" if pd.notna(x) and x != 0 and not pd.isna(x) else "-" 
                 for y in years},
                na_rep="-"
            )
        
            # Apply row highlighting for totals and net cash flow
            def highlight_important_rows(row):
                styles = [''] * len(row)
                if 'TOTAL' in str(row.iloc[0]) or 'NET CASH FLOW' in str(row.iloc[0]):
                    styles = ['font-weight: bold; background-color: #f8f9fa'] * len(row)
                elif any(keyword in str(row.iloc[0]) for keyword in ['OPERATING ACTIVITIES', 'INVESTING ACTIVITIES', 'FINANCING ACTIVITIES']):
                    styles = ['font-weight: bold; background-color: #e9ecef'] * len(row)
                return styles
        
            styled_cf_df = styled_cf_df.apply(highlight_important_rows, axis=1)
        
            # Display the table
            st.dataframe(
                styled_cf_df,
                use_container_width=True,
                hide_index=True
            )
        
        
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
                    
                        # Consolidated P&L Statement
                        pnl_data = {
                            'real_estate_revenue': convert_to_native(re_revenue_row.get(year_str, 0)),
                            'other_revenue': convert_to_native(revenue_row.get(year_str, 0) - re_revenue_row.get(year_str, 0)),
                            'net_revenue': convert_to_native(revenue_row.get(year_str, 0)),
                            'real_estate_cogs': convert_to_native(re_cogs_row.get(year_str, 0)),
                            'other_cogs': convert_to_native(total_cogs_pnl_row.get(year_str, 0) - re_cogs_row.get(year_str, 0)),
                            'total_cogs': convert_to_native(total_cogs_pnl_row.get(year_str, 0)),
                            'gross_profit': convert_to_native(gp_row.get(year_str, 0)),
                            'sga': convert_to_native(sga_row.get(year_str, 0)),
                            'ebitda': convert_to_native(ebitda_row.get(year_str, 0)),
                            'project_interest_expense': convert_to_native(project_interest_pnl_row.get(year_str, 0)),
                            'existing_debt_interest_expense': convert_to_native(existing_interest_pnl_row.get(year_str, 0)),
                            'interest_expense': convert_to_native(interest_row.get(year_str, 0)),
                            'pbt': convert_to_native(pbt_row.get(year_str, 0)),
                            'tax': convert_to_native(tax_row.get(year_str, 0)),
                            'pat': convert_to_native(pat_row.get(year_str, 0)),
                            'minority_interest': convert_to_native(minority_interest_row.get(year_str, 0)),
                            'npatmi': convert_to_native(npatmi_row.get(year_str, 0))
                        }
                    
                        # Consolidated Balance Sheet
                        balance_sheet_data = {
                            # Assets
                            'total_debt': convert_to_native(debt_row.get(year_str, 0)),
                            'total_inventory': convert_to_native(inventory_row.get(year_str, 0)),
                            'total_customer_prepayment': convert_to_native(prepayment_row.get(year_str, 0)),
                            'total_cash': convert_to_native(cash_row.get(year_str, 0)),
                            'net_debt': convert_to_native(net_debt_row.get(year_str, 0)),
                            'working_capital': convert_to_native(working_capital_row.get(year_str, 0)),
                            # Equity
                            'retained_earnings': convert_to_native(retained_earnings_row_bs.get(year_str, 0)),
                            'minority_interest_bs': convert_to_native(minority_interest_row_bs.get(year_str, 0)),
                            'total_equity': convert_to_native(total_equity_row.get(year_str, 0))
                        }
                    
                        # Consolidated Cash Flow Statement
                        cash_flow_data = {
                            'operating_cf': convert_to_native(operating_cf_by_year.get(year_str, 0)),
                            'investing_cf': convert_to_native(investing_cf_by_year.get(year_str, 0)),
                            'financing_cf': convert_to_native(financing_cf_by_year.get(year_str, 0)),
                            'net_cf': convert_to_native(net_cf_by_year.get(year_str, 0)),
                            # Operating CF breakdown
                            'other_segment_revenue_cf': convert_to_native(other_segment_revenue_cf.get(year_str, 0)),
                            'other_segment_cogs_cf': convert_to_native(other_segment_cogs_cf.get(year_str, 0)),
                            'presales_cf': convert_to_native(sum(presales_cf_breakdown.get(p, {}).get(year_str, 0) for p in presales_cf_breakdown)),
                            'interest_outflow': convert_to_native(sum(interest_outflow_breakdown.get(p, {}).get(year_str, 0) for p in interest_outflow_breakdown)),
                            'sga_outflow': convert_to_native(sum(sga_outflow_breakdown.get(p, {}).get(year_str, 0) for p in sga_outflow_breakdown)),
                            'tax_outflow': convert_to_native(sum(tax_outflow_breakdown.get(p, {}).get(year_str, 0) for p in tax_outflow_breakdown)),
                            # Investing CF breakdown
                            'land_outflow': convert_to_native(sum(land_outflow_breakdown.get(p, {}).get(year_str, 0) for p in land_outflow_breakdown)),
                            'construction_outflow': convert_to_native(sum(construction_outflow_breakdown.get(p, {}).get(year_str, 0) for p in construction_outflow_breakdown)),
                            # Financing CF breakdown
                            'debt_changes': convert_to_native(sum(financing_cf_breakdown.get(p, {}).get(year_str, 0) for p in financing_cf_breakdown))
                        }
                    
                        # Business segments detail
                        business_segments_data = {}
                        for segment_name in st.session_state.base_year_revenues.keys():
                            if segment_name in segment_revenue_data:
                                business_segments_data[segment_name] = {
                                    'revenue': convert_to_native(segment_revenue_data[segment_name].get(year_str, 0)),
                                    'cogs': convert_to_native(segment_cogs_data[segment_name].get(year_str, 0)),
                                    'gross_profit': convert_to_native(segment_revenue_data[segment_name].get(year_str, 0) + segment_cogs_data[segment_name].get(year_str, 0))
                                }
                    
                        # Combine all statements for this year
                        consolidated_data['financial_statements'][year_str] = {
                            'pnl': pnl_data,
                            'balance_sheet': balance_sheet_data,
                            'cash_flow': cash_flow_data,
                            'business_segments': business_segments_data,
                            'project_breakdown': {
                                'revenue': {p: convert_to_native(project_revenue_breakdown.get(p, {}).get(year, 0)) for p in project_revenue_breakdown},
                                'cogs': {p: convert_to_native(project_cogs_breakdown.get(p, {}).get(year, 0)) for p in project_cogs_breakdown},
                                'sga': {p: convert_to_native(project_sga_breakdown.get(p, {}).get(year, 0)) for p in project_sga_breakdown},
                                'interest': {p: convert_to_native(project_interest_breakdown.get(p, {}).get(year, 0)) for p in project_interest_breakdown}
                            }
                        }
                
                    # Add historical data for reference - convert all values
                    consolidated_data['historical'] = {
                        'debt': convert_to_native(hist_debt),
                        'inventory': convert_to_native(hist_inventory),
                        'cash': convert_to_native(hist_cash),
                        'customer_prepayment': convert_to_native(hist_customer_prepayment),
                        'retained_earnings': convert_to_native(hist_retained_earnings),
                        'minority_interest': convert_to_native(hist_minority_interest),
                        'pnl_items': {k: convert_to_native(v) for k, v in hist_values.items()}
                    }
                
                    # Save to MongoDB with new collection structure
                    # Apply deep conversion to entire consolidated_data to ensure all numpy types are converted
                    consolidated_data = convert_to_native(consolidated_data)
                    
                    # Save all three financial statements to CompanyForecast collection
                    from utils.mongodb_utils import save_company_forecast
                    
                    # Extract all financial statements data for CompanyForecast collection
                    forecast_data = {}
                    for year_str, year_data in consolidated_data['financial_statements'].items():
                        forecast_data[year_str] = {
                            'pnl': year_data.get('pnl', {}),
                            'balance_sheet': year_data.get('balance_sheet', {}),
                            'cash_flow': year_data.get('cash_flow', {}),
                            'business_segments': year_data.get('business_segments', {}),
                            'project_breakdown': year_data.get('project_breakdown', {})
                        }
                    
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

