#%%
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime


class RevenueForecastTab:
    """Revenue forecast tab with highly optimized vectorized calculations"""
    
    def __init__(self, parent):
        self.parent = parent
    
    def render(self):
        """Render comprehensive revenue forecast including projects and other revenue streams"""
        st.header("Revenue & COGS Forecast")
        
        # Get selected ticker
        selected_ticker = st.session_state.get('selected_company', None)
        if not selected_ticker:
            st.info("Please select a company from the sidebar")
            return
        
        # Load assumptions and initialize data
        company_assumptions = self._load_company_assumptions(selected_ticker)
        self._initialize_revenue_streams(selected_ticker, company_assumptions)
        
        # Load historical data if needed
        self._ensure_historical_data_loaded(selected_ticker)
        
        # Get base year and historical values
        base_year, hist_values = self._get_historical_baseline()
        
        # Generate revenue forecast data
        revenue_forecast = self.parent.generate_revenue_forecast()
        years = revenue_forecast['years']
        
        # Process project data with vectorized operations
        project_data = self._process_project_data_vectorized(years)
        
        # Process business segments with vectorized operations
        segment_data = self._process_business_segments_vectorized(
            years, base_year, company_assumptions
        )
        
        # Render sections
        self._render_business_segments_section(company_assumptions, base_year)
        self._render_revenue_forecast_section(
            project_data, segment_data, years, base_year, hist_values
        )
        self._render_cogs_section(
            project_data, segment_data, years, base_year, hist_values
        )
        self._render_gross_profit_section(
            project_data, segment_data, years, base_year
        )
    
    def _load_company_assumptions(self, selected_ticker):
        """Load company assumptions from MongoDB"""
        from utils.mongodb_utils import get_company_assumptions
        return get_company_assumptions(selected_ticker)
    
    def _initialize_revenue_streams(self, selected_ticker, company_assumptions):
        """Initialize session state for revenue streams"""
        revenue_key = f'base_year_revenues_{selected_ticker}'
        if revenue_key not in st.session_state:
            st.session_state[revenue_key] = {}
        
        # For backward compatibility, sync with general base_year_revenues
        st.session_state.base_year_revenues = st.session_state[revenue_key]
    
    def _ensure_historical_data_loaded(self, selected_ticker):
        """Ensure historical data is loaded"""
        if st.session_state.get('historical_data') is None and selected_ticker:
            with st.spinner(f"Loading historical data for {selected_ticker}..."):
                historical_data = self.parent.load_historical_data_from_csv(selected_ticker)
                if not historical_data.empty:
                    st.session_state.historical_data = historical_data
                    st.success(f"Loaded historical data with {len(historical_data)} records")
                else:
                    st.warning(f"No historical data found for {selected_ticker}")
    
    def _get_historical_baseline(self):
        """Get base year and historical values with vectorized processing"""
        base_year = st.session_state.get('base_year', 2024)
        hist_values = {}
        
        historical_data = st.session_state.get('historical_data')
        
        if historical_data is not None and not historical_data.empty:
            # Vectorized year extraction
            try:
                years_in_data = pd.to_numeric(historical_data.index, errors='coerce')
                years_in_data = years_in_data.dropna().astype(int)
                if len(years_in_data) > 0:
                    base_year = years_in_data.max()
                else:
                    base_year = 2024
            except:
                base_year = 2024
            
            st.session_state.base_year = base_year
            
            # Vectorized historical data extraction
            if base_year in historical_data.index:
                hist_row = historical_data.loc[base_year]
                
                # Vectorized conversion to billions
                hist_columns = {
                    'Net Revenue': 'Net_Revenue',
                    'Gross profit': 'Gross_Profit', 
                    'EBIT': 'EBIT',
                    'NPATMI': 'NPATMI',
                    'Interest expense': 'Interest_Expense'
                }
                
                for key, col in hist_columns.items():
                    if col in hist_row and pd.notna(hist_row[col]):
                        value = hist_row[col] / 1e9
                        hist_values[key] = abs(value) if 'expense' in key.lower() else value
                    else:
                        hist_values[key] = 0
                
                # Calculate COGS if available
                if hist_values['Net Revenue'] > 0 and hist_values['Gross profit'] >= 0:
                    hist_values['COGS'] = hist_values['Net Revenue'] - hist_values['Gross profit']
                else:
                    hist_values['COGS'] = 0
        
        return base_year, hist_values
    
    def _process_project_data_vectorized(self, years):
        """Process project data using vectorized operations"""
        project_data = {
            'revenue_by_year': {year: 0 for year in years},
            'cogs_by_year': {year: 0 for year in years},
            'breakdown': {}
        }
        
        df_projects = st.session_state.project_data
        if df_projects is None or df_projects.empty:
            return project_data
        
        # Initialize breakdown structures
        breakdown_keys = ['revenue', 'cogs', 'land', 'sga', 'interest']
        for key in breakdown_keys:
            project_data['breakdown'][key] = {}
        
        # Vectorized processing of all projects
        for _, project in df_projects.iterrows():
            project_name = project.get('project_name', 'Unknown')
            pnl_schedule = project.get('pnl_schedule', {})
            
            if not isinstance(pnl_schedule, dict):
                continue
            
            # Initialize project in breakdown
            for key in breakdown_keys:
                project_data['breakdown'][key][project_name] = {}
            
            # Vectorized year processing
            for year in years:
                year_str = str(year)
                
                if year_str in pnl_schedule:
                    year_pnl = pnl_schedule[year_str]
                    
                    # Extract all values at once
                    revenue = year_pnl.get('revenue', 0)
                    construction = year_pnl.get('construction_cost', 0)
                    land = year_pnl.get('land_cost', 0)
                    sga = year_pnl.get('sga', 0)
                    interest = year_pnl.get('interest_expense', 0)
                    
                    # Update totals
                    project_data['revenue_by_year'][year] += revenue
                    project_data['cogs_by_year'][year] += (construction + land)
                    
                    # Update breakdown
                    project_data['breakdown']['revenue'][project_name][year] = revenue
                    project_data['breakdown']['cogs'][project_name][year] = construction + land
                    project_data['breakdown']['land'][project_name][year] = land
                    project_data['breakdown']['sga'][project_name][year] = sga
                    project_data['breakdown']['interest'][project_name][year] = interest
                else:
                    # Zero values for missing years
                    for key in breakdown_keys:
                        project_data['breakdown'][key][project_name][year] = 0
        
        return project_data
    
    def _process_business_segments_vectorized(self, years, base_year, company_assumptions):
        """Process business segments using vectorized operations"""
        segment_data = {
            'revenue_by_year': {year: 0 for year in years},
            'cogs_by_year': {year: 0 for year in years},
            'segments': {}
        }
        
        revenue_streams = company_assumptions.get('revenue_streams', [])
        base_revenues = st.session_state.base_year_revenues
        
        # Extract segment metrics
        segment_metrics = {}
        for stream in revenue_streams:
            segment_name = stream.get('segment_name', '')
            if segment_name and 'real estate' not in segment_name.lower():
                segment_metrics[segment_name] = {
                    'revenue_growth': stream.get('revenue_growth', 0.1),
                    'gross_margin': stream.get('gross_margin', 0.3),
                    'sga_percentage': stream.get('sga_percentage', 0.2)
                }
        
        # Vectorized calculation for all segments and years
        for segment_name, base_revenue in base_revenues.items():
            if segment_name in segment_metrics:
                metrics = segment_metrics[segment_name]
                growth_rate = metrics['revenue_growth']
                gross_margin = metrics['gross_margin']
            else:
                growth_rate = 0.1
                gross_margin = 0.3
            
            # Vectorized calculation for all years
            years_array = np.array(years)
            years_from_base = years_array - base_year
            growth_factors = (1 + growth_rate) ** years_from_base
            
            segment_revenues = base_revenue * growth_factors
            segment_cogs = segment_revenues * (1 - gross_margin)
            
            # Store results
            segment_data['segments'][segment_name] = {
                'revenue': dict(zip(years, segment_revenues)),
                'cogs': dict(zip(years, segment_cogs)),
                'growth_rate': growth_rate,
                'gross_margin': gross_margin
            }
            
            # Add to yearly totals
            for i, year in enumerate(years):
                segment_data['revenue_by_year'][year] += segment_revenues[i]
                segment_data['cogs_by_year'][year] += segment_cogs[i]
        
        return segment_data
    
    def _render_business_segments_section(self, company_assumptions, base_year):
        """Render business segments input section"""
        st.subheader("📊 Business Segments Revenue")
        st.info(f"Enter base year ({base_year} - latest historical) revenue for business segments defined in Assumptions")
        
        # Extract business segments
        revenue_streams = company_assumptions.get('revenue_streams', [])
        business_segments = []
        segment_metrics = {}
        
        for stream in revenue_streams:
            segment_name = stream.get('segment_name', '')
            if segment_name and 'real estate' not in segment_name.lower():
                business_segments.append(segment_name)
                segment_metrics[segment_name] = {
                    'revenue_growth': stream.get('revenue_growth', 0.1),
                    'gross_margin': stream.get('gross_margin', 0.3),
                    'sga_percentage': stream.get('sga_percentage', 0.2)
                }
        
        # Create input fields
        if business_segments:
            cols = st.columns(min(len(business_segments), 3))
            selected_ticker = st.session_state.get('selected_company')
            
            for idx, segment in enumerate(business_segments):
                with cols[idx % 3]:
                    metrics = segment_metrics[segment]
                    st.markdown(f"**{segment}**")
                    st.caption(f"Growth: {metrics['revenue_growth']*100:.1f}% | Margin: {metrics['gross_margin']*100:.1f}% | SG&A: {metrics['sga_percentage']*100:.1f}%")
                    
                    input_key = f"base_revenue_{selected_ticker}_{segment}"
                    base_revenue = st.number_input(
                        f"{base_year} Revenue (B VND)",
                        min_value=0.0,
                        value=st.session_state.base_year_revenues.get(segment, 100.0),
                        step=10.0,
                        key=input_key
                    )
                    
                    # Update both session state locations
                    st.session_state.base_year_revenues[segment] = base_revenue
                    revenue_key = f'base_year_revenues_{selected_ticker}'
                    st.session_state[revenue_key][segment] = base_revenue
        else:
            st.info("No business segments defined. Add business segment assumptions in the Assumptions tab.")
        
        st.markdown("---")
    
    def _render_revenue_forecast_section(self, project_data, segment_data, years, base_year, hist_values):
        """Render revenue forecast table with vectorized data"""
        st.subheader("📊 Total Revenue Forecast")
        
        hist_col = f'{base_year}H'
        display_years = [hist_col] + [str(y) for y in years]
        
        # Build revenue rows using vectorized operations
        revenue_rows = []
        
        # Individual project revenues
        for project_name, year_revenues in project_data['breakdown']['revenue'].items():
            row_data = {'Revenue Source': project_name, hist_col: 0}
            for year in years:
                row_data[str(year)] = year_revenues.get(year, 0)
            revenue_rows.append(row_data)
        
        # Projects subtotal
        if revenue_rows:
            projects_total = {'Revenue Source': 'Subtotal: Projects', hist_col: 0}
            for year in years:
                projects_total[str(year)] = project_data['revenue_by_year'][year]
            revenue_rows.append(projects_total)
        
        # Business segments
        for segment_name, segment_info in segment_data['segments'].items():
            row_data = {'Revenue Source': segment_name}
            row_data[hist_col] = st.session_state.base_year_revenues.get(segment_name, 0)
            for year in years:
                row_data[str(year)] = segment_info['revenue'][year]
            revenue_rows.append(row_data)
        
        # Total row
        total_row = {'Revenue Source': 'TOTAL REVENUE'}
        total_row[hist_col] = hist_values.get('Net Revenue', 0)
        for year in years:
            total_revenue = (project_data['revenue_by_year'][year] + 
                           segment_data['revenue_by_year'][year])
            total_row[str(year)] = total_revenue
        revenue_rows.append(total_row)
        
        # Create and display DataFrame
        revenue_df = pd.DataFrame(revenue_rows)
        self._display_styled_table(revenue_df, "Revenue by Source (Billion VND)", display_years)
    
    def _render_cogs_section(self, project_data, segment_data, years, base_year, hist_values):
        """Render COGS section with vectorized calculations"""
        st.markdown("---")
        st.subheader("💰 Cost of Goods Sold (COGS)")
        
        hist_col = f'{base_year}H'
        cogs_rows = []
        
        # Individual project COGS
        for project_name, year_cogs in project_data['breakdown']['cogs'].items():
            row_data = {'COGS Source': project_name, hist_col: 0}
            for year in years:
                row_data[str(year)] = year_cogs.get(year, 0)
            cogs_rows.append(row_data)
        
        # Projects subtotal
        if cogs_rows:
            projects_total = {'COGS Source': 'Subtotal: Project COGS', hist_col: 0}
            for year in years:
                projects_total[str(year)] = project_data['cogs_by_year'][year]
            cogs_rows.append(projects_total)
        
        # Business segments COGS
        for segment_name, segment_info in segment_data['segments'].items():
            row_data = {'COGS Source': f"{segment_name} COGS"}
            base_revenue = st.session_state.base_year_revenues.get(segment_name, 0)
            gross_margin = segment_info['gross_margin']
            
            row_data[hist_col] = -base_revenue * (1 - gross_margin)
            for year in years:
                row_data[str(year)] = -segment_info['cogs'][year]
            cogs_rows.append(row_data)
        
        # Total COGS
        total_row = {'COGS Source': 'TOTAL COGS'}
        total_row[hist_col] = -abs(hist_values.get('COGS', 0))
        for year in years:
            total_cogs = (project_data['cogs_by_year'][year] - 
                         segment_data['cogs_by_year'][year])
            total_row[str(year)] = total_cogs
        cogs_rows.append(total_row)
        
        # Create and display DataFrame
        cogs_df = pd.DataFrame(cogs_rows)
        display_years = [hist_col] + [str(y) for y in years]
        self._display_styled_table(cogs_df, "COGS by Source (Billion VND)", display_years, 'COGS Source')
    
    def _render_gross_profit_section(self, project_data, segment_data, years, base_year):
        """Render gross profit analysis"""
        st.markdown("---")
        st.subheader("📈 Gross Profit")
        
        # Calculate gross profit using vectorized operations
        gross_profit_rows = []
        
        # Projects gross profit
        projects_gp = {'Gross Profit Source': 'Projects', f'{base_year}H': 0}
        for year in years:
            year_str = str(year)
            projects_revenue = project_data['revenue_by_year'][year]
            projects_cogs = project_data['cogs_by_year'][year]  # Already negative
            projects_gp[year_str] = projects_revenue + projects_cogs
        gross_profit_rows.append(projects_gp)
        
        # Business segments gross profit
        for segment_name, segment_info in segment_data['segments'].items():
            gp_row = {'Gross Profit Source': segment_name, f'{base_year}H': 0}
            for year in years:
                year_str = str(year)
                revenue = segment_info['revenue'][year]
                cogs = segment_info['cogs'][year]
                gp_row[year_str] = revenue - cogs  # Revenue minus COGS
            gross_profit_rows.append(gp_row)
        
        # Total gross profit
        total_gp = {'Gross Profit Source': 'TOTAL GROSS PROFIT', f'{base_year}H': 0}
        for year in years:
            year_str = str(year)
            total_revenue = (project_data['revenue_by_year'][year] + 
                           segment_data['revenue_by_year'][year])
            total_cogs = (project_data['cogs_by_year'][year] + 
                         segment_data['cogs_by_year'][year])
            total_gp[year_str] = total_revenue - total_cogs
        gross_profit_rows.append(total_gp)
        
        # Display gross profit table
        gp_df = pd.DataFrame(gross_profit_rows)
        display_years = [f'{base_year}H'] + [str(y) for y in years]
        self._display_styled_table(gp_df, "Gross Profit by Source (Billion VND)", display_years, 'Gross Profit Source')
    
    def _display_styled_table(self, df, title, display_years, source_col=None):
        """Display a styled table with consistent formatting"""
        if source_col is None:
            source_col = df.columns[0]
        
        def highlight_special_rows(row):
            if 'TOTAL' in str(row[source_col]) or 'Subtotal' in str(row[source_col]):
                return ['font-weight: bold'] * len(row)
            return [''] * len(row)
        
        st.write(f"**{title}**")
        
        # Column configuration
        column_config = {
            source_col: st.column_config.TextColumn(source_col, width='medium'),
        }
        for col in display_years:
            column_config[col] = st.column_config.NumberColumn(col, width='small', format='%.1f')
        
        st.dataframe(
            df.style
            .format("{:.1f}", subset=display_years)
            .apply(highlight_special_rows, axis=1),
            use_container_width=True,
            column_config=column_config,
            hide_index=True
        )