#%%
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import time
import os
import sys
import io
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
from utils.project_pipeline_manager import ProjectPipelineManager
from utils.claude_project_extractor import ClaudeProjectExtractor
from utils.god_ai_assistant import GodAIAssistant
# ComprehensiveRevenueAnalyzer removed - financial modeling simplified
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
        self.god_ai = GodAIAssistant()  # Initialize God AI
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
        # Add active tab tracking to preserve tab state
        if 'active_tab' not in st.session_state:
            st.session_state.active_tab = 0
        # Track if we're in the middle of editing to prevent resets
        if 'editing_in_progress' not in st.session_state:
            st.session_state.editing_in_progress = False
        # Store the current tab to persist across reruns
        if 'preserve_tab' not in st.session_state:
            st.session_state.preserve_tab = False
            
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
        st.sidebar.title("Real Estate Model")
        
        # Define callback for company selection
        def on_company_change():
            # Check if the key exists before accessing it
            if 'company_selector_v3' not in st.session_state:
                return
            selected = st.session_state.company_selector_v3
            if selected:
                ticker = selected.split(" - ")[0]
                # Check if ticker has changed
                if 'selected_company' not in st.session_state or st.session_state.selected_company != ticker:
                    # Ticker changed, reset ALL related data
                    st.session_state.selected_company = ticker
                    st.session_state.historical_data = None
                    st.session_state.project_data = None
                    
                    # Clear ALL session state variables related to the old ticker
                    # This ensures a clean slate when switching companies
                    keys_to_delete = []
                    for key in st.session_state.keys():
                        # Delete any ticker-specific keys
                        if isinstance(key, str):
                            if 'base_revenue_' in key or 'editable_assumptions_' in key:
                                keys_to_delete.append(key)
                            elif key in ['selected_streams_data', 'comprehensive_model', 'base_year_revenues']:
                                keys_to_delete.append(key)
                    
                    # Delete all identified keys
                    for key in keys_to_delete:
                        del st.session_state[key]
                    
                    # Initialize empty base_year_revenues for new ticker
                    st.session_state.base_year_revenues = {}
        
        # Load companies with caching
        companies = self.load_real_estate_companies()
        if companies:
            # Get current selection
            current_index = 0
            if 'selected_company' in st.session_state and st.session_state.selected_company is not None:
                for i, company in enumerate(companies):
                    if company.startswith(st.session_state.selected_company + " - "):
                        current_index = i
                        break
            
            selected = st.sidebar.selectbox(
                "Select Company",
                companies,
                index=current_index,
                key="company_selector_v3",
                on_change=on_company_change,
                help="Select a company to analyze"
            )
            
            # Extract ticker from selection
            if selected:
                ticker = selected.split(" - ")[0]
                if ticker != st.session_state.selected_company:
                    st.session_state.selected_company = ticker
                    # Mark that we need to load data for the new ticker
                    st.session_state.needs_data_refresh = True
                    
                # Auto-load data if ticker has changed or data not loaded
                if st.session_state.get('needs_data_refresh', False) or st.session_state.historical_data is None:
                    # Automatically load financial data from CSV if not already loaded
                    if st.session_state.historical_data is None:
                        with st.spinner(f"Loading financial data for {ticker}..."):
                            data = self.load_historical_data_from_csv(ticker)
                            if not data.empty:
                                st.session_state.historical_data = data
                                st.success(f"✅ Loaded financial data for {ticker}", icon="📊")
                            else:
                                st.session_state.historical_data = None
                                st.warning(f"No financial data found for {ticker}")
                    
                    # Automatically sync project data from MongoDB if not already loaded
                    if st.session_state.project_data is None:
                        with st.spinner(f"Syncing project data for {ticker}..."):
                            self.load_project_data_from_mongodb(ticker)
                    
                    # Clear the refresh flag
                    st.session_state.needs_data_refresh = False
                
        # Navigation section (moved here to be above Data Management)
        if st.session_state.selected_company:
            st.sidebar.markdown("---")
            st.sidebar.subheader("Navigation")
            
            # Define tab names for navigation
            tab_names = [
                "Historical Analysis",
                "AI Project Discovery", 
                "Assumptions",
                "Project Pipeline",
                "Revenue Forecast",
                "Valuation",
                "Research Insights",
                "Export Model",
                "God AI Assistant"
            ]
            
            # Initialize selected tab if not exists
            if 'selected_re_tab' not in st.session_state:
                st.session_state.selected_re_tab = tab_names[0]
            
            # Create vertical button navigation
            for tab_name in tab_names:
                # Determine button type based on selection
                if tab_name == st.session_state.selected_re_tab:
                    # Selected tab - use primary button
                    if st.sidebar.button(
                        tab_name,
                        key=f"nav_{tab_name}",
                        use_container_width=True,
                        type="primary"
                    ):
                        st.session_state.selected_re_tab = tab_name
                        st.rerun()
                else:
                    # Unselected tab - use secondary button
                    if st.sidebar.button(
                        tab_name,
                        key=f"nav_{tab_name}",
                        use_container_width=True,
                        type="secondary"
                    ):
                        st.session_state.selected_re_tab = tab_name
                        st.rerun()
            
            # Store tab names for use in render_main_interface
            st.session_state.tab_names = tab_names
        
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
        
        # Refresh Financial Data button
        if st.sidebar.button(
            "🔄 Refresh Financial Data",
            key="refresh_financial_btn_v2",
            use_container_width=True,
            type="secondary"
        ):
            self.refresh_financial_data()
            
        # Sync Project Data button
        if st.sidebar.button(
            "🔗 Sync Project Data",
            key="sync_project_btn_v2",
            use_container_width=True,
            type="secondary"
        ):
            self.sync_project_data()
            
        # Fetch Latest Reports button
        # DO NOT auto-load any data in sidebar to prevent blocking
        if st.sidebar.button(
            "📥 Fetch Latest Reports",
            key="fetch_reports_btn_v2",
            use_container_width=True,
            type="secondary"
        ):
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
        """Load historical financial data from FA_A_processed.csv."""
        try:
            # Use FA_A_processed.csv for all tickers
            fa_path = os.path.join(parent_dir, 'data', 'FA_A_processed.csv')
            
            if not os.path.exists(fa_path):
                st.warning("Financial data file not found")
                return pd.DataFrame()
            
            # Read only necessary columns first
            df_fa = pd.read_csv(fa_path, 
                                usecols=['TICKER', 'DATE', 'KEYCODE', 'VALUE'],
                                dtype={'TICKER': str, 'KEYCODE': str, 'DATE': int})
            
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
        """Load list of all companies from FA_A_processed.csv."""
        try:
            fa_path = os.path.join(parent_dir, 'data', 'FA_A_processed.csv')
            if not os.path.exists(fa_path):
                return []  # Return empty list if file not found
            
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
            # Return empty list on error
            return []
    
    def refresh_financial_data(self):
        """Refresh financial data from FA_A_processed.csv"""
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
        st.title("Real Estate Financial Model - God AI Edition")
        st.caption("Ultimate AI-powered financial modeling with intelligent assistant at your command")
        
        if not st.session_state.selected_company:
            st.info("👈 Please select a company from the sidebar to begin")
            return
            
        # Get selected tab from session state (set in sidebar)
        selected_tab = st.session_state.get('selected_re_tab', None)
        tab_names = st.session_state.get('tab_names', [])
        
        if not selected_tab or not tab_names:
            st.warning("Please select a module from the sidebar navigation")
            return
        
        # Display current module as header
        st.header(selected_tab)
        
        # Render content based on selection
        if selected_tab == tab_names[0]:  # Historical Analysis
            self.render_historical_analysis()
        elif selected_tab == tab_names[1]:  # AI Project Discovery
            self.render_ai_discovery()
        elif selected_tab == tab_names[2]:  # Assumptions
            self.render_assumptions_interface()
        elif selected_tab == tab_names[3]:  # Project Pipeline
            self.render_project_pipeline()
        elif selected_tab == tab_names[4]:  # Revenue Forecast
            self.render_revenue_forecast()
        elif selected_tab == tab_names[5]:  # Valuation
            self.render_valuation()
        elif selected_tab == tab_names[6]:  # Research Insights
            self.render_research_insights()
        elif selected_tab == tab_names[7]:  # Export Model
            self.render_export_interface()
        elif selected_tab == tab_names[8]:  # God AI Assistant
            self.render_god_ai_assistant()
        
    
    def render_historical_analysis(self):
        """Render historical financial analysis - Simple P&L Table"""
        
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
        
        # Get current year to filter out future data
        import datetime
        current_year = datetime.datetime.now().year
        
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
        
        # Calculate margins as percentages
        margin_rows = {}
        for year in years:
            if pnl_df.loc['Net Revenue', year] != 0:
                margin_rows[f'{year}'] = {
                    'Gross Profit Margin %': (pnl_df.loc['Gross Profit', year] / pnl_df.loc['Net Revenue', year] * 100) if pnl_df.loc['Net Revenue', year] != 0 else 0,
                    'EBITDA Margin %': (pnl_df.loc['EBITDA', year] / pnl_df.loc['Net Revenue', year] * 100) if pnl_df.loc['Net Revenue', year] != 0 else 0,
                    'Net Margin %': (pnl_df.loc['NPATMI', year] / pnl_df.loc['Net Revenue', year] * 100) if pnl_df.loc['Net Revenue', year] != 0 else 0
                }
        
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
        
        # Add margin analysis below
        if margin_rows:
            st.subheader("Profitability Margins")
            margin_df = pd.DataFrame(margin_rows)
            
            # Format margin percentages
            def format_margin(val):
                if pd.isna(val) or val == 0:
                    return "-"
                return f"{val:.1f}%"
            
            styled_margins = margin_df.style.format(format_margin)
            st.dataframe(styled_margins, use_container_width=True)
        
        # Add growth rates
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
    
    def render_ai_discovery(self):
        """Render AI-powered project discovery interface"""
        
        # Import the original AIDiscoveryTab
        from tabs.ai_discovery import AIDiscoveryTab
        
        # Initialize the AI discovery tab
        if 'ai_discovery_tab' not in st.session_state:
            st.session_state.ai_discovery_tab = AIDiscoveryTab(parent=self)
        
        # Render the original AI discovery interface
        st.session_state.ai_discovery_tab.render()
    
    def render_claude_discovery(self):
        """Render Claude AI interface for PDF analysis"""
        st.subheader("📄 Extract Projects from Documents using Claude AI")
        st.info("""
        Upload one or multiple PDF documents to extract real estate projects using Claude 3.5 Sonnet.
        Supports **Financial Statements**, **Analyst Reports**, and **Company Presentations**.
        Document types are automatically detected.
        """)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Multiple file uploader
            uploaded_files = st.file_uploader(
                "Choose PDF documents",
                type=['pdf'],
                accept_multiple_files=True,
                help="Upload one or more PDFs (Financial Statements, Analyst Reports, Company Presentations)",
                key="claude_pdf_uploads"
            )
        
        with col2:
            # Company info
            company_name = st.text_input(
                "Company Name",
                value=st.session_state.selected_company or "",
                help="Full company name",
                key="claude_company_name"
            )
            
            company_ticker = st.text_input(
                "Stock Ticker",
                value=st.session_state.selected_company or "",
                help="Stock ticker symbol",
                key="claude_ticker"
            )
            
            # Set selected_ticker in session state for assumptions tab
            if company_ticker:
                st.session_state.selected_ticker = company_ticker
            
            if uploaded_files:
                st.info(f"📚 {len(uploaded_files)} document(s) uploaded")
        
        if uploaded_files and company_name and company_ticker:
            if st.button("Extract Projects from All Documents", type="primary", use_container_width=True):
                # Process multiple documents
                extraction_results = st.session_state.pipeline_manager.claude_extractor.process_multiple_documents(
                    pdf_files=uploaded_files,
                    company_name=company_name,
                    company_ticker=company_ticker
                )
                
                # Display extraction summary
                summary = extraction_results.get('summary', {})
                
                # Show overall results
                if summary.get('successful_extractions', 0) > 0:
                    st.success(f"✅ Successfully processed {summary['successful_extractions']}/{summary['total_documents']} documents")
                    
                    # Store combined projects
                    st.session_state.claude_projects = extraction_results.get('all_projects', [])
                    st.session_state.claude_extraction_results = extraction_results
                    st.session_state.claude_metadata = {
                        'company_name': company_name,
                        'company_ticker': company_ticker,
                        'extraction_date': pd.Timestamp.now().isoformat(),
                        'documents_processed': summary['successful_extractions']
                    }
                    
                    # Display summary metrics
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Documents Processed", f"{summary['successful_extractions']}/{summary['total_documents']}")
                    with col2:
                        st.metric("Unique Projects Found", summary.get('total_unique_projects', 0))
                    with col3:
                        combined_metrics = extraction_results.get('combined_metrics', {})
                        avg_confidence = combined_metrics.get('average_confidence', 0)
                        st.metric("Avg Confidence", f"{avg_confidence:.0%}")
                    with col4:
                        doc_types = combined_metrics.get('document_types', {})
                        st.metric("Document Types", len(doc_types))
                    
                    # Show document-by-document summary
                    if extraction_results.get('document_summaries'):
                        with st.expander("📋 Document Processing Details", expanded=True):
                            doc_summary_df = pd.DataFrame(extraction_results['document_summaries'])
                            doc_summary_df['extraction_quality'] = doc_summary_df['extraction_quality'].apply(lambda x: f"{x:.0%}")
                            st.dataframe(doc_summary_df, use_container_width=True)
                    
                    # Show any failed extractions
                    if extraction_results.get('failed_extractions'):
                        with st.expander(f"⚠️ Failed Extractions ({len(extraction_results['failed_extractions'])})", expanded=False):
                            for failed in extraction_results['failed_extractions']:
                                st.error(f"**{failed['file_name']}**: {failed['error']}")
                                if 'suggestion' in failed:
                                    st.info(f"💡 {failed['suggestion']}")
                    
                    # Show combined project table
                    if st.session_state.claude_projects:
                        st.subheader("All Extracted Projects")

                        # Create enhanced summary table with source information
                        projects_for_table = []
                        for project in st.session_state.claude_projects:
                            project_entry = {
                                'Project Name': project.get('project_name', 'Unknown'),
                                'Location': project.get('location', 'N/A'),
                                'Stage': project.get('stage', project.get('development_stage', 'N/A')),
                                'Total Units': project.get('total_units', 0),
                                'Source Doc': project.get('source_document', 'Unknown'),
                                'Doc Type': project.get('source_type', 'Unknown').replace('_', ' ').title()
                            }
                            
                            # Add value column based on available data
                            if project.get('book_value_vnd'):
                                project_entry['Value (B VND)'] = project['book_value_vnd'] / 1e9
                            elif project.get('nav_value_vnd'):
                                project_entry['NAV (B VND)'] = project['nav_value_vnd'] / 1e9
                            elif project.get('presales_value_vnd'):
                                project_entry['Presales (B VND)'] = project['presales_value_vnd'] / 1e9
                            
                            projects_for_table.append(project_entry)
                        
                        summary_df = pd.DataFrame(projects_for_table)
                        
                        # Format numeric columns
                        if 'Total Units' in summary_df.columns:
                            summary_df['Total Units'] = summary_df['Total Units'].apply(lambda x: f"{int(x):,}" if x else "N/A")
                        for col in ['Value (B VND)', 'NAV (B VND)', 'Presales (B VND)']:
                            if col in summary_df.columns:
                                summary_df[col] = summary_df[col].apply(lambda x: f"{x:.1f}" if x else "N/A")
                        
                        st.dataframe(summary_df, use_container_width=True)
                else:
                    # All extractions failed
                    st.error(f"❌ Failed to process any documents. {len(extraction_results.get('failed_extractions', []))} document(s) failed.")
        else:
            if not uploaded_files:
                st.info("👆 Please upload one or more PDF documents")
            elif not company_name or not company_ticker:
                st.warning("Please enter company details")
    
    def render_perplexity_discovery(self):
        """Render Perplexity web research interface"""
        st.subheader("🌐 Discover Projects from Web using Perplexity AI")
        st.info("Search the web for real estate projects using Perplexity's research capabilities")
        
        col1, col2 = st.columns(2)
        
        with col1:
            company_name = st.text_input(
                "Company Name",
                value=st.session_state.selected_company or "",
                key="perplexity_company_name",
                help="Enter the company name to research"
            )
        
        with col2:
            company_ticker = st.text_input(
                "Stock Ticker",
                value=st.session_state.selected_company or "",
                key="perplexity_ticker",
                help="Stock ticker symbol"
            )
        
        if company_name and company_ticker:
            if st.button("🔍 Research Projects with Perplexity", type="primary", use_container_width=True):
                with st.spinner("Researching projects from web sources..."):
                    # Discover all projects from web (no known_projects parameter needed)
                    all_web_projects = st.session_state.pipeline_manager.discover_all_projects_from_web(
                        company_name=company_name,
                        company_ticker=company_ticker
                    )
                    
                    if all_web_projects:
                        st.session_state.perplexity_projects = all_web_projects
                        st.session_state.perplexity_metadata = {
                            'company_name': company_name,
                            'company_ticker': company_ticker,
                            'source': 'web_research',
                            'total_projects': len(all_web_projects)
                        }
                        
                        st.success(f"✅ Perplexity found {len(all_web_projects)} projects from web research")
                        
                        # Categorize projects
                        current_projects = [p for p in all_web_projects if p.get('status') != 'future']
                        future_projects = [p for p in all_web_projects if p.get('status') == 'future']
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Current Projects", len(current_projects))
                        with col2:
                            st.metric("Future Projects", len(future_projects))
                        
                        # Display projects
                        st.subheader("Projects Found from Web Research")
                        
                        # Convert to DataFrame for display
                        if all_web_projects:
                            display_data = []
                            for proj in all_web_projects:
                                display_data.append({
                                    'Project Name': proj.get('project_name', 'Unknown'),
                                    'Location': proj.get('location', 'N/A'),
                                    'Status': proj.get('status', 'N/A'),
                                    'Units': proj.get('estimated_units', 'N/A'),
                                    'Source': proj.get('source', 'Web'),
                                    'Description': proj.get('description', '')[:100] + '...' if proj.get('description') else ''
                                })
                            
                            df = pd.DataFrame(display_data)
                            st.dataframe(df, use_container_width=True)
                            
                            # Option to enrich with detailed research
                            if st.button("🔬 Get Detailed Information", type="secondary"):
                                progress_bar = st.progress(0)
                                status_text = st.empty()
                                
                                enriched_projects = []
                                for i, project in enumerate(all_web_projects):
                                    progress = (i + 1) / len(all_web_projects)
                                    progress_bar.progress(progress)
                                    status_text.text(f"Researching details for {project.get('project_name')}...")
                                    
                                    # Research detailed information
                                    detailed = st.session_state.pipeline_manager.perplexity_researcher.research_project_details(
                                        project_name=project.get('project_name'),
                                        company_name=company_name,
                                        location_hint=project.get('location')
                                    )
                                    
                                    # Merge with existing data
                                    enriched = {**project, **detailed} if 'error' not in detailed else project
                                    enriched_projects.append(enriched)
                                
                                st.session_state.perplexity_projects = enriched_projects
                                progress_bar.empty()
                                status_text.empty()
                                st.success("✅ Enrichment complete")
                                st.rerun()
                    else:
                        st.warning("No projects found from web research")
        else:
            st.info("👆 Please enter company details to search")
    
    def render_merge_results(self):
        """Render interface to merge Claude and Perplexity results"""
        st.subheader("🔀 AI-Powered Merge & Database Comparison")
        st.info("Claude AI will intelligently merge results from both sources and compare with existing database projects")
        
        # Check if we have results from both sources
        has_claude = 'claude_projects' in st.session_state
        has_perplexity = 'perplexity_projects' in st.session_state
        
        if not has_claude and not has_perplexity:
            st.info("Run Claude AI and/or Perplexity research first to generate results to merge")
            return
        
        # Display available sources
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if has_claude:
                st.success("✅ Claude Results")
                st.metric("Document Projects", len(st.session_state.claude_projects))
            else:
                st.info("No Claude results")
        
        with col2:
            if has_perplexity:
                st.success("✅ Perplexity Results")
                st.metric("Web Projects", len(st.session_state.perplexity_projects))
            else:
                st.info("No Perplexity results")
        
        with col3:
            # Get existing database projects count
            ticker = st.session_state.claude_metadata.get('company_ticker', '') if has_claude else ''
            if ticker:
                existing_projects = st.session_state.pipeline_manager.mongo_helper.get_real_estate_projects(ticker)
                st.info("Database Projects")
                st.metric("Existing", len(existing_projects))
            else:
                existing_projects = []
        
        # Merge button
        if st.button("AI Merge & Compare with Database", type="primary", use_container_width=True):
            # Get company info
            company_name = st.session_state.claude_metadata.get('company_name', '') if has_claude else ''
            company_ticker = st.session_state.claude_metadata.get('company_ticker', '') if has_claude else ''
            
            if not company_ticker and has_perplexity:
                company_ticker = st.session_state.perplexity_metadata.get('company_ticker', '')
                company_name = st.session_state.perplexity_metadata.get('company_name', '')
            
            # Step 1: AI-powered merge of Claude and Perplexity results
            with st.spinner("Using Claude AI to intelligently merge results..."):
                claude_projects = st.session_state.claude_projects if has_claude else []
                perplexity_projects = st.session_state.perplexity_projects if has_perplexity else []
                
                merge_result = st.session_state.pipeline_manager.claude_extractor.merge_claude_perplexity_results(
                    claude_projects=claude_projects,
                    perplexity_projects=perplexity_projects,
                    company_name=company_name,
                    company_ticker=company_ticker
                )
                
                merged_projects = merge_result.get('merged_projects', [])
                merge_summary = merge_result.get('merge_summary', {})
                
                st.session_state.merged_projects = merged_projects
                st.session_state.merge_metadata = merge_result.get('metadata', {})
                st.session_state.merge_summary = merge_summary
            
            # Step 2: Compare with database
            with st.spinner("Comparing with existing database projects..."):
                comparison_result = st.session_state.pipeline_manager.claude_extractor.compare_with_database_projects(
                    merged_projects=merged_projects,
                    existing_projects=existing_projects
                )
                
                st.session_state.comparison_result = comparison_result
            
            # Display results
            st.success("✅ AI Analysis Complete!")
            
            # Show merge summary
            st.subheader("🔀 Merge Analysis")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Unique Projects", merge_summary.get('total_unique_projects', 0))
            with col2:
                st.metric("High Confidence", merge_summary.get('high_confidence_projects', 0))
            with col3:
                st.metric("In Both Sources", merge_summary.get('projects_in_both', 0))
            with col4:
                st.metric("Claude Only", merge_summary.get('projects_only_in_claude', 0))
            
            # Show database comparison
            comp_summary = comparison_result.get('comparison_summary', {})
            
            if comp_summary.get('new_discoveries', 0) > 0:
                st.subheader(f"🆕 New Projects Discovered ({comp_summary['new_discoveries']})")
                
                new_projects = comparison_result.get('new_projects', [])
                if new_projects:
                    new_df = pd.DataFrame(new_projects)
                    st.dataframe(new_df, use_container_width=True)
                    
                    # Highlight significance
                    if comp_summary.get('significance_notes'):
                        st.info(f"💡 {comp_summary['significance_notes']}")
            
            if comp_summary.get('updates_found', 0) > 0:
                with st.expander(f"📝 Updated Projects ({comp_summary['updates_found']})"):
                    updated_projects = comparison_result.get('updated_projects', [])
                    for update in updated_projects:
                        st.write(f"**{update['project_name']}**")
                        for change in update.get('updates', []):
                            st.write(f"  • {change}")
            
            # Show all merged projects
            with st.expander("All Merged Projects", expanded=True):
                display_data = []
                for proj in merged_projects:
                    display_data.append({
                        'Project Name': proj.get('project_name', 'Unknown'),
                        'Location': proj.get('location', 'N/A'),
                        'Confidence': f"{proj.get('confidence_score', 0):.0%}",
                        'Book Value (B VND)': f"{(proj.get('book_value_vnd') or 0)/1e9:.0f}" if proj.get('book_value_vnd') else 'N/A',
                        'Market Value (B VND)': f"{(proj.get('market_value_vnd') or 0)/1e9:.0f}" if proj.get('market_value_vnd') else 'N/A',
                        'Total Units': proj.get('total_units') or 'N/A',
                        'Stage': proj.get('stage', 'N/A'),
                        'Sources': ', '.join(proj.get('data_sources', [])),
                        'Notes': proj.get('merge_notes', '')
                    })
                
                df = pd.DataFrame(display_data)
                st.dataframe(df, use_container_width=True)
            
            # Save options
            st.subheader("💾 Save Options")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("💾 Save All to Database", type="secondary", use_container_width=True):
                    success = st.session_state.pipeline_manager.save_projects_to_mongodb(
                        projects=merged_projects,
                        ticker=company_ticker,
                        mode="merge"
                    )
                    if success:
                        st.success("✅ Saved all projects to MongoDB")
            
            with col2:
                if comp_summary.get('new_discoveries', 0) > 0:
                    if st.button("🆕 Save Only New Projects", type="secondary", use_container_width=True):
                        new_projects_to_save = []
                        new_project_names = [p['project_name'] for p in comparison_result.get('new_projects', [])]
                        
                        for proj in merged_projects:
                            if proj.get('project_name') in new_project_names:
                                new_projects_to_save.append(proj)
                        
                        if new_projects_to_save:
                            success = st.session_state.pipeline_manager.save_projects_to_mongodb(
                                projects=new_projects_to_save,
                                ticker=company_ticker,
                                mode="append"
                            )
                            if success:
                                st.success(f"✅ Saved {len(new_projects_to_save)} new projects")
            
            with col3:
                if st.button("📥 Export to Excel", type="secondary", use_container_width=True):
                    # Create comprehensive Excel export
                    import io
                    buffer = io.BytesIO()
                    
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        # All projects sheet
                        df.to_excel(writer, sheet_name='All Projects', index=False)
                        
                        # New discoveries sheet
                        if comparison_result.get('new_projects'):
                            new_df = pd.DataFrame(comparison_result['new_projects'])
                            new_df.to_excel(writer, sheet_name='New Discoveries', index=False)
                        
                        # Summary sheet
                        summary_data = {
                            'Metric': ['Total Unique Projects', 'High Confidence', 'Medium Confidence', 
                                      'Projects in Both Sources', 'New Discoveries', 'Updated Projects'],
                            'Value': [
                                merge_summary.get('total_unique_projects', 0),
                                merge_summary.get('high_confidence_projects', 0),
                                merge_summary.get('medium_confidence_projects', 0),
                                merge_summary.get('projects_in_both', 0),
                                comp_summary.get('new_discoveries', 0),
                                comp_summary.get('updates_found', 0)
                            ]
                        }
                        summary_df = pd.DataFrame(summary_data)
                        summary_df.to_excel(writer, sheet_name='Summary', index=False)
                    
                    buffer.seek(0)
                    
                    st.download_button(
                        label="📥 Download Excel Report",
                        data=buffer,
                        file_name=f"{company_ticker}_project_analysis_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
    
    def _similar_project_names(self, name1: str, name2: str) -> bool:
        """Check if two project names are similar (likely the same project)"""
        # Simple similarity check - can be enhanced
        name1_clean = name1.lower().replace(' ', '').replace('-', '').replace('_', '')
        name2_clean = name2.lower().replace(' ', '').replace('-', '').replace('_', '')
        
        # Check if one contains the other
        if name1_clean in name2_clean or name2_clean in name1_clean:
            return True
        
        # Check if they share significant parts
        words1 = set(name1.lower().split())
        words2 = set(name2.lower().split())
        common = words1.intersection(words2)
        
        # If they share more than 50% of words, consider them similar
        if len(common) > 0:
            similarity = len(common) / min(len(words1), len(words2))
            return similarity > 0.5
        
        return False
    
    # render_financial_modeling method removed - too complicated
    
    def render_discovery_history(self):
        """Render discovery session history"""
        st.subheader("Discovery History")
        
        if st.session_state.selected_company:
            history = st.session_state.pipeline_manager.mongo_helper.get_discovery_history(
                ticker=st.session_state.selected_company,
                limit=20
            )
            
            if history:
                # Convert to DataFrame for display
                history_df = pd.DataFrame(history)
                
                # Format timestamp
                if 'timestamp' in history_df.columns:
                    history_df['timestamp'] = pd.to_datetime(history_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
                
                # Select columns to display
                display_cols = ['timestamp', 'document_name', 'projects_discovered', 
                               'projects_enriched', 'new_projects', 'updated_projects']
                display_cols = [col for col in display_cols if col in history_df.columns]
                
                st.dataframe(history_df[display_cols], use_container_width=True)
            else:
                st.info("No discovery history available for this company")
        else:
            st.info("Select a company to view discovery history")
    
    @st.fragment
    def render_assumptions_interface(self):
        """Render enhanced assumptions interface with business segment support"""
        st.header("Model Assumptions")
        
        # Import MongoDB utilities
        from utils.mongodb_utils import get_company_assumptions, save_company_assumptions
        
        # Get ticker from sidebar selection
        selected_ticker = st.session_state.get('selected_company', None)
        
        if not selected_ticker:
            st.info("Please select a company from the sidebar to manage assumptions")
            return
        
        st.markdown(f"Managing assumptions for **{selected_ticker}**")
        
        # Add helper text for business segments
        with st.expander("📚 How to Define Business Segments", expanded=False):
            st.markdown("""
            **Business Segment Structure:**
            - Each business segment should have 3 key assumptions:
              1. **Revenue Growth** - Annual growth rate (%)
              2. **Gross Margin** - Gross profit margin (%)
              3. **SG&A % of Revenue** - Selling, General & Admin as % of revenue
            
            **Example for Brokerage segment:**
            - Category: `Business Segment`, Type: `Revenue Growth`, Item: `Brokerage`, Value: `15`, Unit: `%`
            - Category: `Business Segment`, Type: `Gross Margin`, Item: `Brokerage`, Value: `60`, Unit: `%`
            - Category: `Business Segment`, Type: `SG&A % of Revenue`, Item: `Brokerage`, Value: `25`, Unit: `%`
            
            **How to use:**
            - **Category**: Select "Business Segment" for revenue stream assumptions
            - **Type**: Choose the metric type (Revenue Growth, Gross Margin, or SG&A % of Revenue)
            - **Item**: Enter the business segment name (e.g., "Brokerage", "Property Management")
            - **Value**: Enter the numeric value
            - **Unit**: Select the appropriate unit (usually "%")
            
            **Note:** Use consistent segment names across all metrics for proper grouping
            """)
        
        # Initialize editable assumptions in session state if not exists
        assumptions_key = f"editable_assumptions_{selected_ticker}"
        # Use a more stable key that includes timestamp to prevent conflicts
        editor_key = f"assumptions_editor_{selected_ticker}_v2"
        
        # Initialize or load assumptions data
        if assumptions_key not in st.session_state or st.session_state.get('refresh_assumptions', False):
            # Load from MongoDB
            company_assumptions = get_company_assumptions(selected_ticker)
            
            # Build initial assumptions data list
            assumptions_data = []
            
            # Load standard financial assumptions
            wacc = company_assumptions.get('wacc', 0.12) * 100
            debt_financing = company_assumptions.get('debt_financing_pct', 0.30) * 100
            tax_rate = company_assumptions.get('tax_rate', 0.20) * 100
            
            assumptions_data.extend([
                {"Category": "Financial", "Type": "N/A", "Item": "WACC", "Value": wacc, "Unit": "%"},
                {"Category": "Financial", "Type": "N/A", "Item": "Debt Financing %", "Value": debt_financing, "Unit": "%"},
                {"Category": "Financial", "Type": "N/A", "Item": "Tax Rate", "Value": tax_rate, "Unit": "%"}
            ])
            
            # Load business segments from revenue_streams
            revenue_streams = company_assumptions.get('revenue_streams', [])
            for stream in revenue_streams:
                segment_name = stream.get('segment_name', '')
                if segment_name:
                    # Add Revenue Growth
                    if 'revenue_growth' in stream:
                        assumptions_data.append({
                            "Category": "Business Segment",
                            "Type": "Revenue Growth",
                            "Item": segment_name,
                            "Value": stream['revenue_growth'] * 100,  # Convert from decimal to percentage
                            "Unit": "%"
                        })
                    # Add Gross Margin
                    if 'gross_margin' in stream:
                        assumptions_data.append({
                            "Category": "Business Segment",
                            "Type": "Gross Margin",
                            "Item": segment_name,
                            "Value": stream['gross_margin'] * 100,  # Convert from decimal to percentage
                            "Unit": "%"
                        })
                    # Add SG&A Percentage
                    if 'sga_percentage' in stream:
                        assumptions_data.append({
                            "Category": "Business Segment",
                            "Type": "SG&A % of Revenue",
                            "Item": segment_name,
                            "Value": stream['sga_percentage'] * 100,  # Convert from decimal to percentage
                            "Unit": "%"
                        })
            
            # Load any custom assumptions from MongoDB
            custom_assumptions = company_assumptions.get('custom_assumptions', [])
            for custom in custom_assumptions:
                assumptions_data.append({
                    "Category": custom.get('category', 'Other'),
                    "Type": custom.get('type', 'N/A'),
                    "Item": custom.get('item', 'Custom'),
                    "Value": custom.get('value', 0),
                    "Unit": custom.get('unit', '%')
                })
            
            # If still empty, use defaults with example business segment
            if not assumptions_data:
                assumptions_data = [
                    {"Category": "Financial", "Type": "N/A", "Item": "WACC", "Value": 12.0, "Unit": "%"},
                    {"Category": "Financial", "Type": "N/A", "Item": "Debt Financing %", "Value": 30.0, "Unit": "%"},
                    {"Category": "Financial", "Type": "N/A", "Item": "Tax Rate", "Value": 20.0, "Unit": "%"},
                    {"Category": "Business Segment", "Type": "Revenue Growth", "Item": "Brokerage", "Value": 15.0, "Unit": "%"},
                    {"Category": "Business Segment", "Type": "Gross Margin", "Item": "Brokerage", "Value": 60.0, "Unit": "%"},
                    {"Category": "Business Segment", "Type": "SG&A % of Revenue", "Item": "Brokerage", "Value": 25.0, "Unit": "%"},
                    {"Category": "Business Segment", "Type": "Revenue Growth", "Item": "Property Management", "Value": 20.0, "Unit": "%"},
                    {"Category": "Business Segment", "Type": "Gross Margin", "Item": "Property Management", "Value": 45.0, "Unit": "%"},
                    {"Category": "Business Segment", "Type": "SG&A % of Revenue", "Item": "Property Management", "Value": 30.0, "Unit": "%"}
                ]
            
            # Store in session state with ticker-specific key
            st.session_state[assumptions_key] = pd.DataFrame(assumptions_data)
            st.session_state.refresh_assumptions = False
        
        # Get current assumptions DataFrame from session state
        assumptions_df = st.session_state[assumptions_key]
        if not isinstance(assumptions_df, pd.DataFrame):
            assumptions_df = pd.DataFrame(assumptions_df)
        
        # Display editable assumptions table
        st.subheader("Assumptions Table")
        st.info("💡 **How to use:** Click any cell to edit | Use '+' button to add rows | Select row(s) and press Delete/Backspace to remove | Click 'Apply Changes' to save edits")
        
        # Use a form to batch updates and prevent double-entry issues
        with st.form(key=f"assumptions_form_{selected_ticker}"):
            # Create DataFrame with proper handling
            if not assumptions_df.empty:
                # Ensure all rows have Type column
                if 'Type' not in assumptions_df.columns:
                    assumptions_df['Type'] = 'N/A'
                
                # Use Streamlit's data editor with dynamic rows
                edited_df = st.data_editor(
                    assumptions_df,
                    hide_index=True,
                    use_container_width=True,
                    num_rows="dynamic",  # Allow adding/deleting rows
                    column_config={
                    "Category": st.column_config.SelectboxColumn(
                        "Category",
                        options=["Business Segment", "Financial", "Operating", "Other"],
                        required=True,
                        default="Business Segment",
                        width="medium"
                    ),
                    "Type": st.column_config.SelectboxColumn(
                        "Type",
                        options=["Revenue Growth", "Gross Margin", "SG&A % of Revenue", "N/A"],
                        required=True,
                        default="Revenue Growth",
                        help="Select metric type for business segments",
                        width="medium"
                    ),
                    "Item": st.column_config.TextColumn(
                        "Item",
                        required=True,
                        default="New Segment",
                        help="Enter business segment name or assumption item",
                        width="large"
                    ),
                    "Value": st.column_config.NumberColumn(
                        "Value",
                        min_value=0,
                        max_value=1000,
                        step=0.1,
                        format="%.2f",
                        default=10.0,
                        width="small"
                    ),
                    "Unit": st.column_config.SelectboxColumn(
                        "Unit",
                        options=["%", "x", "days", "years", "B VND"],
                        required=True,
                        default="%",
                        width="small"
                    )
                },
                column_order=["Category", "Type", "Item", "Value", "Unit"],
                key=editor_key
            )
            else:
                # Show empty data editor when no assumptions exist
                st.info("No assumptions defined. Click 'Load Defaults' below or use the table to add new assumptions.")
                empty_df = pd.DataFrame(columns=["Category", "Type", "Item", "Value", "Unit"])
                edited_df = st.data_editor(
                empty_df,
                hide_index=True,
                use_container_width=True,
                num_rows="dynamic",  # Allow adding rows even when empty
                column_config={
                    "Category": st.column_config.SelectboxColumn(
                        "Category",
                        options=["Business Segment", "Financial", "Operating", "Other"],
                        required=True,
                        default="Business Segment",
                        width="medium"
                    ),
                    "Type": st.column_config.SelectboxColumn(
                        "Type",
                        options=["Revenue Growth", "Gross Margin", "SG&A % of Revenue", "N/A"],
                        required=True,
                        default="Revenue Growth",
                        help="Select metric type for business segments",
                        width="medium"
                    ),
                    "Item": st.column_config.TextColumn(
                        "Item",
                        required=True,
                        default="New Segment",
                        help="Enter business segment name or assumption item",
                        width="large"
                    ),
                    "Value": st.column_config.NumberColumn(
                        "Value",
                        min_value=0,
                        max_value=1000,
                        step=0.1,
                        format="%.2f",
                        default=10.0,
                        width="small"
                    ),
                    "Unit": st.column_config.SelectboxColumn(
                        "Unit",
                        options=["%", "x", "days", "years", "B VND"],
                        required=True,
                        default="%",
                        width="small"
                    )
                },
                column_order=["Category", "Type", "Item", "Value", "Unit"],
                key=f"editor_{selected_ticker}_empty_v2"
            )
            
            # Add submit button inside the form
            submitted = st.form_submit_button("Apply Changes", type="primary", use_container_width=True)
            if submitted:
                # Update session state with the edited DataFrame
                st.session_state[assumptions_key] = edited_df
                st.success("✅ Changes applied successfully!")
                st.rerun()
        
        # Action buttons outside the form
        st.subheader("💾 Save & Manage")
        col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
        
        with col1:
            if st.button("💾 Save to MongoDB", type="primary", key=f"save_assumptions_{selected_ticker}"):
                # Get the current data from session state (which is now always up-to-date)
                current_df = st.session_state[assumptions_key]
                if isinstance(current_df, pd.DataFrame):
                    current_data = current_df.to_dict('records')
                else:
                    current_data = current_df
                
                # Prepare data for MongoDB
                save_data = {
                    'revenue_streams': [],  # This will be rebuilt from scratch based on current assumptions
                    'wacc': None,
                    'debt_financing_pct': None,
                    'tax_rate': None,
                    'custom_assumptions': []  # Store custom assumptions
                }
                
                # Clear existing revenue_streams to ensure removed segments are not retained
                segments_data = {}  # Track all segments and their metrics
                
                # Parse current assumptions
                for assumption in current_data:
                    item = assumption.get('Item', '')
                    value = assumption.get('Value', 0)
                    category = assumption.get('Category', '')
                    metric_type = assumption.get('Type', 'N/A')
                    unit = assumption.get('Unit', '%')
                    
                    # Convert percentage values to decimal for storage
                    if unit == '%':
                        stored_value = value / 100.0
                    else:
                        stored_value = value
                    
                    # Categorize and store assumptions
                    if category == 'Business Segment':
                        # Use Type column to determine metric type
                        segment_name = item  # Item is now just the segment name
                        
                        # Find or create stream entry
                        stream_entry = next((s for s in save_data['revenue_streams'] 
                                           if s['segment_name'] == segment_name), None)
                        if not stream_entry:
                            stream_entry = {'segment_name': segment_name}
                            save_data['revenue_streams'].append(stream_entry)
                        
                        # Store the metric based on Type column
                        if metric_type == 'Revenue Growth':
                            stream_entry['revenue_growth'] = stored_value
                        elif metric_type == 'Gross Margin':
                            stream_entry['gross_margin'] = stored_value
                        elif metric_type == 'SG&A % of Revenue':
                            stream_entry['sga_percentage'] = stored_value
                        else:
                            # Store as custom if type is not recognized
                            save_data['custom_assumptions'].append({
                                'category': category,
                                'type': metric_type,
                                'item': item,
                                'value': value,
                                'unit': unit
                            })
                    
                    elif item == 'WACC':
                        save_data['wacc'] = stored_value
                    elif item == 'Debt Financing %':
                        save_data['debt_financing_pct'] = stored_value
                    elif item == 'Tax Rate':
                        save_data['tax_rate'] = stored_value
                    else:
                        # Store as custom assumption
                        save_data['custom_assumptions'].append({
                            'category': category,
                            'type': metric_type,
                            'item': item,
                            'value': value,
                            'unit': unit
                        })
                
                # Save to MongoDB
                result = save_company_assumptions(selected_ticker, save_data)
                if result['success']:
                    st.success(f"✅ Saved {len(current_data)} assumptions to MongoDB")
                    # Update comprehensive_model in session state to reflect removed segments
                    if 'comprehensive_model' in st.session_state:
                        st.session_state.comprehensive_model['revenue_streams'] = save_data['revenue_streams']
                    # Force refresh of revenue forecast data
                    if 'selected_streams_data' in st.session_state:
                        # Filter selected streams to only include segments that still exist
                        existing_segments = {s['segment_name'] for s in save_data['revenue_streams']}
                        st.session_state.selected_streams_data = [
                            s for s in st.session_state.selected_streams_data 
                            if s.get('segment_name') in existing_segments
                        ]
                    # Clean up base_year_revenues to remove deleted segments
                    if 'base_year_revenues' in st.session_state:
                        existing_segments = {s['segment_name'] for s in save_data['revenue_streams']}
                        st.session_state.base_year_revenues = {
                            k: v for k, v in st.session_state.base_year_revenues.items()
                            if k in existing_segments
                        }
                    # Also clean ticker-specific base year revenues
                    revenue_key = f'base_year_revenues_{selected_ticker}'
                    if revenue_key in st.session_state:
                        existing_segments = {s['segment_name'] for s in save_data['revenue_streams']}
                        st.session_state[revenue_key] = {
                            k: v for k, v in st.session_state[revenue_key].items()
                            if k in existing_segments
                        }
                else:
                    st.error(f"❌ {result['message']}")
        
        with col2:
            if st.button("🔄 Reload from DB", key=f"reload_assumptions_{selected_ticker}"):
                # Force reload from MongoDB
                company_assumptions = get_company_assumptions(selected_ticker)
                
                # Rebuild assumptions data
                reloaded_data = []
                
                # Load standard financial assumptions
                wacc = company_assumptions.get('wacc', 0.12) * 100
                debt_financing = company_assumptions.get('debt_financing_pct', 0.30) * 100
                tax_rate = company_assumptions.get('tax_rate', 0.20) * 100
                
                reloaded_data.extend([
                    {"Category": "Financial", "Type": "N/A", "Item": "WACC", "Value": wacc, "Unit": "%"},
                    {"Category": "Financial", "Type": "N/A", "Item": "Debt Financing %", "Value": debt_financing, "Unit": "%"},
                    {"Category": "Financial", "Type": "N/A", "Item": "Tax Rate", "Value": tax_rate, "Unit": "%"}
                ])
                
                # Load business segments from revenue_streams
                revenue_streams = company_assumptions.get('revenue_streams', [])
                for stream in revenue_streams:
                    segment_name = stream.get('segment_name', '')
                    if segment_name:
                        if 'revenue_growth' in stream:
                            reloaded_data.append({
                                "Category": "Business Segment",
                                "Type": "Revenue Growth",
                                "Item": segment_name,
                                "Value": stream['revenue_growth'] * 100,
                                "Unit": "%"
                            })
                        if 'gross_margin' in stream:
                            reloaded_data.append({
                                "Category": "Business Segment",
                                "Type": "Gross Margin",
                                "Item": segment_name,
                                "Value": stream['gross_margin'] * 100,
                                "Unit": "%"
                            })
                        if 'sga_percentage' in stream:
                            reloaded_data.append({
                                "Category": "Business Segment",
                                "Type": "SG&A % of Revenue",
                                "Item": segment_name,
                                "Value": stream['sga_percentage'] * 100,
                                "Unit": "%"
                            })
                
                # Load custom assumptions
                custom_assumptions = company_assumptions.get('custom_assumptions', [])
                for custom in custom_assumptions:
                    reloaded_data.append({
                        "Category": custom.get('category', 'Other'),
                        "Type": custom.get('type', 'N/A'),
                        "Item": custom.get('item', 'Custom'),
                        "Value": custom.get('value', 0),
                        "Unit": custom.get('unit', '%')
                    })
                
                # Update session state with DataFrame
                st.session_state[assumptions_key] = pd.DataFrame(reloaded_data)
                # Also update comprehensive_model to ensure consistency
                if 'comprehensive_model' in st.session_state:
                    st.session_state.comprehensive_model['revenue_streams'] = revenue_streams
                # Force refresh of selected streams data
                if 'selected_streams_data' in st.session_state:
                    existing_segments = {s['segment_name'] for s in revenue_streams}
                    st.session_state.selected_streams_data = [
                        s for s in st.session_state.selected_streams_data 
                        if s.get('segment_name') in existing_segments
                    ]
                # Clean up base_year_revenues
                if 'base_year_revenues' in st.session_state:
                    existing_segments = {s['segment_name'] for s in revenue_streams}
                    st.session_state.base_year_revenues = {
                        k: v for k, v in st.session_state.base_year_revenues.items()
                        if k in existing_segments
                    }
                # Also clean ticker-specific base year revenues
                revenue_key = f'base_year_revenues_{selected_ticker}'
                if revenue_key in st.session_state:
                    existing_segments = {s['segment_name'] for s in revenue_streams}
                    st.session_state[revenue_key] = {
                        k: v for k, v in st.session_state[revenue_key].items()
                        if k in existing_segments
                    }
                st.success(f"✅ Reloaded {len(reloaded_data)} assumptions from MongoDB")
                st.rerun()
        
        with col3:
            if st.button("🗑️ Clear All", key=f"clear_assumptions_{selected_ticker}"):
                if st.session_state.get('confirm_clear', False):
                    # Clear all assumptions
                    st.session_state[assumptions_key] = pd.DataFrame(columns=["Category", "Type", "Item", "Value", "Unit"])
                    # Also clear revenue streams in comprehensive_model
                    if 'comprehensive_model' in st.session_state:
                        st.session_state.comprehensive_model['revenue_streams'] = []
                    # Clear selected streams data
                    if 'selected_streams_data' in st.session_state:
                        st.session_state.selected_streams_data = []
                    # Clear base year revenues
                    if 'base_year_revenues' in st.session_state:
                        st.session_state.base_year_revenues = {}
                    # Clear ticker-specific base year revenues
                    revenue_key = f'base_year_revenues_{selected_ticker}'
                    if revenue_key in st.session_state:
                        st.session_state[revenue_key] = {}
                    st.session_state.confirm_clear = False
                    st.success("✅ All assumptions cleared")
                    st.rerun()
                else:
                    st.session_state.confirm_clear = True
                    st.warning("⚠️ Click again to confirm clearing all assumptions")
        
        with col4:
            if st.button("📋 Load Defaults", key=f"load_defaults_{selected_ticker}"):
                # Load default assumptions with business segments using new Type column
                default_assumptions = [
                    {"Category": "Financial", "Type": "N/A", "Item": "WACC", "Value": 12.0, "Unit": "%"},
                    {"Category": "Financial", "Type": "N/A", "Item": "Debt Financing %", "Value": 30.0, "Unit": "%"},
                    {"Category": "Financial", "Type": "N/A", "Item": "Tax Rate", "Value": 20.0, "Unit": "%"},
                    {"Category": "Business Segment", "Type": "Revenue Growth", "Item": "Brokerage", "Value": 15.0, "Unit": "%"},
                    {"Category": "Business Segment", "Type": "Gross Margin", "Item": "Brokerage", "Value": 60.0, "Unit": "%"},
                    {"Category": "Business Segment", "Type": "SG&A % of Revenue", "Item": "Brokerage", "Value": 25.0, "Unit": "%"},
                    {"Category": "Business Segment", "Type": "Revenue Growth", "Item": "Property Management", "Value": 20.0, "Unit": "%"},
                    {"Category": "Business Segment", "Type": "Gross Margin", "Item": "Property Management", "Value": 45.0, "Unit": "%"},
                    {"Category": "Business Segment", "Type": "SG&A % of Revenue", "Item": "Property Management", "Value": 30.0, "Unit": "%"}
                ]
                st.session_state[assumptions_key] = pd.DataFrame(default_assumptions)
                st.success("✅ Default assumptions loaded")
                st.rerun()
        
        # Update session state with current assumptions for calculations if we have data
        current_assumptions = st.session_state[assumptions_key]
        if isinstance(current_assumptions, pd.DataFrame) and not current_assumptions.empty:
            self.update_assumptions_from_grid(current_assumptions)
        elif isinstance(current_assumptions, list) and len(current_assumptions) > 0:
            self.update_assumptions_from_grid(pd.DataFrame(current_assumptions))
    
    def generate_simplified_assumptions_table(self):
        """Generate simplified assumptions table"""
        # Return empty - not used in standalone mode
        return []
    
    def generate_dynamic_assumptions_table(self):
        """Generate assumptions table"""
        # Return empty - not used in standalone mode
        return []
    
    def generate_default_assumptions_table(self):
        """Generate default assumptions table when no AI discovery available"""
        return [
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
        ]
    
    def update_assumptions_from_grid(self, df):
        """Update assumptions from AgGrid changes"""
        for _, row in df.iterrows():
            category = row['Category']
            item = row['Item']
            value = row['Value']
            
            # Handle dynamic segment assumptions
            if 'dynamic_assumptions' in st.session_state:
                # Check if this is a segment-specific assumption
                for segment_name in st.session_state.dynamic_assumptions.keys():
                    if f"{segment_name} Growth" == item:
                        st.session_state.dynamic_assumptions[segment_name]['revenue_growth'] = value
                    elif f"{segment_name} Margin" == item:
                        st.session_state.dynamic_assumptions[segment_name]['gross_margin'] = value
            
            # Map standard assumptions
            if category == "Revenue Growth":
                if item == "Presales Growth":
                    st.session_state.assumptions['revenue_growth']['presales'] = value
                elif item == "Handover Growth":
                    st.session_state.assumptions['revenue_growth']['handover'] = value
                elif item == "Recurring Revenue Growth":
                    st.session_state.assumptions['revenue_growth']['recurring'] = value
            elif category == "Operating Costs":
                if item == "SG&A % of Revenue":
                    st.session_state.assumptions['costs']['sga_pct'] = value
                elif item == "Interest Rate":
                    st.session_state.assumptions['costs']['interest_rate'] = value
                elif item == "Tax Rate":
                    st.session_state.assumptions['costs']['tax_rate'] = value
            elif category == "Working Capital":
                if item == "Receivables Days":
                    st.session_state.assumptions['balance_sheet']['receivables_days'] = value
                elif item == "Inventory Days":
                    st.session_state.assumptions['balance_sheet']['inventory_days'] = value
                elif item == "Payables Days":
                    st.session_state.assumptions['balance_sheet']['payables_days'] = value
            elif category == "Valuation":
                if item == "WACC":
                    st.session_state.assumptions['valuation']['wacc'] = value
                elif item == "Terminal Growth":
                    st.session_state.assumptions['valuation']['terminal_growth'] = value
    
    @st.fragment
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
        
        # Add "Create New Project" option at the beginning
        project_options = ["All Projects (Overview)", "➕ Create New Project"] + project_names
        
        # Use session state to preserve the selected project
        if 'selected_project_for_edit' not in st.session_state:
            st.session_state.selected_project_for_edit = "All Projects (Overview)"
        
        # Create a form to prevent auto-rerun on selection
        with st.container():
            selected_project_name = st.selectbox(
                "Choose a project to view/edit details:",
                options=project_options,
                key="selected_project_for_edit",
                index=project_options.index(st.session_state.selected_project_for_edit) if st.session_state.selected_project_for_edit in project_options else 0,
                help="Select a project to view or edit its details"
            )
        
        if selected_project_name == "➕ Create New Project":
            # Show new project creation form
            self.render_new_project_form()
            return
        elif selected_project_name != "All Projects (Overview)":
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
    
    def render_new_project_form(self):
        """Render form for creating a brand new project"""
        st.subheader("➕ Create New Project")
        st.info("Enter details for your new project. All fields start empty for a fresh start.")
        
        # Initialize empty project data if not exists
        if 'new_project_data' not in st.session_state:
            st.session_state.new_project_data = {}
        
        # Basic Information Section
        st.markdown("### 📋 Basic Information")
        col1, col2 = st.columns(2)
        
        with col1:
            project_name = st.text_input(
                "Project Name *",
                value="",
                placeholder="Enter project name",
                key="new_project_name"
            )
            
            company_ticker = st.text_input(
                "Company Ticker *",
                value=st.session_state.selected_company if st.session_state.selected_company else "",
                placeholder="e.g., VHM, NLG, KDH",
                key="new_project_ticker"
            )
            
            location = st.text_input(
                "Location",
                value="",
                placeholder="e.g., Ho Chi Minh City",
                key="new_project_location"
            )
            
            project_ownership = st.number_input(
                "Project Ownership (%)",
                min_value=0.0,
                max_value=100.0,
                value=100.0,
                step=0.1,
                key="new_project_ownership"
            )
        
        with col2:
            total_units = st.number_input(
                "Total Units",
                min_value=0,
                value=0,
                step=1,
                key="new_project_units"
            )
            
            average_unit_size = st.number_input(
                "Average Unit Size (sqm)",
                min_value=0.0,
                value=0.0,
                step=0.1,
                key="new_project_unit_size"
            )
            
            land_area = st.number_input(
                "Land Area (sqm)",
                min_value=0.0,
                value=0.0,
                step=0.1,
                key="new_project_land_area"
            )
            
            gross_floor_area = st.number_input(
                "Gross Floor Area (sqm)",
                min_value=0.0,
                value=0.0,
                step=0.1,
                key="new_project_gfa"
            )
        
        st.markdown("---")
        
        # Financial Parameters Section
        st.markdown("### 💰 Financial Parameters")
        col3, col4 = st.columns(2)
        
        with col3:
            average_selling_price = st.number_input(
                "Average Selling Price (VND/sqm)",
                min_value=0.0,
                value=0.0,
                step=1000000.0,
                format="%.0f",
                key="new_project_asp"
            )
            
            construction_cost_per_sqm = st.number_input(
                "Construction Cost (VND/sqm)",
                min_value=0.0,
                value=0.0,
                step=100000.0,
                format="%.0f",
                key="new_project_construction_cost"
            )
            
            land_cost_per_sqm = st.number_input(
                "Land Cost (VND/sqm)",
                min_value=0.0,
                value=0.0,
                step=100000.0,
                format="%.0f",
                key="new_project_land_cost"
            )
        
        with col4:
            sga_percentage = st.number_input(
                "SG&A (% of Revenue)",
                min_value=0.0,
                max_value=100.0,
                value=8.0,
                step=0.1,
                key="new_project_sga"
            )
            
            wacc_rate = st.number_input(
                "WACC (%)",
                min_value=0.0,
                max_value=30.0,
                value=12.0,
                step=0.1,
                key="new_project_wacc"
            )
            
            cost_of_debt = st.number_input(
                "Cost of Debt (%)",
                min_value=0.0,
                max_value=20.0,
                value=8.0,
                step=0.1,
                key="new_project_cost_of_debt"
            )
        
        st.markdown("---")
        
        # Timeline Section
        st.markdown("### 📅 Project Timeline")
        current_year = datetime.now().year
        col5, col6 = st.columns(2)
        
        with col5:
            construction_start_year = st.number_input(
                "Construction Start Year",
                min_value=2020,
                max_value=2040,
                value=current_year,
                step=1,
                key="new_project_construction_start"
            )
            
            construction_years = st.number_input(
                "Construction Duration (years)",
                min_value=1,
                max_value=10,
                value=3,
                step=1,
                key="new_project_construction_years"
            )
            
            sale_start_year = st.number_input(
                "Sales Start Year",
                min_value=2020,
                max_value=2040,
                value=current_year,
                step=1,
                key="new_project_sale_start"
            )
        
        with col6:
            sales_years = st.number_input(
                "Sales Duration (years)",
                min_value=1,
                max_value=10,
                value=3,
                step=1,
                key="new_project_sales_years"
            )
            
            revenue_booking_start_year = st.number_input(
                "Revenue Booking Start Year",
                min_value=2020,
                max_value=2040,
                value=current_year + 1,
                step=1,
                key="new_project_revenue_start"
            )
            
            project_completion_year = st.number_input(
                "Project Completion Year",
                min_value=2020,
                max_value=2040,
                value=current_year + 3,
                step=1,
                key="new_project_completion"
            )
        
        st.markdown("---")
        
        # Action Buttons
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            if st.button("💾 Save New Project", type="primary", use_container_width=True):
                # Validate required fields
                if not project_name:
                    st.error("Project Name is required!")
                    return
                if not company_ticker:
                    st.error("Company Ticker is required!")
                    return
                
                # Prepare project data
                new_project_data = {
                    'project_name': project_name,
                    'company_ticker': company_ticker.upper(),
                    'location': location,
                    'project_ownership': project_ownership / 100,  # Store as decimal
                    'total_units': total_units,
                    'average_unit_size': average_unit_size,
                    'net_sellable_area': total_units * average_unit_size if total_units and average_unit_size else 0,
                    'land_area': land_area,
                    'gross_floor_area': gross_floor_area,
                    'average_selling_price': average_selling_price,
                    'construction_cost_per_sqm': construction_cost_per_sqm,
                    'land_cost_per_sqm': land_cost_per_sqm,
                    'sga_percentage': sga_percentage / 100,  # Store as decimal
                    'wacc_rate': wacc_rate / 100,  # Store as decimal
                    'cost_of_debt': cost_of_debt / 100,  # Store as decimal
                    'construction_start_year': construction_start_year,
                    'construction_years': construction_years,
                    'sale_start_year': sale_start_year,
                    'sales_years': sales_years,
                    'revenue_booking_start_year': revenue_booking_start_year,
                    'project_completion_year': project_completion_year,
                    'land_payment_year': construction_start_year,  # Default to construction start
                    'revenue_distribution': {},  # Empty for new project
                    'presales_distribution': {},  # Empty for new project
                    'pnl_schedule': {},  # Empty for new project
                }
                
                # Calculate total values
                nsa = new_project_data['net_sellable_area']
                new_project_data['total_revenue'] = (nsa * average_selling_price) / 1e9 if nsa and average_selling_price else 0
                new_project_data['total_construction_cost'] = (gross_floor_area * construction_cost_per_sqm) / 1e9 if gross_floor_area and construction_cost_per_sqm else 0
                new_project_data['total_land_cost'] = (land_area * land_cost_per_sqm) / 1e9 if land_area and land_cost_per_sqm else 0
                new_project_data['total_sga_cost'] = new_project_data['total_revenue'] * (sga_percentage / 100) if new_project_data['total_revenue'] else 0
                
                # Save to MongoDB
                from utils.mongodb_utils import save_project_to_mongodb
                result = save_project_to_mongodb(new_project_data, project_name)
                
                if result['success']:
                    st.success(f"✅ {result['message']}")
                    
                    # Refresh project data
                    from utils.mongodb_utils import load_projects_data
                    df_projects = load_projects_data()
                    
                    # Filter for selected company if applicable
                    if st.session_state.selected_company:
                        df_projects = df_projects[df_projects['company_ticker'] == st.session_state.selected_company]
                    
                    st.session_state.project_data = df_projects
                    
                    # Clear the form by resetting session state
                    if 'new_project_data' in st.session_state:
                        del st.session_state.new_project_data
                    
                    # Switch to the newly created project
                    st.session_state.selected_project_for_edit = project_name
                    st.rerun()
                else:
                    st.error(f"❌ {result['message']}")
        
        with col_cancel:
            if st.button("❌ Cancel", use_container_width=True):
                # Clear form and go back to overview
                if 'new_project_data' in st.session_state:
                    del st.session_state.new_project_data
                st.session_state.selected_project_for_edit = "All Projects (Overview)"
                st.rerun()
    
    def get_ai_project_suggestions(self, project_name, project_data):
        """Use Perplexity AI to research and suggest project parameters"""
        import os
        from utils.perplexity_utils import get_project_basic_info_perplexity, parse_perplexity_response
        
        # Get API key
        perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
        
        if not perplexity_api_key:
            st.error("❌ PERPLEXITY_API_KEY not configured. Please add it to your .env file.")
            return
        
        # Extract company information for comprehensive search
        company_ticker = project_data.get('company_ticker', '')
        company_name = project_data.get('company_name', '')
        location = project_data.get('location', '')
        
        # Create detailed search query with all available information
        search_parts = [project_name]
        if company_ticker:
            search_parts.append(f"by {company_ticker}")
        if company_name:
            search_parts.append(company_name)
        if location:
            search_parts.append(f"in {location}")
        search_parts.append("Vietnam real estate project")
        
        search_query = " ".join(search_parts)
        
        with st.spinner(f"🔍 AI researching {project_name} - gathering market data and comparable projects..."):
            try:
                # Call Perplexity API with the full project name
                response = get_project_basic_info_perplexity(project_name, perplexity_api_key)
                
                if isinstance(response, str):
                    # Parse the response
                    parsed_info = parse_perplexity_response(response)
                    
                    if parsed_info and not parsed_info.get("error"):
                        st.success("✅ AI research completed successfully!")
                        
                        # Store AI suggestions in session state for inline display
                        ai_suggestions_key = f"ai_suggestions_{project_name}"
                        st.session_state[ai_suggestions_key] = parsed_info
                        
                        # Also store raw response for reference
                        st.session_state[f"ai_raw_response_{project_name}"] = response
                        
                        # Display summary in full width expander
                        with st.expander("AI Research Summary", expanded=True):
                            # Show basic info if available in full width
                            if parsed_info.get("basic_info"):
                                st.info(f"**Project Description:** {parsed_info['basic_info']}")
                            
                            # Show confidence level if available
                            if parsed_info.get("confidence"):
                                st.caption(f"**Confidence Level:** {parsed_info['confidence']}")
                            
                            # Show analysis method if available
                            if parsed_info.get("analysis_method"):
                                st.caption(f"**Analysis Method:** {parsed_info['analysis_method']}")
                            
                            # Show sources if available
                            if parsed_info.get("sources"):
                                st.caption(f"**Sources:** {parsed_info['sources']}")
                            
                            st.info("💡 AI suggestions are displayed below each input field. Review and modify values as needed before saving.")
                            
                            # Create a table for suggested values comparison
                            suggestions = []
                            
                            # Map parsed fields to project parameters
                            if parsed_info.get("location"):
                                suggestions.append({
                                    "Parameter": "Location",
                                    "AI Suggestion": str(parsed_info["location"]),
                                    "Current Value": str(project_data.get('location', 'N/A'))
                                })
                            
                            if parsed_info.get("total_units"):
                                try:
                                    ai_units = float(parsed_info['total_units'])
                                    suggestions.append({
                                        "Parameter": "Total Units",
                                        "AI Suggestion": f"{ai_units:,.0f}",
                                        "Current Value": f"{float(project_data.get('total_units', 0)):,.0f}"
                                    })
                                except (ValueError, TypeError):
                                    suggestions.append({
                                        "Parameter": "Total Units",
                                        "AI Suggestion": str(parsed_info['total_units']),
                                        "Current Value": str(project_data.get('total_units', 0))
                                    })
                            
                            if parsed_info.get("total_area_sqm"):
                                try:
                                    ai_area = float(parsed_info['total_area_sqm'])
                                    suggestions.append({
                                        "Parameter": "Gross Floor Area (sqm)",
                                        "AI Suggestion": f"{ai_area:,.0f}",
                                        "Current Value": f"{float(project_data.get('gross_floor_area', 0)):,.0f}"
                                    })
                                except (ValueError, TypeError):
                                    suggestions.append({
                                        "Parameter": "Gross Floor Area (sqm)",
                                        "AI Suggestion": str(parsed_info['total_area_sqm']),
                                        "Current Value": str(project_data.get('gross_floor_area', 0))
                                    })
                            
                            if parsed_info.get("land_area_sqm"):
                                try:
                                    ai_land = float(parsed_info['land_area_sqm'])
                                    suggestions.append({
                                        "Parameter": "Land Area (sqm)",
                                        "AI Suggestion": f"{ai_land:,.0f}",
                                        "Current Value": f"{float(project_data.get('land_area', 0)):,.0f}"
                                    })
                                except (ValueError, TypeError):
                                    suggestions.append({
                                        "Parameter": "Land Area (sqm)",
                                        "AI Suggestion": str(parsed_info['land_area_sqm']),
                                        "Current Value": str(project_data.get('land_area', 0))
                                    })
                            
                            if parsed_info.get("avg_selling_price_per_sqm"):
                                try:
                                    ai_price = float(parsed_info['avg_selling_price_per_sqm'])
                                    suggestions.append({
                                        "Parameter": "Avg Selling Price (M VND/sqm)",
                                        "AI Suggestion": f"{ai_price:,.0f}",
                                        "Current Value": f"{float(project_data.get('average_selling_price', 0)):,.0f}"
                                    })
                                except (ValueError, TypeError):
                                    suggestions.append({
                                        "Parameter": "Avg Selling Price (M VND/sqm)",
                                        "AI Suggestion": str(parsed_info['avg_selling_price_per_sqm']),
                                        "Current Value": str(project_data.get('average_selling_price', 0))
                                    })
                            
                            if parsed_info.get("construction_cost_per_sqm"):
                                try:
                                    ai_cost = float(parsed_info['construction_cost_per_sqm'])
                                    suggestions.append({
                                        "Parameter": "Construction Cost (M VND/sqm)",
                                        "AI Suggestion": f"{ai_cost:,.0f}",
                                        "Current Value": f"{float(project_data.get('construction_cost_per_sqm', 0)):,.0f}"
                                    })
                                except (ValueError, TypeError):
                                    suggestions.append({
                                        "Parameter": "Construction Cost (M VND/sqm)",
                                        "AI Suggestion": str(parsed_info['construction_cost_per_sqm']),
                                        "Current Value": str(project_data.get('construction_cost_per_sqm', 0))
                                    })
                            
                            if parsed_info.get("project_duration"):
                                suggestions.append({
                                    "Parameter": "Construction Years",
                                    "AI Suggestion": parsed_info["project_duration"],
                                    "Current Value": project_data.get('construction_years', 'N/A')
                                })
                            
                            if suggestions:
                                df_suggestions = pd.DataFrame(suggestions)
                                st.dataframe(df_suggestions, use_container_width=True)
                            else:
                                st.warning("No specific parameter suggestions found. The AI may need more specific information about this project.")
                    else:
                        st.error("❌ Could not parse AI response. Please try again.")
                else:
                    st.error(f"❌ AI research failed: {response}")
                    
            except Exception as e:
                st.error(f"❌ Error during AI research: {str(e)}")
    
    def render_individual_project_editor(self, project_name, df_projects):
        """Render editor for individual project with revenue/presales distribution"""
        # Get the selected project data
        project_data = df_projects[df_projects['project_name'] == project_name].iloc[0].to_dict()
        
        # Add default values for new fields if they don't exist
        defaults = {
            'revenue_distribution': {},
            'presales_distribution': {},
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
        
        # Add AI Suggestion button
        col_ai, col_space = st.columns([2, 3])
        with col_ai:
            if st.button("AI Suggest Parameters", key=f"ai_suggest_{project_name}", type="primary"):
                self.get_ai_project_suggestions(project_name, project_data)
        
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
        
        # Get AI suggestions if available
        project_name = project_data.get('project_name', '')
        ai_suggestions_key = f"ai_suggestions_{project_name}"
        ai_suggestions = st.session_state.get(ai_suggestions_key, {})
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Location
            location = st.text_input(
                "Location",
                value=str(project_data.get('location', '') or ''),
                key="edit_location"
            )
            # Show AI suggestion inline if available
            if ai_suggestions.get("location"):
                st.caption(f"AI Suggestion: {ai_suggestions['location']}")
            st.session_state.edited_project['location'] = location
            
            # Total Units
            total_units = st.number_input(
                "Total Units",
                value=int(project_data.get('total_units', 0) or 0),
                min_value=0,
                key="edit_total_units"
            )
            # Show AI suggestion inline if available
            if ai_suggestions.get("total_units"):
                try:
                    ai_units = float(ai_suggestions['total_units'])
                    st.caption(f"AI Suggestion: {ai_units:,.0f} units")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['total_units']} units")
            st.session_state.edited_project['total_units'] = total_units
            
            # Average Unit Size
            avg_unit_size = st.number_input(
                "Average Unit Size (m²)",
                value=float(project_data.get('average_unit_size', 0) or 0),
                min_value=0.0,
                key="edit_avg_unit_size"
            )
            # Show AI suggestion inline if available
            if ai_suggestions.get("average_unit_size"):
                try:
                    ai_size = float(ai_suggestions['average_unit_size'])
                    st.caption(f"AI Suggestion: {ai_size:,.0f} m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['average_unit_size']} m²")
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
            # Show AI suggestion inline if available
            if ai_suggestions.get("avg_selling_price_per_sqm"):
                try:
                    ai_price = float(ai_suggestions['avg_selling_price_per_sqm'])
                    st.caption(f"AI Suggestion: {ai_price:,.0f} VND/m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['avg_selling_price_per_sqm']} VND/m²")
            st.session_state.edited_project['average_selling_price'] = asp
            
            # Land Area
            land_area = st.number_input(
                "Land Area (m²)",
                value=float(project_data.get('land_area', 0) or 0),
                min_value=0.0,
                key="edit_land_area"
            )
            # Show AI suggestion inline if available
            if ai_suggestions.get("land_area_sqm"):
                try:
                    ai_land = float(ai_suggestions['land_area_sqm'])
                    st.caption(f"AI Suggestion: {ai_land:,.0f} m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['land_area_sqm']} m²")
            st.session_state.edited_project['land_area'] = land_area
            
            # Construction Cost per sqm
            const_cost = st.number_input(
                "Construction Cost (VND/m²)",
                value=float(project_data.get('construction_cost_per_sqm', 0) or 0),
                min_value=0.0,
                format="%.0f",
                key="edit_const_cost"
            )
            # Show AI suggestion inline if available
            if ai_suggestions.get("construction_cost_per_sqm"):
                try:
                    ai_const = float(ai_suggestions['construction_cost_per_sqm'])
                    st.caption(f"AI Suggestion: {ai_const:,.0f} VND/m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['construction_cost_per_sqm']} VND/m²")
            st.session_state.edited_project['construction_cost_per_sqm'] = const_cost
            
            # Land Cost per sqm
            land_cost = st.number_input(
                "Land Cost (VND/m²)",
                value=float(project_data.get('land_cost_per_sqm', 0) or 0),
                min_value=0.0,
                format="%.0f",
                key="edit_land_cost"
            )
            # Show AI suggestion inline if available
            if ai_suggestions.get("land_cost_per_sqm"):
                try:
                    ai_land_cost = float(ai_suggestions['land_cost_per_sqm'])
                    st.caption(f"AI Suggestion: {ai_land_cost:,.0f} VND/m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['land_cost_per_sqm']} VND/m²")
            st.session_state.edited_project['land_cost_per_sqm'] = land_cost
            
            # GFA
            gfa = st.number_input(
                "Gross Floor Area (m²)",
                value=float(project_data.get('gross_floor_area', 0) or 0),
                min_value=0.0,
                key="edit_gfa"
            )
            # Show AI suggestion inline if available
            if ai_suggestions.get("total_area_sqm"):
                try:
                    ai_gfa = float(ai_suggestions['total_area_sqm'])
                    st.caption(f"AI Suggestion: {ai_gfa:,.0f} m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['total_area_sqm']} m²")
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
                
                # Store the P&L schedule in session state for saving
                st.session_state.last_calculated_pnl = df_pnl
                
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
                    
                    # Use the P&L schedule from RNAV calculation if available
                    if 'last_calculated_pnl' in st.session_state:
                        df_pnl = st.session_state.last_calculated_pnl
                        
                        # Extract P&L schedule from the DataFrame
                        pnl_schedule = {}
                        
                        # Process each year in the P&L schedule
                        for _, row in df_pnl.iterrows():
                            if row['Type'] != 'Summary':  # Skip summary row
                                year_str = str(int(row['Year']))
                                
                                # Store complete P&L data with original signs (negative for costs)
                                pnl_schedule[year_str] = {
                                    'revenue': row['Revenue'],
                                    'construction_cost': row['Construction Payment'],  # Keep negative
                                    'land_cost': row['Land Payment'],  # Keep negative
                                    'sga': row['SG&A'],  # Keep negative
                                    'ebitda': row['EBITDA'],
                                    'interest_expense': row['Interest Expense'],  # Keep negative
                                    'pbt': row['PBT'],
                                    'tax': row['Tax Expense (20%)'],
                                    'pat': row['PAT']
                                }
                    else:
                        # Fallback: Calculate P&L if not available from RNAV
                        current_year = datetime.now().year
                        project_start = min(
                            edited.get('construction_start_year', current_year),
                            edited.get('sale_start_year', current_year),
                            edited.get('land_payment_year', current_year),
                            current_year
                        )
                        project_end = edited.get('project_completion_year', current_year + 3)
                        
                        # Simple proportional distribution based on revenue distribution
                        revenue_dist = edited.get('revenue_distribution', {})
                        if not isinstance(revenue_dist, dict):
                            revenue_dist = {}
                        
                        pnl_schedule = {}
                        
                        for year in range(int(project_start), int(project_end) + 1):
                            year_str = str(year)
                            year_pct = revenue_dist.get(year_str, 0) / 100.0
                            
                            revenue = total_revenue * year_pct / 1e9
                            construction = -total_const_cost * year_pct / 1e9  # Negative
                            land = -total_land_cost * year_pct / 1e9  # Negative
                            sga = -total_sga * year_pct / 1e9  # Negative
                            
                            pnl_schedule[year_str] = {
                                'revenue': revenue,
                                'construction_cost': construction,  # Negative value
                                'land_cost': land,  # Negative value
                                'sga': sga,  # Negative value
                                'ebitda': revenue + construction + land + sga,
                                'interest_expense': 0,  # No interest if not calculated
                                'pbt': revenue + construction + land + sga,
                                'tax': max(0, (revenue + construction + land + sga) * 0.2),
                                'pat': (revenue + construction + land + sga) * 0.8
                            }
                    
                    # Only add P&L schedule to edited data (remove redundant individual schedules)
                    edited['pnl_schedule'] = pnl_schedule
                    # Clear individual schedules to avoid redundancy
                    edited.pop('revenue_schedule', None)
                    edited.pop('construction_schedule', None)
                    edited.pop('land_schedule', None)
                    edited.pop('sga_schedule', None)
                    edited.pop('interest_schedule', None)
                    
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
        """Render comprehensive revenue forecast including projects and other revenue streams"""
        st.header("Revenue & COGS Forecast")
        
        # Get selected ticker
        selected_ticker = st.session_state.get('selected_company', None)
        if not selected_ticker:
            st.info("Please select a company from the sidebar")
            return
        
        # Import MongoDB utilities
        from utils.mongodb_utils import get_company_assumptions
        
        # Load assumptions from MongoDB
        company_assumptions = get_company_assumptions(selected_ticker)
        custom_assumptions = company_assumptions.get('custom_assumptions', [])
        
        # Initialize session state for base year revenues (ticker-specific)
        revenue_key = f'base_year_revenues_{selected_ticker}'
        if revenue_key not in st.session_state:
            st.session_state[revenue_key] = {}
        
        # For backward compatibility, sync with general base_year_revenues
        st.session_state.base_year_revenues = st.session_state[revenue_key]
        
        # Section 1: Other Revenue Streams Setup
        st.subheader("Business Segments Revenue")
        # Get base_year from session state or from the analysis above
        display_base_year = st.session_state.get('base_year', base_year if 'base_year' in locals() else 2024)
        st.info(f"Enter base year ({display_base_year} - latest historical) revenue for business segments defined in Assumptions")
        
        # Extract business segments from revenue_streams
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
        
        # Create input fields for base year revenues
        if business_segments:
            cols = st.columns(min(len(business_segments), 3))
            for idx, segment in enumerate(business_segments):
                with cols[idx % 3]:
                    metrics = segment_metrics[segment]
                    st.markdown(f"**{segment}**")
                    st.caption(f"Growth: {metrics['revenue_growth']*100:.1f}% | Margin: {metrics['gross_margin']*100:.1f}% | SG&A: {metrics['sga_percentage']*100:.1f}%")
                    # Use ticker-specific key for base revenue input
                    input_key = f"base_revenue_{selected_ticker}_{segment}"
                    base_revenue = st.number_input(
                        f"{display_base_year} Revenue (B VND)",
                        min_value=0.0,
                        value=st.session_state.base_year_revenues.get(segment, 100.0),
                        step=10.0,
                        key=input_key
                    )
                    st.session_state.base_year_revenues[segment] = base_revenue
                    # Also update ticker-specific storage
                    revenue_key = f'base_year_revenues_{selected_ticker}'
                    st.session_state[revenue_key][segment] = base_revenue
        else:
            st.info("No business segments defined. Add business segment assumptions in the Assumptions tab.")
        
        st.markdown("---")
            
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
                
                # Interest expense
                if 'Interest_Expense' in historical_data.columns:
                    try:
                        raw_value = historical_data.loc[hist_date_idx, 'Interest_Expense']
                        hist_values['Interest expense'] = abs(raw_value) / 1e9 if not pd.isna(raw_value) else 0
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
                    
                    # Get P&L schedule from MongoDB - contains all financial data
                    pnl_schedule = project.get('pnl_schedule', {})
                    
                    # Ensure schedule is a dictionary
                    if not isinstance(pnl_schedule, dict):
                        pnl_schedule = {}
                    
                    # Add to yearly totals
                    year_str = str(year)
                    
                    if year_str in pnl_schedule:
                        year_pnl = pnl_schedule[year_str]
                        
                        # Get revenue
                        revenue_amount = year_pnl.get('revenue', 0)
                        project_revenue_by_year[year] += revenue_amount
                        project_revenue_breakdown[project_name][year] = revenue_amount
                        
                        # Get COGS (construction + land) - these should be negative values
                        construction_cost = year_pnl.get('construction_cost', 0)
                        land_cost = year_pnl.get('land_cost', 0)
                        project_cogs = construction_cost + land_cost  # Both should be negative
                        
                        project_cogs_breakdown[project_name][year] = project_cogs
                        project_cogs_by_year[year] += project_cogs
                        project_land_breakdown[project_name][year] = land_cost
                        
                        # Get SG&A - should be negative
                        sga_amount = year_pnl.get('sga', 0)
                        project_sga_breakdown[project_name][year] = sga_amount
                        
                        # Get Interest expense - should be negative/positive based on calculation
                        interest_amount = year_pnl.get('interest_expense', 0)
                        project_interest_breakdown[project_name][year] = interest_amount
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
                
                for segment_name, base_revenue in st.session_state.base_year_revenues.items():
                    # Get metrics from segment_metrics if available
                    if segment_name in segment_metrics:
                        growth_rate = segment_metrics[segment_name]['revenue_growth']
                        gross_margin = segment_metrics[segment_name]['gross_margin']
                    else:
                        # Fallback to defaults
                        growth_rate = 0.1  # Default 10%
                        gross_margin = 0.3  # Default 30%
                    
                    # Calculate revenue with growth
                    # Base year is the latest historical year, apply growth from there
                    years_from_base = year - base_year
                    year_revenue = base_revenue * ((1 + growth_rate) ** years_from_base)
                    
                    other_revenue_by_year[year] += year_revenue
                    
                    # Calculate COGS from gross margin
                    year_cogs = year_revenue * (1 - gross_margin)
                    other_cogs_by_year[year] += year_cogs
            
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
                    growth_rate = 0.1  # Default 10%
                
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
                        growth_rate = 0.1
                    
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
                column_config[col] = st.column_config.NumberColumn(col, width='small', format='%.1f')
            
            st.dataframe(
                revenue_df.style
                .format("{:.1f}", subset=[hist_col] + [str(y) for y in years])
                .apply(highlight_special_rows, axis=1),
                use_container_width=True,
                column_config=column_config,
                hide_index=True
            )
            
            # Section 3: COGS Table
            st.markdown("---")
            st.subheader("💰 Cost of Goods Sold (COGS)")
            
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
                    growth_rate = 0.1  # Default 10%
                    gross_margin = 0.3  # Default 30%
                
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
                        growth_rate = 0.1
                        gross_margin = 0.3
                    
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
                cogs_column_config[col] = st.column_config.NumberColumn(col, width='small', format='%.1f')
            
            st.dataframe(
                cogs_df.style
                .format("{:.1f}", subset=[hist_col] + [str(y) for y in years])
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
                    growth_rate = 0.1  # Default 10%
                    gross_margin = 0.3  # Default 30%
                
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
                gp_column_config[col] = st.column_config.NumberColumn(col, width='small', format='%.1f')
            
            st.dataframe(
                gross_profit_df.style
                .format("{:.1f}", subset=[hist_col] + [str(y) for y in years])
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
                    gross_margin = 30.0  # Default 30%
                
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
            
            # Section 4.4: SG&A by Source
            st.markdown("---")
            st.subheader("💼 SG&A by Source")
            
            # Initialize SG&A rows
            sga_rows = []
            
            # SG&A for individual projects (Real Estate) - Load from MongoDB schedules
            project_sga_total_by_year = {year: 0 for year in years}
            
            # Add individual project SG&A from loaded schedules
            for project_name in project_sga_breakdown.keys():
                row_data = {'SG&A Source': f"{project_name}"}
                row_data[hist_col] = 0  # No historical breakdown
                
                for year in years:
                    # Get SG&A from the loaded schedule
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
                    sga_pct = 0.15  # Default 15%
                
                # Historical SG&A (negative)
                row_data[hist_col] = -base_revenue * sga_pct
                
                for year in years:
                    # Calculate segment revenue for the year
                    if segment_name in segment_metrics:
                        growth_rate = segment_metrics[segment_name]['revenue_growth']
                    else:
                        growth_rate = 0.1  # Default 10%
                    
                    # Base year is the latest historical year, apply growth from there
                    years_from_base = year - base_year
                    segment_revenue = base_revenue * ((1 + growth_rate) ** years_from_base)
                    row_data[str(year)] = -segment_revenue * sga_pct  # Negative value for expense
                
                sga_rows.append(row_data)
            
            # Total SG&A row
            total_sga_row = {'SG&A Source': 'TOTAL SG&A'}
            # Calculate historical SG&A by summing all segments
            hist_sga_total = sum(row[hist_col] for row in sga_rows if row['SG&A Source'] != 'TOTAL SG&A')
            total_sga_row[hist_col] = hist_sga_total
            for year in years:
                total_sga = sum(row[str(year)] for row in sga_rows if row['SG&A Source'] != 'TOTAL SG&A')
                total_sga_row[str(year)] = total_sga
            sga_rows.append(total_sga_row)
            
            # Create DataFrame for SG&A
            sga_df = pd.DataFrame(sga_rows)
            
            st.write("**SG&A Expense by Source (Billion VND)**")
            
            # Style function to highlight total and subtotal rows
            def highlight_sga_rows(row):
                source = str(row['SG&A Source'])
                if 'TOTAL SG&A' in source:
                    return ['font-weight: bold; background-color: #f0f0f0'] * len(row)
                elif 'Total Projects' in source:
                    return ['font-weight: bold'] * len(row)
                else:
                    return [''] * len(row)
            
            # Define column configuration for consistent width
            sga_column_config = {
                'SG&A Source': st.column_config.TextColumn('SG&A Source', width='medium'),
            }
            for col in [hist_col] + [str(y) for y in years]:
                sga_column_config[col] = st.column_config.NumberColumn(col, width='small', format='%.1f')
            
            st.dataframe(
                sga_df.style
                .format("{:.1f}", subset=[hist_col] + [str(y) for y in years])
                .apply(highlight_sga_rows, axis=1),
                use_container_width=True,
                column_config=sga_column_config,
                hide_index=True
            )
            
            # Section 4.5: Interest Expense by Source
            st.markdown("---")
            st.subheader("💰 Interest Expense by Source")
            
            # Initialize Interest Expense rows
            interest_rows = []
            
            # Get debt financing percentage from assumptions
            debt_financing_pct = 0.30  # Default 30%
            # Get assumptions from MongoDB or use defaults
            try:
                # Try to get from session state or MongoDB
                assumptions_key = f'assumptions_df_{selected_ticker}'
                if assumptions_key in st.session_state:
                    assumptions_data = st.session_state[assumptions_key]
                    if isinstance(assumptions_data, pd.DataFrame):
                        assumptions_list = assumptions_data.to_dict('records')
                    else:
                        assumptions_list = assumptions_data
                    
                    for assumption in assumptions_list:
                        if assumption.get('Item') == 'Debt Financing %':
                            debt_financing_pct = assumption.get('Value', 30) / 100
                            break
            except:
                pass  # Use default if any error
            
            # Interest rate assumption (could be from assumptions or default)
            interest_rate = 0.07  # Default 7% annual interest rate
            
            # Interest on individual project financing - Load from MongoDB schedules
            project_interest_total_by_year = {year: 0 for year in years}
            
            # Add individual project interest from loaded schedules
            for project_name in project_interest_breakdown.keys():
                row_data = {'Interest Source': f"{project_name} Financing"}
                row_data[hist_col] = 0  # No historical breakdown
                
                for year in years:
                    # Get interest expense from the loaded schedule
                    project_interest = project_interest_breakdown[project_name].get(year, 0)
                    row_data[str(year)] = project_interest
                    project_interest_total_by_year[year] += project_interest
                
                interest_rows.append(row_data)
            
            # Total Interest Expense row (same as Total Project Financing if no other sources)
            if project_cogs_breakdown:
                total_interest_row = {'Interest Source': 'TOTAL INTEREST EXPENSE'}
                total_interest_row[hist_col] = 0  # No historical breakdown
                for year in years:
                    total_interest_row[str(year)] = project_interest_total_by_year[year]
                interest_rows.append(total_interest_row)
            
            # Create DataFrame for Interest Expense
            interest_df = pd.DataFrame(interest_rows)
            
            st.write("**Interest Expense by Source (Billion VND)**")
            
            # Style function to highlight total and subtotal rows
            def highlight_interest_rows(row):
                source = str(row['Interest Source'])
                if 'TOTAL INTEREST' in source:
                    return ['font-weight: bold; background-color: #f0f0f0'] * len(row)
                elif 'Total Project' in source:
                    return ['font-weight: bold'] * len(row)
                else:
                    return [''] * len(row)
            
            # Define column configuration for consistent width
            interest_column_config = {
                'Interest Source': st.column_config.TextColumn('Interest Source', width='medium'),
            }
            for col in [hist_col] + [str(y) for y in years]:
                interest_column_config[col] = st.column_config.NumberColumn(col, width='small', format='%.1f')
            
            st.dataframe(
                interest_df.style
                .format("{:.1f}", subset=[hist_col] + [str(y) for y in years])
                .apply(highlight_interest_rows, axis=1),
                use_container_width=True,
                column_config=interest_column_config,
                hide_index=True
            )
            
            # Section 4.6: Debt Management
            st.markdown("---")
            st.subheader("💳 Debt Management")
            
            # Get historical data if available
            historical_data = st.session_state.get('historical_data')
            
            # Initialize debt management data
            debt_mgmt_rows = []
            
            # Determine the latest historical year
            latest_hist_year = None
            hist_values = {}
            
            if historical_data is not None and not historical_data.empty:
                # Get 2024 data from annual dataset
                latest_date_idx = None
                
                # Check if base_year exists in the index
                if str(base_year) in historical_data.index:
                    latest_date_idx = str(base_year)
                    latest_hist_year = base_year
                elif base_year in historical_data.index:
                    latest_date_idx = base_year
                    latest_hist_year = base_year
                    
                    if latest_date_idx is not None:
                        # Extract values from historical data - using correct column names from FA_processed.csv
                        # Cash and Cash Equivalents
                        if 'Cash' in historical_data.columns:
                            hist_values['Cash and cash equivalents'] = historical_data.loc[latest_date_idx, 'Cash']
                        elif 'Cash_Equivalent' in historical_data.columns:
                            cash_equiv = historical_data.loc[latest_date_idx, 'Cash_Equivalent']
                            hist_values['Cash and cash equivalents'] = cash_equiv
                        else:
                            hist_values['Cash and cash equivalents'] = 0
                        
                        # Short-term investment - might not be directly available
                        hist_values['Short-term investment'] = 0  # Default as this is often not separated
                        
                        # Short-term debt
                        if 'ST_Debt' in historical_data.columns:
                            hist_values['Short-term debt'] = historical_data.loc[latest_date_idx, 'ST_Debt']
                        else:
                            hist_values['Short-term debt'] = 0
                        
                        # Long-term debt
                        if 'LT_Debt' in historical_data.columns:
                            hist_values['Long-term debt'] = historical_data.loc[latest_date_idx, 'LT_Debt']
                        else:
                            hist_values['Long-term debt'] = 0
                        
                        # Interest expense
                        if 'Interest_Expense' in historical_data.columns:
                            hist_values['Interest expense'] = abs(historical_data.loc[latest_date_idx, 'Interest_Expense'])
                        else:
                            hist_values['Interest expense'] = 0
                        
                        # Convert to billions VND
                        for key in hist_values:
                            if hist_values[key] and not pd.isna(hist_values[key]):
                                hist_values[key] = hist_values[key] / 1e9  # Convert to billions
                            else:
                                hist_values[key] = 0
            
            # Create columns for display (use consistent format with other tables)
            debt_display_years = ['2024H'] + [str(y) for y in years]
            
            # Row 1: Cash and cash equivalents
            cash_row = {'Item': 'Cash and cash equivalents'}
            cash_row['2024H'] = hist_values.get('Cash and cash equivalents', 100)
            for year in years:
                # For now, keep historical value or use default
                base_value = hist_values.get('Cash and cash equivalents', 100) if hist_values else 100
                growth_rate = 1.05  # 5% growth assumption
                years_ahead = year - (latest_hist_year if latest_hist_year else years[0] - 1)
                cash_row[str(year)] = base_value * (growth_rate ** years_ahead)
            debt_mgmt_rows.append(cash_row)
            
            # Row 2: Short-term investment
            st_inv_row = {'Item': 'Short-term investment'}
            st_inv_row['2024H'] = hist_values.get('Short-term investment', 50)
            for year in years:
                base_value = hist_values.get('Short-term investment', 50) if hist_values else 50
                growth_rate = 1.03  # 3% growth assumption
                years_ahead = year - (latest_hist_year if latest_hist_year else years[0] - 1)
                st_inv_row[str(year)] = base_value * (growth_rate ** years_ahead)
            debt_mgmt_rows.append(st_inv_row)
            
            # Row 3: Short-term debt
            st_debt_row = {'Item': 'Short-term debt'}
            st_debt_row['2024H'] = hist_values.get('Short-term debt', 200)
            for year in years:
                base_value = hist_values.get('Short-term debt', 200) if hist_values else 200
                # Short-term debt might fluctuate with working capital needs
                st_debt_row[str(year)] = base_value * (1 + 0.1 * ((year - years[0]) / len(years)))
            debt_mgmt_rows.append(st_debt_row)
            
            # Row 4: Long-term debt
            lt_debt_row = {'Item': 'Long-term debt'}
            lt_debt_row['2024H'] = hist_values.get('Long-term debt', 500)
            for year in years:
                base_value = hist_values.get('Long-term debt', 500) if hist_values else 500
                # Long-term debt might increase with project financing
                lt_debt_row[str(year)] = base_value * (1 + 0.15 * ((year - years[0]) / len(years)))
            debt_mgmt_rows.append(lt_debt_row)
            
            # Row 5: Interest expense
            int_expense_row = {'Item': 'Interest expense'}
            int_expense_row['2024H'] = hist_values.get('Interest expense', 40)
            for year in years:
                # Calculate based on net debt and interest rate
                cash = cash_row[str(year)]
                st_inv = st_inv_row[str(year)]
                st_debt = st_debt_row[str(year)]
                lt_debt = lt_debt_row[str(year)]
                net_debt = st_debt + lt_debt - cash - st_inv
                
                # Use historical interest rate or default
                if latest_hist_year and hist_values.get('Interest expense', 0) > 0:
                    hist_net_debt = (hist_values.get('Short-term debt', 0) + hist_values.get('Long-term debt', 0) - 
                                   hist_values.get('Cash and cash equivalents', 0) - hist_values.get('Short-term investment', 0))
                    if hist_net_debt > 0:
                        implied_rate = hist_values['Interest expense'] / hist_net_debt
                    else:
                        implied_rate = 0.07  # Default 7%
                else:
                    implied_rate = 0.07  # Default 7%
                
                int_expense_row[str(year)] = max(0, net_debt * implied_rate)
            debt_mgmt_rows.append(int_expense_row)
            
            # Row 6: Net Debt
            net_debt_row = {'Item': 'Net Debt'}
            # Calculate for historical year
            net_debt_row['2024H'] = (st_debt_row['2024H'] + lt_debt_row['2024H'] - 
                                    cash_row['2024H'] - st_inv_row['2024H'])
            # Calculate for forecast years
            for year in years:
                year_str = str(year)
                net_debt_row[year_str] = (st_debt_row[year_str] + lt_debt_row[year_str] - 
                                         cash_row[year_str] - st_inv_row[year_str])
            debt_mgmt_rows.append(net_debt_row)
            
            # Row 7: Interest expense rate
            int_rate_row = {'Item': 'Interest expense rate (%)'}
            # Calculate for historical year
            if net_debt_row['2024H'] > 0:
                int_rate_row['2024H'] = (int_expense_row['2024H'] / net_debt_row['2024H']) * 100
            else:
                int_rate_row['2024H'] = 0
            # Calculate for forecast years
            for year in years:
                year_str = str(year)
                if net_debt_row[year_str] > 0:
                    int_rate_row[year_str] = (int_expense_row[year_str] / net_debt_row[year_str]) * 100
                else:
                    int_rate_row[year_str] = 0
            debt_mgmt_rows.append(int_rate_row)
            
            # Create DataFrame
            debt_mgmt_df = pd.DataFrame(debt_mgmt_rows)
            
            # Format the dataframe for display
            st.write("**Debt Management (Billion VND)**")
            
            # Simple approach - format the DataFrame values before styling
            formatted_df = debt_mgmt_df.copy()
            
            # Format numeric columns
            for col in debt_display_years:
                col_str = col
                if col_str in formatted_df.columns:
                    # Format as numbers with 1 decimal, except for Interest expense rate
                    formatted_df[col_str] = formatted_df.apply(
                        lambda row: f"{row[col_str]:.1f}%" if row['Item'] == 'Interest expense rate (%)' 
                        else f"{row[col_str]:.1f}", 
                        axis=1
                    )
            
            # Apply highlighting for Net Debt and Interest expense rate rows
            def highlight_important_rows(row):
                if row['Item'] in ['Net Debt', 'Interest expense rate (%)']:
                    return ['font-weight: bold'] * len(row)
                return [''] * len(row)
            
            styled_df = formatted_df.style.apply(highlight_important_rows, axis=1)
            
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            # Add explanation
            st.caption("Net Debt = Short-term debt + Long-term debt - Cash and cash equivalents - Short-term investment")
            st.caption("Interest expense rate = Interest expense / Net Debt")
            
            # Section 5: Comprehensive P&L with Interest Expense (moved here from below)
            st.markdown("---")
            st.subheader("💰 Comprehensive P&L Statement")
            
            # Calculate interest expense for all projects
            project_interest_by_year = {}
            cumulative_debt = 0
            debt_financing_pct = company_assumptions.get('debt_financing_pct', 0.30)  # Default 30%
            
            for year in years:
                year_str = str(year)
                total_interest = 0
                
                # Aggregate interest from all projects
                for _, project in df_projects.iterrows():
                    # Check if project has saved interest schedule
                    interest_schedule = project.get('interest_schedule', {})
                    if isinstance(interest_schedule, dict) and year_str in interest_schedule:
                        total_interest += interest_schedule[year_str]
                    else:
                        # Simple fallback calculation
                        cost_of_debt = 0.08  # Default 8%
                        capital_needs = (project_cogs_by_year[year])
                        new_debt = capital_needs * debt_financing_pct
                        cumulative_debt += new_debt
                        revenue_this_year = project_revenue_by_year[year]
                        debt_repayment = min(cumulative_debt, revenue_this_year * 0.7)
                        cumulative_debt = max(0, cumulative_debt - debt_repayment)
                        total_interest += cumulative_debt * cost_of_debt
                
                project_interest_by_year[year] = total_interest
            
            # Calculate SG&A expenses
            sga_by_year = {}
            for year in years:
                # SG&A for projects (typically 8% of project revenue)
                project_sga = project_revenue_by_year[year] * 0.08
                
                # SG&A for other segments
                other_sga = 0
                for segment_name in st.session_state.base_year_revenues.keys():
                    if segment_name in segment_metrics:
                        sga_pct = segment_metrics[segment_name]['sga_percentage']
                    else:
                        sga_pct = 0.15  # Default 15%
                    
                    # Calculate segment revenue for the year
                    base_revenue = st.session_state.base_year_revenues[segment_name]
                    if segment_name in segment_metrics:
                        growth_rate = segment_metrics[segment_name]['revenue_growth']
                    else:
                        growth_rate = 0.1
                    
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
            total_interest_row = interest_df[interest_df['Interest Source'] == 'TOTAL INTEREST EXPENSE'].iloc[0]
            
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
                    gross_margin = 0.3
                
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
            
            # Interest Expense row (negative values)
            interest_row = {'P&L Item': 'Interest Expense'}
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
            tax_row = {'P&L Item': 'Tax (20%)'}
            tax_row[hist_col] = -max(0, pbt_row[hist_col] * 0.2)  # Add historical as negative
            for year in years:
                year_str = str(year)
                pbt_value = pbt_row[year_str]
                tax_row[year_str] = -max(0, pbt_value * 0.2)  # Tax as negative (expense)
            pnl_rows.append(tax_row)
            
            # PAT row (PBT + Tax where Tax is negative)
            pat_row = {'P&L Item': 'Profit After Tax'}
            pat_row[hist_col] = pbt_row[hist_col] + tax_row[hist_col]  # Add historical
            for year in years:
                year_str = str(year)
                # Since Tax is negative, we add it (not subtract)
                pat_row[year_str] = pbt_row[year_str] + tax_row[year_str]
            pnl_rows.append(pat_row)
            
            # Create DataFrame
            pnl_df = pd.DataFrame(pnl_rows)
            
            # Load saved forecast for comparison BEFORE displaying table
            from utils.mongodb_utils import load_company_forecast
            saved_forecast = load_company_forecast(selected_ticker)
            
            # Create a mapping of P&L items to their saved values
            saved_values_map = {}
            if saved_forecast:
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
                    saved_values_map[year_str]['Interest Expense'] = saved_year.get('interest_expense', None)
                    saved_values_map[year_str]['Profit Before Tax'] = saved_year.get('pbt', None)
                    saved_values_map[year_str]['Tax (20%)'] = saved_year.get('tax', None)
                    saved_values_map[year_str]['Profit After Tax'] = saved_year.get('pat', None)
                    
                    # Map business segments
                    if 'business_segments' in saved_year:
                        for segment_name, segment_data in saved_year['business_segments'].items():
                            saved_values_map[year_str][f'  {segment_name}'] = segment_data.get('revenue', None)
                            saved_values_map[year_str][f'  {segment_name} COGS'] = segment_data.get('cogs', None)
            
            # Create display DataFrame with change indicators
            display_df = pnl_df.copy()
            changed_cells = []  # Track cells that have changed for styling
            
            # Add change indicators to values
            for idx, row in pnl_df.iterrows():
                item = row['P&L Item']
                for year in years:
                    year_str = str(year)
                    if year_str in saved_values_map and item in saved_values_map[year_str]:
                        current_val = row[year_str]
                        saved_val = saved_values_map[year_str][item]
                        
                        if saved_val is not None and abs(current_val - saved_val) > 0.01:
                            # Format as "new (old)" for changed values
                            display_df.at[idx, year_str] = f"{current_val:.1f}\n({saved_val:.1f})"
                            changed_cells.append((idx, year_str))
            
            # Style function to highlight key rows and changed cells
            def style_pnl_table(df_style):
                # Create style DataFrame
                styles = pd.DataFrame('', index=df_style.index, columns=df_style.columns)
                
                # Apply row-level styles
                for idx, row in df_style.iterrows():
                    item = pnl_df.iloc[idx]['P&L Item']
                    if item in ['Net Revenue', 'Total COGS', 'Gross Profit', 'EBITDA', 'Profit After Tax']:
                        styles.iloc[idx] = 'font-weight: bold'
                    elif item.startswith('  '):
                        styles.iloc[idx] = 'padding-left: 20px'
                
                # Apply cell-level highlighting for changes
                for idx, col in changed_cells:
                    current_style = styles.at[idx, col]
                    styles.at[idx, col] = f"{current_style}; background-color: #90EE90"  # Light green
                
                return styles
            
            # Format function for proper display
            def format_pnl_values(val):
                if isinstance(val, str) and '\n' in val:
                    return val  # Already formatted with old value
                else:
                    return f"{val:.1f}"
            
            st.write("**Comprehensive P&L Statement (Billion VND)**")
            if changed_cells:
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
            
            # Display change indicator
            if has_changes:
                st.warning("⚠️ Unsaved changes detected in the P&L forecast compared to the database")
                with st.expander("View changes summary"):
                    for year_str, items in changed_items.items():
                        st.write(f"**Year {year_str}:** {', '.join(items)}")
            elif saved_forecast:
                st.success("✅ P&L forecast matches the saved version in database")
            
            # Save forecast to MongoDB button
            col_save1, col_save2, col_save3 = st.columns([1, 2, 1])
            with col_save2:
                button_type = "primary" if has_changes else "secondary"
                button_label = "💾 Save Changes to Database" if has_changes else "💾 Save to Database"
                
                if st.button(button_label, type=button_type, use_container_width=True):
                    # Prepare forecast data for MongoDB
                    forecast_data = {}
                    
                    for year in years:
                        year_str = str(year)
                        
                        # Extract P&L data for this year
                        year_pnl = {
                            'real_estate_revenue': re_revenue_row[year_str],
                            'net_revenue': revenue_row[year_str],
                            'real_estate_cogs': re_cogs_row[year_str],
                            'total_cogs': total_cogs_pnl_row[year_str],
                            'gross_profit': gp_row[year_str],
                            'sga': sga_row[year_str],
                            'ebitda': ebitda_row[year_str],
                            'interest_expense': interest_row[year_str],
                            'pbt': pbt_row[year_str],
                            'tax': tax_row[year_str],
                            'pat': pat_row[year_str],
                            # Add individual business segments
                            'business_segments': {}
                        }
                        
                        # Add each business segment's revenue and COGS
                        for segment_name in st.session_state.base_year_revenues.keys():
                            year_pnl['business_segments'][segment_name] = {
                                'revenue': segment_revenue_data[segment_name][year_str],
                                'cogs': segment_cogs_data[segment_name][year_str]
                            }
                        
                        forecast_data[year_str] = year_pnl
                    
                    # Save to MongoDB
                    from utils.mongodb_utils import save_company_forecast
                    result = save_company_forecast(selected_ticker, forecast_data)
                    
                    if result['success']:
                        st.success(f"✅ {result['message']}")
                        # Store in session state for reference
                        st.session_state[f'saved_forecast_{selected_ticker}'] = forecast_data
                        st.rerun()  # Rerun to update the change detection
                    else:
                        st.error(f"❌ {result['message']}")
            
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
            
            # Section 6: Visualization Chart (moved to bottom)
            st.markdown("---")
            st.subheader("Revenue, COGS, and Gross Profit Visualization")
            
            # Create visualization
            fig = go.Figure()
            
            # Extract data for visualization
            revenue_values = [total_revenue_row[str(y)] for y in years]
            cogs_values = [total_cogs_row[str(y)] for y in years]  # Already negative
            gross_profit_values = [total_gp_row[str(y)] for y in years]
            
            # Add revenue bars
            fig.add_trace(go.Bar(
                name='Total Revenue',
                x=years,
                y=revenue_values,
                marker_color='lightblue',
                text=[f'{v:.0f}B' for v in revenue_values],
                textposition='outside'
            ))
            
            # Add COGS bars (show absolute values for visualization but keep negative in data)
            fig.add_trace(go.Bar(
                name='Total COGS',
                x=years,
                y=[abs(v) for v in cogs_values],  # Show as positive bars for visualization
                marker_color='lightcoral',
                text=[f'{v:.0f}B' for v in cogs_values],  # Show actual negative values in text
                textposition='outside'
            ))
            
            # Add gross profit line
            fig.add_trace(go.Scatter(
                name='Gross Profit',
                x=years,
                y=gross_profit_values,
                mode='lines+markers',
                line=dict(color='green', width=3),
                marker=dict(size=8),
                yaxis='y2'
            ))
            
            fig.update_layout(
                title="Revenue, COGS, and Gross Profit Forecast",
                xaxis_title="Year",
                yaxis=dict(title="Billion VND", side='left'),
                yaxis2=dict(title="Gross Profit (B VND)", overlaying='y', side='right'),
                barmode='group',
                height=500,
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.info("No project data available. Please add projects in the Project Pipeline tab.")
    
    def render_total_company_forecast(self):
        """Render total company revenue forecast combining selected segments only"""
        st.subheader("Total Company Revenue Forecast")
        
        # Get only selected revenue streams
        if 'selected_streams_data' in st.session_state:
            revenue_streams = st.session_state.selected_streams_data
        else:
            revenue_streams = st.session_state.comprehensive_model.get('revenue_streams', [])
        current_year = datetime.now().year
        forecast_years = st.session_state.get('forecast_years', 5)
        years = list(range(current_year, current_year + forecast_years + 1))
        
        # Initialize forecast data
        forecast_data = {year: {} for year in years}
        
        # Generate forecast for each segment using dynamic assumptions
        for stream in revenue_streams:
            segment_name = stream.get('segment_name', 'Unknown')
            base_revenue = stream.get('revenue_2023', 0) or stream.get('revenue_2022', 0)
            
            # Get dynamic assumptions for this segment
            if 'dynamic_assumptions' in st.session_state and segment_name in st.session_state.dynamic_assumptions:
                growth_rate = st.session_state.dynamic_assumptions[segment_name]['revenue_growth'] / 100
                margin = st.session_state.dynamic_assumptions[segment_name]['gross_margin'] / 100
            else:
                growth_rate = stream.get('growth_rate', 0.10)
                margin = stream.get('gross_margin', 0.25)
            
            # Calculate forecast for this segment
            for i, year in enumerate(years):
                if 'real estate' in segment_name.lower() and st.session_state.project_data is not None:
                    # Use project-based forecast for real estate
                    revenue = self.calculate_real_estate_revenue_for_year(year)
                else:
                    # Use growth-based forecast for other segments
                    revenue = base_revenue * ((1 + growth_rate) ** (i + 1))
                
                forecast_data[year][segment_name] = revenue
        
        # Create DataFrame for display
        forecast_df = pd.DataFrame(forecast_data).T
        forecast_df.index.name = 'Year'
        
        # Add total column
        forecast_df['TOTAL'] = forecast_df.sum(axis=1)
        
        # Display in billions VND
        st.write("**Revenue Forecast by Segment (Billion VND)**")
        display_df = forecast_df / 1e9
        st.dataframe(display_df.style.format("{:.1f}"), use_container_width=True)
        
        # Create stacked bar chart
        fig = go.Figure()
        
        for column in forecast_df.columns:
            if column != 'TOTAL':
                fig.add_trace(go.Bar(
                    name=column,
                    x=years,
                    y=forecast_df[column] / 1e9,
                    text=[f"{v:.0f}B" if v > 100e9 else "" for v in forecast_df[column]],
                    textposition='inside'
                ))
        
        # Add total line
        fig.add_trace(go.Scatter(
            x=years,
            y=forecast_df['TOTAL'] / 1e9,
            name='Total Revenue',
            mode='lines+markers+text',
            line=dict(color='red', width=3),
            text=[f"{v:.0f}B" for v in forecast_df['TOTAL'] / 1e9],
            textposition='top center',
            yaxis='y2'
        ))
        
        fig.update_layout(
            title="Total Company Revenue Forecast",
            xaxis_title="Year",
            yaxis=dict(title="Revenue (Billion VND)"),
            yaxis2=dict(title="Total (Billion VND)", overlaying='y', side='right'),
            barmode='stack',
            height=500,
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show growth metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_growth = (forecast_df['TOTAL'].iloc[-1] / forecast_df['TOTAL'].iloc[0]) ** (1/forecast_years) - 1
            st.metric("CAGR", f"{total_growth*100:.1f}%")
        
        with col2:
            avg_revenue = forecast_df['TOTAL'].mean() / 1e9
            st.metric("Avg Annual Revenue", f"{avg_revenue:.0f}B VND")
        
        with col3:
            peak_revenue = forecast_df['TOTAL'].max() / 1e9
            st.metric("Peak Revenue", f"{peak_revenue:.0f}B VND")
    
    def render_project_pipeline_forecast(self):
        """Render forecast specifically from real estate projects"""
        st.subheader("🏗️ Real Estate Project Pipeline Forecast")
        
        if st.session_state.project_data is None or (isinstance(st.session_state.project_data, pd.DataFrame) and st.session_state.project_data.empty):
            st.info("No project data available. Please sync project data from the sidebar.")
            return
        
        # Generate revenue forecast from projects
        revenue_forecast = self.generate_revenue_forecast()
        df_projects = st.session_state.project_data
        years = revenue_forecast['years']
        current_year = datetime.now().year
        
        # Initialize aggregated revenue and project breakdown
        total_revenue_by_year = [0] * len(years)
        project_revenue_matrix = {}  # Store revenue by project and year
        
        # Aggregate revenue from all projects
        for _, project in df_projects.iterrows():
            project_name = project.get('project_name', 'Unknown')
            project_revenue_matrix[project_name] = [0] * len(years)
            
            # Get revenue schedule
            revenue_schedule = project.get('revenue_schedule', {})
            
            # If no saved schedule, calculate it
            if not isinstance(revenue_schedule, dict) or not revenue_schedule:
                # Calculate on the fly
                nsa = float(project.get('net_sellable_area', 0) or 0)
                asp = float(project.get('average_selling_price', 0) or 0)
                total_revenue = nsa * asp / 1e9  # Convert to billions
                
                revenue_dist = project.get('revenue_distribution', {})
                if not isinstance(revenue_dist, dict):
                    revenue_dist = {}
                
                revenue_start = int(project.get('revenue_booking_start_year', current_year))
                project_end = int(project.get('project_completion_year', current_year + 3))
                
                # If no distribution, create even split
                if not revenue_dist:
                    booking_years = list(range(revenue_start, project_end + 1))
                    if booking_years:
                        even_pct = 100.0 / len(booking_years)
                        for year in booking_years:
                            revenue_dist[str(year)] = even_pct
                
                # Create schedule
                revenue_schedule = {}
                for year in range(revenue_start, project_end + 1):
                    year_str = str(year)
                    year_pct = revenue_dist.get(year_str, 0) / 100.0
                    revenue_schedule[year_str] = total_revenue * year_pct
            
            # Add to yearly totals and project matrix
            for i, year in enumerate(years):
                year_str = str(year)
                if year_str in revenue_schedule:
                    revenue_amount = revenue_schedule[year_str]
                    total_revenue_by_year[i] += revenue_amount
                    project_revenue_matrix[project_name][i] = revenue_amount
        
        # Create stacked bar chart showing breakdown by project
        fig = go.Figure()
        
        # Define colors for projects
        colors = px.colors.qualitative.Plotly + px.colors.qualitative.Set1 + px.colors.qualitative.Set2
        
        # Add a bar for each project
        for idx, (project_name, revenues) in enumerate(project_revenue_matrix.items()):
            # Only add projects that have revenue
            if sum(revenues) > 0:
                fig.add_trace(go.Bar(
                    x=years,
                    y=revenues,
                    name=project_name,
                    marker_color=colors[idx % len(colors)],
                    text=[f'{v:.0f}B' if v > 0 else '' for v in revenues],
                    textposition='inside',
                    hovertemplate='%{y:.1f}B VND<extra></extra>'
                ))
        
        # Add total revenue line
        fig.add_trace(go.Scatter(
            x=years,
            y=total_revenue_by_year,
            name='Total Revenue',
            mode='lines+markers+text',
            line=dict(color='red', width=3),
            marker=dict(size=8),
            text=[f'{v:.0f}B' for v in total_revenue_by_year],
            textposition='top center',
            yaxis='y2',
            hovertemplate='Total: %{y:.1f}B VND<extra></extra>'
        ))
        
        fig.update_layout(
            title="Revenue Forecast by Project (Billion VND)",
            xaxis_title="Year",
            yaxis=dict(title="Revenue (B VND)", side='left'),
            yaxis2=dict(title="Total Revenue (B VND)", overlaying='y', side='right'),
            barmode='stack',
            height=600,
            hovermode='x unified',
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.1
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show project summary table
        st.write("**Project Revenue Summary (Billion VND)**")
        summary_data = []
        for project_name, revenues in project_revenue_matrix.items():
            if sum(revenues) > 0:
                summary_data.append({
                    'Project': project_name,
                    'Total Revenue': sum(revenues),
                    'Peak Year': years[revenues.index(max(revenues))],
                    'Peak Revenue': max(revenues)
                })
        
        if summary_data:
            summary_df = pd.DataFrame(summary_data)
            summary_df = summary_df.sort_values('Total Revenue', ascending=False)
            st.dataframe(summary_df.style.format({'Total Revenue': '{:.1f}', 'Peak Revenue': '{:.1f}'}), use_container_width=True)
    
    def render_other_segments_forecast(self):
        """Render forecast for selected non-real estate segments"""
        st.subheader("💼 Other Business Segments Forecast")
        
        # Get only selected revenue streams
        if 'selected_streams_data' in st.session_state:
            revenue_streams = st.session_state.selected_streams_data
        else:
            revenue_streams = st.session_state.comprehensive_model.get('revenue_streams', [])
        
        non_real_estate = [s for s in revenue_streams if 'real estate' not in s.get('segment_name', '').lower()]
        
        if not non_real_estate:
            st.info("No other business segments identified")
            return
        
        current_year = datetime.now().year
        forecast_years = st.session_state.get('forecast_years', 5)
        years = list(range(current_year, current_year + forecast_years + 1))
        
        # Create forecast for each non-real estate segment
        fig = go.Figure()
        
        for stream in non_real_estate:
            segment_name = stream.get('segment_name', 'Unknown')
            base_revenue = stream.get('revenue_2023', 0) or stream.get('revenue_2022', 0)
            
            # Get dynamic assumptions
            if 'dynamic_assumptions' in st.session_state and segment_name in st.session_state.dynamic_assumptions:
                growth_rate = st.session_state.dynamic_assumptions[segment_name]['revenue_growth'] / 100
            else:
                growth_rate = stream.get('growth_rate', 0.10)
            
            # Calculate forecast
            forecast = []
            for i in range(len(years)):
                revenue = base_revenue * ((1 + growth_rate) ** (i + 1))
                forecast.append(revenue / 1e9)
            
            fig.add_trace(go.Scatter(
                x=years,
                y=forecast,
                name=segment_name,
                mode='lines+markers',
                line=dict(width=2),
                marker=dict(size=8)
            ))
        
        fig.update_layout(
            title="Other Business Segments Revenue Forecast",
            xaxis_title="Year",
            yaxis_title="Revenue (Billion VND)",
            height=400,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show segment details
        st.write("**Segment Growth Assumptions:**")
        
        cols = st.columns(len(non_real_estate) if len(non_real_estate) <= 4 else 4)
        for i, stream in enumerate(non_real_estate):
            segment_name = stream.get('segment_name', 'Unknown')
            col_idx = i % len(cols)
            
            with cols[col_idx]:
                if 'dynamic_assumptions' in st.session_state and segment_name in st.session_state.dynamic_assumptions:
                    growth = st.session_state.dynamic_assumptions[segment_name]['revenue_growth']
                    margin = st.session_state.dynamic_assumptions[segment_name]['gross_margin']
                else:
                    growth = stream.get('growth_rate', 0.10) * 100
                    margin = stream.get('gross_margin', 0.25) * 100
                
                st.metric(segment_name, f"{growth:.1f}% growth", f"{margin:.1f}% margin")
    
    def render_consolidated_forecast(self):
        """Render consolidated P&L forecast combining all segments"""
        st.subheader("Consolidated Financial Forecast")
        
        current_year = datetime.now().year
        forecast_years = st.session_state.get('forecast_years', 5)
        years = list(range(current_year, current_year + forecast_years + 1))
        
        # Initialize P&L structure
        pnl_data = []
        
        # Calculate revenue for each year
        for year in years:
            year_data = {'Year': year}
            
            # Real Estate revenue from projects (only if selected)
            real_estate_selected = any('real estate' in s.get('segment_name', '').lower() 
                                      for s in st.session_state.get('selected_streams_data', []))
            
            if real_estate_selected:
                re_revenue = self.calculate_real_estate_revenue_for_year(year)
                year_data['Real Estate Revenue'] = re_revenue / 1e9
            else:
                year_data['Real Estate Revenue'] = 0
            
            # Other segments revenue
            other_revenue = 0
            # Get only selected revenue streams
            if 'selected_streams_data' in st.session_state:
                revenue_streams = st.session_state.selected_streams_data
            else:
                revenue_streams = st.session_state.comprehensive_model.get('revenue_streams', [])
            
            for stream in revenue_streams:
                if 'real estate' not in stream.get('segment_name', '').lower():
                    segment_name = stream.get('segment_name')
                    base_revenue = stream.get('revenue_2023', 0) or stream.get('revenue_2022', 0)
                    
                    if 'dynamic_assumptions' in st.session_state and segment_name in st.session_state.dynamic_assumptions:
                        growth_rate = st.session_state.dynamic_assumptions[segment_name]['revenue_growth'] / 100
                    else:
                        growth_rate = stream.get('growth_rate', 0.10)
                    
                    year_idx = year - current_year
                    segment_revenue = base_revenue * ((1 + growth_rate) ** (year_idx + 1))
                    other_revenue += segment_revenue
            
            year_data['Other Segments Revenue'] = other_revenue / 1e9
            year_data['Total Revenue'] = year_data['Real Estate Revenue'] + year_data['Other Segments Revenue']
            
            # Calculate costs and margins
            # Use weighted average margins
            re_margin = 0.30  # Default real estate margin
            other_margin = 0.20  # Default other segments margin
            
            if year_data['Total Revenue'] > 0:
                weighted_margin = (year_data['Real Estate Revenue'] * re_margin + 
                                 year_data['Other Segments Revenue'] * other_margin) / year_data['Total Revenue']
            else:
                weighted_margin = 0.25
            
            year_data['Gross Profit'] = year_data['Total Revenue'] * weighted_margin
            year_data['Operating Expenses'] = year_data['Total Revenue'] * st.session_state.assumptions['costs']['sga_pct'] / 100
            year_data['EBIT'] = year_data['Gross Profit'] - year_data['Operating Expenses']
            year_data['Tax'] = max(0, year_data['EBIT'] * st.session_state.assumptions['costs']['tax_rate'] / 100)
            year_data['Net Profit'] = year_data['EBIT'] - year_data['Tax']
            
            pnl_data.append(year_data)
        
        # Create DataFrame
        pnl_df = pd.DataFrame(pnl_data)
        pnl_df.set_index('Year', inplace=True)
        
        # Display table
        st.write("**Consolidated P&L Forecast (Billion VND)**")
        st.dataframe(pnl_df.style.format("{:.1f}"), use_container_width=True)
        
        # Create waterfall chart for revenue composition
        fig = go.Figure()
        
        # Add bars for each revenue component
        fig.add_trace(go.Bar(
            name='Real Estate',
            x=years,
            y=pnl_df['Real Estate Revenue'],
            marker_color='lightblue'
        ))
        
        fig.add_trace(go.Bar(
            name='Other Segments',
            x=years,
            y=pnl_df['Other Segments Revenue'],
            marker_color='lightgreen'
        ))
        
        # Add profit line
        fig.add_trace(go.Scatter(
            name='Net Profit',
            x=years,
            y=pnl_df['Net Profit'],
            mode='lines+markers',
            line=dict(color='darkgreen', width=3),
            yaxis='y2'
        ))
        
        fig.update_layout(
            title="Revenue Composition and Profitability",
            xaxis_title="Year",
            yaxis=dict(title="Revenue (Billion VND)"),
            yaxis2=dict(title="Net Profit (Billion VND)", overlaying='y', side='right'),
            barmode='stack',
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Show key metrics
        st.write("**Key Financial Metrics**")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            avg_margin = pnl_df['Net Profit'].sum() / pnl_df['Total Revenue'].sum() * 100
            st.metric("Avg Net Margin", f"{avg_margin:.1f}%")
        
        with col2:
            revenue_cagr = (pnl_df['Total Revenue'].iloc[-1] / pnl_df['Total Revenue'].iloc[0]) ** (1/forecast_years) - 1
            st.metric("Revenue CAGR", f"{revenue_cagr*100:.1f}%")
        
        with col3:
            profit_cagr = (pnl_df['Net Profit'].iloc[-1] / pnl_df['Net Profit'].iloc[0]) ** (1/forecast_years) - 1 if pnl_df['Net Profit'].iloc[0] > 0 else 0
            st.metric("Profit CAGR", f"{profit_cagr*100:.1f}%")
        
        with col4:
            peak_profit = pnl_df['Net Profit'].max()
            st.metric("Peak Net Profit", f"{peak_profit:.0f}B VND")
    
    def calculate_real_estate_revenue_for_year(self, year):
        """Calculate real estate revenue for a specific year from projects"""
        if st.session_state.project_data is None or st.session_state.project_data.empty:
            return 0
        
        total_revenue = 0
        
        for _, project in st.session_state.project_data.iterrows():
            revenue_schedule = project.get('revenue_schedule', {})
            year_str = str(year)
            
            if year_str in revenue_schedule:
                total_revenue += revenue_schedule[year_str] * 1e9  # Convert from billions
        
        return total_revenue
    
    def display_project_revenue_forecast(self):
        """Display revenue forecast specifically from projects"""
        # This is the existing project forecast logic
        # Can reuse most of the existing code
        pass
    
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
        else:
            # Fallback to assumption-based forecast if no project data
            forecast = self.calculate_assumption_based_revenue(forecast)
        
        return forecast
    
    def display_aggregated_pnl_forecast(self):
        """Display aggregated P&L forecast from all projects"""
        if st.session_state.project_data is None or st.session_state.project_data.empty:
            st.info("No project data available for P&L aggregation")
            return
        
        df_projects = st.session_state.project_data
        current_year = datetime.now().year
        forecast_years = st.session_state.forecast_years
        years = list(range(current_year, current_year + forecast_years + 1))
        
        # Initialize aggregated data
        aggregated_data = {
            'Year': years,
            'Revenue': [0] * len(years),
            'Construction Cost': [0] * len(years),
            'Land Cost': [0] * len(years),
            'SG&A': [0] * len(years),
            'EBITDA': [0] * len(years),
            'PBT': [0] * len(years),
            'Tax (20%)': [0] * len(years),
            'PAT': [0] * len(years)
        }
        
        # Dictionary to store project-level details
        project_details = {year: [] for year in years}
        
        # Aggregate schedules from all projects
        for _, project in df_projects.iterrows():
            project_name = project.get('project_name', 'Unknown')
            
            # Get schedules from project data
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
            
            # If schedules are empty, calculate them on-the-fly
            if not revenue_schedule:
                # Calculate total values
                nsa = float(project.get('net_sellable_area', 0) or 0)
                asp = float(project.get('average_selling_price', 0) or 0)
                gfa = float(project.get('gross_floor_area', 0) or 0)
                land_area = float(project.get('land_area', 0) or 0)
                const_cost = float(project.get('construction_cost_per_sqm', 0) or 0)
                land_cost = float(project.get('land_cost_per_sqm', 0) or 0)
                
                total_revenue = nsa * asp / 1e9  # Convert to billions
                total_const_cost = gfa * const_cost / 1e9
                total_land_cost = land_area * land_cost / 1e9
                sga_pct = float(project.get('sga_percentage', 0.08) or 0.08)
                total_sga = total_revenue * sga_pct
                
                # Get revenue distribution
                revenue_dist = project.get('revenue_distribution', {})
                if not isinstance(revenue_dist, dict):
                    revenue_dist = {}
                
                # Calculate schedules based on distribution
                revenue_start = int(project.get('revenue_booking_start_year', current_year))
                project_end = int(project.get('project_completion_year', current_year + 3))
                
                # If no distribution, create even split
                if not revenue_dist:
                    booking_years = list(range(revenue_start, project_end + 1))
                    if booking_years:
                        even_pct = 100.0 / len(booking_years)
                        for year in booking_years:
                            revenue_dist[str(year)] = even_pct
                
                # Calculate schedules
                for year in range(revenue_start, project_end + 1):
                    year_str = str(year)
                    year_pct = revenue_dist.get(year_str, 0) / 100.0
                    revenue_schedule[year_str] = total_revenue * year_pct
                    construction_schedule[year_str] = total_const_cost * year_pct
                    land_schedule[year_str] = total_land_cost * year_pct
                    sga_schedule[year_str] = total_sga * year_pct
            
            # Aggregate for each year
            for i, year in enumerate(years):
                year_str = str(year)
                
                # Get values for this year (already in billions)
                year_revenue = revenue_schedule.get(year_str, 0)
                year_construction = construction_schedule.get(year_str, 0)
                year_land = land_schedule.get(year_str, 0)
                year_sga = sga_schedule.get(year_str, 0)
                
                # Add to aggregated totals
                aggregated_data['Revenue'][i] += year_revenue
                aggregated_data['Construction Cost'][i] += year_construction
                aggregated_data['Land Cost'][i] += year_land
                aggregated_data['SG&A'][i] += year_sga
                
                # Store project details if there's any activity
                if year_revenue > 0 or year_construction > 0 or year_land > 0:
                    project_details[year].append({
                        'Project': project_name,
                        'Revenue': year_revenue,
                        'Construction': year_construction,
                        'Land': year_land,
                        'SG&A': year_sga
                    })
        
        # Calculate EBITDA, PBT, Tax, PAT
        for i in range(len(years)):
            aggregated_data['EBITDA'][i] = (aggregated_data['Revenue'][i] - 
                                            aggregated_data['Construction Cost'][i] - 
                                            aggregated_data['Land Cost'][i] - 
                                            aggregated_data['SG&A'][i])
            aggregated_data['PBT'][i] = aggregated_data['EBITDA'][i]  # No interest for now
            aggregated_data['Tax (20%)'][i] = max(0, aggregated_data['PBT'][i] * 0.2)
            aggregated_data['PAT'][i] = aggregated_data['PBT'][i] - aggregated_data['Tax (20%)'][i]
        
        # Create DataFrame
        df_pnl = pd.DataFrame(aggregated_data)
        
        # Display aggregated P&L table
        st.dataframe(
            df_pnl.style.format({
                'Year': '{:.0f}',
                'Revenue': '{:,.1f}B',
                'Construction Cost': '{:,.1f}B',
                'Land Cost': '{:,.1f}B',
                'SG&A': '{:,.1f}B',
                'EBITDA': '{:,.1f}B',
                'PBT': '{:,.1f}B',
                'Tax (20%)': '{:,.1f}B',
                'PAT': '{:,.1f}B'
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Show breakdown by project
        with st.expander("View Project-by-Project Breakdown"):
            selected_year = st.selectbox(
                "Select Year for Breakdown:",
                years,
                index=0,
                key="pnl_year_selector"
            )
            
            if selected_year in project_details and project_details[selected_year]:
                df_breakdown = pd.DataFrame(project_details[selected_year])
                
                # Add totals row
                totals = {
                    'Project': 'TOTAL',
                    'Revenue': df_breakdown['Revenue'].sum(),
                    'Construction': df_breakdown['Construction'].sum(),
                    'Land': df_breakdown['Land'].sum(),
                    'SG&A': df_breakdown['SG&A'].sum()
                }
                df_breakdown = pd.concat([df_breakdown, pd.DataFrame([totals])], ignore_index=True)
                
                st.dataframe(
                    df_breakdown.style.format({
                        'Revenue': '{:,.1f}B',
                        'Construction': '{:,.1f}B',
                        'Land': '{:,.1f}B',
                        'SG&A': '{:,.1f}B'
                    }).applymap(
                        lambda x: 'font-weight: bold' if x == 'TOTAL' else '',
                        subset=['Project']
                    ),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Pie chart for revenue contribution
                df_pie = df_breakdown[df_breakdown['Project'] != 'TOTAL']
                if not df_pie.empty and df_pie['Revenue'].sum() > 0:
                    fig = px.pie(
                        values=df_pie['Revenue'],
                        names=df_pie['Project'],
                        title=f"Revenue Contribution by Project - {selected_year}"
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"No project activity scheduled for {selected_year}")
    
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
    
    def render_valuation(self):
        """Render simplified valuation analysis based on RNAV and revenue forecasts"""
        st.header("Valuation Analysis")
        
        # RNAV Valuation
        st.subheader("RNAV Valuation")
        
        total_rnav = 0  # Initialize total_rnav
        if st.session_state.project_data is not None and isinstance(st.session_state.project_data, pd.DataFrame) and not st.session_state.project_data.empty:
            if 'rnav_value' in st.session_state.project_data.columns:
                total_rnav = st.session_state.project_data['rnav_value'].sum()
                st.metric("Total RNAV", f"{total_rnav/1e9:,.0f}B VND")
                
                # Show project-level RNAV breakdown
                project_rnav = st.session_state.project_data[['project_name', 'rnav_value']].copy()
                project_rnav['rnav_value'] = project_rnav['rnav_value'] / 1e9  # Convert to billions
                project_rnav = project_rnav.sort_values('rnav_value', ascending=False)
                
                st.dataframe(
                    project_rnav.style.format({'rnav_value': '{:,.0f}B'}),
                    use_container_width=True
                )
            else:
                st.info("RNAV values not available in project data")
        else:
            st.info("Sync project data to calculate RNAV")
        
        # Simple Revenue-based Valuation
        st.subheader("Revenue-Based Valuation")
        
        if 'selected_streams_data' in st.session_state and len(st.session_state.selected_streams_data) > 0:
            # Calculate simple P/S based valuation
            total_revenue = sum(s.get('revenue_2023', 0) for s in st.session_state.selected_streams_data)
            
            if total_revenue > 0:
                # Assume industry average P/S ratios
                ps_ratios = {
                    'Conservative': 1.5,
                    'Base': 2.5,
                    'Optimistic': 3.5
                }
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    value = (total_revenue * ps_ratios['Conservative']) / 1e9
                    st.metric("Conservative (1.5x P/S)", f"{value:,.0f}B VND")
                
                with col2:
                    value = (total_revenue * ps_ratios['Base']) / 1e9
                    st.metric("Base (2.5x P/S)", f"{value:,.0f}B VND")
                
                with col3:
                    value = (total_revenue * ps_ratios['Optimistic']) / 1e9
                    st.metric("Optimistic (3.5x P/S)", f"{value:,.0f}B VND")
        else:
            st.info("Select revenue streams to see revenue-based valuation")
    
    def render_research_insights(self):
        """Render AI-powered research insights"""
        st.header("Research & Analytics Insights")
        
        # Earnings Commentary Analysis
        st.subheader("Earnings Commentary Analysis")
        
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
        st.subheader("Sell-Side Research Summary")
        
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
        st.subheader("AI-Generated Investment Thesis")
        
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
            if st.button("Export to Excel", use_container_width=True):
                self.export_to_excel()
                
        with col2:
            if st.button("Generate PDF Report", use_container_width=True):
                self.generate_pdf_report()
                
        with col3:
            if st.button("Save Model State", use_container_width=True):
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
    
    def render_god_ai_assistant(self):
        """Render the God AI Assistant interface"""
        st.header("God AI Assistant")
        st.caption("Your intelligent companion for comprehensive financial analysis")
        
        # Initialize chat history if not exists
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        
        if 'current_ai_result' not in st.session_state:
            st.session_state.current_ai_result = None
        
        # Main container for conversation and results (takes most of the screen)
        main_container = st.container()
        with main_container:
            # Display area for chat history and results
            display_container = st.container(height=500)
            with display_container:
                # Show chat history
                for msg in st.session_state.chat_history:
                    if msg['role'] == 'user':
                        with st.chat_message("user"):
                            st.write(msg['content'])
                    else:
                        with st.chat_message("assistant"):
                            # Display the message
                            st.write(msg.get('content', ''))
                            
                            # If this is the most recent AI response, show the detailed results
                            if st.session_state.chat_history and msg == st.session_state.chat_history[-1] and msg['role'] == 'assistant':
                                if st.session_state.current_ai_result:
                                    self.display_ai_results_inline()
                
                # If no messages yet, show welcome message
                if not st.session_state.chat_history:
                    with st.chat_message("assistant"):
                        st.write("👋 Hello! I'm your AI Assistant for comprehensive financial analysis.")
                        st.write("")
                        st.write("I can help you with:")
                        st.write("• List and analyze all real estate projects")
                        st.write("• Rank projects by RNAV, revenue, or other metrics")
                        st.write("• Suggest ASP and construction costs using market data")
                        st.write("• Analyze growth trends and profitability")
                        st.write("• Research project details from the web")
                        st.write("• Extract projects from uploaded documents")
                        st.write("")
                        st.write("Just type your question below. For example:")
                        st.write("*'Show me all projects'*, *'What's the largest RNAV?'*, or *'Which year has the highest growth?'*")
        
        # Separator
        st.markdown("---")
        
        # Bottom section with input and controls
        bottom_container = st.container()
        with bottom_container:
            # Input area with cleaner layout
            col_input, col_send, col_upload, col_clear = st.columns([7, 1, 1, 1])
            
            with col_input:
                user_input = st.text_input(
                    "Message",
                    key="ai_chat_input",
                    placeholder="Ask me anything about your real estate projects...",
                    label_visibility="collapsed"
                )
            
            with col_send:
                if st.button("Send", type="primary", use_container_width=True):
                    if user_input:
                        self.process_ai_query(user_input)
            
            with col_upload:
                uploaded_file = st.file_uploader(
                    "Upload",
                    type=['pdf', 'xlsx', 'xls'],
                    key="ai_file_upload",
                    label_visibility="collapsed",
                    help="Upload PDF or Excel for analysis"
                )
                if uploaded_file:
                    self.process_file_upload(uploaded_file)
            
            with col_clear:
                if st.button("Clear", use_container_width=True, help="Clear conversation"):
                    st.session_state.chat_history = []
                    st.session_state.current_ai_result = None
                    st.rerun()
    
    def process_ai_query(self, query: str):
        """Process user query through God AI"""
        if not query:
            return
        
        # Prepare context
        context = {
            'selected_company': st.session_state.get('selected_company'),
            'project_data': st.session_state.get('project_data'),
            'historical_data': st.session_state.get('historical_data'),
            'assumptions': st.session_state.get('assumptions')
        }
        
        # Process query
        with st.spinner("🤔 Thinking..."):
            result = self.god_ai.process_query(query, context)
        
        # Trigger rerun to display results
        st.rerun()
    
    def process_file_upload(self, uploaded_file):
        """Process uploaded file for AI analysis"""
        st.info(f"Processing {uploaded_file.name}...")
        # This would integrate with Claude for document extraction
        self.process_ai_query(f"Extract projects from uploaded {uploaded_file.name}")
    
    def display_ai_results_inline(self):
        """Display AI results inline within the chat message"""
        if st.session_state.current_ai_result is None:
            return
        
        result = st.session_state.current_ai_result
        
        # Display based on result type
        if result['type'] == 'project_list':
            if result.get('data') is not None and not result['data'].empty:
                st.dataframe(
                    result['data'],
                    use_container_width=True
                )
        
        elif result['type'] == 'ranked_projects':
            if result.get('data') is not None:
                st.dataframe(result['data'], use_container_width=True)
            if result.get('metric'):
                st.caption(f"Ranked by: {result['metric']}")
        
        elif result['type'] == 'forecast_analysis':
            if result.get('data') is not None:
                st.dataframe(result['data'], use_container_width=True)
            if result.get('summary'):
                st.caption(f"Analysis: {result['summary']}")
        
        elif result['type'] == 'parameter_suggestions':
            suggestions = result.get('suggestions', [])
            for suggestion in suggestions:
                with st.container(border=True):
                    st.write(f"**{suggestion['project']}**")
                    st.caption(f"{suggestion['parameter']}: {suggestion['value']:,.0f} {suggestion['unit']}")
                    st.caption(f"Source: {suggestion['source']}")
        
        elif result['type'] == 'growth_analysis':
            if result.get('chart'):
                st.plotly_chart(result['chart'], use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                if result.get('peak_year'):
                    st.metric("Peak Growth Year", result['peak_year'])
                if result.get('growth_rate'):
                    st.metric("Growth Rate", f"{result['growth_rate']:.1%}")
            with col2:
                if result.get('top_project'):
                    st.metric("Top Contributor", result['top_project'])
                if result.get('revenue_impact'):
                    st.metric("Revenue Impact", f"{result['revenue_impact']:.0f}B VND")
            
            if result.get('data') is not None:
                with st.expander("View detailed data"):
                    st.dataframe(result['data'], use_container_width=True)
        
        elif result['type'] == 'metrics':
            if result.get('metrics'):
                metrics = result['metrics']
                cols = st.columns(min(len(metrics), 4))
                for i, (key, value) in enumerate(metrics.items()):
                    with cols[i % len(cols)]:
                        st.metric(key, value)
            
            if result.get('data') is not None:
                with st.expander("View detailed metrics"):
                    st.dataframe(result['data'], use_container_width=True)
        
        elif result['type'] == 'project_details':
            if result.get('data') is not None:
                st.dataframe(result['data'], use_container_width=True)
        
        # Handle chart results
        elif result['type'] == 'chart':
            # Display the chart
            if result.get('chart'):
                st.plotly_chart(result['chart'], use_container_width=True)
            else:
                st.warning("Chart data not available. Please ensure P&L schedule is calculated for the project.")
            
            # Display summary data if available
            if result.get('data') is not None and not result['data'].empty:
                with st.expander("View Project Summary"):
                    st.dataframe(result['data'], use_container_width=True)
        
        # Handle comparison results
        elif result['type'] == 'comparison':
            # Display comparison table
            if result.get('data') is not None and not result['data'].empty:
                st.dataframe(result['data'], use_container_width=True)
        
        # Handle all metric-specific result types
        elif result['type'].startswith('metric_'):
            # This handles metric_revenue, metric_profit, metric_trends, etc.
            if result.get('data') is not None and not result['data'].empty:
                st.dataframe(result['data'], use_container_width=True)
            
            # If there's a chart (for trends), display it
            if result.get('chart'):
                st.plotly_chart(result['chart'], use_container_width=True)
        
        elif result['type'] == 'error':
            st.error(result.get('message', 'An error occurred'))
        
        elif result['type'] == 'info':
            st.info(result.get('message', 'Information'))
    
    def display_ai_results(self):
        """Display AI query results in the results panel"""
        
        if st.session_state.current_ai_result is None:
            st.info("Results will appear here. Try asking: 'Show all projects' or 'What's the largest RNAV?'")
            return
        
        result = st.session_state.current_ai_result
        
        # Display based on result type
        if result['type'] == 'project_list':
            st.markdown("#### 📋 Project List")
            
            if result.get('data') is not None and not result['data'].empty:
                st.dataframe(
                    result['data'],
                    use_container_width=True,
                    height=300
                )
            else:
                st.warning(result.get('message', 'No data available'))
        
        elif result['type'] == 'ranked_projects':
            st.markdown(f"#### 🏆 {result.get('message', 'Ranked Projects')}")
            
            if result.get('data') is not None:
                st.dataframe(
                    result['data'],
                    use_container_width=True,
                    height=300
                )
            
            # Display metric used
            if result.get('metric'):
                st.info(f"Ranked by: {result['metric']}")
        
        elif result['type'] == 'parameter_suggestions':
            st.markdown("#### 💡 AI Suggestions")
            
            suggestions = result.get('suggestions', [])
            for suggestion in suggestions:
                with st.container(border=True):
                    st.markdown(f"**{suggestion['project']}**")
                    st.caption(f"{suggestion['parameter']}: {suggestion['value']:,.0f} {suggestion['unit']}")
                    st.caption(f"Source: {suggestion['source']}")
        
        elif result['type'] == 'growth_analysis':
            st.markdown("#### Growth Analysis")
            
            # Display chart if available
            if result.get('chart'):
                st.plotly_chart(result['chart'], use_container_width=True)
            
            # Display metrics
            col1, col2 = st.columns(2)
            with col1:
                if result.get('peak_year'):
                    st.metric("Peak Growth Year", result['peak_year'])
                if result.get('growth_rate'):
                    st.metric("Growth Rate", f"{result['growth_rate']:.1%}")
            with col2:
                if result.get('top_project'):
                    st.metric("Top Contributor", result['top_project'])
                if result.get('revenue_impact'):
                    st.metric("Revenue Impact", f"{result['revenue_impact']:.0f}B VND")
            
            # Display data table if available
            if result.get('data') is not None:
                st.dataframe(result['data'], use_container_width=True)
        
        elif result['type'] == 'metrics':
            st.markdown("#### Portfolio Metrics")
            
            if result.get('data') is not None:
                st.dataframe(result['data'], use_container_width=True)
            
            # Display key metrics in cards
            if result.get('metrics'):
                metrics = result['metrics']
                cols = st.columns(len(metrics))
                for i, (key, value) in enumerate(metrics.items()):
                    with cols[i % len(cols)]:
                        st.metric(key, value)
        
        elif result['type'] == 'project_details':
            st.markdown(f"#### 📄 {result.get('message', 'Project Details')}")
            
            if result.get('data') is not None:
                st.dataframe(result['data'], use_container_width=True)
        
        elif result['type'] == 'project_summary':
            st.markdown(f"#### 📋 {result.get('message', 'Project Summary')}")
            
            if result.get('data') is not None:
                st.dataframe(result['data'], use_container_width=True, height=400)
        
        # Handle comparison results
        elif result['type'] == 'comparison':
            st.markdown("#### 🔍 Project Comparison")
            
            # Display comparison table
            if result.get('data') is not None and not result['data'].empty:
                st.dataframe(result['data'], use_container_width=True, height=500)
        
        # Handle chart results
        elif result['type'] == 'chart':
            st.markdown("#### Financial Chart")
            
            # Display the chart
            if result.get('chart'):
                st.plotly_chart(result['chart'], use_container_width=True)
            else:
                st.warning("Chart data not available. Please ensure P&L schedule is calculated for the project.")
            
            # Display summary data if available
            if result.get('data') is not None and not result['data'].empty:
                with st.expander("View Project Summary"):
                    st.dataframe(result['data'], use_container_width=True)
        
        # Handle all metric-specific result types
        elif result['type'].startswith('metric_'):
            # Extract the metric type name for display
            metric_name = result['type'].replace('metric_', '').replace('_', ' ').title()
            st.markdown(f"#### {metric_name} Analysis")
            
            # Display the message if available
            if result.get('message'):
                # Parse out just the title part (after the emoji)
                message_lines = result['message'].split('\n')
                for line in message_lines:
                    if '**Revenue Analysis**' in line or '**Profit Analysis**' in line or '**Financial' in line:
                        st.write(line)
                        break
            
            # Display the data
            if result.get('data') is not None and not result['data'].empty:
                st.dataframe(result['data'], use_container_width=True, height=400)
            else:
                st.warning("No data available for this metric")
            
            # If there's a chart (for trends), display it
            if result.get('chart'):
                st.plotly_chart(result['chart'], use_container_width=True)
        
        elif result['type'] == 'error':
            st.error(result.get('message', 'An error occurred'))
        
        elif result['type'] == 'info':
            st.info(result.get('message', 'Information'))
        
        elif result['type'] == 'general_response':
            st.markdown("#### 💬 AI Response")
            st.write(result.get('message', ''))
        
        else:
            # Default display
            st.write(result.get('message', 'Processing complete'))
            if result.get('data') is not None:
                st.dataframe(result['data'], use_container_width=True)

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