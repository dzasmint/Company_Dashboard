#%%
"""
Real Estate Financial Model with AI-Powered Analysis

A comprehensive financial modeling tool for real estate companies featuring:
- AI-powered document analysis for business segments and projects
- Vectorized calculations for better performance
- Modular tab architecture for easier maintenance
- Claude AI integration for intelligent data extraction
- MongoDB integration for persistent storage
- Real-time project pipeline management
"""

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

# Import tab components
from tabs.historical_analysis import HistoricalAnalysisTab
from tabs.ai_discovery import AIDiscoveryTab
from tabs.assumptions import AssumptionsTab
from tabs.project_pipeline import ProjectPipelineTab
from tabs.revenue_forecast import RevenueForecastTab
from tabs.god_ai_assistant import GodAIAssistantTab

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

from utils.perplexity_utils import (
    get_project_basic_info_perplexity,
    analyze_earnings_commentary,
    parse_sell_side_reports
)
from utils.project_pipeline_manager import ProjectPipelineManager
from utils.claude_project_extractor import ClaudeProjectExtractor
from utils.god_ai_assistant import GodAIAssistant

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
    """Real Estate Financial Model with AI-powered analysis and modular architecture"""
    
    def __init__(self):
        """Initialize the refactored financial model"""
        self.db_client = None
        self.mongo_initialized = False
        self.god_ai = GodAIAssistant()
        
        # Initialize tab components
        self.historical_tab = HistoricalAnalysisTab(self)
        self.ai_discovery_tab = AIDiscoveryTab(self)
        self.assumptions_tab = AssumptionsTab(self)
        self.project_pipeline_tab = ProjectPipelineTab(self)
        self.revenue_forecast_tab = RevenueForecastTab(self)
        self.god_ai_tab = GodAIAssistantTab(self)
        
        self.initialize_session_state()
        self.setup_sidebar()
    
    def initialize_session_state(self):
        """Initialize session state variables"""
        defaults = {
            'model_data': {},
            'assumptions': self.get_default_assumptions(),
            'forecast_years': 5,
            'selected_company': None,
            'historical_data': None,
            'project_data': None,
            'loading_projects': False,
            'active_tab': 0,
            'editing_in_progress': False,
            'preserve_tab': False
        }
        
        for key, default_value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default_value
    
    def get_default_assumptions(self):
        """Get default modeling assumptions"""
        return {
            'revenue_growth': {
                'presales': 0.15,
                'handover': 0.12,
                'recurring': 0.08
            },
            'margins': {
                'gross_margin': 0.35,
                'ebitda_margin': 0.28,
                'net_margin': 0.20
            },
            'costs': {
                'sga_pct': 0.08,
                'interest_rate': 0.08,
                'tax_rate': 0.20
            },
            'balance_sheet': {
                'receivables_days': 90,
                'inventory_days': 365,
                'payables_days': 60,
                'capex_pct_revenue': 0.02
            },
            'valuation': {
                'wacc': 0.11,
                'terminal_growth': 0.03,
                'target_pe': 12,
                'target_pb': 1.5
            }
        }
    
    def setup_sidebar(self):
        """Setup sidebar for company selection and controls"""
        st.sidebar.title("Real Estate Model")
        st.sidebar.caption("🏢 AI-Powered Financial Analysis")
        
        # Company selection with callback
        def on_company_change():
            if 'company_selector_refactored' not in st.session_state:
                return
            
            selected = st.session_state.company_selector_refactored
            if selected and selected != "Select a company":
                # Extract ticker - handle both "TICKER" and "TICKER - Company Name" formats
                if " - " in selected:
                    ticker = selected.split(" - ")[0].strip()
                else:
                    ticker = selected.strip()
                    
                if st.session_state.get('selected_company') != ticker:
                    # Clean state for new company
                    self._reset_company_state(ticker)
        
        # Load all companies
        companies = self.load_all_companies()
            
        if companies:
            # Add default option
            companies = ["Select a company"] + companies
            current_index = self._get_current_company_index(companies)
            
            selected = st.sidebar.selectbox(
                "Select Ticker",
                companies,
                index=current_index,
                key="company_selector_refactored",
                on_change=on_company_change,
                help="Select a company ticker to analyze"
            )
        
        # Forecast parameters
        st.sidebar.markdown("---")
        st.sidebar.subheader("Forecast Settings")
        st.session_state.forecast_years = st.sidebar.slider(
            "Forecast Years",
            min_value=3,
            max_value=10,
            value=st.session_state.get('forecast_years', 5),
            help="Number of years to forecast"
        )
        
        # Data management controls
        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 Data Management")
        
        if st.sidebar.button("🔄 Sync Project Data"):
            self.sync_project_data()
        
        if st.sidebar.button("📈 Load Financial Data"):
            self.load_and_cache_financial_data()
        
        # Display data status
        self._display_data_status()
        
        # Performance metrics
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚡ Performance")
        if 'last_calculation_time' in st.session_state:
            st.sidebar.metric("Last Calc Time", f"{st.session_state.last_calculation_time:.2f}s")
    
    def _reset_company_state(self, ticker):
        """Reset session state for new company selection and load data"""
        # Clear previous data
        st.session_state.historical_data = None
        st.session_state.project_data = None
        
        # Set new company
        st.session_state.selected_company = ticker
        
        # Auto-load historical data
        with st.spinner(f"Loading data for {ticker}..."):
            data = self.load_historical_data_from_csv(ticker)
            if not data.empty:
                st.session_state.historical_data = data
                
        # Auto-sync project data
        self.sync_project_data()
    
    def _get_current_company_index(self, companies):
        """Get current company index for selectbox"""
        current_index = 0
        selected_company = st.session_state.get('selected_company')
        
        if selected_company:
            for i, company in enumerate(companies):
                # Check if company starts with the ticker
                if company.startswith(f"{selected_company} - ") or company == selected_company:
                    current_index = i
                    break
        
        return current_index
    
    def _display_data_status(self):
        """Display current data status in sidebar"""
        st.sidebar.markdown("**Data Status:**")
        
        # Historical data status
        if st.session_state.historical_data is not None:
            st.sidebar.success(f"📊 Historical: {len(st.session_state.historical_data)} records")
        else:
            st.sidebar.info("📊 Historical: Not loaded")
        
        # Project data status
        if st.session_state.project_data is not None:
            st.sidebar.success(f"🏗️ Projects: {len(st.session_state.project_data)} projects")
        else:
            st.sidebar.info("🏗️ Projects: Not loaded")
    
    def load_all_companies(self):
        """Load all companies from the dataset"""
        @st.cache_data(ttl=300)  # Cache for 5 minutes
        def _load_all_companies():
            try:
                # Load from CSV files
                fa_df = pd.read_csv('data/FA_A_processed.csv')
                classification_df = pd.read_excel('data/Classification.xlsx')
                
                # Get unique tickers
                if 'TICKER' in fa_df.columns and 'Ticker' in classification_df.columns:
                    # Merge to get company names
                    merged = fa_df.merge(
                        classification_df[['Ticker', 'Company_Name']], 
                        left_on='TICKER', 
                        right_on='Ticker', 
                        how='left'
                    )
                    
                    # Get unique companies
                    unique_companies = merged.drop_duplicates(subset=['TICKER'])
                    
                    # Format as ticker - name
                    companies = []
                    for _, row in unique_companies.iterrows():
                        ticker = row['TICKER']
                        name = row.get('Company_Name', ticker)
                        if pd.notna(name) and name != ticker:
                            companies.append(f"{ticker} - {name}")
                        else:
                            companies.append(ticker)
                    
                    return sorted(companies)
                else:
                    # Fallback to just tickers
                    tickers = fa_df['TICKER'].unique() if 'TICKER' in fa_df.columns else []
                    return sorted(tickers)
                    
            except Exception as e:
                st.error(f"Error loading companies: {e}")
                # Try simple fallback
                try:
                    fa_df = pd.read_csv('data/FA_A_processed.csv')
                    if 'TICKER' in fa_df.columns:
                        return sorted(fa_df['TICKER'].unique().tolist())
                except:
                    pass
                return []
        
        return _load_all_companies()
    
    def load_real_estate_companies(self):
        """Load real estate companies with caching"""
        @st.cache_data(ttl=300)  # Cache for 5 minutes
        def _load_companies():
            try:
                # Load from CSV files with real estate sector filter
                fa_df = pd.read_csv('data/FA_A_processed.csv')
                classification_df = pd.read_excel('data/Classification.xlsx')
                
                # Merge to get sector information
                if 'TICKER' in fa_df.columns and 'Ticker' in classification_df.columns:
                    merged = fa_df.merge(
                        classification_df[['Ticker', 'Company_Name', 'Sector']], 
                        left_on='TICKER', 
                        right_on='Ticker', 
                        how='left'
                    )
                    
                    # Filter for real estate companies
                    real_estate_filter = merged['Sector'].str.contains('Real Estate', case=False, na=False)
                    real_estate_companies = merged[real_estate_filter]
                    
                    # Create company list
                    companies = []
                    for _, row in real_estate_companies.iterrows():
                        ticker = row.get('TICKER', row.get('Ticker', ''))
                        name = row.get('Company_Name', f'Company {ticker}')
                        if ticker and name:
                            companies.append(f"{ticker} - {name}")
                    
                    return sorted(list(set(companies)))
                
                return []
            except Exception as e:
                st.sidebar.error(f"Error loading companies: {str(e)}")
                return []
        
        return _load_companies()
    
    def sync_project_data(self):
        """Sync project data from MongoDB with progress tracking"""
        selected_ticker = st.session_state.get('selected_company')
        
        if not selected_ticker:
            st.sidebar.warning("⚠️ Please select a company first")
            return
            
        with st.spinner(f"Syncing project data for {selected_ticker}..."):
            start_time = time.time()
            
            try:
                # Load ALL projects first
                df_all_projects = load_projects_data()
                
                if not df_all_projects.empty:
                    # Filter for selected ticker
                    if 'ticker' in df_all_projects.columns:
                        df_projects = df_all_projects[df_all_projects['ticker'] == selected_ticker].copy()
                    else:
                        # If no ticker column, return empty
                        df_projects = pd.DataFrame()
                    
                    if not df_projects.empty:
                        st.session_state.project_data = df_projects
                        
                        # Calculate sync time
                        sync_time = time.time() - start_time
                        st.session_state.last_calculation_time = sync_time
                        
                        st.sidebar.success(f"✅ Synced {len(df_projects)} projects for {selected_ticker} ({sync_time:.2f}s)")
                    else:
                        st.session_state.project_data = pd.DataFrame()
                        st.sidebar.info(f"No projects found for {selected_ticker}")
                else:
                    st.session_state.project_data = pd.DataFrame()
                    st.sidebar.warning("⚠️ No projects found in MongoDB")
                    
            except Exception as e:
                st.session_state.project_data = pd.DataFrame()
                st.sidebar.error(f"❌ Error syncing data: {str(e)}")
    
    def load_and_cache_financial_data(self):
        """Load and cache financial data"""
        selected_company = st.session_state.get('selected_company')
        if not selected_company:
            st.sidebar.warning("Please select a company first")
            return
        
        with st.spinner(f"Loading financial data for {selected_company}..."):
            start_time = time.time()
            
            try:
                # Load historical data
                historical_data = self.load_historical_data_from_csv(selected_company)
                
                if not historical_data.empty:
                    st.session_state.historical_data = historical_data
                    
                    # Calculate load time
                    load_time = time.time() - start_time
                    st.session_state.last_calculation_time = load_time
                    
                    st.sidebar.success(f"✅ Loaded data ({load_time:.2f}s)")
                else:
                    st.sidebar.warning(f"⚠️ No data found for {selected_company}")
                    
            except Exception as e:
                st.sidebar.error(f"❌ Error loading data: {str(e)}")
    
    def load_historical_data_from_csv(self, ticker):
        """Load historical data from CSV files with vectorized operations"""
        @st.cache_data(ttl=300, show_spinner=False)
        def _load_data(ticker):
            try:
                # Load financial statements
                fa_df = pd.read_csv('data/FA_A_processed.csv')
                
                # Debug: Show unique tickers available
                # st.sidebar.info(f"Loading data for ticker: {ticker}")
                
                # Filter for specific ticker using vectorized operation
                ticker_data = fa_df[fa_df['TICKER'] == ticker].copy()
                
                if ticker_data.empty:
                    # Debug to see why no data found
                    available_tickers = fa_df['TICKER'].unique()[:10]  # Show first 10
                    st.sidebar.warning(f"No data found for {ticker}. Sample tickers: {', '.join(available_tickers)}")
                    return pd.DataFrame()
                
                # Set date as index and convert to datetime
                if 'DATE' in ticker_data.columns:
                    ticker_data['DATE'] = pd.to_datetime(ticker_data['DATE'], errors='coerce')
                    ticker_data['YEAR'] = ticker_data['DATE'].dt.year
                    
                    # Pivot to get years as index and metrics as columns
                    pivot_data = ticker_data.pivot_table(
                        index='YEAR',
                        values=[col for col in ticker_data.columns if col not in ['TICKER', 'DATE', 'YEAR']],
                        aggfunc='first'
                    )
                    
                    # Flatten column names
                    pivot_data.columns = [col[0] if isinstance(col, tuple) else col for col in pivot_data.columns]
                    
                    # st.sidebar.success(f"Loaded {len(pivot_data)} years of data for {ticker}")
                    return pivot_data.sort_index()
                
                return pd.DataFrame()
                
            except Exception as e:
                st.error(f"Error loading data for {ticker}: {str(e)}")
                return pd.DataFrame()
        
        return _load_data(ticker)
    
    def generate_revenue_forecast(self):
        """Generate revenue forecast with vectorized calculations"""
        current_year = datetime.now().year
        forecast_years = st.session_state.get('forecast_years', 5)
        years = list(range(current_year + 1, current_year + forecast_years + 1))
        
        return {
            'years': years,
            'current_year': current_year,
            'forecast_years': forecast_years
        }
    
    def render_main_interface(self):
        """Render the main interface with optimized tab structure"""
        st.title("🏢 Real Estate Financial Model - Refactored")
        st.caption("⚡ Optimized with vectorized calculations and modular architecture")
        
        # Main navigation tabs
        tab_names = [
            "📊 Historical Analysis",
            "🤖 AI Discovery", 
            "⚙️ Assumptions",
            "🏗️ Project Pipeline",
            "💰 Revenue Forecast",
            "📈 Valuation",
            "📋 Research Insights",
            "📁 Export",
            "🧠 God AI Assistant"
        ]
        
        # Use session state to preserve active tab
        if 'active_tab_refactored' not in st.session_state:
            st.session_state.active_tab_refactored = 0
        
        # Create tabs
        tabs = st.tabs(tab_names)
        
        # Render tab content
        with tabs[0]:
            self.historical_tab.render()
        
        with tabs[1]:
            self.ai_discovery_tab.render()
        
        with tabs[2]:
            self.assumptions_tab.render()
        
        with tabs[3]:
            self.project_pipeline_tab.render()
        
        with tabs[4]:
            self.revenue_forecast_tab.render()
        
        with tabs[5]:
            self.render_valuation_placeholder()
        
        with tabs[6]:
            self.render_research_insights_placeholder()
        
        with tabs[7]:
            self.render_export_placeholder()
        
        with tabs[8]:
            self.god_ai_tab.render()
    
    def render_valuation_placeholder(self):
        """Placeholder for valuation tab"""
        st.header("📈 Valuation Analysis")
        st.info("🚧 Valuation module will be refactored in next iteration")
        
        # Basic valuation metrics
        if st.session_state.project_data is not None:
            df_projects = st.session_state.project_data
            
            # Simple RNAV calculation
            total_rnav = df_projects['rnav_value'].fillna(0).sum() if 'rnav_value' in df_projects.columns else 0
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total RNAV", f"{total_rnav/1e9:.1f}B VND")
            
            with col2:
                total_projects = len(df_projects)
                st.metric("Total Projects", total_projects)
            
            with col3:
                avg_rnav = total_rnav / total_projects if total_projects > 0 else 0
                st.metric("Avg RNAV per Project", f"{avg_rnav/1e9:.2f}B VND")
    
    def render_research_insights_placeholder(self):
        """Placeholder for research insights"""
        st.header("📋 Research Insights")
        st.info("🚧 Research insights module will be refactored in next iteration")
    
    def render_export_placeholder(self):
        """Placeholder for export functionality"""
        st.header("📁 Export & Reports")
        st.info("🚧 Export functionality will be refactored in next iteration")
    
    # Placeholder methods for tab compatibility
    def extract_projects_with_claude(self, uploaded_file, financial_text):
        """Placeholder for Claude project extraction"""
        return {"success": False, "message": "Claude extraction not implemented in refactored version"}
    
    def research_additional_projects_with_perplexity(self, company_ticker):
        """Placeholder for Perplexity research"""
        return {"success": False, "message": "Perplexity research not implemented in refactored version"}
    
    def merge_discovered_projects(self):
        """Placeholder for project merging"""
        return {"success": False, "message": "Project merging not implemented in refactored version"}
    
    def load_discovery_history(self, company_ticker):
        """Placeholder for discovery history"""
        return []
    
    def save_new_project(self, project_data):
        """Placeholder for saving new projects"""
        return {"success": False, "message": "Save new project not implemented in refactored version"}
    
    def render_individual_project_editor(self, project_name, df_projects):
        """Placeholder for individual project editor"""
        st.info(f"🚧 Individual project editor for '{project_name}' will be refactored in next iteration")


def main():
    """Main application entry point"""
    try:
        # Initialize the refactored model
        model = RealEstateFinancialModel()
        
        # Render the main interface
        model.render_main_interface()
        
    except Exception as e:
        st.error(f"Application Error: {str(e)}")
        st.exception(e)


if __name__ == "__main__":
    main()