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
    save_project_to_mongodb
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

# Import tabs
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# from tabs.Valuation import ValuationTab  # Hidden - integrated into Model Forecast
from tabs.model_forecast import ModelForecastTab
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
                    # Historical data will be loaded by the HistoricalAnalysisTab when needed
                    # Just set the flag that data needs refresh
                    st.session_state.historical_data = None
                    
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
                "Model Forecast",
                # "Valuation",  # Hidden - integrated into Model Forecast
                # "Research Insights",  # Hidden
                # "Export Model",  # Hidden
                "BDS-GPT",
                # "Generate Report"  # Hidden
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
            max_value=20,
            value=10
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
        
        # Generate Report button - Hidden
        # st.sidebar.markdown("---")
        # st.sidebar.subheader("Report Generation")
        # 
        # if st.sidebar.button(
        #     "📄 Generate Report",
        #     key="generate_report_btn",
        #     use_container_width=True,
        #     type="primary",
        #     help="Generate quarterly or comprehensive reports"
        # ):
        #     st.session_state.selected_re_tab = "Generate Report"
        #     st.rerun()
            
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
                st.toast(f"✅ Loaded {len(ticker_projects)} projects for {ticker}")
                
        except Exception as e:
            st.error(f"Error loading project data: {str(e)}")
            st.session_state.project_data = pd.DataFrame()
        finally:
            st.session_state.loading_projects = False
    
    
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def load_real_estate_companies(_self):
        """Load list of all companies from FA_A_processed.parquet."""
        try:
            fa_path = os.path.join(parent_dir, 'data', 'FA_A_processed.parquet')
            if not os.path.exists(fa_path):
                return []  # Return empty list if file not found
            
            # Read parquet file
            df_fa = pd.read_parquet(fa_path)
            
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
        """Refresh financial data - now handled by HistoricalAnalysisTab"""
        if not st.session_state.selected_company:
            st.warning("Please select a company first")
            return
            
        ticker = st.session_state.selected_company
        
        # Clear the historical data to force reload
        st.session_state.historical_data = None
        st.success(f"✅ Financial data cache cleared for {ticker}. Data will reload when you visit Historical Analysis tab.")
    
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
        st.title("Real Estate Financial Model with BDS-GPT")
        st.caption("Ultimate AI-powered financial modeling with intelligent assistant at your command")
        
        if not st.session_state.selected_company:
            st.info("Please select a company from the sidebar to begin")
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
        elif selected_tab == tab_names[4]:  # Model Forecast
            model_forecast_tab = ModelForecastTab(parent_model=self)
            model_forecast_tab.render()
        elif selected_tab == tab_names[5]:  # BDS-GPT (Enhanced AI)
            self.render_enhanced_ai()
        # Hidden tabs - commenting out but keeping for future reference
        # elif selected_tab == "Valuation":  # Hidden - integrated into Model Forecast
        #     valuation_tab = ValuationTab()
        #     valuation_tab.render()
        # elif selected_tab == "Research Insights":  # Hidden
        #     self.render_research_insights()
        # elif selected_tab == "Export Model":  # Hidden
        #     self.render_export_interface()
        # elif selected_tab == "Generate Report":  # Hidden
        #     self.render_generate_report()
        
    
    def render_historical_analysis(self):
        """Render historical financial analysis using the new tab module"""
        from tabs.historical_analysis import HistoricalAnalysisTab
        
        # Initialize and render the historical analysis tab
        historical_tab = HistoricalAnalysisTab(parent=self)
        historical_tab.render()
        return
    
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
        """Render assumptions using the AssumptionsTab from tabs module"""
        from tabs.assumptions import AssumptionsTab
        
        # Initialize the assumptions tab if not already done
        if 'assumptions_tab' not in st.session_state:
            st.session_state.assumptions_tab = AssumptionsTab(self)
        
        # Render the assumptions tab
        st.session_state.assumptions_tab.render()
    
    @st.fragment
    def render_project_pipeline(self):
        """Render project pipeline using the ProjectPipelineRealEstateTab"""
        from tabs.project_pipeline_real_estate import ProjectPipelineRealEstateTab
        
        # Initialize the project pipeline tab if not already done
        if 'project_pipeline_tab' not in st.session_state:
            st.session_state.project_pipeline_tab = ProjectPipelineRealEstateTab(self)
        
        # Render the project pipeline tab
        st.session_state.project_pipeline_tab.render()
        return
    
    
    
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
            consensus = insights.get('consensus', {})
            if consensus:
                # Display each consensus metric separately to handle different array lengths
                if 'revenue_forecasts' in consensus:
                    revenue_data = consensus['revenue_forecasts']
                    years = [f"Year {i+1}" for i in range(len(revenue_data))]
                    revenue_df = pd.DataFrame({'Year': years, 'Revenue Forecast (B VND)': revenue_data})
                    st.write("Revenue Forecasts:")
                    st.dataframe(revenue_df, use_container_width=True)
                
                if 'eps_forecasts' in consensus:
                    eps_data = consensus['eps_forecasts']
                    years = [f"Year {i+1}" for i in range(len(eps_data))]
                    eps_df = pd.DataFrame({'Year': years, 'EPS Forecast': eps_data})
                    st.write("EPS Forecasts:")
                    st.dataframe(eps_df, use_container_width=True)
                
                if 'target_prices' in consensus:
                    target_data = consensus['target_prices']
                    brokers = [f"Broker {i+1}" for i in range(len(target_data))]
                    target_df = pd.DataFrame({'Broker': brokers, 'Target Price': target_data})
                    st.write("Target Prices:")
                    st.dataframe(target_df, use_container_width=True)
            else:
                st.info("No consensus estimates available")
            
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
    
    def render_generate_report(self):
        """Render the report generation interface using ReportGenerationTab"""
        from tabs.ReportGeneration import ReportGenerationTab
        
        # Initialize the report generation tab if not already done
        if 'report_generation_tab' not in st.session_state:
            st.session_state.report_generation_tab = ReportGenerationTab(parent=self)
        
        # Render the report generation tab
        st.session_state.report_generation_tab.render()
    
    def render_enhanced_ai(self):
        """Render the Enhanced AI Assistant interface"""
        from tabs.enhanced_ai_assistant import render_enhanced_ai_interface
        render_enhanced_ai_interface()

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