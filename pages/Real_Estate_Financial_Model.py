#%%
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os
import sys
from dotenv import load_dotenv
import requests
import json
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
except ImportError:
    st.warning("Please install streamlit-aggrid: pip install streamlit-aggrid")
    AgGrid = None

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Load environment variables from parent directory
env_path = os.path.join(parent_dir, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    st.error(f"⚠️ .env file not found at {env_path}")

# Import utilities
from utils.mongodb_utils import (
    init_mongodb_connection,
    load_companies_data,
    load_projects_data,
    get_financials_for_company
)
from utils.RNAV_utils import (
    selling_progress_schedule,
    land_use_right_payment_schedule_single_year,
    construction_payment_schedule,
    generate_pnl_schedule,
    RNAV_Calculation
)
from utils.perplexity_utils import (
    get_project_basic_info_perplexity,
    analyze_earnings_commentary,
    parse_sell_side_reports,
    get_financial_statements_ssi
)
from core.data_loader import data_loader
from config.constants import FINANCIAL_CONFIG, REAL_ESTATE_CONFIG

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Real Estate Financial Model",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

class RealEstateFinancialModel:
    """Comprehensive financial modeling tool for real estate companies"""
    
    def __init__(self):
        """Initialize the financial model"""
        # Initialize MongoDB connection first
        self.db_client = init_mongodb_connection()
        self.initialize_session_state()
        self.setup_sidebar()
        
    def initialize_session_state(self):
        """Initialize session state variables"""
        if 'model_data' not in st.session_state:
            st.session_state.model_data = {}
        if 'assumptions' not in st.session_state:
            st.session_state.assumptions = self.get_default_assumptions()
        if 'forecast_years' not in st.session_state:
            st.session_state.forecast_years = 5
        if 'selected_company' not in st.session_state:
            st.session_state.selected_company = None
        if 'historical_data' not in st.session_state:
            st.session_state.historical_data = None
        if 'project_data' not in st.session_state:
            st.session_state.project_data = None
            
    def get_default_assumptions(self):
        """Get default modeling assumptions"""
        return {
            'revenue_growth': {
                'presales': 0.15,  # 15% YoY growth
                'handover': 0.12,  # 12% YoY growth
                'recurring': 0.08   # 8% YoY growth
            },
            'margins': {
                'gross_margin': 0.35,      # 35%
                'ebitda_margin': 0.28,     # 28%
                'net_margin': 0.20         # 20%
            },
            'costs': {
                'sga_pct': 0.08,           # 8% of revenue
                'interest_rate': 0.08,     # 8% cost of debt
                'tax_rate': 0.20           # 20% corporate tax
            },
            'balance_sheet': {
                'receivables_days': 90,
                'inventory_days': 365,
                'payables_days': 60,
                'capex_pct_revenue': 0.02
            },
            'valuation': {
                'wacc': 0.11,              # 11% WACC
                'terminal_growth': 0.03,   # 3% terminal growth
                'target_pe': 12,           # 12x P/E
                'target_pb': 1.5           # 1.5x P/B
            }
        }
    
    def setup_sidebar(self):
        """Setup sidebar for company selection and controls"""
        st.sidebar.title("🏢 Real Estate Model")
        
        # Company selection
        companies = self.load_real_estate_companies()
        if companies:
            selected = st.sidebar.selectbox(
                "Select Company",
                companies,
                key="company_selector"
            )
            if selected:
                ticker = selected.split(" - ")[0]
                st.session_state.selected_company = ticker
                
        # Forecast parameters
        st.sidebar.subheader("Forecast Settings")
        st.session_state.forecast_years = st.sidebar.slider(
            "Forecast Years",
            min_value=3,
            max_value=10,
            value=5
        )
        
        # Data refresh buttons
        st.sidebar.subheader("Data Management")
        if st.sidebar.button("📊 Refresh Financial Data"):
            self.refresh_financial_data()
        if st.sidebar.button("🏗️ Sync Project Data"):
            self.sync_project_data()
        if st.sidebar.button("📰 Fetch Latest Reports"):
            self.fetch_analyst_reports()
            
    def load_real_estate_companies(self):
        """Load list of all companies from FA_processed.csv"""
        try:
            # Load FA data from CSV
            fa_path = os.path.join(parent_dir, 'data', 'FA_processed.csv')
            if not os.path.exists(fa_path):
                st.error(f"FA_processed.csv not found at {fa_path}")
                return []
            
            df_fa = pd.read_csv(fa_path)
            
            # Get all unique tickers (column name is TICKER in uppercase)
            tickers = sorted(df_fa['TICKER'].unique().tolist())
            
            # Try to get company names from Classification.xlsx if available
            class_path = os.path.join(parent_dir, 'data', 'Classification.xlsx')
            if os.path.exists(class_path):
                try:
                    df_class = pd.read_excel(class_path)
                    # Create a mapping of ticker to name
                    ticker_name_map = dict(zip(df_class['TICKER'], df_class['NAME']))
                    
                    # Create display names with company names if available
                    display_names = []
                    for ticker in tickers:
                        if ticker in ticker_name_map:
                            display_names.append(f"{ticker} - {ticker_name_map[ticker]}")
                        else:
                            display_names.append(ticker)
                    return display_names
                except:
                    # If there's any issue with classification file, just return tickers
                    return tickers
            else:
                # Return just the tickers if no classification file
                return tickers
                
        except Exception as e:
            st.error(f"Error loading companies: {e}")
        return []
    
    def refresh_financial_data(self):
        """Refresh financial data from multiple sources"""
        if not st.session_state.selected_company:
            st.warning("Please select a company first")
            return
            
        ticker = st.session_state.selected_company
        
        with st.spinner(f"Fetching latest financials for {ticker}..."):
            try:
                # Try SSI API first
                ssi_data = get_financial_statements_ssi(ticker)
                
                # Fallback to MongoDB
                mongo_data = get_financials_for_company(ticker, "All")
                
                # Combine data sources
                if ssi_data is not None or not mongo_data.empty:
                    st.session_state.historical_data = self.process_financial_data(
                        ssi_data, mongo_data
                    )
                    st.success("✅ Financial data refreshed successfully")
                else:
                    st.warning("No financial data available")
                    
            except Exception as e:
                st.error(f"Error refreshing data: {e}")
    
    def process_financial_data(self, ssi_data, mongo_data):
        """Process and combine financial data from multiple sources"""
        # Combine and clean data
        combined_data = pd.DataFrame()
        
        if ssi_data is not None:
            combined_data = ssi_data
            
        if not mongo_data.empty and combined_data.empty:
            combined_data = mongo_data
            
        # Standardize column names and format
        if not combined_data.empty:
            combined_data = self.standardize_financial_data(combined_data)
            
        return combined_data
    
    def standardize_financial_data(self, df):
        """Standardize financial data format"""
        # Map common column names
        column_mapping = {
            'REVENUE': 'revenue',
            'NET_REVENUE': 'revenue',
            'GROSS_PROFIT': 'gross_profit',
            'EBIT': 'ebit',
            'NET_PROFIT': 'net_income',
            'TOTAL_ASSETS': 'total_assets',
            'TOTAL_EQUITY': 'total_equity',
            'TOTAL_DEBT': 'total_debt'
        }
        
        # Rename columns
        for old, new in column_mapping.items():
            if old in df.columns:
                df[new] = df[old]
                
        return df
    
    def sync_project_data(self):
        """Sync project data from MongoDB"""
        if not st.session_state.selected_company:
            st.warning("Please select a company first")
            return
            
        ticker = st.session_state.selected_company
        
        with st.spinner(f"Syncing project data for {ticker}..."):
            try:
                df_projects = load_projects_data()
                if not df_projects.empty:
                    company_projects = df_projects[
                        df_projects['company_ticker'] == ticker
                    ]
                    st.session_state.project_data = company_projects
                    st.success(f"✅ Synced {len(company_projects)} projects")
                else:
                    st.warning("No project data available")
                    
            except Exception as e:
                st.error(f"Error syncing projects: {e}")
    
    def fetch_analyst_reports(self):
        """Fetch and analyze sell-side reports and earnings commentary"""
        if not st.session_state.selected_company:
            st.warning("Please select a company first")
            return
            
        ticker = st.session_state.selected_company
        
        with st.spinner("Analyzing latest reports..."):
            try:
                # Fetch earnings commentary
                earnings_analysis = analyze_earnings_commentary(ticker)
                
                # Parse sell-side reports
                sellside_insights = parse_sell_side_reports(ticker)
                
                # Store in session state
                st.session_state.model_data['earnings_analysis'] = earnings_analysis
                st.session_state.model_data['sellside_insights'] = sellside_insights
                
                st.success("✅ Reports analyzed successfully")
                
            except Exception as e:
                st.error(f"Error fetching reports: {e}")
    
    def render_main_interface(self):
        """Render the main modeling interface"""
        st.title("🏢 Real Estate Financial Model")
        
        if not st.session_state.selected_company:
            st.info("👈 Please select a company from the sidebar to begin")
            return
            
        # Create tabs for different sections
        tabs = st.tabs([
            "📊 Historical Analysis",
            "🎯 Assumptions",
            "🏗️ Project Pipeline",
            "📈 Revenue Forecast",
            "💰 Financial Projections",
            "📑 Valuation",
            "📰 Research Insights",
            "📥 Export Model"
        ])
        
        with tabs[0]:
            self.render_historical_analysis()
            
        with tabs[1]:
            self.render_assumptions_interface()
            
        with tabs[2]:
            self.render_project_pipeline()
            
        with tabs[3]:
            self.render_revenue_forecast()
            
        with tabs[4]:
            self.render_financial_projections()
            
        with tabs[5]:
            self.render_valuation()
            
        with tabs[6]:
            self.render_research_insights()
            
        with tabs[7]:
            self.render_export_interface()
    
    def render_historical_analysis(self):
        """Render historical financial analysis"""
        st.header("Historical Financial Analysis")
        
        if st.session_state.historical_data is None:
            st.info("Click 'Refresh Financial Data' to load historical data")
            return
            
        df = st.session_state.historical_data
        
        # Display key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            latest_revenue = df['revenue'].iloc[-1] if 'revenue' in df.columns else 0
            st.metric("Latest Revenue", f"{latest_revenue:,.0f}B VND")
            
        with col2:
            latest_profit = df['net_income'].iloc[-1] if 'net_income' in df.columns else 0
            st.metric("Latest Net Income", f"{latest_profit:,.0f}B VND")
            
        with col3:
            gross_margin = (df['gross_profit'].iloc[-1] / df['revenue'].iloc[-1] * 100) if 'gross_profit' in df.columns else 0
            st.metric("Gross Margin", f"{gross_margin:.1f}%")
            
        with col4:
            roe = (df['net_income'].iloc[-1] / df['total_equity'].iloc[-1] * 100) if 'total_equity' in df.columns else 0
            st.metric("ROE", f"{roe:.1f}%")
        
        # Historical trends chart
        st.subheader("Historical Trends")
        
        fig = go.Figure()
        
        if 'revenue' in df.columns:
            fig.add_trace(go.Bar(
                x=df.index,
                y=df['revenue'],
                name='Revenue',
                yaxis='y'
            ))
            
        if 'net_income' in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df['net_income'],
                name='Net Income',
                yaxis='y2',
                line=dict(color='red', width=2)
            ))
        
        fig.update_layout(
            title="Revenue and Profitability Trend",
            yaxis=dict(title="Revenue (B VND)", side='left'),
            yaxis2=dict(title="Net Income (B VND)", overlaying='y', side='right'),
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Display historical data table
        st.subheader("Historical Financial Data")
        st.dataframe(df, use_container_width=True)
    
    def render_assumptions_interface(self):
        """Render Excel-like assumptions input interface"""
        st.header("Model Assumptions")
        st.markdown("Adjust assumptions below to customize your forecast")
        
        # Use AgGrid for Excel-like editing
        assumptions_df = pd.DataFrame([
            {"Category": "Revenue Growth", "Item": "Presales Growth", "Value": st.session_state.assumptions['revenue_growth']['presales'], "Unit": "%"},
            {"Category": "Revenue Growth", "Item": "Handover Growth", "Value": st.session_state.assumptions['revenue_growth']['handover'], "Unit": "%"},
            {"Category": "Revenue Growth", "Item": "Recurring Revenue Growth", "Value": st.session_state.assumptions['revenue_growth']['recurring'], "Unit": "%"},
            {"Category": "Margins", "Item": "Gross Margin", "Value": st.session_state.assumptions['margins']['gross_margin'], "Unit": "%"},
            {"Category": "Margins", "Item": "EBITDA Margin", "Value": st.session_state.assumptions['margins']['ebitda_margin'], "Unit": "%"},
            {"Category": "Margins", "Item": "Net Margin", "Value": st.session_state.assumptions['margins']['net_margin'], "Unit": "%"},
            {"Category": "Costs", "Item": "SG&A % of Revenue", "Value": st.session_state.assumptions['costs']['sga_pct'], "Unit": "%"},
            {"Category": "Costs", "Item": "Interest Rate", "Value": st.session_state.assumptions['costs']['interest_rate'], "Unit": "%"},
            {"Category": "Costs", "Item": "Tax Rate", "Value": st.session_state.assumptions['costs']['tax_rate'], "Unit": "%"},
            {"Category": "Working Capital", "Item": "Receivables Days", "Value": st.session_state.assumptions['balance_sheet']['receivables_days'], "Unit": "days"},
            {"Category": "Working Capital", "Item": "Inventory Days", "Value": st.session_state.assumptions['balance_sheet']['inventory_days'], "Unit": "days"},
            {"Category": "Working Capital", "Item": "Payables Days", "Value": st.session_state.assumptions['balance_sheet']['payables_days'], "Unit": "days"},
            {"Category": "Valuation", "Item": "WACC", "Value": st.session_state.assumptions['valuation']['wacc'], "Unit": "%"},
            {"Category": "Valuation", "Item": "Terminal Growth", "Value": st.session_state.assumptions['valuation']['terminal_growth'], "Unit": "%"},
            {"Category": "Valuation", "Item": "Target P/E", "Value": st.session_state.assumptions['valuation']['target_pe'], "Unit": "x"},
            {"Category": "Valuation", "Item": "Target P/B", "Value": st.session_state.assumptions['valuation']['target_pb'], "Unit": "x"}
        ])
        
        # Use AgGrid if available, otherwise use standard dataframe editor
        if AgGrid:
            # Configure AgGrid
            gb = GridOptionsBuilder.from_dataframe(assumptions_df)
            gb.configure_default_column(editable=False, filter=True)
            gb.configure_column("Value", editable=True, type=["numericColumn"])
            gb.configure_grid_options(domLayout='autoHeight')
            
            grid_response = AgGrid(
                assumptions_df,
                gridOptions=gb.build(),
                data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
                update_mode=GridUpdateMode.VALUE_CHANGED,
                height=500,
                theme='streamlit'
            )
            
            # Update assumptions if changed
            if grid_response['data'] is not None:
                updated_df = grid_response['data']
                self.update_assumptions_from_grid(updated_df)
        else:
            # Fallback to Streamlit's data editor
            edited_df = st.data_editor(
                assumptions_df,
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                disabled=["Category", "Item", "Unit"]
            )
            self.update_assumptions_from_grid(edited_df)
        
        # Sensitivity analysis
        st.subheader("Sensitivity Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            sensitivity_var = st.selectbox(
                "Select Variable",
                ["Gross Margin", "Revenue Growth", "WACC", "Tax Rate"]
            )
            
        with col2:
            sensitivity_range = st.slider(
                "Sensitivity Range (%)",
                min_value=-50,
                max_value=50,
                value=(-20, 20)
            )
        
        if st.button("Run Sensitivity Analysis"):
            self.run_sensitivity_analysis(sensitivity_var, sensitivity_range)
    
    def update_assumptions_from_grid(self, df):
        """Update assumptions from AgGrid changes"""
        for _, row in df.iterrows():
            category = row['Category']
            item = row['Item']
            value = row['Value']
            
            # Map back to assumptions structure
            if category == "Revenue Growth":
                if item == "Presales Growth":
                    st.session_state.assumptions['revenue_growth']['presales'] = value
                elif item == "Handover Growth":
                    st.session_state.assumptions['revenue_growth']['handover'] = value
                elif item == "Recurring Revenue Growth":
                    st.session_state.assumptions['revenue_growth']['recurring'] = value
            # Continue mapping for other categories...
    
    def render_project_pipeline(self):
        """Render project pipeline and timeline"""
        st.header("Project Pipeline Analysis")
        
        if st.session_state.project_data is None:
            st.info("Click 'Sync Project Data' to load project information")
            return
            
        df_projects = st.session_state.project_data
        
        if df_projects.empty:
            st.warning("No projects found for this company")
            return
        
        # Project summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Projects", len(df_projects))
            
        with col2:
            total_units = df_projects['total_units'].sum()
            st.metric("Total Units", f"{total_units:,}")
            
        with col3:
            total_nsa = df_projects['net_sellable_area'].sum()
            st.metric("Total NSA", f"{total_nsa:,.0f} sqm")
            
        with col4:
            avg_price = df_projects['average_selling_price'].mean()
            st.metric("Avg Price/sqm", f"{avg_price:,.0f}M VND")
        
        # Project timeline visualization
        st.subheader("Project Timeline")
        
        timeline_data = []
        for _, project in df_projects.iterrows():
            timeline_data.append({
                'Project': project['project_name'],
                'Start': project.get('construction_start_year', 2025),
                'End': project.get('project_completion_year', 2028),
                'Revenue Start': project.get('revenue_booking_start_year', 2026)
            })
        
        timeline_df = pd.DataFrame(timeline_data)
        
        # Create Gantt chart
        fig = go.Figure()
        
        for idx, row in timeline_df.iterrows():
            fig.add_trace(go.Scatter(
                x=[row['Start'], row['End']],
                y=[row['Project'], row['Project']],
                mode='lines',
                line=dict(width=20),
                name=row['Project'],
                showlegend=False
            ))
            
            # Add revenue start marker
            fig.add_trace(go.Scatter(
                x=[row['Revenue Start']],
                y=[row['Project']],
                mode='markers',
                marker=dict(size=10, color='red'),
                name='Revenue Start',
                showlegend=idx == 0
            ))
        
        fig.update_layout(
            title="Project Development Timeline",
            xaxis_title="Year",
            yaxis_title="Project",
            height=400,
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Project details table
        st.subheader("Project Details")
        
        display_columns = [
            'project_name', 'location', 'total_units', 'net_sellable_area',
            'average_selling_price', 'construction_start_year', 
            'project_completion_year', 'rnav_value'
        ]
        
        available_columns = [col for col in display_columns if col in df_projects.columns]
        st.dataframe(df_projects[available_columns], use_container_width=True)
    
    def render_revenue_forecast(self):
        """Render revenue forecast based on project pipeline"""
        st.header("Revenue Forecast Model")
        
        if st.session_state.project_data is None:
            st.warning("Project data required for revenue forecasting")
            return
        
        # Generate revenue forecast from projects
        revenue_forecast = self.generate_revenue_forecast()
        
        # Display forecast chart
        st.subheader("Revenue Forecast by Source")
        
        fig = go.Figure()
        
        years = list(range(datetime.now().year, datetime.now().year + st.session_state.forecast_years + 1))
        
        # Add revenue streams
        fig.add_trace(go.Bar(
            x=years,
            y=revenue_forecast.get('presales', [0] * len(years)),
            name='Presales',
            marker_color='lightblue'
        ))
        
        fig.add_trace(go.Bar(
            x=years,
            y=revenue_forecast.get('handover', [0] * len(years)),
            name='Handover Revenue',
            marker_color='darkblue'
        ))
        
        fig.add_trace(go.Bar(
            x=years,
            y=revenue_forecast.get('recurring', [0] * len(years)),
            name='Recurring Revenue',
            marker_color='green'
        ))
        
        fig.update_layout(
            title="Revenue Forecast Breakdown",
            xaxis_title="Year",
            yaxis_title="Revenue (Billion VND)",
            barmode='stack',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Revenue forecast table
        st.subheader("Detailed Revenue Forecast")
        
        forecast_df = pd.DataFrame({
            'Year': years,
            'Presales': revenue_forecast.get('presales', [0] * len(years)),
            'Handover Revenue': revenue_forecast.get('handover', [0] * len(years)),
            'Recurring Revenue': revenue_forecast.get('recurring', [0] * len(years)),
            'Total Revenue': [
                revenue_forecast.get('presales', [0])[i] + 
                revenue_forecast.get('handover', [0])[i] + 
                revenue_forecast.get('recurring', [0])[i]
                for i in range(len(years))
            ]
        })
        
        st.dataframe(forecast_df.style.format({
            'Presales': '{:,.0f}',
            'Handover Revenue': '{:,.0f}',
            'Recurring Revenue': '{:,.0f}',
            'Total Revenue': '{:,.0f}'
        }), use_container_width=True)
        
        # Project contribution analysis
        st.subheader("Revenue Contribution by Project")
        
        if not st.session_state.project_data.empty:
            project_revenue = self.calculate_project_revenue_contribution()
            
            fig = px.pie(
                project_revenue,
                values='revenue',
                names='project',
                title="Project Revenue Contribution (Next 5 Years)"
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    def generate_revenue_forecast(self):
        """Generate revenue forecast from project pipeline"""
        forecast = {
            'presales': [],
            'handover': [],
            'recurring': []
        }
        
        current_year = datetime.now().year
        forecast_years = st.session_state.forecast_years
        
        # Base case from historical data
        if st.session_state.historical_data is not None:
            base_revenue = st.session_state.historical_data['revenue'].iloc[-1] if 'revenue' in st.session_state.historical_data.columns else 1000
        else:
            base_revenue = 1000  # Default base
        
        # Generate forecast based on assumptions
        for year in range(forecast_years + 1):
            # Presales forecast
            presales = base_revenue * 0.4 * (1 + st.session_state.assumptions['revenue_growth']['presales']) ** year
            forecast['presales'].append(presales)
            
            # Handover revenue (delayed from presales)
            handover = base_revenue * 0.5 * (1 + st.session_state.assumptions['revenue_growth']['handover']) ** year
            forecast['handover'].append(handover)
            
            # Recurring revenue
            recurring = base_revenue * 0.1 * (1 + st.session_state.assumptions['revenue_growth']['recurring']) ** year
            forecast['recurring'].append(recurring)
        
        # Adjust based on project pipeline
        if st.session_state.project_data is not None and not st.session_state.project_data.empty:
            forecast = self.adjust_forecast_for_projects(forecast)
        
        return forecast
    
    def adjust_forecast_for_projects(self, forecast):
        """Adjust revenue forecast based on actual project pipeline"""
        df_projects = st.session_state.project_data
        current_year = datetime.now().year
        
        for _, project in df_projects.iterrows():
            # Calculate project revenue schedule
            revenue_start = project.get('revenue_booking_start_year', current_year)
            completion_year = project.get('project_completion_year', current_year + 3)
            
            total_revenue = project.get('total_units', 0) * project.get('average_selling_price', 0) * project.get('average_unit_size', 0) / 1e9  # Convert to billions
            
            # Distribute revenue over project lifecycle
            for year_offset in range(st.session_state.forecast_years + 1):
                year = current_year + year_offset
                
                if revenue_start <= year <= completion_year:
                    # Simple linear distribution
                    years_span = max(completion_year - revenue_start + 1, 1)
                    annual_revenue = total_revenue / years_span
                    
                    # Add to handover revenue
                    if year_offset < len(forecast['handover']):
                        forecast['handover'][year_offset] += annual_revenue
        
        return forecast
    
    def calculate_project_revenue_contribution(self):
        """Calculate revenue contribution by project"""
        df_projects = st.session_state.project_data
        
        project_revenues = []
        for _, project in df_projects.iterrows():
            total_revenue = (
                project.get('total_units', 0) * 
                project.get('average_selling_price', 0) * 
                project.get('average_unit_size', 0) / 1e9
            )
            project_revenues.append({
                'project': project['project_name'],
                'revenue': total_revenue
            })
        
        return pd.DataFrame(project_revenues)
    
    def render_financial_projections(self):
        """Render complete financial projections"""
        st.header("Financial Projections")
        
        # Generate projections
        projections = self.generate_financial_projections()
        
        # Income Statement Projections
        st.subheader("Projected Income Statement")
        
        income_statement = projections['income_statement']
        st.dataframe(
            income_statement.style.format("{:,.0f}"),
            use_container_width=True
        )
        
        # Balance Sheet Projections
        st.subheader("Projected Balance Sheet")
        
        balance_sheet = projections['balance_sheet']
        st.dataframe(
            balance_sheet.style.format("{:,.0f}"),
            use_container_width=True
        )
        
        # Cash Flow Projections
        st.subheader("Projected Cash Flow Statement")
        
        cash_flow = projections['cash_flow']
        st.dataframe(
            cash_flow.style.format("{:,.0f}"),
            use_container_width=True
        )
        
        # Key Metrics Dashboard
        st.subheader("Key Financial Metrics")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Revenue CAGR
            revenue_cagr = self.calculate_cagr(
                income_statement['Revenue'].iloc[0],
                income_statement['Revenue'].iloc[-1],
                len(income_statement) - 1
            )
            st.metric("Revenue CAGR", f"{revenue_cagr:.1f}%")
            
        with col2:
            # Average Net Margin
            avg_margin = (income_statement['Net Income'] / income_statement['Revenue']).mean() * 100
            st.metric("Avg Net Margin", f"{avg_margin:.1f}%")
            
        with col3:
            # Average ROE
            avg_roe = (income_statement['Net Income'] / balance_sheet['Total Equity']).mean() * 100
            st.metric("Avg ROE", f"{avg_roe:.1f}%")
    
    def generate_financial_projections(self):
        """Generate complete financial projections"""
        revenue_forecast = self.generate_revenue_forecast()
        years = list(range(datetime.now().year, datetime.now().year + st.session_state.forecast_years + 1))
        
        # Income Statement
        income_statement = pd.DataFrame()
        income_statement['Year'] = years
        income_statement['Revenue'] = [
            revenue_forecast['presales'][i] + 
            revenue_forecast['handover'][i] + 
            revenue_forecast['recurring'][i]
            for i in range(len(years))
        ]
        
        income_statement['Gross Profit'] = income_statement['Revenue'] * st.session_state.assumptions['margins']['gross_margin']
        income_statement['SG&A'] = income_statement['Revenue'] * st.session_state.assumptions['costs']['sga_pct']
        income_statement['EBITDA'] = income_statement['Revenue'] * st.session_state.assumptions['margins']['ebitda_margin']
        income_statement['EBIT'] = income_statement['EBITDA'] - income_statement['Revenue'] * 0.02  # Depreciation
        income_statement['Interest'] = income_statement['Revenue'] * 0.05  # Simplified
        income_statement['EBT'] = income_statement['EBIT'] - income_statement['Interest']
        income_statement['Tax'] = income_statement['EBT'] * st.session_state.assumptions['costs']['tax_rate']
        income_statement['Net Income'] = income_statement['EBT'] - income_statement['Tax']
        
        # Balance Sheet (simplified)
        balance_sheet = pd.DataFrame()
        balance_sheet['Year'] = years
        balance_sheet['Total Assets'] = income_statement['Revenue'] * 3  # Simplified asset turnover
        balance_sheet['Total Debt'] = balance_sheet['Total Assets'] * 0.4  # 40% debt ratio
        balance_sheet['Total Equity'] = balance_sheet['Total Assets'] - balance_sheet['Total Debt']
        
        # Cash Flow (simplified)
        cash_flow = pd.DataFrame()
        cash_flow['Year'] = years
        cash_flow['Operating Cash Flow'] = income_statement['Net Income'] + income_statement['Revenue'] * 0.02  # Add back depreciation
        cash_flow['Investing Cash Flow'] = -income_statement['Revenue'] * st.session_state.assumptions['balance_sheet']['capex_pct_revenue']
        cash_flow['Financing Cash Flow'] = balance_sheet['Total Debt'].diff().fillna(0)
        cash_flow['Free Cash Flow'] = cash_flow['Operating Cash Flow'] + cash_flow['Investing Cash Flow']
        
        return {
            'income_statement': income_statement,
            'balance_sheet': balance_sheet,
            'cash_flow': cash_flow
        }
    
    def calculate_cagr(self, begin_value, end_value, periods):
        """Calculate Compound Annual Growth Rate"""
        if begin_value <= 0:
            return 0
        return ((end_value / begin_value) ** (1/periods) - 1) * 100
    
    def render_valuation(self):
        """Render valuation analysis"""
        st.header("Valuation Analysis")
        
        projections = self.generate_financial_projections()
        
        # DCF Valuation
        st.subheader("DCF Valuation")
        
        dcf_value = self.calculate_dcf_valuation(projections)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Enterprise Value", f"{dcf_value['enterprise_value']:,.0f}B VND")
            
        with col2:
            st.metric("Equity Value", f"{dcf_value['equity_value']:,.0f}B VND")
            
        with col3:
            st.metric("Value per Share", f"{dcf_value['value_per_share']:,.0f} VND")
        
        # Multiples Valuation
        st.subheader("Multiples Valuation")
        
        multiples_value = self.calculate_multiples_valuation(projections)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("P/E Based Value", f"{multiples_value['pe_value']:,.0f} VND")
            
        with col2:
            st.metric("P/B Based Value", f"{multiples_value['pb_value']:,.0f} VND")
        
        # RNAV Valuation
        st.subheader("RNAV Valuation")
        
        if st.session_state.project_data is not None and not st.session_state.project_data.empty:
            total_rnav = st.session_state.project_data['rnav_value'].sum()
            st.metric("Total RNAV", f"{total_rnav:,.0f}B VND")
        else:
            st.info("Sync project data to calculate RNAV")
        
        # Valuation Summary
        st.subheader("Valuation Summary")
        
        valuation_summary = pd.DataFrame({
            'Method': ['DCF', 'P/E Multiple', 'P/B Multiple', 'RNAV'],
            'Value per Share': [
                dcf_value['value_per_share'],
                multiples_value['pe_value'],
                multiples_value['pb_value'],
                total_rnav * 1e9 / 1e9 if st.session_state.project_data is not None else 0  # Placeholder
            ]
        })
        
        fig = go.Figure(data=[
            go.Bar(x=valuation_summary['Method'], y=valuation_summary['Value per Share'])
        ])
        
        fig.update_layout(
            title="Valuation Comparison",
            xaxis_title="Valuation Method",
            yaxis_title="Value per Share (VND)",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def calculate_dcf_valuation(self, projections):
        """Calculate DCF valuation"""
        cash_flows = projections['cash_flow']['Free Cash Flow'].values
        wacc = st.session_state.assumptions['valuation']['wacc']
        terminal_growth = st.session_state.assumptions['valuation']['terminal_growth']
        
        # Calculate present value of cash flows
        pv_cash_flows = 0
        for i, cf in enumerate(cash_flows[1:], 1):  # Skip first year
            pv_cash_flows += cf / (1 + wacc) ** i
        
        # Terminal value
        terminal_cf = cash_flows[-1] * (1 + terminal_growth)
        terminal_value = terminal_cf / (wacc - terminal_growth)
        pv_terminal = terminal_value / (1 + wacc) ** len(cash_flows)
        
        enterprise_value = pv_cash_flows + pv_terminal
        
        # Calculate equity value (simplified)
        net_debt = projections['balance_sheet']['Total Debt'].iloc[-1] * 0.8  # Assume some cash
        equity_value = enterprise_value - net_debt
        
        # Per share value (placeholder shares outstanding)
        shares_outstanding = 1e9  # 1 billion shares placeholder
        value_per_share = equity_value * 1e9 / shares_outstanding
        
        return {
            'enterprise_value': enterprise_value,
            'equity_value': equity_value,
            'value_per_share': value_per_share
        }
    
    def calculate_multiples_valuation(self, projections):
        """Calculate multiples-based valuation"""
        # Forward P/E valuation
        forward_earnings = projections['income_statement']['Net Income'].iloc[1]  # Next year
        target_pe = st.session_state.assumptions['valuation']['target_pe']
        pe_market_cap = forward_earnings * target_pe
        
        # P/B valuation
        book_value = projections['balance_sheet']['Total Equity'].iloc[-1]
        target_pb = st.session_state.assumptions['valuation']['target_pb']
        pb_market_cap = book_value * target_pb
        
        # Per share values (placeholder shares outstanding)
        shares_outstanding = 1e9  # 1 billion shares placeholder
        
        return {
            'pe_value': pe_market_cap * 1e9 / shares_outstanding,
            'pb_value': pb_market_cap * 1e9 / shares_outstanding
        }
    
    def render_research_insights(self):
        """Render AI-powered research insights"""
        st.header("Research & Analytics Insights")
        
        # Earnings Commentary Analysis
        st.subheader("📊 Earnings Commentary Analysis")
        
        if 'earnings_analysis' in st.session_state.model_data:
            analysis = st.session_state.model_data['earnings_analysis']
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("**Key Takeaways:**")
                st.write(analysis.get('key_points', 'No analysis available'))
                
            with col2:
                sentiment = analysis.get('sentiment', 'Neutral')
                color = 'green' if sentiment == 'Positive' else 'red' if sentiment == 'Negative' else 'gray'
                st.markdown(f"**Sentiment:** <span style='color:{color}'>{sentiment}</span>", unsafe_allow_html=True)
        else:
            st.info("Click 'Fetch Latest Reports' to analyze earnings commentary")
        
        # Sell-Side Research Insights
        st.subheader("📈 Sell-Side Research Summary")
        
        if 'sellside_insights' in st.session_state.model_data:
            insights = st.session_state.model_data['sellside_insights']
            
            # Display consensus estimates
            st.markdown("**Consensus Estimates:**")
            consensus_df = pd.DataFrame(insights.get('consensus', {}))
            if not consensus_df.empty:
                st.dataframe(consensus_df, use_container_width=True)
            
            # Display key risks and opportunities
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Key Risks:**")
                risks = insights.get('risks', [])
                for risk in risks[:5]:
                    st.write(f"• {risk}")
                    
            with col2:
                st.markdown("**Key Opportunities:**")
                opportunities = insights.get('opportunities', [])
                for opp in opportunities[:5]:
                    st.write(f"• {opp}")
        else:
            st.info("Click 'Fetch Latest Reports' to analyze sell-side research")
        
        # AI-Generated Investment Thesis
        st.subheader("🤖 AI-Generated Investment Thesis")
        
        if st.button("Generate Investment Thesis"):
            with st.spinner("Generating investment thesis..."):
                thesis = self.generate_investment_thesis()
                st.markdown(thesis)
    
    def generate_investment_thesis(self):
        """Generate AI-powered investment thesis"""
        # This would integrate with Perplexity/OpenAI to generate thesis
        # For now, return a template
        return """
        ### Investment Thesis
        
        **Bull Case:**
        - Strong project pipeline with diversified geographic exposure
        - Improving margins driven by operational efficiency
        - Favorable demographics supporting long-term demand
        
        **Bear Case:**
        - Regulatory risks related to property market cooling measures
        - Rising interest rates impacting affordability
        - Execution risks on large-scale projects
        
        **Recommendation:** HOLD
        - Target Price: Based on DCF and multiples analysis
        - Key Catalysts: Project launches, margin improvement, policy clarity
        """
    
    def render_export_interface(self):
        """Render export options for the model"""
        st.header("Export Financial Model")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📊 Export to Excel", use_container_width=True):
                self.export_to_excel()
                
        with col2:
            if st.button("📄 Generate PDF Report", use_container_width=True):
                self.generate_pdf_report()
                
        with col3:
            if st.button("💾 Save Model State", use_container_width=True):
                self.save_model_state()
        
        # Model sharing
        st.subheader("Share Model")
        
        share_link = st.text_input(
            "Shareable Link",
            value=f"https://model.share/{st.session_state.selected_company}_{datetime.now().strftime('%Y%m%d')}",
            disabled=True
        )
        
        if st.button("Copy Link"):
            st.success("Link copied to clipboard!")
    
    def export_to_excel(self):
        """Export model to Excel file"""
        import io
        from xlsxwriter import Workbook
        
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Export projections
            projections = self.generate_financial_projections()
            
            projections['income_statement'].to_excel(
                writer, sheet_name='Income Statement', index=False
            )
            projections['balance_sheet'].to_excel(
                writer, sheet_name='Balance Sheet', index=False
            )
            projections['cash_flow'].to_excel(
                writer, sheet_name='Cash Flow', index=False
            )
            
            # Export assumptions
            assumptions_df = pd.DataFrame([st.session_state.assumptions])
            assumptions_df.to_excel(
                writer, sheet_name='Assumptions', index=False
            )
            
            # Export project data if available
            if st.session_state.project_data is not None:
                st.session_state.project_data.to_excel(
                    writer, sheet_name='Projects', index=False
                )
        
        output.seek(0)
        
        st.download_button(
            label="Download Excel Model",
            data=output,
            file_name=f"{st.session_state.selected_company}_model_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    def generate_pdf_report(self):
        """Generate PDF report of the model"""
        st.info("PDF generation feature coming soon!")
    
    def save_model_state(self):
        """Save current model state"""
        model_state = {
            'company': st.session_state.selected_company,
            'assumptions': st.session_state.assumptions,
            'forecast_years': st.session_state.forecast_years,
            'timestamp': datetime.now().isoformat()
        }
        
        # Save to JSON
        import json
        model_json = json.dumps(model_state, indent=2)
        
        st.download_button(
            label="Download Model State",
            data=model_json,
            file_name=f"{st.session_state.selected_company}_state_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json"
        )
        
        st.success("Model state saved successfully!")
    
    def run_sensitivity_analysis(self, variable, range_pct):
        """Run sensitivity analysis on selected variable"""
        # Implementation would vary the selected variable and recalculate valuations
        st.info(f"Running sensitivity analysis on {variable} with range {range_pct}%")
        
        # Placeholder for sensitivity results
        sensitivity_results = pd.DataFrame({
            'Scenario': ['Bear', 'Base', 'Bull'],
            'Variable Value': [range_pct[0], 0, range_pct[1]],
            'Valuation': [100, 120, 150]  # Placeholder values
        })
        
        fig = go.Figure(data=[
            go.Scatter(
                x=sensitivity_results['Variable Value'],
                y=sensitivity_results['Valuation'],
                mode='lines+markers',
                name='Valuation'
            )
        ])
        
        fig.update_layout(
            title=f"Sensitivity Analysis: {variable}",
            xaxis_title=f"{variable} Change (%)",
            yaxis_title="Valuation",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)

def main():
    """Main function to run the application"""
    model = RealEstateFinancialModel()
    model.render_main_interface()

if __name__ == "__main__":
    main()