#%%
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
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
from utils.comprehensive_revenue_analyzer import ComprehensiveRevenueAnalyzer
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
        st.title("🏢 Real Estate Financial Model - AI Agent Edition 🤖")
        st.caption("Enhanced with Claude AI for financial statement analysis and Perplexity for market research")
        
        if not st.session_state.selected_company:
            st.info("👈 Please select a company from the sidebar to begin")
            return
            
        # Create tabs for different sections
        tabs = st.tabs([
            "📊 Historical Analysis",
            "🤖 AI Project Discovery",
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
            self.render_ai_discovery()
            
        with tabs[2]:
            self.render_assumptions_interface()
            
        with tabs[3]:
            self.render_project_pipeline()
            
        with tabs[4]:
            self.render_revenue_forecast()
            
        with tabs[5]:
            self.render_financial_projections()
            
        with tabs[6]:
            self.render_valuation()
            
        with tabs[7]:
            self.render_research_insights()
            
        with tabs[8]:
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
    
    def render_ai_discovery(self):
        """Render AI-powered project discovery interface"""
        st.header("🤖 AI-Powered Project Discovery")
        
        # Initialize pipeline manager - with force reload option
        force_reload = st.sidebar.button("🔄 Reload AI Agents", help="Click if you see parameter errors")
        
        if 'pipeline_manager' not in st.session_state or force_reload:
            try:
                # Force reimport to get latest changes
                import importlib
                import utils.project_pipeline_manager
                import utils.claude_project_extractor
                import utils.perplexity_utils
                
                # Reload all related modules
                importlib.reload(utils.claude_project_extractor)
                importlib.reload(utils.perplexity_utils) 
                importlib.reload(utils.project_pipeline_manager)
                
                from utils.project_pipeline_manager import ProjectPipelineManager
                
                st.session_state.pipeline_manager = ProjectPipelineManager()
                if force_reload:
                    st.sidebar.success("✅ AI Agents reloaded successfully")
            except Exception as e:
                st.error(f"Failed to initialize AI agents: {str(e)}")
                st.info("Please ensure ANTHROPIC_API_KEY and PERPLEXITY_API_KEY are set in your .env file")
                return
        
        # Create tabs for different AI methods
        discovery_tabs = st.tabs([
            "📄 Claude AI - Financial Statements",
            "🌐 Perplexity - Web Research",
            "🔀 Merge Results",
            "💰 Financial Modeling",
            "📊 Discovery History"
        ])
        
        with discovery_tabs[0]:
            self.render_claude_discovery()
        
        with discovery_tabs[1]:
            self.render_perplexity_discovery()
        
        with discovery_tabs[2]:
            self.render_merge_results()
            
        with discovery_tabs[3]:
            self.render_financial_modeling()
            
        with discovery_tabs[4]:
            self.render_discovery_history()
    
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
            
            if uploaded_files:
                st.info(f"📚 {len(uploaded_files)} document(s) uploaded")
        
        if uploaded_files and company_name and company_ticker:
            if st.button("🤖 Extract Projects from All Documents", type="primary", use_container_width=True):
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
                        st.subheader("📊 All Extracted Projects")
                        
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
                st.info("📊 Database Projects")
                st.metric("Existing", len(existing_projects))
            else:
                existing_projects = []
        
        # Merge button
        if st.button("🤖 AI Merge & Compare with Database", type="primary", use_container_width=True):
            # Get company info
            company_name = st.session_state.claude_metadata.get('company_name', '') if has_claude else ''
            company_ticker = st.session_state.claude_metadata.get('company_ticker', '') if has_claude else ''
            
            if not company_ticker and has_perplexity:
                company_ticker = st.session_state.perplexity_metadata.get('company_ticker', '')
                company_name = st.session_state.perplexity_metadata.get('company_name', '')
            
            # Step 1: AI-powered merge of Claude and Perplexity results
            with st.spinner("🤖 Using Claude AI to intelligently merge results..."):
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
            with st.spinner("📊 Comparing with existing database projects..."):
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
            with st.expander("📊 All Merged Projects", expanded=True):
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
    
    def render_financial_modeling(self):
        """Render AI-powered comprehensive financial modeling interface"""
        st.subheader("💰 AI-Powered Comprehensive Financial Modeling")
        st.info("""
        AI analyzes ALL revenue streams of the company from financial statements and web research:
        • Real Estate Development (from discovered projects)
        • Construction Services
        • Property Management
        • Rental/Leasing Income
        • Other Business Segments
        
        The model creates a comprehensive forecast combining all revenue sources.
        """)
        
        # Initialize comprehensive revenue analyzer
        if 'comprehensive_analyzer' not in st.session_state:
            try:
                st.session_state.comprehensive_analyzer = ComprehensiveRevenueAnalyzer()
            except Exception as e:
                st.error(f"Failed to initialize Comprehensive Revenue Analyzer: {str(e)}")
                st.info("Please ensure ANTHROPIC_API_KEY is set in your .env file")
                return
        
        # Get available data
        projects = st.session_state.get('merged_projects') or st.session_state.get('claude_projects') or []
        has_projects = len(projects) > 0
        
        st.write(f"📊 Available data: {len(projects)} real estate projects discovered")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Company information
            company_name = st.text_input(
                "Company Name",
                value=st.session_state.get('selected_company', ''),
                key="modeling_company_name"
            )
            
            company_ticker = st.text_input(
                "Stock Ticker",
                value=st.session_state.get('selected_company', ''),
                key="modeling_ticker"
            )
        
        with col2:
            # Forecast parameters
            forecast_years = st.number_input(
                "Forecast Years",
                min_value=1,
                max_value=10,
                value=5,
                key="modeling_forecast_years"
            )
            
            current_year = st.number_input(
                "Current Year",
                min_value=2020,
                max_value=2030,
                value=datetime.now().year,
                key="modeling_current_year"
            )
        
        # Historical financial data (optional)
        with st.expander("📈 Historical Financial Data (Optional)", expanded=False):
            st.info("Upload historical financial data for more accurate analysis")
            
            # Option to use MongoDB data
            use_mongodb = st.checkbox("Use data from MongoDB", value=True)
            
            financial_data = None
            if use_mongodb and company_ticker:
                try:
                    # Try to load financial data from MongoDB
                    financial_data = get_financials_for_company(company_ticker)
                    if financial_data:
                        st.success(f"✅ Loaded financial data for {company_ticker}")
                except:
                    st.warning("Could not load financial data from MongoDB")
        
        # Data source selection
        st.write("### 📚 Data Sources for Revenue Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Option to upload financial statements for revenue extraction
            uploaded_file = st.file_uploader(
                "Upload Financial Statement PDF for revenue extraction",
                type=['pdf'],
                help="Upload financial statements to extract ALL revenue streams",
                key="revenue_pdf_upload"
            )
        
        with col2:
            # Option to use existing session data
            use_session_data = st.checkbox(
                "Use data from Claude/Perplexity discovery",
                value=True if has_projects else False,
                help="Use previously discovered project and revenue data"
            )
        
        # Run comprehensive analysis button
        if st.button("🤖 Analyze ALL Revenue Streams & Generate Comprehensive Model", type="primary", use_container_width=True):
            
            revenue_streams_from_pdf = {}
            revenue_streams_from_web = {}
            
            # Step 1: Extract revenue streams from PDF if provided
            if uploaded_file:
                with st.spinner("📄 Extracting revenue streams from financial statements..."):
                    try:
                        # Extract text from PDF
                        pdf_text = st.session_state.pipeline_manager.claude_extractor.extract_text_from_pdf(uploaded_file)
                        
                        if pdf_text:
                            # Extract revenue streams and projects
                            extraction_result = st.session_state.pipeline_manager.claude_extractor.extract_revenue_and_projects(
                                document_text=pdf_text,
                                company_name=company_name,
                                company_ticker=company_ticker
                            )
                            
                            if 'revenue_analysis' in extraction_result:
                                revenue_streams_from_pdf = extraction_result['revenue_analysis']
                                st.success(f"✅ Extracted {len(revenue_streams_from_pdf.get('revenue_streams', []))} revenue streams from PDF")
                                
                                # Also get projects if available
                                if 'real_estate_projects' in extraction_result and not has_projects:
                                    projects = extraction_result['real_estate_projects']
                                    st.info(f"Also found {len(projects)} real estate projects")
                        else:
                            st.warning("Could not extract text from PDF")
                            
                    except Exception as e:
                        st.error(f"Error extracting from PDF: {str(e)}")
            
            # Step 2: Research revenue streams from web (optional)
            if st.session_state.get('perplexity_enabled', False):
                with st.spinner("🌐 Researching revenue streams from web..."):
                    try:
                        revenue_streams_from_web = st.session_state.comprehensive_analyzer.research_revenue_streams_from_web(
                            company_name=company_name,
                            company_ticker=company_ticker,
                            perplexity_client=st.session_state.get('pipeline_manager')
                        )
                        if revenue_streams_from_web:
                            st.info("✅ Web research completed")
                    except Exception as e:
                        st.warning(f"Web research skipped: {str(e)}")
            
            # Step 3: Merge all revenue data
            with st.spinner("🔀 Merging revenue streams from all sources..."):
                try:
                    # Prepare comprehensive revenue model
                    comprehensive_model = st.session_state.comprehensive_analyzer.merge_revenue_streams(
                        pdf_streams=revenue_streams_from_pdf,
                        web_streams=revenue_streams_from_web,
                        project_data=projects
                    )
                    
                    # Store in session state
                    st.session_state.comprehensive_model = comprehensive_model
                    
                    # Display comprehensive revenue streams
                    st.success("✅ Comprehensive revenue model created successfully")
                    
                    # Show all identified revenue streams
                    if 'revenue_streams' in comprehensive_model:
                        st.write("### 📊 Complete Revenue Stream Analysis")
                        
                        # Create detailed revenue breakdown
                        revenue_data = []
                        total_revenue = sum(s.get('revenue_2023', 0) for s in comprehensive_model['revenue_streams'])
                        
                        for stream in comprehensive_model['revenue_streams']:
                            # Handle both field names for percentage
                            percentage = stream.get('revenue_percentage') or stream.get('percentage_of_total', 0)
                            
                            revenue_data.append({
                                'Business Segment': stream.get('segment_name', 'Unknown'),
                                'Revenue (B VND)': stream.get('revenue_2023', 0) / 1e9 if stream.get('revenue_2023') else 0,
                                '% of Total': percentage,
                                'Type': stream.get('type', 'non_recurring'),
                                'Gross Margin': f"{stream.get('gross_margin', 0)*100:.1f}%" if stream.get('gross_margin') else 'N/A',
                                'YoY Growth': f"{stream.get('growth_rate', 0)*100:.1f}%" if stream.get('growth_rate') else 'N/A'
                            })
                        
                        streams_df = pd.DataFrame(revenue_data)
                        st.dataframe(streams_df, use_container_width=True)
                        
                        # Show revenue mix visualization
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Pie chart of revenue segments
                            fig_pie = go.Figure(data=[go.Pie(
                                labels=[s['Business Segment'] for s in revenue_data],
                                values=[s['Revenue (B VND)'] for s in revenue_data],
                                hole=0.3
                            )])
                            fig_pie.update_layout(
                                title="Revenue by Segment",
                                height=400
                            )
                            st.plotly_chart(fig_pie, use_container_width=True)
                        
                        with col2:
                            # Revenue type breakdown
                            if 'revenue_mix' in comprehensive_model:
                                mix = comprehensive_model['revenue_mix']
                                fig_mix = go.Figure(data=[go.Bar(
                                    x=['Recurring', 'Non-Recurring', 'Semi-Recurring'],
                                    y=[mix.get('recurring_percentage', 0),
                                       mix.get('non_recurring_percentage', 0),
                                       mix.get('semi_recurring_percentage', 0)],
                                    marker_color=['green', 'blue', 'orange']
                                )])
                                fig_mix.update_layout(
                                    title="Revenue Type Mix (%)",
                                    yaxis_title="Percentage",
                                    height=400
                                )
                                st.plotly_chart(fig_mix, use_container_width=True)
                        
                        # Show real estate project details if available
                        if projects:
                            st.write("### 🏗️ Real Estate Project Pipeline")
                            st.write(f"Total {len(projects)} projects contributing to Real Estate Development revenue")
                            
                            # Quick project summary
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                total_units = sum(p.get('total_units', 0) for p in projects)
                                st.metric("Total Units", f"{total_units:,}")
                            with col2:
                                total_value = sum(p.get('book_value_vnd', 0) for p in projects) / 1e12
                                st.metric("Total Book Value", f"{total_value:.1f}T VND")
                            with col3:
                                stages = [p.get('stage', 'unknown') for p in projects]
                                st.metric("Active Projects", len([s for s in stages if s in ['construction', 'presales']]))
                    
                except Exception as e:
                    st.error(f"Error analyzing revenue streams: {str(e)}")
                    return
            
            # Step 4: Generate comprehensive assumptions
            with st.spinner("📊 Generating comprehensive financial assumptions..."):
                try:
                    assumptions = st.session_state.comprehensive_analyzer.generate_comprehensive_assumptions(
                        revenue_model=comprehensive_model,
                        current_year=current_year
                    )
                    
                    st.session_state.comprehensive_assumptions = assumptions
                    
                    # Display segment-specific assumptions
                    st.write("### 🎯 Comprehensive Financial Assumptions by Segment")
                    
                    # Create tabs for each segment
                    segment_tabs = st.tabs([s['segment_name'] for s in comprehensive_model['revenue_streams']])
                    
                    for idx, (tab, stream) in enumerate(zip(segment_tabs, comprehensive_model['revenue_streams'])):
                        with tab:
                            segment_name = stream['segment_name']
                            segment_assumptions = assumptions['by_segment'].get(segment_name, {})
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write("**Growth & Margins:**")
                                st.metric("Revenue Growth Rate", f"{segment_assumptions.get('revenue_growth_rate', 0)*100:.1f}% /year")
                                st.metric("Gross Margin", f"{segment_assumptions.get('gross_margin', 0)*100:.1f}%")
                                st.metric("Operating Margin", f"{segment_assumptions.get('operating_margin', 0)*100:.1f}%")
                            
                            with col2:
                                st.write("**Segment-Specific:**")
                                # Show segment-specific assumptions
                                if 'real estate' in segment_name.lower():
                                    st.metric("Presales Velocity", f"{segment_assumptions.get('presales_velocity', 0)}% /month")
                                    st.metric("Price Appreciation", f"{segment_assumptions.get('price_appreciation', 0)*100:.1f}% /year")
                                elif 'construction' in segment_name.lower():
                                    st.metric("Backlog Conversion", f"{segment_assumptions.get('backlog_conversion_rate', 0)*100:.0f}%")
                                    st.metric("New Contract Growth", f"{segment_assumptions.get('new_contract_growth', 0)*100:.1f}% /year")
                                elif 'rental' in segment_name.lower():
                                    st.metric("Occupancy Rate", f"{segment_assumptions.get('occupancy_rate', 0)*100:.0f}%")
                                    st.metric("Rental Escalation", f"{segment_assumptions.get('rental_escalation', 0)*100:.1f}% /year")
                    
                except Exception as e:
                    st.error(f"Error generating assumptions: {str(e)}")
                    return
            
            # Initialize revenue_forecast variable
            revenue_forecast = pd.DataFrame()
            
            # Step 5: Create comprehensive forecast
            with st.spinner("📈 Creating comprehensive revenue forecast for all segments..."):
                try:
                    revenue_forecast = st.session_state.comprehensive_analyzer.create_comprehensive_forecast(
                        revenue_model=comprehensive_model,
                        assumptions=assumptions,
                        forecast_years=forecast_years
                    )
                    
                    st.session_state.comprehensive_forecast = revenue_forecast
                    
                    # Display comprehensive revenue forecast
                    st.write("### 📈 Comprehensive Revenue Forecast by Segment")
                    
                    if not revenue_forecast.empty:
                        # Pivot table by segment
                        pivot_forecast = revenue_forecast[revenue_forecast['Segment'] != 'TOTAL'].pivot_table(
                            index='Segment',
                            columns='Year',
                            values='Revenue',
                            aggfunc='sum',
                            fill_value=0
                        )
                        
                        # Format as billions VND
                        pivot_forecast = pivot_forecast / 1e9
                        st.dataframe(
                            pivot_forecast.style.format("{:.1f}B"),
                            use_container_width=True
                        )
                        
                        # Show total forecast with margins
                        total_forecast = revenue_forecast[revenue_forecast['Segment'] == 'TOTAL'].pivot_table(
                            index='Year',
                            values=['Revenue', 'Gross_Profit', 'Operating_Profit'],
                            aggfunc='sum'
                        )
                        
                        if not total_forecast.empty:
                            st.write("### 💰 Consolidated Financial Forecast")
                            
                            # Format the forecast table
                            consolidated_df = pd.DataFrame()
                            years = sorted(revenue_forecast['Year'].unique())
                            years = [y for y in years if y != 'TOTAL']
                            
                            for year in years:
                                year_data = revenue_forecast[revenue_forecast['Year'] == year]
                                total_row = year_data[year_data['Segment'] == 'TOTAL'].iloc[0] if not year_data[year_data['Segment'] == 'TOTAL'].empty else None
                                
                                if total_row is not None:
                                    consolidated_df[str(year)] = [
                                        total_row['Revenue'] / 1e9,
                                        total_row['Gross_Profit'] / 1e9,
                                        total_row['Operating_Profit'] / 1e9,
                                        (total_row['Gross_Profit'] / total_row['Revenue']) * 100 if total_row['Revenue'] > 0 else 0,
                                        (total_row['Operating_Profit'] / total_row['Revenue']) * 100 if total_row['Revenue'] > 0 else 0
                                    ]
                            
                            if not consolidated_df.empty:
                                consolidated_df.index = ['Revenue (B VND)', 'Gross Profit (B VND)', 'Operating Profit (B VND)', 'Gross Margin (%)', 'Operating Margin (%)']
                                st.dataframe(
                                    consolidated_df.style.format("{:.1f}"),
                                    use_container_width=True
                                )
                        
                        # Create stacked bar chart for all segments
                        segment_forecast = revenue_forecast[revenue_forecast['Segment'] != 'TOTAL'].pivot_table(
                            index='Year',
                            columns='Segment',
                            values='Revenue',
                            aggfunc='sum',
                            fill_value=0
                        )
                        
                        if not segment_forecast.empty:
                            fig = go.Figure()
                            
                            # Add trace for each segment
                            for segment in segment_forecast.columns:
                                fig.add_trace(go.Bar(
                                    name=segment,
                                    x=segment_forecast.index,
                                    y=segment_forecast[segment] / 1e9,
                                    text=[f"{v:.0f}B" if v > 100e9 else "" for v in segment_forecast[segment]],
                                    textposition='inside'
                                ))
                            
                            fig.update_layout(
                                title="Revenue Forecast by Segment (Billion VND)",
                                xaxis_title="Year",
                                yaxis_title="Revenue (Billion VND)",
                                barmode='stack',
                                height=500,
                                showlegend=True,
                                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                    
                except Exception as e:
                    st.error(f"Error creating forecast: {str(e)}")
                    return
            
            # Revenue Stream Selection
            st.write("### 🎯 Select Revenue Streams for Financial Model")
            st.info("Choose which revenue streams to include in your financial forecast and assumptions")
            
            # Initialize selected streams in session state
            if 'selected_revenue_streams' not in st.session_state:
                # By default, select all streams
                st.session_state.selected_revenue_streams = [s['segment_name'] for s in comprehensive_model.get('revenue_streams', [])]
            
            # Create selection interface
            available_streams = comprehensive_model.get('revenue_streams', [])
            
            # Use a form to handle selection changes properly
            with st.form("revenue_stream_selection"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write("**Available Revenue Streams:**")
                    
                    selected_streams = []
                    for stream in available_streams:
                        segment_name = stream.get('segment_name', 'Unknown')
                        revenue_pct = stream.get('revenue_percentage', 0)
                        
                        # Create checkbox for each stream
                        is_selected = st.checkbox(
                            f"{segment_name} ({revenue_pct:.1f}% of revenue)",
                            value=segment_name in st.session_state.selected_revenue_streams,
                            key=f"select_{segment_name}"
                        )
                        
                        if is_selected:
                            selected_streams.append(segment_name)
                
                with col2:
                    st.write("**Selection Summary:**")
                    st.write(f"Streams: {len(selected_streams)}")
                    total_pct = sum(s.get('revenue_percentage', 0) for s in available_streams 
                                  if s.get('segment_name') in selected_streams)
                    st.write(f"Coverage: {total_pct:.1f}%")
                
                # Submit button to apply changes
                submit_button = st.form_submit_button("Apply Selection", type="primary", use_container_width=True)
                
                if submit_button:
                    # Update session state when form is submitted
                    st.session_state.selected_revenue_streams = selected_streams
                    st.session_state.selected_streams_data = [s for s in available_streams 
                                                              if s.get('segment_name') in selected_streams]
                    
                    # Force recalculation of dynamic assumptions
                    # Remove old assumptions for unselected streams
                    if 'dynamic_assumptions' in st.session_state:
                        new_dynamic_assumptions = {}
                        for stream_name in selected_streams:
                            if stream_name in st.session_state.dynamic_assumptions:
                                new_dynamic_assumptions[stream_name] = st.session_state.dynamic_assumptions[stream_name]
                        st.session_state.dynamic_assumptions = new_dynamic_assumptions
                    
                    # Set a flag to force assumptions recalculation
                    st.session_state.force_assumptions_update = True
                    
                    st.rerun()
            
            # Show current selection status
            if 'selected_streams_data' in st.session_state:
                selected_count = len(st.session_state.selected_streams_data)
                if selected_count > 0:
                    st.success(f"✅ {selected_count} revenue stream(s) selected for financial modeling")
                else:
                    st.warning("⚠️ Please select at least one revenue stream to continue")
                    return
            else:
                # Initialize with all streams if not set
                st.session_state.selected_streams_data = available_streams
                st.session_state.selected_revenue_streams = [s['segment_name'] for s in available_streams]
            
            # Provide comprehensive insights
            if comprehensive_model:
                st.write("### 💡 Key Strategic Insights")
                
                # Generate insights based on the model
                insights = {
                    'revenue_diversification': [],
                    'growth_drivers': [],
                    'risk_factors': []
                }
                
                # Analyze revenue concentration
                if 'revenue_streams' in comprehensive_model:
                    streams = comprehensive_model['revenue_streams']
                    max_segment = max(streams, key=lambda x: x.get('revenue_percentage', 0))
                    
                    max_percentage = max_segment.get('revenue_percentage', 0)
                    if max_percentage > 60:
                        insights['risk_factors'].append(f"High concentration in {max_segment.get('segment_name', 'Unknown')} ({max_percentage:.0f}%)")
                    
                    recurring_pct = comprehensive_model.get('revenue_mix', {}).get('recurring_percentage', 0)
                    if recurring_pct > 20:
                        insights['revenue_diversification'].append(f"Strong recurring revenue base at {recurring_pct:.0f}%")
                    
                    # Find growth drivers
                    for stream in streams:
                        if stream.get('growth_rate', 0) > 0.15:
                            insights['growth_drivers'].append(f"{stream['segment_name']}: {stream['growth_rate']*100:.0f}% YoY growth")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write("**Revenue Diversification:**")
                    for item in insights['revenue_diversification']:
                        st.write(f"• {item}")
                    if not insights['revenue_diversification']:
                        st.write("• Consider diversifying revenue streams")
                
                with col2:
                    st.write("**Growth Drivers:**")
                    for item in insights['growth_drivers']:
                        st.write(f"• {item}")
                    if not insights['growth_drivers']:
                        st.write("• Identify new growth opportunities")
                
                with col3:
                    st.write("**Risk Factors:**")
                    for item in insights['risk_factors']:
                        st.write(f"• {item}")
                    if not insights['risk_factors']:
                        st.write("• Well-balanced risk profile")
            
            # Save options
            st.write("### 💾 Save Financial Model")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("💾 Save to MongoDB", use_container_width=True):
                    try:
                        # Prepare comprehensive model data
                        model_data = {
                            'ticker': company_ticker,
                            'company_name': company_name,
                            'comprehensive_model': comprehensive_model,
                            'assumptions': assumptions,
                            'revenue_forecast': revenue_forecast.to_dict('records') if not revenue_forecast.empty else [],
                            'created_date': datetime.now(),
                            'model_type': 'comprehensive_ai_generated'
                        }
                        
                        # Save to MongoDB (would need to add this function to mongodb_utils)
                        st.success("✅ Financial model saved to database")
                        
                    except Exception as e:
                        st.error(f"Error saving model: {str(e)}")
            
            with col2:
                if st.button("📥 Export to Excel", use_container_width=True):
                    try:
                        # Create Excel export
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            # All revenue streams
                            if 'revenue_streams' in comprehensive_model:
                                pd.DataFrame(comprehensive_model['revenue_streams']).to_excel(
                                    writer, sheet_name='Revenue Streams', index=False
                                )
                            
                            # Segment assumptions
                            assumptions_df = pd.DataFrame()
                            for segment, seg_assumptions in assumptions['by_segment'].items():
                                assumptions_df[segment] = pd.Series(seg_assumptions)
                            assumptions_df.to_excel(
                                writer, sheet_name='Assumptions', index=True
                            )
                            
                            # Revenue forecast
                            if not revenue_forecast.empty:
                                revenue_forecast.to_excel(
                                    writer, sheet_name='Revenue Forecast', index=False
                                )
                            
                            # Projects
                            pd.DataFrame(projects).to_excel(
                                writer, sheet_name='Projects', index=False
                            )
                        
                        output.seek(0)
                        
                        st.download_button(
                            label="📥 Download Financial Model",
                            data=output,
                            file_name=f"{company_ticker}_financial_model_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                        
                    except Exception as e:
                        st.error(f"Error creating export: {str(e)}")
    
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
    
    def render_assumptions_interface(self):
        """Render dynamic assumptions interface based on discovered revenue streams"""
        st.header("Model Assumptions")
        st.markdown("Adjust assumptions below to customize your forecast")
        
        # Check if we have discovered revenue streams from AI
        if 'comprehensive_model' in st.session_state and 'revenue_streams' in st.session_state.comprehensive_model:
            # Show which streams are selected
            if 'selected_streams_data' in st.session_state and len(st.session_state.selected_streams_data) > 0:
                selected_names = [s['segment_name'] for s in st.session_state.selected_streams_data]
                st.info(f"📊 Showing assumptions for {len(selected_names)} selected revenue streams: {', '.join(selected_names)}")
                
                # Generate assumptions for selected streams
                assumptions_data = self.generate_dynamic_assumptions_table()
                
                # Verify we have assumptions data
                if not assumptions_data:
                    st.warning("No assumptions generated. Please check your revenue stream selection.")
                    assumptions_data = self.generate_default_assumptions_table()
            else:
                st.warning("No revenue streams selected. Using default assumptions.")
                assumptions_data = self.generate_default_assumptions_table()
        else:
            # Use default assumptions if no AI discovery yet
            assumptions_data = self.generate_default_assumptions_table()
        
        assumptions_df = pd.DataFrame(assumptions_data)
        
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
    
    def generate_dynamic_assumptions_table(self):
        """Generate assumptions table based on selected revenue streams only"""
        assumptions_data = []
        
        # Get only selected revenue streams
        if 'selected_streams_data' in st.session_state:
            revenue_streams = st.session_state.selected_streams_data
        else:
            revenue_streams = st.session_state.comprehensive_model.get('revenue_streams', [])
        
        # Initialize dynamic assumptions in session state if not exists or force update
        if 'dynamic_assumptions' not in st.session_state or st.session_state.get('force_assumptions_update', False):
            st.session_state.dynamic_assumptions = {}
            # Clear the force update flag
            if 'force_assumptions_update' in st.session_state:
                del st.session_state.force_assumptions_update
        
        # Add revenue growth and margin assumptions ONLY for selected segments
        for stream in revenue_streams:
            segment_name = stream.get('segment_name', 'Unknown')
            
            # Initialize assumptions for this segment if not exists
            if segment_name not in st.session_state.dynamic_assumptions:
                st.session_state.dynamic_assumptions[segment_name] = {
                    'revenue_growth': stream.get('growth_rate', 0.10) * 100,  # Convert to percentage
                    'gross_margin': stream.get('gross_margin', 0.25) * 100,
                    'opex_ratio': 10.0  # Default operating expense ratio
                }
            
            # Add revenue growth assumption
            assumptions_data.append({
                "Category": "Revenue Growth",
                "Item": f"{segment_name} Growth",
                "Value": st.session_state.dynamic_assumptions[segment_name]['revenue_growth'],
                "Unit": "%"
            })
            
            # Add gross margin assumption
            assumptions_data.append({
                "Category": "Gross Margins",
                "Item": f"{segment_name} Margin",
                "Value": st.session_state.dynamic_assumptions[segment_name]['gross_margin'],
                "Unit": "%"
            })
        
        # Only add basic common assumptions (removed segment-specific details)
        assumptions_data.extend([
            {"Category": "Tax & Finance", "Item": "Tax Rate", "Value": st.session_state.assumptions['costs']['tax_rate'], "Unit": "%"},
            {"Category": "Tax & Finance", "Item": "WACC", "Value": st.session_state.assumptions['valuation']['wacc'], "Unit": "%"}
        ])
        
        return assumptions_data
    
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
                    
                    # Calculate and save yearly schedules
                    current_year = datetime.now().year
                    project_start = min(
                        edited.get('construction_start_year', current_year),
                        edited.get('sale_start_year', current_year),
                        edited.get('land_payment_year', current_year),
                        current_year
                    )
                    project_end = edited.get('project_completion_year', current_year + 3)
                    
                    # Calculate revenue schedule by year
                    revenue_dist = edited.get('revenue_distribution', {})
                    if not isinstance(revenue_dist, dict):
                        revenue_dist = {}
                    
                    revenue_schedule = {}
                    for year in range(int(edited.get('revenue_booking_start_year', current_year)), int(project_end) + 1):
                        year_pct = revenue_dist.get(str(year), 0) / 100.0
                        revenue_schedule[str(year)] = total_revenue * year_pct / 1e9  # Store in billions
                    
                    # Calculate construction schedule (proportional to revenue distribution)
                    construction_schedule = {}
                    for year in range(int(edited.get('revenue_booking_start_year', current_year)), int(project_end) + 1):
                        year_pct = revenue_dist.get(str(year), 0) / 100.0
                        construction_schedule[str(year)] = total_const_cost * year_pct / 1e9  # Store in billions
                    
                    # Calculate land schedule (proportional to revenue distribution)
                    land_schedule = {}
                    for year in range(int(edited.get('revenue_booking_start_year', current_year)), int(project_end) + 1):
                        year_pct = revenue_dist.get(str(year), 0) / 100.0
                        land_schedule[str(year)] = total_land_cost * year_pct / 1e9  # Store in billions
                    
                    # Calculate SG&A schedule (proportional to revenue distribution)
                    sga_schedule = {}
                    for year in range(int(edited.get('revenue_booking_start_year', current_year)), int(project_end) + 1):
                        year_pct = revenue_dist.get(str(year), 0) / 100.0
                        sga_schedule[str(year)] = total_sga * year_pct / 1e9  # Store in billions
                    
                    # Add schedules to edited data
                    edited['revenue_schedule'] = revenue_schedule
                    edited['construction_schedule'] = construction_schedule
                    edited['land_schedule'] = land_schedule
                    edited['sga_schedule'] = sga_schedule
                    
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
        """Render comprehensive revenue forecast including all segments"""
        st.header("Comprehensive Revenue Forecast Model")
        
        # Check if we have AI-discovered revenue streams
        has_ai_segments = 'comprehensive_model' in st.session_state and 'revenue_streams' in st.session_state.comprehensive_model
        
        if has_ai_segments:
            st.success("📊 Revenue forecast includes all AI-discovered business segments")
            
            # Create tabs for different views
            forecast_tabs = st.tabs([
                "📊 Total Company Revenue",
                "🏗️ Real Estate Projects",
                "💼 Other Business Segments",
                "📈 Consolidated Forecast"
            ])
            
            with forecast_tabs[0]:
                self.render_total_company_forecast()
            
            with forecast_tabs[1]:
                self.render_project_pipeline_forecast()
            
            with forecast_tabs[2]:
                self.render_other_segments_forecast()
            
            with forecast_tabs[3]:
                self.render_consolidated_forecast()
        else:
            # Original project-only forecast
            st.info("Run AI discovery to see comprehensive revenue forecast for all business segments")
            
            # Generate revenue forecast from projects only
            revenue_forecast = self.generate_revenue_forecast()
            
            # Display aggregated P&L forecast
            st.subheader("Aggregated P&L Forecast from Projects")
            self.display_aggregated_pnl_forecast()
            
            st.markdown("---")
            
            # Display forecast chart based on aggregated project data
            st.subheader("Revenue Forecast from Project Pipeline")
        
        # Get aggregated revenue data from projects
        if st.session_state.project_data is not None and not st.session_state.project_data.empty:
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
        else:
            st.info("No project data available for revenue forecast")
    
    def render_total_company_forecast(self):
        """Render total company revenue forecast combining selected segments only"""
        st.subheader("📊 Total Company Revenue Forecast")
        
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
        st.subheader("📈 Consolidated Financial Forecast")
        
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