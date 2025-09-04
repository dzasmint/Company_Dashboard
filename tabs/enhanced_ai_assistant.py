"""
Enhanced AI Assistant - Comprehensive MCP Framework for Financial Analysis
Integrates all data sources: CSV files, MongoDB collections, and AI services

## NEW CAPABILITIES (Updated: December 2024)

### Enhanced Data Access:
- **Quarterly Historical Data**: Access quarterly financial statements from FA_processed.parquet
- **Annual Historical Data**: Access annual financial statements from FA_A_processed.parquet  
- **MongoDB Integration**: Direct access to CompanyForecast and RealEstateProjects collections
- **Comprehensive Forecast Data**: All saved forecast data including interest income calculations

### New Analysis Tools:

1. **get_historical_financials** - Enhanced with quarterly data support
   - Parameters: tickers, metrics, years, period_type (annual/quarterly/both), quarters
   - Returns both annual and quarterly financial data with growth rates

2. **get_comprehensive_forecast_details** - Complete forecast analysis
   - Access all financial statements (P&L, BS, CF) with project breakdowns
   - Includes interest income calculations and growth rate analysis
   - Parameters: ticker, years, include_project_breakdown, include_assumptions

3. **analyze_balance_sheet_changes** - Detailed BS movement analysis
   - Track inventory, debt, prepayment, and cash changes by project
   - Shows both project-level and consolidated changes
   - Parameters: ticker, year, change_type (inventory/debt/prepayment/cash/all)

4. **get_project_details** - Enhanced with MongoDB RealEstateProjects
   - Access complete project information including AI assumptions
   - Parameters: project_names, ticker, include_financials, include_assumptions
   - Fallback to CSV if MongoDB unavailable

5. **get_project_cash_flow_breakdown** - Project-level cash flow analysis
   - Detailed presales, cash collection, and operating CF by project
   - Includes cash conversion rates and consolidated comparison
   - Parameters: ticker, year, project_names

6. **analyze_financial_trends** - Enhanced with quarterly support
   - Calculate YoY, QoQ, TTM (trailing twelve months), and CAGR
   - Support for both annual and quarterly data frequencies
   - Parameters: ticker, metrics, period_type, data_frequency

7. **create_financial_chart** - Interactive Plotly visualizations
   - Chart types: line, bar, waterfall, scatter, area, combo
   - Auto-detects data structure from other tools
   - Parameters: chart_type, data, title, x_axis, y_axis, options
   - Automatically displays in Streamlit context

### Data Sources:
- Historical Financial Data: FA_A_processed.parquet (annual), FA_processed.parquet (quarterly)
- Forecast Data: MongoDB CompanyForecast collection
- Project Details: MongoDB RealEstateProjects collection
- Market Data: MongoDB MoC collections
- Valuation Metrics: Val_processed.csv

### Key Features:
- Automatic fallback to CSV when MongoDB unavailable
- Smart data caching for performance
- Comprehensive error handling
- Support for complex financial calculations (interest income, RNAV, cash flows)
- Integration with AI services (Perplexity, OpenAI/Anthropic)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Callable
from datetime import datetime
from pathlib import Path
import json
from functools import wraps, lru_cache
import re
import os
import sys
from dotenv import load_dotenv
import streamlit as st
from pymongo import MongoClient
import anthropic
from openai import OpenAI
import plotly.graph_objects as go
import plotly.express as px

# Import chart utilities (if available)
try:
    from utils.chart_utils import create_plotly_chart
    CHART_UTILS_AVAILABLE = True
except ImportError:
    CHART_UTILS_AVAILABLE = False
    create_plotly_chart = None

# Import utilities
from utils.mongodb_utils import (
    init_mongodb_connection,
    load_projects_data,
    get_company_assumptions,
    save_project_to_mongodb
)
from utils.perplexity_utils import get_project_basic_info_perplexity

load_dotenv()

class EnhancedAIToolSystem:
    """
    Enhanced AI Tool System with comprehensive data integration
    Following MCP (Modular Component Pattern) architecture
    """
    
    def __init__(self):
        """Initialize the enhanced tool system"""
        # Set data directory
        self.data_dir = Path(__file__).parent.parent / "data"
        
        # Tool registry
        self.tools = {}
        self.tool_schemas = []
        
        # Data caches
        self.data = {}
        self._data_loaded = {}
        
        # Initialize MongoDB connection
        self.mongo_client = None
        self.vietnam_stocks_db = None
        self.moc_db = None
        self._init_mongodb()
        
        # Initialize AI services
        self.anthropic_client = None
        self._init_ai_services()
        
        # Register all tools
        self._register_all_tools()
    
    def _init_mongodb(self):
        """Initialize MongoDB connections"""
        try:
            connection_string = os.getenv('MONGODB_CONNECTION_STRING')
            if connection_string:
                self.mongo_client = MongoClient(connection_string)
                self.vietnam_stocks_db = self.mongo_client['VietnamStocks']
                self.moc_db = self.mongo_client['MoCDB']
        except Exception as e:
            print(f"MongoDB initialization error: {e}")
            self.mongo_client = None
    
    def _init_ai_services(self):
        """Initialize AI services"""
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        if anthropic_key:
            self.anthropic_client = anthropic.Anthropic(api_key=anthropic_key)
    
    # ========== Data Loading Methods ==========
    
    @lru_cache(maxsize=1)
    def _load_financial_statements_csv(self):
        """Load annual financial statements from parquet"""
        if 'financial_csv' not in self.data:
            fa_path = self.data_dir / 'FA_A_processed.parquet'
            if fa_path.exists():
                self.data['financial_csv'] = pd.read_parquet(fa_path)
                self._data_loaded['financial_csv'] = True
            else:
                return pd.DataFrame()
        return self.data.get('financial_csv', pd.DataFrame())
    
    @lru_cache(maxsize=1)
    def _load_quarterly_financial_statements(self):
        """Load quarterly financial statements from parquet"""
        if 'quarterly_csv' not in self.data:
            fa_path = self.data_dir / 'FA_processed.parquet'
            if fa_path.exists():
                self.data['quarterly_csv'] = pd.read_parquet(fa_path)
                self._data_loaded['quarterly_csv'] = True
            else:
                return pd.DataFrame()
        return self.data.get('quarterly_csv', pd.DataFrame())
    
    @lru_cache(maxsize=1)
    def _load_valuation_csv(self):
        """Load valuation metrics from CSV"""
        if 'valuation_csv' not in self.data:
            val_path = self.data_dir / 'Val_processed.csv'
            if val_path.exists():
                self.data['valuation_csv'] = pd.read_csv(val_path)
                self._data_loaded['valuation_csv'] = True
            else:
                return pd.DataFrame()
        return self.data.get('valuation_csv', pd.DataFrame())
    
    @lru_cache(maxsize=1)
    def _load_moc_data_csv(self):
        """Load Ministry of Construction data from CSV"""
        if 'moc_csv' not in self.data:
            moc_path = self.data_dir / 'MoC_Data.csv'
            if moc_path.exists():
                self.data['moc_csv'] = pd.read_csv(moc_path)
                self._data_loaded['moc_csv'] = True
            else:
                return pd.DataFrame()
        return self.data.get('moc_csv', pd.DataFrame())
    
    @lru_cache(maxsize=1)
    def _load_real_estate_projects(self):
        """Load real estate projects from MongoDB"""
        if 'projects' not in self.data:
            self.data['projects'] = load_projects_data()
            self._data_loaded['projects'] = True
        return self.data['projects']
    
    def tool(self, name: str, description: str, parameters: Dict = None):
        """Decorator to register a tool with OpenAI schema"""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    return {
                        "error": f"Error in {name}: {str(e)}",
                        "status": "failed"
                    }
            
            # Register the tool
            self.tools[name] = wrapper
            
            # Create OpenAI function schema
            clean_params = {}
            required_params = []
            
            if parameters:
                for param_name, param_def in parameters.items():
                    is_required = param_def.get("required", True)
                    if is_required:
                        required_params.append(param_name)
                    clean_param = {k: v for k, v in param_def.items() if k != "required"}
                    clean_params[param_name] = clean_param
            
            schema = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": clean_params,
                        "required": required_params
                    }
                }
            }
            self.tool_schemas.append(schema)
            
            return wrapper
        return decorator
    
    def _register_all_tools(self):
        """Register all available tools"""
        self._register_financial_forecast_tools()
        self._register_real_estate_tools()
        self._register_market_tools()
        self._register_ai_tools()
        self._register_visualization_tools()
    
    def _parse_period_notation(self, period: str) -> Dict:
        """Parse period notation like 2H25, 4Q24, 1H23 into components"""
        import re
        
        result = {
            "type": None,  # "half", "quarter", "annual"
            "period_num": None,  # 1, 2, 3, 4
            "year": None,
            "required_quarters": []
        }
        
        # Match patterns like 1H25, 2H24
        half_match = re.match(r'([12])H(\d{2,4})', period.upper())
        if half_match:
            half_num = int(half_match.group(1))
            year = half_match.group(2)
            if len(year) == 2:
                year = "20" + year
            result["type"] = "half"
            result["period_num"] = half_num
            result["year"] = year
            if half_num == 1:
                result["required_quarters"] = [f"{year}Q1", f"{year}Q2"]
            else:
                result["required_quarters"] = [f"{year}Q3", f"{year}Q4"]
            return result
        
        # Match patterns like 1Q25, 4Q24, 2024Q1
        quarter_match = re.match(r'(\d{4})Q([1-4])|([1-4])Q(\d{2,4})', period.upper())
        if quarter_match:
            if quarter_match.group(1):  # Format: 2024Q1
                year = quarter_match.group(1)
                quarter = int(quarter_match.group(2))
            else:  # Format: 1Q24
                quarter = int(quarter_match.group(3))
                year = quarter_match.group(4)
                if len(year) == 2:
                    year = "20" + year
            result["type"] = "quarter"
            result["period_num"] = quarter
            result["year"] = year
            result["required_quarters"] = [f"{year}Q{quarter}"]
            return result
        
        # Match full year like 2024, 2025
        year_match = re.match(r'(20\d{2})', period)
        if year_match:
            result["type"] = "annual"
            result["year"] = year_match.group(1)
            result["required_quarters"] = [f"{result['year']}Q{i}" for i in range(1, 5)]
            return result
        
        return result
    
    def _check_data_availability(self, ticker: str, year: str, metrics: List[str]) -> Dict:
        """Check what data is available for period calculations"""
        availability = {
            "annual_forecast": False,
            "annual_actual": False,
            "quarters_available": [],
            "quarters_missing": [],
            "can_calculate_full_year": False,
            "can_calculate_1H": False,
            "can_calculate_2H": False
        }
        
        # Check forecast availability (MongoDB)
        if self.vietnam_stocks_db is not None:
            try:
                collection = self.vietnam_stocks_db['CompanyForecast']
                forecast = collection.find_one({'ticker': ticker.upper()})
                if forecast and year in forecast.get('forecast_data', {}):
                    availability["annual_forecast"] = True
            except:
                pass
        
        # Check historical quarterly data
        df_q = self._load_quarterly_financial_statements()
        if not df_q.empty:
            ticker_data = df_q[df_q['TICKER'] == ticker.upper()]
            for q in range(1, 5):
                quarter_str = f"{year}Q{q}"
                if quarter_str in ticker_data['DATE'].values:
                    availability["quarters_available"].append(quarter_str)
                else:
                    availability["quarters_missing"].append(quarter_str)
        
        # Check annual historical data
        df_a = self._load_financial_statements_csv()
        if not df_a.empty:
            ticker_data = df_a[df_a['TICKER'] == ticker.upper()]
            if int(year) in ticker_data['DATE'].values:
                availability["annual_actual"] = True
        
        # Determine calculation possibilities
        q1_q2 = f"{year}Q1" in availability["quarters_available"] and f"{year}Q2" in availability["quarters_available"]
        q3_q4 = f"{year}Q3" in availability["quarters_available"] and f"{year}Q4" in availability["quarters_available"]
        
        availability["can_calculate_1H"] = q1_q2
        availability["can_calculate_2H"] = q3_q4 or (availability["annual_forecast"] and q1_q2)
        availability["can_calculate_full_year"] = len(availability["quarters_available"]) == 4
        
        return availability

    def _register_financial_forecast_tools(self):
        """Register company financial analysis tools"""
        from utils.AI.AI_financial_forecast_tools import register_financial_forecast_tools
        register_financial_forecast_tools(self)

    def _register_real_estate_tools(self):
        """Register real estate project tools"""
        from utils.AI.AI_real_estate_project_tools import register_real_estate_tools
        register_real_estate_tools(self)
            
    
    def _register_market_tools(self):
        """Register market analysis tools (MoC data)"""
        
        from utils.AI.AI_market_data_tools import register_market_tools
        register_market_tools(self)
    
    def _register_ai_tools(self):
        """Register AI-enhanced tools"""
        
        @self.tool(
            name="get_latest_market_info",
            description="Get latest market information from the internet using intelligent search",
            parameters={
                "query": {
                    "type": "string",
                    "description": "Natural language query about market information (e.g., 'How many units left in Vinhomes Grand Park?', 'What is the latest consensus forecast for VHM?')",
                    "required": True
                },
                "ticker": {
                    "type": "string", 
                    "description": "Company ticker if applicable",
                    "required": False
                },
                "project_name": {
                    "type": "string",
                    "description": "Real estate project name if applicable",
                    "required": False
                },
                "query_type": {
                    "type": "string",
                    "enum": ["project_update", "consensus_forecast", "market_news", "price_check", "general"],
                    "description": "Type of query to optimize search",
                    "required": False
                }
            }
        )
        def get_latest_market_info(query: str, ticker: str = None, project_name: str = None, query_type: str = "general") -> Dict:
            """Get latest market information using ChatGPT to build queries and Perplexity to search"""
            
            # Check API keys
            openai_key = os.getenv('OPENAI_API_KEY')
            perplexity_key = os.getenv('PERPLEXITY_API_KEY')
            
            if not openai_key:
                return {"error": "OpenAI API key not configured", "status": "failed"}
            if not perplexity_key:
                return {"error": "Perplexity API key not configured", "status": "failed"}
            
            try:
                # Initialize OpenAI client
                openai_client = OpenAI(api_key=openai_key)
                
                # Step 1: Use ChatGPT to build optimized search query
                search_query = self._build_search_query_with_chatgpt(
                    openai_client, query, ticker, project_name, query_type
                )
                
                if search_query.get("status") != "success":
                    return search_query
                
                # Step 2: Execute search with Perplexity
                search_results = self._search_with_perplexity(
                    perplexity_key, search_query["search_query"], search_query["search_context"]
                )
                
                if search_results.get("status") != "success":
                    return search_results
                
                # Step 3: Use ChatGPT to parse and structure the results
                structured_results = self._parse_results_with_chatgpt(
                    openai_client, query, search_results["content"], query_type
                )
                
                return {
                    "query": query,
                    "ticker": ticker,
                    "project_name": project_name,
                    "query_type": query_type,
                    "search_query_used": search_query["search_query"],
                    "raw_results": search_results["content"],
                    "structured_results": structured_results,
                    "sources": search_results.get("sources", []),
                    "timestamp": datetime.now().isoformat(),
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": f"Failed to get market information: {str(e)}", "status": "failed"}
    
    def _build_search_query_with_chatgpt(self, openai_client, user_query: str, ticker: str = None, 
                                        project_name: str = None, query_type: str = "general") -> Dict:
        """Use ChatGPT to build an optimized search query for Perplexity"""
        
        prompt = f"""You are a search query optimizer for Vietnamese financial and real estate markets.
Convert the user's natural language query into an optimized search query for web search.

User Query: {user_query}
Query Type: {query_type}
{"Ticker: " + ticker if ticker else ""}
{"Project Name: " + project_name if project_name else ""}

Based on the query type, create an optimized search query:

1. For project_update queries:
   - Include project name, developer, location
   - Add keywords: "units sold", "remaining inventory", "price list", "latest update"
   - Include Vietnamese real estate sites: batdongsan.com.vn

2. For consensus_forecast queries:
   - Include ticker and company name
   - Add keywords: "analyst consensus", "target price", "earnings forecast", "SSI", "HSC", "VCSC"
   - Focus on recent reports (2024, 2025)

3. For market_news queries:
   - Include relevant market terms
   - Add "Vietnam", "latest news", current year
   - Include major Vietnamese news sources

4. For price_check queries:
   - Include specific product/project name
   - Add "current price", "price per sqm", "VND"
   - Include comparison terms if relevant

Return a JSON response with:
{{
    "search_query": "the optimized search query string",
    "search_context": "brief context about what to look for",
    "search_tips": ["tip1", "tip2"],
    "expected_sources": ["source1", "source2"]
}}"""

        try:
            response = openai_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=1,
                max_tokens=500
            )
            
            result = json.loads(response.choices[0].message.content)
            result["status"] = "success"
            return result
            
        except Exception as e:
            return {"error": f"Failed to build search query: {str(e)}", "status": "failed"}
    
    def _search_with_perplexity(self, api_key: str, search_query: str, search_context: str) -> Dict:
        """Execute search using Perplexity API"""
        
        import requests
        
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Build the search prompt
        system_prompt = """You are a financial and real estate market researcher specializing in Vietnam.
Provide accurate, up-to-date information from reliable sources.
Focus on specific numbers, dates, and facts.
Always cite your sources."""

        user_prompt = f"""Search for: {search_query}

Context: {search_context}

Provide:
1. Specific facts and figures found
2. Dates and timeline information
3. Source credibility assessment
4. Any conflicting information from different sources

Focus on the most recent and reliable information available."""

        payload = {
            "model": "sonar-pro",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 2000,
            "temperature": 0.2,
            "stream": False
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                
                # Try to extract sources from the content
                sources = []
                if "source" in content.lower():
                    # Simple extraction of URLs or source mentions
                    import re
                    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]*'
                    urls = re.findall(url_pattern, content)
                    sources.extend(urls)
                
                return {
                    "content": content,
                    "sources": sources,
                    "status": "success"
                }
            else:
                return {"error": "Unexpected Perplexity API response", "status": "failed"}
                
        except Exception as e:
            return {"error": f"Perplexity search failed: {str(e)}", "status": "failed"}
    
    def _parse_results_with_chatgpt(self, openai_client, original_query: str, 
                                   search_results: str, query_type: str) -> Dict:
        """Use ChatGPT to parse and structure the search results"""
        
        # Build parsing prompt based on query type
        if query_type == "project_update":
            parse_prompt = """Extract the following information:
- Total units in project
- Units sold to date
- Units remaining
- Current average price per sqm
- Recent price changes
- Sales momentum (fast/moderate/slow)
- Latest update date"""
        
        elif query_type == "consensus_forecast":
            parse_prompt = """Extract the following information:
- Revenue forecasts (next 3 years)
- EPS forecasts
- Target prices from different brokers
- Buy/Hold/Sell recommendations count
- Recent rating changes
- Key assumptions
- Risk factors mentioned"""
        
        elif query_type == "price_check":
            parse_prompt = """Extract the following information:
- Current price or price range
- Price per unit (sqm, unit, etc.)
- Recent price changes
- Comparison with similar products
- Factors affecting price
- Last updated date"""
        
        else:
            parse_prompt = """Extract key information relevant to the query."""
        
        prompt = f"""Parse the following search results to answer the user's query.

Original Query: {original_query}

Search Results:
{search_results}

{parse_prompt}

Return a JSON response with the extracted information. Use null for any information not found.
Include a "summary" field with a brief answer to the original query.
Include a "confidence" field (high/medium/low) based on data quality."""

        try:
            response = openai_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=1,
                max_tokens=1000
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            # Fallback to simple text summary
            return {
                "summary": search_results[:500],
                "error": f"Failed to parse results: {str(e)}",
                "raw_content": search_results
            }
    
    def execute_tool(self, tool_name: str, arguments: Dict = None) -> Dict:
        """Execute a tool by name"""
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}", "status": "failed"}
        
        tool_func = self.tools[tool_name]
        
        # Get function signature
        import inspect
        sig = inspect.signature(tool_func)
        
        # Filter arguments
        filtered_args = {}
        for param_name in sig.parameters:
            if param_name != 'self' and arguments and param_name in arguments:
                filtered_args[param_name] = arguments[param_name]
        
        try:
            result = tool_func(**filtered_args)
            return result
        except Exception as e:
            return {"error": f"Error executing {tool_name}: {str(e)}", "status": "failed"}
    
    def _register_visualization_tools(self):
        """Register data visualization tools"""
        from utils.AI.AI_visualisation_tool import register_visualization_tools
        register_visualization_tools(self)
    
    def get_openai_tools(self) -> List[Dict]:
        """Get tool schemas for OpenAI"""
        return self.tool_schemas
    
    def get_tool_list(self) -> List[str]:
        """Get list of available tool names"""
        return list(self.tools.keys())


# Singleton instance
_enhanced_tool_system = None

def get_enhanced_tool_system() -> EnhancedAIToolSystem:
    """Get or create the enhanced tool system instance"""
    global _enhanced_tool_system
    if _enhanced_tool_system is None:
        _enhanced_tool_system = EnhancedAIToolSystem()
    return _enhanced_tool_system






def execute_tool_call(tool_system: EnhancedAIToolSystem, tool_name: str, arguments: Dict) -> Dict:
    """Execute a tool and return results"""
    # Log the tool execution
    execution_log = {
        "tool": tool_name,
        "arguments": arguments,
        "timestamp": datetime.now().isoformat()
    }
    
    # Execute the tool
    result = tool_system.execute_tool(tool_name, arguments)
    
    execution_log["result"] = result
    
    # Store execution log in session state
    if 'tool_executions' not in st.session_state:
        st.session_state.tool_executions = []
    st.session_state.tool_executions.append(execution_log)
    
    return result


def get_historical_data_cutoff():
    """Dynamically determine the historical data cutoff year"""
    try:
        import pandas as pd
        
        # Try annual data first
        fa_path = 'data/FA_A_processed.parquet'
        if os.path.exists(fa_path):
            # Load a small sample to check structure
            df = pd.read_parquet(fa_path, columns=['DATE'])
            if 'DATE' in df.columns:
                # DATE column contains year as integer (e.g., 2024)
                max_year = int(df['DATE'].max())
                return max_year
        
        # Fallback to CSV
        fa_csv_path = 'data/FA_processed.csv'
        if os.path.exists(fa_csv_path):
            df = pd.read_csv(fa_csv_path, nrows=1000)
            if 'YEAR' in df.columns:
                return int(df['YEAR'].max())
            elif 'DATE' in df.columns:
                return int(df['DATE'].max())
        
        # Check quarterly data
        fa_q_path = 'data/FA_Q_processed.parquet'
        if os.path.exists(fa_q_path):
            df = pd.read_parquet(fa_q_path, columns=['DATE'])
            if 'DATE' in df.columns:
                max_date = df['DATE'].max()
                # DATE column contains values like 20242 (2024Q2)
                if isinstance(max_date, (int, float)):
                    year = int(max_date // 10)  # Remove quarter digit
                    quarter = int(max_date % 10)  # Get quarter digit
                    # If we have Q4 data, year is complete
                    if quarter == 4:
                        return year
                    else:
                        return year  # Current year with partial data
                        
    except Exception:
        pass
    
    # Default fallback - conservative estimate
    return 2024  # Known good value from our data

def chat_with_ai(user_message: str, tool_system: EnhancedAIToolSystem, stream_container=None) -> str:
    """
    Send message to OpenAI and handle tool calls with streaming support
    Similar to Bank_Sample/7_DucGPT_Chatbot.py implementation
    
    Args:
        user_message: The user's input message
        tool_system: The enhanced AI tool system
        stream_container: Optional Streamlit container for streaming responses
    """
    # Initialize session token tracking
    if 'session_total_tokens' not in st.session_state:
        st.session_state.session_total_tokens = 0
        st.session_state.session_total_cost = 0.0
    
    # Initialize pending charts in session state if not exists
    if 'pending_charts' not in st.session_state:
        st.session_state.pending_charts = []
    
    # Clear pending charts from previous messages
    st.session_state.pending_charts = []
    
    # Initialize OpenAI client if not exists
    if 'openai_client' not in st.session_state:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            st.session_state.openai_client = OpenAI(api_key=api_key)
        else:
            st.session_state.openai_client = None
    
    if not st.session_state.openai_client:
        return "❌ OpenAI API key not configured. Please set OPENAI_API_KEY in your .env file."
    
    
    # Get the dynamic historical data cutoff
    historical_cutoff = get_historical_data_cutoff()
    forecast_start = historical_cutoff + 1
    
    # Prepare messages
    messages = []
    
    # Add system message for real estate and financial analysis
    system_content = f"""You are a comprehensive financial analyst assistant specializing in Vietnamese real estate and financial markets for an investment firm.
Use the available tools to gather data and provide detailed analysis.

CRITICAL TOOL SELECTION RULES:

**Core Financial Analysis Tools:**

1. **get_historical_financials** - Historical data (2016-{historical_cutoff})
   - Contains 1000+ companies (VHM, DXG, NLG, TCH, etc.)
   - Returns actual financial statements from CSV/Parquet
   - Supports annual and quarterly data
   - Years are integers: {historical_cutoff-1}, {historical_cutoff}

2. **get_forecast_summary** - Lightweight forecast summary (USE THIS FIRST!)
   - Returns key metrics only: revenue, NPATMI, margins, ROE
   - Optimized for quick analysis (~200 tokens vs 800-5000)
   - Perfect for overview questions and comparisons

3. **get_financial_forecasts** - Detailed forecast data ({forecast_start}-2030+)
   - Use ONLY when user needs detailed financial statements
   - Available for: DXG, KDH, NTL, NLG, TAL, TCH, etc. in (MongoDB)
   - Returns P&L, Balance Sheet, Cash Flow projections
   - Years are strings: "{forecast_start}", "{forecast_start+1}"
   - TOKEN OPTIMIZATION REQUIRED:
     * ALWAYS specify 1-3 years explicitly (e.g., ["2025", "2026"])
     * Use statement_type="pnl" for income statement questions
     * Use statement_type="all" only when user needs complete financials
     * Set include_breakdown=True ONLY if user asks for project details
     * Default behavior (2 years, P&L) is optimized for most queries

4. **calculate_period_metrics** - Smart period calculations
   - Handles half-year periods: 1HYY, 2HYY (H = half year, YY = year)
   - Handles quarters: 1QYY, 2QYY, 3QYY, 4QYY
   - AUTOMATICALLY derives values when possible:
     * 1HYY = Q1 YYYY + Q2 YYYY actuals
     * 2HYY = YYYY Annual Forecast - 1HYY actual
     * 4QYY = YYYY Annual Forecast - (Q1+Q2+Q3 actuals)

**Valuation & Scoring Tools:**

5. **get_valuation_analysis** - Comprehensive valuation metrics
   - Combines all valuation ratios (P/E, P/B, EV/EBITDA, etc.)
   - Historical and forward multiples
   - Peer comparison capabilities
   - Available for companies with forecast data

6. **get_company_total_score** - Investment scoring (1-10 scale)
   - RNAV upside (25% weight)
   - Valuation multiples (30% weight)
   - Growth prospects (25% weight)
   - Leverage metrics (20% weight)
   - Returns STRONG BUY/BUY/HOLD/SELL recommendation
   - ALWAYS display full breakdown when showing scores

7. **get_rnav_breakdown** - Real estate RNAV calculation
   - Detailed project-by-project analysis
   - Land value, construction costs, sales assumptions
   - Available for: KDH, TAL, TCH, NLG, NTL, DXG, etc.

**Balance Sheet & Ratio Analysis:**

8. **calculate_balance_sheet_ratios** - Comprehensive BS ratios
   - Supports historical (2016-{historical_cutoff}) and forecast ({forecast_start}+) data
   - Quarterly and annual calculations
   - Key ratios: debt_to_equity, net_debt_to_equity, current_ratio, etc.
   - Automatically detects data availability

**Trend & Comparison Tools:**

9. **analyze_financial_trends** - Multi-year trend analysis
   - Growth rates, margins, returns over time
   - Identifies inflection points and patterns

10. **compare_companies** - Peer comparison
   - Side-by-side financial metrics
   - Relative valuation analysis
   - Sector benchmarking

**Real Estate Project Tools:**

11. **list_real_estate_projects** - Project inventory
    - Filter by ticker, status, location
    - Summary statistics

12. **get_project_details** - Detailed project financials
    - IRR, NPV, margins, timeline
    - Construction progress, sales status

13. **rank_projects_by_metric** - Project ranking
    - Sort by IRR, NPV, margin, size
    - Investment prioritization

14. **calculate_rnav_sensitivity** - RNAV sensitivity analysis
    - Test different ASP, cost, discount rate assumptions
    - Scenario planning

**Advanced Forecast Tools:**

15. **analyze_project_contribution_to_forecast** - Project impact analysis
    - How individual projects affect company forecasts
    - Revenue/profit contribution by project

16. **get_comprehensive_forecast_details** - Deep forecast dive
    - Segment breakdown, project details
    - Assumptions and drivers

**Data Format Requirements:**
- Tickers: Single string "VHM" or array ["VHM", "DXG"]
- Historical years: integers ({historical_cutoff-1}, {historical_cutoff})
- Forecast years: strings ("{forecast_start}", "{forecast_start+1}")
- Quarters: "{historical_cutoff}Q1", "{historical_cutoff}Q2" format

**Key Guidelines:**
- For years ≤{historical_cutoff}: use get_historical_financials
- For years ≥{forecast_start}: use get_financial_forecasts with OPTIMIZED parameters:
  * Specify 1-3 years max (avoid default all years)
  * Use statement_type="pnl" for P&L questions
  * Use include_breakdown=False unless project details needed
- For scoring/recommendations: ALWAYS use get_company_total_score
- For valuation: use get_valuation_analysis (consolidated tool)
- For balance sheet metrics: use calculate_balance_sheet_ratios
- Display full details when presenting scores or analysis
- Cite data sources (CSV for historical, MongoDB for forecast)
- MINIMIZE TOKEN USAGE: Be specific with parameters to avoid large responses"""
    
    # Add context from previous conversation if available
    #if context_str:
    #    system_content += f"\n\n**Previous conversation context:**\n{context_str}"
    
    messages.append({
        "role": "system",
        "content": system_content
    })
    
    # Add user message
    messages.append({"role": "user", "content": user_message})
    
    # Get tool schemas (all tools available)
    tools = tool_system.get_openai_tools()
    
    # Initialize progress tracking and token counting
    max_rounds = 20
    tool_calls_made = []  # Track tool calls for compression
    total_input_tokens = 0
    total_output_tokens = 0
    total_tool_tokens = 0
    
    # Estimate initial tokens (system prompt + user message + tool schemas)
    import json
    initial_messages_str = json.dumps(messages, default=str)
    tools_str = json.dumps(tools, default=str) if tools else ""
    initial_tokens = len(initial_messages_str) // 4 + len(tools_str) // 4
    total_input_tokens += initial_tokens
    
    with st.spinner("🤖 AI is analyzing..."):
        rounds = 0
        final_response = None
        tool_call_count = 0
        
        while rounds < max_rounds:
            rounds += 1
            
            # Call OpenAI with streaming support
            try:
                # Enable streaming only for final response (when no more tools expected)
                should_stream = (rounds > 0 or not tools) and stream_container is not None
                
                response = st.session_state.openai_client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=1,
                    stream=should_stream,
                    timeout=30.0  # Add 30 second timeout
                )
            except Exception as e:
                return f"❌ Error calling OpenAI: {str(e)}"
            
            # Handle streaming or regular response
            if should_stream and stream_container is not None:
                # Collect streamed response
                collected_content = []
                assistant_message = None
                tool_calls = []
                current_tool_call = None
                
                for chunk in response:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        
                        # Handle tool calls in stream
                        if hasattr(delta, 'tool_calls') and delta.tool_calls:
                            for tc_delta in delta.tool_calls:
                                if tc_delta.index is not None:
                                    # New or continuing tool call
                                    while len(tool_calls) <= tc_delta.index:
                                        tool_calls.append({
                                            "id": "",
                                            "type": "function",
                                            "function": {"name": "", "arguments": ""}
                                        })
                                    
                                    current_tool_call = tool_calls[tc_delta.index]
                                    if tc_delta.id:
                                        current_tool_call["id"] = tc_delta.id
                                    if tc_delta.function:
                                        if tc_delta.function.name:
                                            current_tool_call["function"]["name"] = tc_delta.function.name
                                        if tc_delta.function.arguments:
                                            current_tool_call["function"]["arguments"] += tc_delta.function.arguments
                        
                        # Stream content to user
                        if delta.content:
                            collected_content.append(delta.content)
                            # Update the stream container with accumulated content
                            stream_container.markdown(''.join(collected_content))
                
                # Create assistant message from streamed data
                if tool_calls:
                    # Convert tool calls to proper format
                    from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall
                    from openai.types.chat.chat_completion_message import ChatCompletionMessage
                    formatted_tool_calls = [
                        ChatCompletionMessageToolCall(
                            id=tc["id"],
                            type="function",
                            function={"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}
                        ) for tc in tool_calls
                    ]
                    assistant_message = ChatCompletionMessage(
                        role="assistant",
                        content=None,
                        tool_calls=formatted_tool_calls
                    )
                elif collected_content:
                    from openai.types.chat.chat_completion_message import ChatCompletionMessage
                    assistant_message = ChatCompletionMessage(
                        role="assistant",
                        content=''.join(collected_content)
                    )
                else:
                    # Empty response
                    from openai.types.chat.chat_completion_message import ChatCompletionMessage
                    assistant_message = ChatCompletionMessage(
                        role="assistant",
                        content=""
                    )
                
                messages.append(assistant_message.model_dump())
            else:
                # Non-streaming response
                assistant_message = response.choices[0].message
                messages.append(assistant_message.model_dump())
            
            # Track tokens from OpenAI response (if available)
            if hasattr(response, 'usage') and response.usage:
                if hasattr(response.usage, 'prompt_tokens'):
                    total_input_tokens += response.usage.prompt_tokens - initial_tokens  # Avoid double counting
                    initial_tokens = 0  # Only count initial once
                if hasattr(response.usage, 'completion_tokens'):
                    total_output_tokens += response.usage.completion_tokens
            else:
                # Estimate if not provided
                assistant_str = json.dumps(assistant_message.model_dump(), default=str)
                total_output_tokens += len(assistant_str) // 4
            
            # Check if there are tool calls
            if assistant_message.tool_calls:
                # Show tool execution status
                tool_status = st.empty()
                tool_results_container = st.container()
                
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Update status
                    tool_call_count += 1
                    tool_calls_made.append(function_name)  # Track for compression
                    running_total = total_input_tokens + total_output_tokens + total_tool_tokens
                    tool_status.info(f"🔧 Executing tool #{tool_call_count}: **{function_name}** | Tokens so far: ~{running_total:,}")
                    
                    # Execute the tool
                    tool_result = execute_tool_call(tool_system, function_name, function_args)
                    
                    # Track tool result tokens
                    tool_result_str = json.dumps(tool_result, default=str)
                    tool_tokens = len(tool_result_str) // 4
                    total_tool_tokens += tool_tokens
                    
                    # Add warning if tool result is large
                    if tool_tokens > 3000:
                        tool_result["_token_warning"] = f"Large tool response: ~{tool_tokens} tokens"
                    
                    # Check if this is a chart rendering tool
                    if function_name in ["render_chart", "create_financial_chart"] and tool_result.get("status") == "success":
                        if "chart_spec" in tool_result:
                            st.session_state.pending_charts.append(tool_result["chart_spec"])
                    
                    # Show tool result in expander
                    with tool_results_container.expander(f"Tool: {function_name} (~{tool_tokens} tokens)", expanded=False):
                        st.code(json.dumps(function_args, indent=2))
                        if tool_result.get("status") == "success":
                            st.success("✅ Success")
                            # Show summary
                            if "records" in tool_result:
                                st.write(f"Found {tool_result['records']} records")
                            if "data" in tool_result and isinstance(tool_result["data"], list) and tool_result["data"]:
                                df = pd.DataFrame(tool_result["data"][:5])
                                st.dataframe(df)
                        else:
                            st.error(f"❌ {tool_result.get('error', 'Failed')}")
                    
                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result, default=str)
                    })
                
                # Clear the status
                tool_status.empty()
                
                # Continue to next round
                continue
            else:
                # No more tool calls, we have the final response
                final_response = assistant_message.content
                
                # Calculate total tokens and cost
                total_tokens = total_input_tokens + total_output_tokens + total_tool_tokens
                # Estimate cost (GPT-5 pricing: $1.25 per 1000000 input, $10 per 1000000 output)
                estimated_cost = (total_input_tokens * (1.25/1000000) + (total_output_tokens + total_tool_tokens) * (10/1000000))

                # Add usage summary
                usage_summary = []
                if tool_call_count > 0:
                    usage_summary.append(f"Analysis completed using {tool_call_count} tool{'s' if tool_call_count > 1 else ''}")
                
                # Update session totals
                st.session_state.session_total_tokens += total_tokens
                st.session_state.session_total_cost += estimated_cost
                
                # Add token usage details
                token_details = [
                    f"**Token Usage (This Query):**",
                    f"• Input: ~{total_input_tokens:,} tokens",
                    f"• Output: ~{total_output_tokens:,} tokens", 
                    f"• Tool data: ~{total_tool_tokens:,} tokens",
                    f"• **Total: ~{total_tokens:,} tokens** (≈${estimated_cost:.3f})",
                    f"",
                    f"**Session Total:** ~{st.session_state.session_total_tokens:,} tokens (≈${st.session_state.session_total_cost:.3f})"
                ]
                
                if total_tool_tokens > 5000:
                    token_details.append("")
                    token_details.append("⚠️ **Optimization Tips:**")
                    if "get_financial_forecasts" in tool_calls_made:
                        token_details.append("• Use `get_forecast_summary` for overview questions")
                        token_details.append("• Specify fewer years (1-2 instead of all)")
                        token_details.append("• Use `statement_type='pnl'` when only P&L needed")
                    if total_tool_tokens > 10000:
                        token_details.append("• Consider breaking query into smaller, specific questions")
                        token_details.append("• Use year/ticker filters to reduce data volume")
                
                usage_summary.extend(token_details)
                
                if usage_summary:
                    final_response = f"{final_response}\n\n---\n" + "\n".join(usage_summary)
                break
        
        if not final_response:
            if rounds >= max_rounds:
                final_response = f"Analysis completed with {tool_call_count} tool calls. The query may be too complex."
            else:
                final_response = "Please provide a more specific question about companies, projects, or market data."
            
            # Add token usage even for edge cases
            total_tokens = total_input_tokens + total_output_tokens + total_tool_tokens
            if total_tokens > 0:
                estimated_cost = (total_input_tokens * (1.25/1000000) + (total_output_tokens + total_tool_tokens) * (10/1000000))
                final_response += f"\n\n---\n**Token Usage:** ~{total_tokens:,} tokens (≈${estimated_cost:.3f})"
        
        
        # Render any pending charts after the response
        if st.session_state.pending_charts and create_plotly_chart:
            for chart_spec in st.session_state.pending_charts:
                try:
                    fig = create_plotly_chart(chart_spec)
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Error rendering chart: {str(e)}")
            # Clear pending charts after rendering
            st.session_state.pending_charts = []
        
        return final_response


def render_enhanced_ai_interface():
    """Render the enhanced AI interface in Streamlit"""
    
    # st.header("Enhanced AI Assistant")
    st.markdown("Powered by GPT with automatic tool selection for comprehensive financial analysis")
    
    # Initialize tool system
    if 'enhanced_tool_system' not in st.session_state:
        st.session_state.enhanced_tool_system = get_enhanced_tool_system()
    
    tool_system = st.session_state.enhanced_tool_system
    
    # Initialize OpenAI client
    if 'openai_client' not in st.session_state:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            st.session_state.openai_client = OpenAI(api_key=api_key)
        else:
            st.session_state.openai_client = None
    
    # Check API key
    if not st.session_state.openai_client:
        st.error("⚠️ OpenAI API key not configured!")
        st.info("Please add OPENAI_API_KEY to your .env file")
        return
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Model selection
        model = st.selectbox(
            "Model",
            ["gpt-4o", "gpt-4.1", "gpt-5", "gpt-5-mini"],
            index=0  # Default to gpt-4o
        )
        os.environ["OPENAI_MODEL"] = model
        
        # Show available tools count
        st.metric("Available Tools", len(tool_system.get_tool_list()))
        
        # Show available tools
        with st.expander("📋 Available Tools", expanded=False):
            tools = tool_system.get_tool_list()
            for tool in tools:
                st.write(f"• {tool}")
        
        # Token usage statistics
        st.divider()
        st.subheader("📊 Token Usage")
        
        if 'session_total_tokens' in st.session_state:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Session Tokens", f"{st.session_state.session_total_tokens:,}")
            with col2:
                st.metric("Est. Cost", f"${st.session_state.session_total_cost:.3f}")
            
            if st.button("Reset Session Stats"):
                st.session_state.session_total_tokens = 0
                st.session_state.session_total_cost = 0.0
                st.rerun()
        
        # Clear history
        st.divider()
        if st.button("🗑️ Clear History"):
            st.session_state.tool_executions = []
            st.session_state.enhanced_chat_history = []
            st.rerun()
    
    # Main chat interface
    st.markdown("### 💬 Chat Interface")
    
    # Information box
    with st.expander("ℹ️ How to use", expanded=False):
        st.markdown("""
        **Example queries:**
        - "Show me VHM's financial performance for 2023"
        - "List all real estate projects for DXG and NLG"
        - "Compare revenue growth of VHM, DXG, and KDH from 2020 to 2023"
        - "What are the transaction volumes for apartments in Q1-Q3 2024?"
        - "Rank top 5 projects by revenue potential"
        - "Analyze credit outstanding trends for real estate sector"
        
        **The AI will automatically:**
        - Select appropriate tools to answer your query
        - Execute multiple tools if needed
        - Provide comprehensive analysis with data
        """)
    
    # Chat messages container for display
    if 'enhanced_chat_history' not in st.session_state:
        st.session_state.enhanced_chat_history = []
    
    # Display chat history
    for msg in st.session_state.enhanced_chat_history:
        if msg['role'] == 'user':
            with st.chat_message("user"):
                st.write(msg['content'])
        else:
            with st.chat_message("assistant"):
                st.write(msg['content'])
    
    # Chat input
    user_input = st.chat_input("Ask about companies, projects, or market data...")
    
    if user_input:
        # Add user message to history and display
        st.session_state.enhanced_chat_history.append({
            'role': 'user',
            'content': user_input,
            'timestamp': datetime.now().isoformat()
        })
        
        with st.chat_message("user"):
            st.write(user_input)
        
        # Get AI response
        with st.chat_message("assistant"):
            response_container = st.empty()
            
            # Process with OpenAI and tools (with streaming support)
            response = chat_with_ai(user_input, tool_system, stream_container=response_container)
            
            # Display response (only if not already streamed)
            if isinstance(response, str):
                # Either an error or the full response with token info
                # Clear container and write the full response
                response_container.markdown(response)
            
            # Add to history
            st.session_state.enhanced_chat_history.append({
                'role': 'assistant',
                'content': response,
                'timestamp': datetime.now().isoformat()
            })
    
    # Tool execution history
    if 'tool_executions' in st.session_state and st.session_state.tool_executions:
        with st.expander(f"🔧 Tool Execution History ({len(st.session_state.tool_executions)} executions)"):
            for i, execution in enumerate(reversed(st.session_state.tool_executions[-10:])):
                st.write(f"**{execution['tool']}** - {execution['timestamp']}")
                col1, col2 = st.columns(2)
                with col1:
                    st.code(json.dumps(execution['arguments'], indent=2), language="json")
                with col2:
                    if execution['result'].get('status') == 'success':
                        st.success("✅ Success")
                        if 'records' in execution['result']:
                            st.write(f"Records: {execution['result']['records']}")
                    else:
                        st.error(f"❌ {execution['result'].get('error', 'Failed')}")
                st.divider()