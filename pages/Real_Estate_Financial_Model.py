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

# Force reload of RNAV utils to get latest functions
import importlib
if 'utils.RNAV_utils' in sys.modules:
    import utils.RNAV_utils
    importlib.reload(utils.RNAV_utils)

# Import utilities
from utils.mongodb_utils import (
    init_mongodb_connection,
    load_projects_data,
    get_financials_for_company,
    save_project_to_mongodb,
    load_financial_statements_from_mongodb,
    load_valuation_metrics_from_mongodb,
    get_available_tickers_from_mongodb
)
# RNAV utilities temporarily disabled
# from utils.RNAV_utils import (
#     selling_progress_schedule,
#     land_use_right_payment_schedule_single_year,
#     construction_payment_schedule,
#     generate_pnl_schedule,
#     RNAV_Calculation
# )
from utils.perplexity_utils import (
    get_project_basic_info_perplexity,
    analyze_earnings_commentary,
    parse_sell_side_reports
)
# from core.data_loader import data_loader
# from config.constants import FINANCIAL_CONFIG, REAL_ESTATE_CONFIG

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
        # Don't initialize MongoDB connection here - only connect when needed
        self.db_client = None
        self.mongo_initialized = False
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
        if 'loading_projects' not in st.session_state:
            st.session_state.loading_projects = False
            
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
        
        # Load companies with caching
        companies = self.load_real_estate_companies()
        if companies:
            selected = st.sidebar.selectbox(
                "Select Company",
                companies,
                key="company_selector"
            )
            if selected:
                ticker = selected.split(" - ")[0]
                # Check if ticker has changed
                if 'selected_company' not in st.session_state or st.session_state.selected_company != ticker:
                    # Ticker changed, reset data
                    st.session_state.selected_company = ticker
                    st.session_state.historical_data = None
                    st.session_state.project_data = None
                
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
            
        # DO NOT auto-load any data in sidebar to prevent blocking
        if st.sidebar.button("📰 Fetch Latest Reports"):
            self.fetch_analyst_reports()
            
    def load_project_data_from_mongodb(self, ticker):
        """Load project data from MongoDB for the selected ticker"""
        # Prevent multiple simultaneous loads
        if st.session_state.loading_projects:
            return
        
        st.session_state.loading_projects = True
        
        try:
            # Initialize MongoDB connection lazily
            if not self.mongo_initialized:
                try:
                    # Only initialize once per session
                    self.db_client = init_mongodb_connection()
                    self.mongo_initialized = True
                except Exception as conn_error:
                    st.warning(f"MongoDB connection failed: {conn_error}. Using fallback data.")
                    st.session_state.project_data = pd.DataFrame()
                    return
            
            # Load all projects data with timeout
            with st.spinner(f"Loading projects for {ticker}..."):
                df_projects = load_projects_data()
            
            if df_projects.empty:
                st.info("No project data available in MongoDB")
                st.session_state.project_data = pd.DataFrame()
                return
            
            # Filter for selected ticker
            ticker_projects = df_projects[df_projects['company_ticker'] == ticker].copy()
            
            if ticker_projects.empty:
                st.info(f"No projects found for {ticker}")
                st.session_state.project_data = pd.DataFrame()
            else:
                st.session_state.project_data = ticker_projects
                st.success(f"✅ Loaded {len(ticker_projects)} projects for {ticker}")
                
        except Exception as e:
            st.error(f"Error loading project data: {str(e)}")
            st.session_state.project_data = pd.DataFrame()
        finally:
            st.session_state.loading_projects = False
    
    @st.cache_data(ttl=600)  # Cache for 10 minutes
    def load_historical_data_from_csv(_self, ticker):
        """Load historical financial data. Try MongoDB first for DXG, fallback to CSV."""
        try:
            # For DXG, try MongoDB first but with timeout
            if ticker == 'DXG':
                try:
                    pivot_data = load_financial_statements_from_mongodb(ticker)
                    if not pivot_data.empty:
                        return pivot_data
                except:
                    pass  # Fall through to CSV
            
            # Fallback to CSV for other tickers or if MongoDB fails
            fa_path = os.path.join(parent_dir, 'data', 'FA_processed.csv')
            
            if not os.path.exists(fa_path):
                st.warning("Financial data file not found")
                return pd.DataFrame()
            
            # Read only necessary columns first
            df_fa = pd.read_csv(fa_path, 
                                usecols=['TICKER', 'DATE', 'KEYCODE', 'VALUE'],
                                dtype={'TICKER': str, 'KEYCODE': str})
            
            # Filter for selected ticker
            ticker_data = df_fa[df_fa['TICKER'] == ticker].copy()
            
            if ticker_data.empty:
                return pd.DataFrame()
            
            # Pivot data to create time series
            pivot_data = ticker_data.pivot_table(
                index='DATE',
                columns='KEYCODE',
                values='VALUE',
                aggfunc='first'
            )
            
            # Sort by date
            pivot_data.sort_index(inplace=True)
            
            return pivot_data
            
        except Exception as e:
            st.error(f"Error loading historical data: {str(e)}")
            return pd.DataFrame()
    
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def load_real_estate_companies(_self):
        """Load list of all companies from FA_processed.csv."""
        try:
            fa_path = os.path.join(parent_dir, 'data', 'FA_processed.csv')
            if not os.path.exists(fa_path):
                return ['DXG - Dat Xanh Group']  # Fallback to known company
            
            # Read only the TICKER column to speed up loading
            df_fa = pd.read_csv(fa_path, usecols=['TICKER'])
            
            # Get all unique tickers
            tickers = sorted(df_fa['TICKER'].unique().tolist())
            
            # Try to get company names from Classification.xlsx if available
            class_path = os.path.join(parent_dir, 'data', 'Classification.xlsx')
            if os.path.exists(class_path):
                try:
                    df_class = pd.read_excel(class_path, usecols=['TICKER', 'NAME'])
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
                    return tickers
            else:
                return tickers
                
        except Exception as e:
            # Return fallback list
            return ['DXG - Dat Xanh Group']
    
    def refresh_financial_data(self):
        """Refresh financial data from FA_processed.csv"""
        if not st.session_state.selected_company:
            st.warning("Please select a company first")
            return
            
        ticker = st.session_state.selected_company
        
        with st.spinner(f"Loading financial data for {ticker}..."):
            # Clear cache for this specific ticker
            self.load_historical_data_from_csv.clear()
            # Load fresh data
            data = self.load_historical_data_from_csv(ticker)
            if not data.empty:
                st.session_state.historical_data = data
                st.success(f"✅ Loaded financial data for {ticker}")
            else:
                st.session_state.historical_data = None
                st.warning(f"No financial data found for {ticker}")
    
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
        
        # Clear existing project data to force reload
        st.session_state.project_data = None
            
        ticker = st.session_state.selected_company
        
        with st.spinner(f"Syncing project data for {ticker}..."):
            self.load_project_data_from_mongodb(ticker)
    
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
        
        # Load data if not already loaded
        if st.session_state.historical_data is None and st.session_state.selected_company:
            with st.spinner(f"Loading data for {st.session_state.selected_company}..."):
                data = self.load_historical_data_from_csv(st.session_state.selected_company)
                if not data.empty:
                    st.session_state.historical_data = data
        
        if st.session_state.historical_data is None:
            st.info("👈 Select a company to view historical data")
            return
            
        df = st.session_state.historical_data
        
        # Display key metrics using FA_processed column names
        col1, col2, col3, col4 = st.columns(4)
        
        # Map FA_processed KEYCODE to display names (handle both Sales and Net_Revenue)
        with col1:
            if 'Sales' in df.columns:
                latest_revenue = df['Sales'].iloc[-1]
            elif 'Net_Revenue' in df.columns:
                latest_revenue = df['Net_Revenue'].iloc[-1]
            else:
                latest_revenue = 0
            st.metric("Latest Revenue", f"{latest_revenue/1e9:,.0f}B VND")
            
        with col2:
            if 'NPATMI' in df.columns:
                latest_profit = df['NPATMI'].iloc[-1]
            elif 'NPAT' in df.columns:
                latest_profit = df['NPAT'].iloc[-1]
            else:
                latest_profit = 0
            st.metric("Latest NPATMI", f"{latest_profit/1e9:,.0f}B VND")
            
        with col3:
            if 'Gross_Profit' in df.columns and 'Sales' in df.columns and df['Sales'].iloc[-1] != 0:
                gross_margin = (df['Gross_Profit'].iloc[-1] / df['Sales'].iloc[-1] * 100)
            else:
                gross_margin = 0
            st.metric("Gross Margin", f"{gross_margin:.1f}%")
            
        with col4:
            if 'NPATMI' in df.columns and 'Total_Equity' in df.columns and df['Total_Equity'].iloc[-1] != 0:
                roe = (df['NPATMI'].iloc[-1] / df['Total_Equity'].iloc[-1] * 100)
            elif 'NPAT' in df.columns and 'Total_Equity' in df.columns and df['Total_Equity'].iloc[-1] != 0:
                roe = (df['NPAT'].iloc[-1] / df['Total_Equity'].iloc[-1] * 100)
            else:
                roe = 0
            st.metric("ROE", f"{roe:.1f}%")
        
        # Annual Revenue and NPATMI Chart
        st.subheader("Annual Revenue and NPATMI Trends")
        
        # Extract year from index if it's a date
        df_annual = df.copy()
        if not df_annual.empty:
            # Parse the index as datetime if it's not already
            try:
                df_annual.index = pd.to_datetime(df_annual.index)
                # Group by year and take the last value (year-end)
                df_annual['Year'] = df_annual.index.year
                
                # Prepare data for annual metrics
                annual_metrics = []
                for year in df_annual['Year'].unique():
                    year_data = df_annual[df_annual['Year'] == year].iloc[-1]  # Take last quarter/period of year
                    
                    revenue = 0
                    if 'Sales' in df_annual.columns:
                        revenue = year_data['Sales']
                    elif 'Net_Revenue' in df_annual.columns:
                        revenue = year_data['Net_Revenue']
                    
                    npatmi = 0
                    if 'NPATMI' in df_annual.columns:
                        npatmi = year_data['NPATMI']
                    elif 'NPAT' in df_annual.columns:
                        npatmi = year_data['NPAT']
                    
                    annual_metrics.append({
                        'Year': year,
                        'Revenue': revenue / 1e9,  # Convert to billions
                        'NPATMI': npatmi / 1e9     # Convert to billions
                    })
                
                annual_df = pd.DataFrame(annual_metrics)
                
                # Create dual-axis chart for Revenue and NPATMI
                fig = go.Figure()
                
                # Add Revenue bars
                fig.add_trace(go.Bar(
                    x=annual_df['Year'],
                    y=annual_df['Revenue'],
                    name='Annual Revenue',
                    marker_color='lightblue',
                    yaxis='y',
                    text=annual_df['Revenue'].round(0),
                    texttemplate='%{text:.0f}B',
                    textposition='outside'
                ))
                
                # Add NPATMI line
                fig.add_trace(go.Scatter(
                    x=annual_df['Year'],
                    y=annual_df['NPATMI'],
                    name='Annual NPATMI',
                    mode='lines+markers',
                    marker=dict(size=8, color='red'),
                    line=dict(color='red', width=2),
                    yaxis='y2',
                    text=annual_df['NPATMI'].round(0),
                    texttemplate='%{text:.0f}B',
                    textposition='top center'
                ))
                
                fig.update_layout(
                    title=f"Annual Revenue and NPATMI - {st.session_state.selected_company}",
                    xaxis=dict(title="Year", tickmode='linear', dtick=1),
                    yaxis=dict(title="Revenue (Billion VND)", side='left'),
                    yaxis2=dict(title="NPATMI (Billion VND)", overlaying='y', side='right'),
                    hovermode='x unified',
                    height=500,
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Display annual data table
                st.subheader("Annual Financial Summary")
                annual_display = annual_df.copy()
                annual_display['Revenue Growth (%)'] = annual_display['Revenue'].pct_change() * 100
                annual_display['NPATMI Growth (%)'] = annual_display['NPATMI'].pct_change() * 100
                annual_display['Net Margin (%)'] = (annual_display['NPATMI'] / annual_display['Revenue'] * 100)
                
                # Format the display
                st.dataframe(
                    annual_display.style.format({
                        'Year': '{:.0f}',
                        'Revenue': '{:.1f}B',
                        'NPATMI': '{:.1f}B',
                        'Revenue Growth (%)': '{:.1f}%',
                        'NPATMI Growth (%)': '{:.1f}%',
                        'Net Margin (%)': '{:.1f}%'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
                
            except Exception as e:
                st.warning(f"Could not parse dates for annual analysis: {str(e)}")
                # Fallback to showing raw data
                pass
        
        # Display detailed historical data table
        st.subheader("Detailed Historical Financial Data")
        
        # Select and display key columns if they exist from CSV
        key_columns = ['Sales', 'Net_Revenue', 'Gross_Profit', 'EBITDA', 'NPATMI', 'NPAT', 'Total_Assets', 'Total_Equity', 'Total_Debt', 'Operating_Cash_Flow']
        available_columns = [col for col in key_columns if col in df.columns]
        
        if available_columns:
            display_df = df[available_columns].copy()
            # Convert to billions for better readability
            for col in display_df.columns:
                display_df[col] = display_df[col] / 1e9
            
            # Format the dataframe
            display_df = display_df.round(1)
            st.dataframe(display_df, use_container_width=True)
        else:
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
        
        df_projects = st.session_state.project_data
        
        if df_projects is None or (isinstance(df_projects, pd.DataFrame) and df_projects.empty):
            st.info("👈 Click 'Sync Project Data' in the sidebar to load projects from MongoDB")
            return
        
        # Add project selector for individual project editing
        st.subheader("🎯 Select Individual Project")
        project_names = df_projects['project_name'].tolist()
        selected_project_name = st.selectbox(
            "Choose a project to view/edit details:",
            options=["All Projects (Overview)"] + project_names,
            key="selected_project_for_edit"
        )
        
        if selected_project_name != "All Projects (Overview)":
            # Show individual project editor
            self.render_individual_project_editor(selected_project_name, df_projects)
            return
        
        # Project summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Projects", len(df_projects))
            
        with col2:
            total_units = df_projects['total_units'].sum() if 'total_units' in df_projects.columns else 0
            st.metric("Total Units", f"{int(total_units):,}")
            
        with col3:
            total_nsa = df_projects['net_sellable_area'].sum() if 'net_sellable_area' in df_projects.columns else 0
            st.metric("Total NSA", f"{total_nsa:,.0f} sqm")
            
        with col4:
            avg_price = df_projects['average_selling_price'].mean() if 'average_selling_price' in df_projects.columns else 0
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
                line=dict(width=20, color='lightblue'),
                name=row['Project'],
                showlegend=False,
                hovertemplate=f"Project: {row['Project']}<br>Period: {row['Start']}-{row['End']}<extra></extra>"
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
        
        # Define columns to display based on what's typically in MongoDB
        display_columns = [
            'project_name', 'location', 'total_units', 'net_sellable_area',
            'average_selling_price', 'construction_start_year', 
            'project_completion_year', 'rnav_value', 'last_updated'
        ]
        
        # Check which columns are actually available
        available_columns = [col for col in display_columns if col in df_projects.columns]
        
        if available_columns:
            # Create a display dataframe with formatting
            display_df = df_projects[available_columns].copy()
            
            # Format numeric columns for better display
            if 'net_sellable_area' in display_df.columns:
                display_df['net_sellable_area'] = display_df['net_sellable_area'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
            if 'total_units' in display_df.columns:
                display_df['total_units'] = display_df['total_units'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "N/A")
            if 'average_selling_price' in display_df.columns:
                display_df['average_selling_price'] = display_df['average_selling_price'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
            if 'rnav_value' in display_df.columns:
                display_df['rnav_value'] = display_df['rnav_value'].apply(lambda x: f"{x/1e9:,.1f}B" if pd.notna(x) and x > 0 else "N/A")
            
            # Rename columns for better display
            column_rename = {
                'project_name': 'Project Name',
                'location': 'Location',
                'total_units': 'Total Units',
                'net_sellable_area': 'NSA (sqm)',
                'average_selling_price': 'Avg Price (M VND/sqm)',
                'construction_start_year': 'Construction Start',
                'project_completion_year': 'Completion Year',
                'rnav_value': 'RNAV (VND)',
                'last_updated': 'Last Updated'
            }
            
            display_df = display_df.rename(columns=column_rename)
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            # If no standard columns found, display all available columns
            st.dataframe(
                df_projects,
                use_container_width=True,
                hide_index=True
            )
    
    def render_individual_project_editor(self, project_name, df_projects):
        """Render editor for individual project with revenue/presales distribution"""
        # Get the selected project data
        project_data = df_projects[df_projects['project_name'] == project_name].iloc[0].to_dict()
        
        # Add default values for new fields if they don't exist
        defaults = {
            'revenue_distribution': {},
            'presales_distribution': {},
            'custom_revenue_schedule': True,
            'custom_presales_schedule': True,
            'sga_percentage': 0.08,
            'cost_of_debt': 0.08,
            'wacc_rate': 0.12,
            'sales_years': 3,
            'construction_years': 3
        }
        
        for key, default_value in defaults.items():
            if key not in project_data or project_data[key] is None:
                project_data[key] = default_value
            # Special handling for distribution fields - ensure they're dictionaries
            elif key in ['revenue_distribution', 'presales_distribution']:
                if not isinstance(project_data[key], dict):
                    project_data[key] = default_value
        
        st.subheader(f"🏗️ Project: {project_name}")
        
        # Check if we're switching to a different project
        if 'current_editing_project' not in st.session_state:
            st.session_state.current_editing_project = project_name
            st.session_state.edited_project = project_data.copy()
        elif st.session_state.current_editing_project != project_name:
            # Different project selected, reset the edited data
            st.session_state.current_editing_project = project_name
            st.session_state.edited_project = project_data.copy()
        elif 'edited_project' not in st.session_state:
            # Same project but edited_project was deleted (e.g., after save)
            st.session_state.edited_project = project_data.copy()
        
        # Render all sections in a single scrollable view
        st.markdown("---")
        self.render_project_basic_info(project_data)
        
        st.markdown("---")
        self.render_project_timeline(project_data)
        
        st.markdown("---")
        self.render_presales_distribution_editor(project_data)
        
        st.markdown("---")
        self.render_revenue_distribution_editor(project_data)
        
        st.markdown("---")
        self.render_project_financial_analysis(project_data)
        
        st.markdown("---")
        self.render_project_save_interface(project_data)
    
    def render_project_basic_info(self, project_data):
        """Render basic project information editor"""
        st.subheader("Basic Project Information")
        
        # Ensure project_data is a dictionary
        if not isinstance(project_data, dict):
            st.error("Invalid project data format")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Location
            location = st.text_input(
                "Location",
                value=str(project_data.get('location', '') or ''),
                key="edit_location"
            )
            st.session_state.edited_project['location'] = location
            
            # Total Units
            total_units = st.number_input(
                "Total Units",
                value=int(project_data.get('total_units', 0) or 0),
                min_value=0,
                key="edit_total_units"
            )
            st.session_state.edited_project['total_units'] = total_units
            
            # Average Unit Size
            avg_unit_size = st.number_input(
                "Average Unit Size (m²)",
                value=float(project_data.get('average_unit_size', 0) or 0),
                min_value=0.0,
                key="edit_avg_unit_size"
            )
            st.session_state.edited_project['average_unit_size'] = avg_unit_size
            
            # Calculate NSA
            nsa = total_units * avg_unit_size
            st.info(f"Net Sellable Area: {nsa:,.0f} m²")
            st.session_state.edited_project['net_sellable_area'] = nsa
            
            # Project Ownership
            ownership = st.number_input(
                "Project Ownership (0-1)",
                value=float(project_data.get('project_ownership', 1.0) or 1.0),
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                key="edit_ownership"
            )
            st.session_state.edited_project['project_ownership'] = ownership
        
        with col2:
            # Average Selling Price
            asp = st.number_input(
                "Average Selling Price (VND/m²)",
                value=float(project_data.get('average_selling_price', 0) or 0),
                min_value=0.0,
                format="%.0f",
                key="edit_asp"
            )
            st.session_state.edited_project['average_selling_price'] = asp
            
            # Land Area
            land_area = st.number_input(
                "Land Area (m²)",
                value=float(project_data.get('land_area', 0) or 0),
                min_value=0.0,
                key="edit_land_area"
            )
            st.session_state.edited_project['land_area'] = land_area
            
            # Construction Cost per sqm
            const_cost = st.number_input(
                "Construction Cost (VND/m²)",
                value=float(project_data.get('construction_cost_per_sqm', 0) or 0),
                min_value=0.0,
                format="%.0f",
                key="edit_const_cost"
            )
            st.session_state.edited_project['construction_cost_per_sqm'] = const_cost
            
            # Land Cost per sqm
            land_cost = st.number_input(
                "Land Cost (VND/m²)",
                value=float(project_data.get('land_cost_per_sqm', 0) or 0),
                min_value=0.0,
                format="%.0f",
                key="edit_land_cost"
            )
            st.session_state.edited_project['land_cost_per_sqm'] = land_cost
            
            # GFA
            gfa = st.number_input(
                "Gross Floor Area (m²)",
                value=float(project_data.get('gross_floor_area', 0) or 0),
                min_value=0.0,
                key="edit_gfa"
            )
            st.session_state.edited_project['gross_floor_area'] = gfa
    
    def render_project_timeline(self, project_data):
        """Render project timeline editor"""
        st.subheader("Project Timeline")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Construction timeline
            const_start = st.number_input(
                "Construction Start Year",
                value=int(project_data.get('construction_start_year', datetime.now().year) or datetime.now().year),
                min_value=2000,  # Allow historical years
                max_value=2040,
                key="edit_const_start"
            )
            st.session_state.edited_project['construction_start_year'] = const_start
            
            const_years = st.number_input(
                "Construction Duration (years)",
                value=int(project_data.get('construction_years', 3) or 3),
                min_value=1,
                max_value=10,
                key="edit_const_years"
            )
            st.session_state.edited_project['construction_years'] = const_years
            
            # Sales timeline
            sales_start = st.number_input(
                "Sales Start Year",
                value=int(project_data.get('sale_start_year', datetime.now().year) or datetime.now().year),
                min_value=2000,  # Allow historical years
                max_value=2040,
                key="edit_sales_start"
            )
            st.session_state.edited_project['sale_start_year'] = sales_start
            
            sales_years = st.number_input(
                "Sales Duration (years)",
                value=int(project_data.get('sales_years', 3) or 3),
                min_value=1,
                max_value=10,
                key="edit_sales_years"
            )
            st.session_state.edited_project['sales_years'] = sales_years
        
        with col2:
            # Revenue booking timeline
            revenue_start = st.number_input(
                "Revenue Booking Start Year",
                value=int(project_data.get('revenue_booking_start_year', datetime.now().year + 1) or datetime.now().year + 1),
                min_value=2000,  # Allow historical years
                max_value=2040,
                key="edit_revenue_start"
            )
            st.session_state.edited_project['revenue_booking_start_year'] = revenue_start
            
            completion_year = st.number_input(
                "Project Completion Year (Revenue Booking End Year)",
                value=int(project_data.get('project_completion_year', datetime.now().year + 3) or datetime.now().year + 3),
                min_value=2000,  # Allow historical years
                max_value=2040,
                key="edit_completion"
            )
            st.session_state.edited_project['project_completion_year'] = completion_year
            
            # Land payment year
            land_payment = st.number_input(
                "Land Payment Year",
                value=int(project_data.get('land_payment_year', const_start) or const_start),
                min_value=2000,  # Allow historical years
                max_value=2040,
                key="edit_land_payment"
            )
            st.session_state.edited_project['land_payment_year'] = land_payment
            
            # Financial parameters
            wacc = st.number_input(
                "WACC Rate",
                value=float(project_data.get('wacc_rate', 0.12) or 0.12),
                min_value=0.0,
                max_value=1.0,
                step=0.01,
                format="%.2f",
                key="edit_wacc"
            )
            st.session_state.edited_project['wacc_rate'] = wacc
            
            # SG&A Percentage
            sga_pct = st.number_input(
                "SG&A as % of Revenue",
                value=float(project_data.get('sga_percentage', 0.08) or 0.08),
                min_value=0.0,
                max_value=0.5,
                step=0.01,
                format="%.2f",
                key="edit_sga_pct"
            )
            st.session_state.edited_project['sga_percentage'] = sga_pct
            
            # Cost of Debt
            cost_of_debt = st.number_input(
                "Cost of Debt (Interest Rate)",
                value=float(project_data.get('cost_of_debt', 0.08) or 0.08),
                min_value=0.0,
                max_value=0.5,
                step=0.01,
                format="%.2f",
                key="edit_cost_of_debt"
            )
            st.session_state.edited_project['cost_of_debt'] = cost_of_debt
    
    def render_revenue_distribution_editor(self, project_data):
        """Render revenue distribution editor with year-by-year percentages"""
        st.subheader("Revenue Distribution Schedule")
        st.info("💡 Enter percentage of total revenue to recognize in each year. Must sum to 100%.")
        
        # Get timeline parameters from edited project
        revenue_start = st.session_state.edited_project.get('revenue_booking_start_year', 
                                                             project_data.get('revenue_booking_start_year', datetime.now().year) or datetime.now().year)
        revenue_end = st.session_state.edited_project.get('project_completion_year',
                                                          project_data.get('project_completion_year', datetime.now().year + 3) or datetime.now().year + 3)
        
        # Always use custom schedule
        st.session_state.edited_project['custom_revenue_schedule'] = True
        
        # Get existing distribution from session state (which may have been updated by reset button)
        # If not in session state, get from project data
        existing_dist = st.session_state.edited_project.get('revenue_distribution', 
                                                            project_data.get('revenue_distribution', {}))
        if not isinstance(existing_dist, dict):
            existing_dist = {}
        
        # Create input fields for each year
        years = list(range(int(revenue_start), int(revenue_end) + 1))
        distribution = {}
        
        # If no existing distribution or empty, create even split
        if not existing_dist or len(existing_dist) == 0:
            for year in years:
                existing_dist[str(year)] = 100.0 / len(years) if len(years) > 0 else 100.0
        
        # Calculate totals for display
        edited = st.session_state.edited_project
        total_units = float(edited.get('total_units', 0) or 0)
        nsa = float(edited.get('net_sellable_area', 0) or 0)
        asp = float(edited.get('average_selling_price', 0) or 0)
        total_revenue = nsa * asp / 1e9  # Convert to billions
        
        cols = st.columns(min(len(years), 4))  # Max 4 columns
        
        for i, year in enumerate(years):
            col_idx = i % len(cols)
            with cols[col_idx]:
                default_val = existing_dist.get(str(year), 100.0/len(years))
                pct = st.number_input(
                    f"Year {year} (%)",
                    value=float(default_val),
                    min_value=0.0,
                    max_value=100.0,
                    step=0.1,
                    key=f"revenue_dist_{year}"
                )
                distribution[str(year)] = pct
                
                # Display calculated units and value
                units_for_year = int(total_units * pct / 100)
                value_for_year = total_revenue * pct / 100
                st.caption(f"Units: {units_for_year:,}")
                st.caption(f"Value: {value_for_year:.0f}B VND")
        
        # Validate percentages
        total_pct = sum(distribution.values())
        col1, col2 = st.columns(2)
        
        with col1:
            if abs(total_pct - 100.0) < 0.01:
                st.success(f"✅ Total: {total_pct:.1f}%")
            else:
                st.error(f"❌ Total: {total_pct:.1f}% (must be 100%)")
        
        with col2:
            if st.button("Reset to Linear Distribution", key="reset_revenue"):
                # Reset to even distribution across all years
                even_pct = 100.0 / len(years) if len(years) > 0 else 100.0
                reset_dist = {}
                for year in years:
                    reset_dist[str(year)] = even_pct
                st.session_state.edited_project['revenue_distribution'] = reset_dist
                st.rerun()
        
        st.session_state.edited_project['revenue_distribution'] = distribution
        
        # Show visual chart of distribution
        if years:
            import plotly.graph_objects as go
            
            # Calculate total revenue to show absolute values
            edited = st.session_state.edited_project
            nsa = float(edited.get('net_sellable_area', 0) or 0)
            asp = float(edited.get('average_selling_price', 0) or 0)
            total_revenue = nsa * asp / 1e9  # Convert to billions
            
            # Calculate absolute values for each year
            absolute_values = [total_revenue * distribution.get(str(y), 0) / 100 for y in years]
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=[str(y) for y in years],
                y=absolute_values,
                text=[f"{abs_val:.0f}B ({distribution.get(str(y), 0):.1f}%)" for y, abs_val in zip(years, absolute_values)],
                textposition='auto',
                marker_color='darkblue'
            ))
            fig.update_layout(
                title="Revenue Recognition Schedule",
                xaxis_title="Year",
                yaxis_title="Revenue (VND Billions)",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
    
    def render_presales_distribution_editor(self, project_data):
        """Render presales distribution editor with year-by-year percentages"""
        st.subheader("Presales Distribution Schedule")
        st.info("💡 Enter percentage of total sales to achieve in each year. Must sum to 100%.")
        
        # Get timeline parameters from edited project
        sales_start = st.session_state.edited_project.get('sale_start_year',
                                                          project_data.get('sale_start_year', datetime.now().year) or datetime.now().year)
        sales_years = st.session_state.edited_project.get('sales_years',
                                                          project_data.get('sales_years', 3) or 3)
        sales_end = int(sales_start or datetime.now().year) + int(sales_years or 3) - 1
        
        # Always use custom schedule
        st.session_state.edited_project['custom_presales_schedule'] = True
        
        # Get existing distribution from session state (which may have been updated by reset button)
        # If not in session state, get from project data
        existing_dist = st.session_state.edited_project.get('presales_distribution', 
                                                            project_data.get('presales_distribution', {}))
        if not isinstance(existing_dist, dict):
            existing_dist = {}
        
        # Create input fields for each year
        years = list(range(int(sales_start), int(sales_end) + 1))
        distribution = {}
        
        # If no existing distribution or empty, create even split
        if not existing_dist or len(existing_dist) == 0:
            for year in years:
                existing_dist[str(year)] = 100.0 / len(years) if len(years) > 0 else 100.0
        
        # Calculate totals for display
        edited = st.session_state.edited_project
        total_units = float(edited.get('total_units', 0) or 0)
        nsa = float(edited.get('net_sellable_area', 0) or 0)
        asp = float(edited.get('average_selling_price', 0) or 0)
        total_revenue = nsa * asp / 1e9  # Convert to billions
        
        cols = st.columns(min(len(years), 4))  # Max 4 columns
        
        for i, year in enumerate(years):
            col_idx = i % len(cols)
            with cols[col_idx]:
                default_val = existing_dist.get(str(year), 100.0/len(years))
                pct = st.number_input(
                    f"Year {year} (%)",
                    value=float(default_val),
                    min_value=0.0,
                    max_value=100.0,
                    step=0.1,
                    key=f"presales_dist_{year}"
                )
                distribution[str(year)] = pct
                
                # Display calculated units and value
                units_for_year = int(total_units * pct / 100)
                value_for_year = total_revenue * pct / 100
                st.caption(f"Units: {units_for_year:,}")
                st.caption(f"Value: {value_for_year:.0f}B VND")
        
        # Validate percentages
        total_pct = sum(distribution.values())
        col1, col2 = st.columns(2)
        
        with col1:
            if abs(total_pct - 100.0) < 0.01:
                st.success(f"✅ Total: {total_pct:.1f}%")
            else:
                st.error(f"❌ Total: {total_pct:.1f}% (must be 100%)")
        
        with col2:
            if st.button("Reset to Linear Distribution", key="reset_presales"):
                # Reset to even distribution across all years
                even_pct = 100.0 / len(years) if len(years) > 0 else 100.0
                reset_dist = {}
                for year in years:
                    reset_dist[str(year)] = even_pct
                st.session_state.edited_project['presales_distribution'] = reset_dist
                st.rerun()
        
        st.session_state.edited_project['presales_distribution'] = distribution
        
        # Show visual chart of distribution
        if years:
            import plotly.graph_objects as go
            
            # Calculate total revenue to show absolute values for presales
            edited = st.session_state.edited_project
            nsa = float(edited.get('net_sellable_area', 0) or 0)
            asp = float(edited.get('average_selling_price', 0) or 0)
            total_revenue = nsa * asp / 1e9  # Convert to billions
            
            # Calculate absolute values for each year
            absolute_values = [total_revenue * distribution.get(str(y), 0) / 100 for y in years]
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=[str(y) for y in years],
                y=absolute_values,
                text=[f"{abs_val:.0f}B ({distribution.get(str(y), 0):.1f}%)" for y, abs_val in zip(years, absolute_values)],
                textposition='auto',
                marker_color='lightblue'
            ))
            fig.update_layout(
                title="Presales Schedule",
                xaxis_title="Year",
                yaxis_title="Presales Value (VND Billions)",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
    
    def render_project_financial_analysis(self, project_data):
        """Render financial analysis including RNAV calculation"""
        st.subheader("Financial Analysis & RNAV Calculation")
        
        # Import RNAV utilities
        from utils.RNAV_utils import (
            selling_progress_schedule_custom,
            land_use_right_payment_schedule_single_year,
            construction_payment_schedule,
            sga_payment_schedule_custom,
            generate_pnl_schedule_custom,
            RNAV_Calculation
        )
        
        # Get all parameters from edited project
        edited = st.session_state.edited_project
        
        # Calculate total values with proper defaults and type conversion
        nsa = float(edited.get('net_sellable_area', 0) or 0)
        asp = float(edited.get('average_selling_price', 0) or 0)
        gfa = float(edited.get('gross_floor_area', 0) or 0)
        land_area = float(edited.get('land_area', 0) or 0)
        const_cost = float(edited.get('construction_cost_per_sqm', 0) or 0)
        land_cost = float(edited.get('land_cost_per_sqm', 0) or 0)
        
        total_revenue = nsa * asp
        total_const_cost = gfa * const_cost
        total_land_cost = land_area * land_cost
        sga_pct = float(edited.get('sga_percentage', 0.08) or 0.08)
        total_sga = total_revenue * sga_pct
        
        # Display key metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Revenue", f"{total_revenue/1e9:,.1f}B VND")
            st.metric("Total Construction Cost", f"{total_const_cost/1e9:,.1f}B VND")
        
        with col2:
            st.metric("Total Land Cost", f"{total_land_cost/1e9:,.1f}B VND")
            st.metric("Total SG&A", f"{total_sga/1e9:,.1f}B VND")
        
        with col3:
            pbt = total_revenue - total_const_cost - total_land_cost - total_sga
            pat = pbt * 0.8  # 20% tax
            st.metric("Estimated PBT", f"{pbt/1e9:,.1f}B VND")
            st.metric("Estimated PAT", f"{pat/1e9:,.1f}B VND")
        
        # Calculate RNAV if requested
        if st.button("🧮 Calculate RNAV", key="calc_rnav"):
            try:
                current_year = datetime.now().year
                project_start = min(
                    edited.get('construction_start_year', current_year),
                    edited.get('sale_start_year', current_year),
                    edited.get('land_payment_year', current_year),
                    current_year
                )
                
                # Generate schedules with custom distributions
                presales_dist = edited.get('presales_distribution', {})
                if not isinstance(presales_dist, dict):
                    presales_dist = {}
                selling_progress = selling_progress_schedule_custom(
                    total_revenue/1e9,
                    int(project_start),
                    int(current_year),
                    int(edited.get('sale_start_year', current_year)),
                    int(edited.get('sales_years', 3)),
                    int(edited.get('project_completion_year', current_year + 3)),
                    presales_dist  # Pass custom distribution
                )
                
                construction_payment = construction_payment_schedule(
                    -total_const_cost/1e9,
                    int(project_start),
                    int(current_year),
                    int(edited.get('construction_start_year', current_year)),
                    int(edited.get('construction_years', 3)),
                    int(edited.get('project_completion_year', current_year + 3))
                )
                
                land_payment = land_use_right_payment_schedule_single_year(
                    -total_land_cost/1e9,
                    int(project_start),
                    int(current_year),
                    int(edited.get('land_payment_year', current_year)),
                    int(edited.get('project_completion_year', current_year + 3))
                )
                
                sga_payment = sga_payment_schedule_custom(
                    -total_sga/1e9,
                    int(project_start),
                    int(current_year),
                    int(edited.get('sale_start_year', current_year)),
                    int(edited.get('sales_years', 3)),
                    int(edited.get('project_completion_year', current_year + 3)),
                    presales_dist  # SG&A follows sales distribution
                )
                
                # Generate P&L with custom revenue distribution
                revenue_dist = edited.get('revenue_distribution', {})
                if not isinstance(revenue_dist, dict):
                    revenue_dist = {}
                df_pnl = generate_pnl_schedule_custom(
                    total_revenue/1e9,
                    -total_land_cost/1e9,
                    -total_const_cost/1e9,
                    -total_sga/1e9,
                    int(project_start),
                    int(current_year),
                    int(edited.get('revenue_booking_start_year', current_year + 1)),
                    int(edited.get('project_completion_year', current_year + 3)),
                    -total_const_cost/1e9,
                    int(edited.get('construction_years', 3)),
                    float(edited.get('cost_of_debt', 0.08)),
                    revenue_dist  # Pass custom revenue distribution
                )
                
                # Extract tax expense
                tax_expense = []
                for year in range(int(project_start), int(edited.get('project_completion_year', current_year + 3)) + 1):
                    year_data = df_pnl[df_pnl["Year"] == year]
                    if not year_data.empty and year_data["Type"].iloc[0] != "Summary":
                        tax_value = year_data["Tax Expense (20%)"].iloc[0]
                    else:
                        tax_value = 0.0
                    tax_expense.append(tax_value)
                
                # Calculate RNAV
                df_rnav = RNAV_Calculation(
                    selling_progress,
                    construction_payment,
                    sga_payment,
                    tax_expense,
                    land_payment,
                    float(edited.get('wacc_rate', 0.12)),
                    int(project_start),
                    int(current_year)
                )
                
                # Get RNAV value
                total_row = df_rnav[df_rnav["Year"] == "Total RNAV"]
                if not total_row.empty:
                    rnav_value = total_row["Discounted Cash Flow"].iloc[0] * 1e9
                else:
                    rnav_value = df_rnav.loc[df_rnav.index[-1], 'Discounted Cash Flow'] * 1e9
                
                # Display RNAV result
                st.success(f"🎯 RNAV Calculated Successfully!")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Project RNAV", f"{rnav_value/1e9:,.1f}B VND")
                    ownership = edited.get('project_ownership', 1.0)
                    st.metric("RNAV to Company", f"{(rnav_value * ownership)/1e9:,.1f}B VND")
                
                with col2:
                    if 'rnav_value' in project_data and project_data['rnav_value']:
                        old_rnav = project_data['rnav_value']
                        st.metric(
                            "Previous RNAV",
                            f"{old_rnav/1e9:,.1f}B VND",
                            delta=f"{(rnav_value - old_rnav)/1e9:,.1f}B"
                        )
                
                # Store RNAV in edited project
                st.session_state.edited_project['rnav_value'] = rnav_value
                
                # Display P&L Schedule
                with st.expander("View P&L Schedule"):
                    st.dataframe(df_pnl)
                
                # Display RNAV Schedule
                with st.expander("View RNAV Calculation Details"):
                    st.dataframe(df_rnav)
                    
            except Exception as e:
                st.error(f"Error calculating RNAV: {str(e)}")
    
    def render_project_save_interface(self, project_data):
        """Render interface to save project changes to MongoDB"""
        st.subheader("Save Project Changes")
        
        # Show what has changed
        changes = []
        edited = st.session_state.edited_project
        
        for key, value in edited.items():
            try:
                if key in project_data:
                    old_value = project_data[key]
                    if isinstance(value, dict):
                        # For distribution dictionaries, check if they're different
                        old_dict = old_value if isinstance(old_value, dict) else {}
                        if value != old_dict:
                            changes.append(f"{key}: Updated")
                    elif isinstance(value, (int, float)):
                        # Compare numeric values
                        if isinstance(old_value, (int, float)):
                            if abs(float(old_value) - float(value)) > 0.001:
                                changes.append(f"{key}: {old_value} → {value}")
                        else:
                            # Old value is not numeric, just note the change
                            changes.append(f"{key}: {old_value} → {value}")
                    else:
                        # Compare other types (strings, etc.)
                        if old_value != value:
                            changes.append(f"{key}: {old_value} → {value}")
                else:
                    if value:  # Only show if new value is not empty
                        changes.append(f"{key}: New value = {value}")
            except Exception as e:
                # If any error in comparison, just note it as changed
                changes.append(f"{key}: Modified")
        
        if changes:
            st.info(f"🔄 {len(changes)} changes detected:")
            with st.expander("View changes"):
                for change in changes[:20]:  # Limit to 20 changes
                    st.write(f"- {change}")
                if len(changes) > 20:
                    st.write(f"... and {len(changes) - 20} more changes")
        else:
            st.info("✅ No changes detected")
        
        # Save button
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 Save Changes to MongoDB", type="primary", disabled=len(changes) == 0):
                try:
                    # Calculate financial metrics before saving
                    nsa = edited.get('net_sellable_area', 0)
                    asp = edited.get('average_selling_price', 0)
                    gfa = edited.get('gross_floor_area', 0)
                    land_area = edited.get('land_area', 0)
                    const_cost = edited.get('construction_cost_per_sqm', 0)
                    land_cost = edited.get('land_cost_per_sqm', 0)
                    
                    total_revenue = float(nsa) * float(asp)
                    total_const_cost = float(gfa) * float(const_cost)
                    total_land_cost = float(land_area) * float(land_cost)
                    sga_pct = float(edited.get('sga_percentage', 0.08))
                    total_sga = total_revenue * sga_pct
                    pbt = total_revenue - total_const_cost - total_land_cost - total_sga
                    pat = pbt * 0.8
                    
                    # Update financial totals
                    edited['total_revenue'] = total_revenue
                    edited['total_construction_cost'] = total_const_cost
                    edited['total_land_cost'] = total_land_cost
                    edited['total_sga_cost'] = total_sga
                    edited['total_pbt'] = pbt
                    edited['total_pat'] = pat
                    
                    # Get RNAV if calculated
                    rnav_value = edited.get('rnav_value', project_data.get('rnav_value', None))
                    
                    # Save to MongoDB
                    from utils.mongodb_utils import save_project_to_mongodb
                    
                    result = save_project_to_mongodb(
                        edited,
                        edited['project_name'],
                        rnav_value
                    )
                    
                    if result['success']:
                        st.success(result['message'])
                        # Clear the edited project from session state
                        if 'edited_project' in st.session_state:
                            del st.session_state.edited_project
                        if 'current_editing_project' in st.session_state:
                            del st.session_state.current_editing_project
                        # Refresh project data
                        self.sync_project_data()
                    else:
                        st.error(result['message'])
                        
                except Exception as e:
                    st.error(f"Error saving project: {str(e)}")
        
        with col2:
            if st.button("🔄 Reset Changes"):
                if 'edited_project' in st.session_state:
                    del st.session_state.edited_project
                if 'current_editing_project' in st.session_state:
                    del st.session_state.current_editing_project
                st.rerun()
    
    def render_revenue_forecast(self):
        """Render revenue forecast based on project pipeline"""
        st.header("Revenue Forecast Model")
        
        if st.session_state.project_data is None or (isinstance(st.session_state.project_data, pd.DataFrame) and st.session_state.project_data.empty):
            st.warning("Project data required for accurate revenue forecasting. Click 'Sync Project Data' in the sidebar.")
            st.info("Showing assumption-based forecast instead.")
        
        # Generate revenue forecast from projects
        revenue_forecast = self.generate_revenue_forecast()
        
        # Display forecast chart
        st.subheader("Revenue Forecast by Source")
        
        fig = go.Figure()
        
        years = revenue_forecast['years']
        
        # Add revenue streams
        fig.add_trace(go.Bar(
            x=years,
            y=revenue_forecast['presales'],
            name='Presales',
            marker_color='lightblue',
            text=[f'{v:.0f}B' if v > 0 else '' for v in revenue_forecast['presales']],
            textposition='inside'
        ))
        
        fig.add_trace(go.Bar(
            x=years,
            y=revenue_forecast['handover'],
            name='Handover Revenue',
            marker_color='darkblue',
            text=[f'{v:.0f}B' if v > 0 else '' for v in revenue_forecast['handover']],
            textposition='inside'
        ))
        
        fig.add_trace(go.Bar(
            x=years,
            y=revenue_forecast['recurring'],
            name='Recurring Revenue',
            marker_color='green',
            text=[f'{v:.0f}B' if v > 0 else '' for v in revenue_forecast['recurring']],
            textposition='inside'
        ))
        
        # Add total revenue line
        fig.add_trace(go.Scatter(
            x=years,
            y=revenue_forecast['total'],
            name='Total Revenue',
            mode='lines+markers+text',
            line=dict(color='red', width=2),
            marker=dict(size=8),
            text=[f'{v:.0f}B' for v in revenue_forecast['total']],
            textposition='top center',
            yaxis='y2'
        ))
        
        fig.update_layout(
            title="Revenue Forecast Breakdown (Billion VND)",
            xaxis_title="Year",
            yaxis=dict(title="Revenue Components (B VND)", side='left'),
            yaxis2=dict(title="Total Revenue (B VND)", overlaying='y', side='right'),
            barmode='stack',
            height=500,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Revenue forecast summary table
        st.subheader("Revenue Forecast Summary")
        
        forecast_df = pd.DataFrame({
            'Year': years,
            'Presales': revenue_forecast['presales'],
            'Handover': revenue_forecast['handover'],
            'Recurring': revenue_forecast['recurring'],
            'Total': revenue_forecast['total']
        })
        
        # Add growth rates
        forecast_df['YoY Growth (%)'] = forecast_df['Total'].pct_change() * 100
        
        st.dataframe(
            forecast_df.style.format({
                'Year': '{:.0f}',
                'Presales': '{:,.1f}B',
                'Handover': '{:,.1f}B',
                'Recurring': '{:,.1f}B',
                'Total': '{:,.1f}B',
                'YoY Growth (%)': '{:.1f}%'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Project-by-Year Revenue Breakdown
        if 'project_details' in revenue_forecast and st.session_state.project_data is not None and isinstance(st.session_state.project_data, pd.DataFrame) and not st.session_state.project_data.empty:
            st.subheader("Project-by-Year Revenue Breakdown")
            
            # Create tabs for each year
            year_tabs = st.tabs([str(year) for year in years])
            
            for i, year in enumerate(years):
                with year_tabs[i]:
                    if year in revenue_forecast['project_details'] and revenue_forecast['project_details'][year]:
                        # Create DataFrame for this year's projects
                        year_projects = pd.DataFrame(revenue_forecast['project_details'][year])
                        
                        # Pivot to show projects vs revenue type
                        if not year_projects.empty:
                            pivot_df = year_projects.pivot_table(
                                index='project',
                                columns='type',
                                values='amount',
                                aggfunc='sum',
                                fill_value=0
                            )
                            
                            # Add total column
                            pivot_df['Total'] = pivot_df.sum(axis=1)
                            
                            # Sort by total revenue
                            pivot_df = pivot_df.sort_values('Total', ascending=False)
                            
                            # Display the table
                            st.dataframe(
                                pivot_df.style.format('{:,.1f}B'),
                                use_container_width=True
                            )
                            
                            # Show pie chart of project contributions
                            fig_pie = px.pie(
                                values=pivot_df['Total'].values,
                                names=pivot_df.index,
                                title=f"Project Revenue Distribution - {year}"
                            )
                            st.plotly_chart(fig_pie, use_container_width=True)
                    else:
                        st.info(f"No project revenue scheduled for {year}")
        
        # Overall project contribution analysis
        st.subheader("Total Revenue by Project (All Years)")
        
        if st.session_state.project_data is not None and isinstance(st.session_state.project_data, pd.DataFrame) and not st.session_state.project_data.empty:
            project_revenue = self.calculate_project_revenue_contribution()
            
            if not project_revenue.empty:
                # Sort by revenue and display
                project_revenue = project_revenue.sort_values('revenue', ascending=False)
                
                # Bar chart of project contributions
                fig_bar = px.bar(
                    project_revenue.head(15),  # Top 15 projects
                    x='revenue',
                    y='project',
                    orientation='h',
                    title="Top Projects by Total Revenue Contribution",
                    labels={'revenue': 'Total Revenue (B VND)', 'project': 'Project'}
                )
                
                fig_bar.update_layout(height=400)
                st.plotly_chart(fig_bar, use_container_width=True)
                
                # Display summary table
                st.dataframe(
                    project_revenue.style.format({'revenue': '{:,.1f}B'}),
                    use_container_width=True,
                    hide_index=True
                )
    
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
            'project_details': {}  # Store project-level breakdown
        }
        
        # If we have project data, calculate revenue from projects
        if st.session_state.project_data is not None and isinstance(st.session_state.project_data, pd.DataFrame) and not st.session_state.project_data.empty:
            forecast = self.calculate_project_based_revenue(forecast)
        else:
            # Fallback to assumption-based forecast if no project data
            forecast = self.calculate_assumption_based_revenue(forecast)
        
        return forecast
    
    def calculate_project_based_revenue(self, forecast):
        """Calculate revenue forecast based on actual project details"""
        df_projects = st.session_state.project_data
        current_year = datetime.now().year
        
        # Initialize project details dictionary
        for year in forecast['years']:
            forecast['project_details'][year] = []
        
        # Process each project
        for _, project in df_projects.iterrows():
            project_name = project.get('project_name', 'Unknown Project')
            
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
    
    def calculate_assumption_based_revenue(self, forecast):
        """Fallback to assumption-based forecast when no project data available"""
        # Use historical data as base
        base_revenue = 1000  # Default base in billions
        
        if st.session_state.historical_data is not None:
            if 'Sales' in st.session_state.historical_data.columns:
                base_revenue = st.session_state.historical_data['Sales'].iloc[-1] / 1e9
            elif 'Net_Revenue' in st.session_state.historical_data.columns:
                base_revenue = st.session_state.historical_data['Net_Revenue'].iloc[-1] / 1e9
        
        # Generate forecast based on assumptions
        for i, year in enumerate(forecast['years']):
            year_offset = i
            
            # Apply growth rates
            forecast['presales'][i] = base_revenue * 0.4 * (1 + st.session_state.assumptions['revenue_growth']['presales']) ** year_offset
            forecast['handover'][i] = base_revenue * 0.5 * (1 + st.session_state.assumptions['revenue_growth']['handover']) ** year_offset
            forecast['recurring'][i] = base_revenue * 0.1 * (1 + st.session_state.assumptions['revenue_growth']['recurring']) ** year_offset
            forecast['total'][i] = forecast['presales'][i] + forecast['handover'][i] + forecast['recurring'][i]
        
        return forecast
    
    # This method is no longer needed as we've integrated the logic into calculate_project_based_revenue
    
    def calculate_project_revenue_contribution(self):
        """Calculate revenue contribution by project"""
        df_projects = st.session_state.project_data
        
        if df_projects is None or (isinstance(df_projects, pd.DataFrame) and df_projects.empty):
            return pd.DataFrame()
        
        project_revenues = []
        for _, project in df_projects.iterrows():
            project_name = project.get('project_name', 'Unknown Project')
            
            # Calculate total revenue
            total_revenue = 0
            if 'total_revenue' in project and pd.notna(project['total_revenue']) and project['total_revenue'] > 0:
                total_revenue = project['total_revenue'] / 1e9  # Convert to billions
            else:
                # Calculate from components
                nsa = project.get('net_sellable_area', 0)
                avg_price = project.get('average_selling_price', 0)
                
                if nsa > 0 and avg_price > 0:
                    # Total revenue = NSA * Price per sqm
                    total_revenue = (nsa * avg_price) / 1e3  # Convert from millions to billions
                else:
                    # Try with units if NSA not available
                    total_units = project.get('total_units', 0)
                    if total_units > 0 and avg_price > 0:
                        avg_unit_size = project.get('average_unit_size', 70)  # Default 70 sqm
                        total_revenue = (total_units * avg_unit_size * avg_price) / 1e3
            
            if total_revenue > 0:
                project_revenues.append({
                    'project': project_name,
                    'revenue': total_revenue
                })
        
        return pd.DataFrame(project_revenues)
    
    def render_financial_projections(self):
        """Render complete financial projections"""
        st.header("Financial Projections")
        
        # Generate projections with error handling
        try:
            projections = self.generate_financial_projections()
        except Exception as e:
            st.error(f"Error generating projections: {str(e)}")
            return
        
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
        years = revenue_forecast['years']
        
        # Income Statement
        income_statement = pd.DataFrame()
        income_statement['Year'] = years
        income_statement['Revenue'] = revenue_forecast['total']
        
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
        
        try:
            projections = self.generate_financial_projections()
        except Exception as e:
            st.error(f"Error generating projections for valuation: {str(e)}")
            return
        
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
        
        total_rnav = 0  # Initialize total_rnav
        if st.session_state.project_data is not None and isinstance(st.session_state.project_data, pd.DataFrame) and not st.session_state.project_data.empty:
            if 'rnav_value' in st.session_state.project_data.columns:
                total_rnav = st.session_state.project_data['rnav_value'].sum()
                st.metric("Total RNAV", f"{total_rnav/1e9:,.0f}B VND")
            else:
                st.info("RNAV values not available in project data")
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
                total_rnav  # Use the initialized total_rnav
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
            if st.session_state.project_data is not None and isinstance(st.session_state.project_data, pd.DataFrame):
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
    try:
        model = RealEstateFinancialModel()
        model.render_main_interface()
    except Exception as e:
        st.error(f"Application error: {e}")
        st.info("Try refreshing the page or clearing cache (press 'c' in the menu)")

if __name__ == "__main__":
    main()