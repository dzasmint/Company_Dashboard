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
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
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
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.2,
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


def compress_ai_response(response: str, tool_calls_made: List[str], user_message: str) -> Dict:
    """Compress assistant response to structured data to save tokens"""
    import re
    
    compressed = {
        "tickers": [],
        "projects": [],
        "periods": [],
        "metrics": {},
        "analysis_type": "",
        "tools": tool_calls_made[:5],  # Keep first 5 tools
        "summary": ""
    }
    
    # Extract company tickers (3-4 letter uppercase)
    tickers = re.findall(r'\b[A-Z]{3,4}\b', response + " " + user_message)
    # Filter common real estate/financial tickers
    valid_tickers = ['VHM', 'DXG', 'NVL', 'NLG', 'KDH', 'TCH', 'TAL', 'NTL', 'BCM', 'PDR', 'VIC', 'VRE']
    compressed["tickers"] = list(set([t for t in tickers if t in valid_tickers]))[:10]
    
    # Extract project names (capitalized phrases)
    project_patterns = [
        r'(?:project|Project)\s+([A-Z][a-zA-Z\s]+)',
        r'([A-Z][a-zA-Z]+\s+(?:Park|Tower|City|Plaza|Residence|Garden))',
    ]
    for pattern in project_patterns:
        projects = re.findall(pattern, response)
        compressed["projects"].extend(projects)
    compressed["projects"] = list(set(compressed["projects"]))[:5]
    
    # Extract time periods (years, quarters, date ranges)
    years = re.findall(r'\b(20\d{2})\b', response)
    quarters = re.findall(r'\b(\d{4}-Q\d)\b|\b(Q\d\s*\d{4})\b', response)
    date_ranges = re.findall(r'\b(20\d{2})-?(20\d{2})\b', response)
    
    compressed["periods"] = list(set(years))[:5]
    if quarters:
        compressed["periods"].extend([q[0] if q[0] else q[1] for q in quarters[:3]])
    if date_ranges:
        compressed["periods"].append(f"{date_ranges[0][0]}-{date_ranges[0][1]}")
    
    # Extract key metrics mentioned
    metric_patterns = {
        "revenue": r'revenue[:\s]+([0-9,\.]+\s*(?:billion|trillion|B|T)?\s*VND)',
        "ebitda": r'EBITDA[:\s]+([0-9,\.]+)',
        "rnav": r'RNAV[:\s]+([0-9,\.]+)',
        "npv": r'NPV[:\s]+([0-9,\.]+)',
        "roe": r'ROE[:\s]+([0-9\.]+%)',
        "growth": r'growth[:\s]+([0-9\.]+%)'
    }
    
    for metric, pattern in metric_patterns.items():
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            compressed["metrics"][metric] = match.group(1)
    
    # Determine analysis type based on tools and content
    if any('forecast' in tool.lower() for tool in tool_calls_made):
        compressed["analysis_type"] = "forecast"
    elif any('project' in tool.lower() for tool in tool_calls_made):
        compressed["analysis_type"] = "project"
    elif any('market' in tool.lower() for tool in tool_calls_made):
        compressed["analysis_type"] = "market"
    elif any('financial' in tool.lower() for tool in tool_calls_made):
        compressed["analysis_type"] = "financial"
    else:
        compressed["analysis_type"] = "general"
    
    # Create summary
    if compressed["tickers"] and compressed["periods"]:
        compressed["summary"] = f"{', '.join(compressed['tickers'][:2])} {compressed['periods'][0]} {compressed['analysis_type']}"
    elif compressed["projects"]:
        compressed["summary"] = f"Projects: {', '.join(compressed['projects'][:2])}"
    elif compressed["tickers"]:
        compressed["summary"] = f"Analyzed {', '.join(compressed['tickers'][:3])}"
    else:
        compressed["summary"] = f"{compressed['analysis_type'].capitalize()} analysis"
    
    return compressed


def reconstruct_context(compressed_history: List[Dict]) -> str:
    """Reconstruct concise context from compressed history"""
    if not compressed_history:
        return ""
    
    context_parts = []
    
    # Only use last 3-5 exchanges
    recent_history = compressed_history[-6:] if len(compressed_history) > 6 else compressed_history
    
    for item in recent_history:
        if item.get("role") == "user":
            content = item.get("content", "")
            if len(content) > 100:
                context_parts.append(f"User asked: {content[:100]}...")
            else:
                context_parts.append(f"User asked: {content}")
                
        elif item.get("role") == "assistant_compressed":
            data = item.get("data", {})
            parts = []
            
            # Build context from compressed data
            if data.get("tickers"):
                parts.append(f"Discussed {', '.join(data['tickers'][:3])}")
            if data.get("projects"):
                parts.append(f"projects: {', '.join(data['projects'][:2])}")
            if data.get("periods"):
                parts.append(f"for {', '.join(data['periods'][:2])}")
            if data.get("analysis_type"):
                parts.append(f"({data['analysis_type']} analysis)")
            
            if parts:
                context_parts.append(" ".join(parts))
    
    return " | ".join(context_parts) if context_parts else ""


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


def chat_with_ai(user_message: str, tool_system: EnhancedAIToolSystem) -> str:
    """
    Send message to OpenAI and handle tool calls with compressed memory
    Similar to Bank_Sample/7_DucGPT_Chatbot.py implementation
    """
    # Initialize session state for memory
    if 'compressed_conversation_history' not in st.session_state:
        st.session_state.compressed_conversation_history = []
    
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
    
    # Reconstruct context from compressed history
    context_str = reconstruct_context(st.session_state.compressed_conversation_history)
    
    # Prepare messages
    messages = []
    
    # Add system message for real estate and financial analysis
    system_content = """You are a comprehensive financial analyst assistant specializing in Vietnamese real estate and financial markets.
Use the available tools to gather data and provide detailed analysis.

CRITICAL TOOL SELECTION RULES:

**Financial Data Tools:**
1. For HISTORICAL data (2016-2024): use get_historical_financials
   - Contains 1000+ companies (VHM, DXG, NLG, etc.)
   - Returns actual financial statements from CSV
   - Years are integers: 2023, 2024

2. For FORECAST data (2025-2030+): use get_financial_forecasts  
   - Available for: DXG, KDH, NTL, TAL, TCH only
   - Returns P&L, Balance Sheet, Cash Flow projections
   - Years are strings: "2025", "2026"

3. For valuation ratios: use get_valuation_metrics

4. **For PERIOD CALCULATIONS (NEW)**: use calculate_period_metrics
   - Handles half-year periods: 1H25, 2H25 (H = half year)
   - Handles quarters: 1Q25, 2Q25, 3Q25, 4Q25
   - AUTOMATICALLY derives values when possible:
     * 1H25 = Q1 2025 + Q2 2025 actuals
     * 2H25 = 2025 Annual Forecast - 1H25 actual (where 1H25 = Q1+Q2 actuals)
     * 4Q25 = 2025 Annual Forecast - (Q1+Q2+Q3 actuals)
   - For 2H calculation: Needs Q1 and Q2 actuals PLUS annual forecast
   - For 4Q calculation: Needs Q1, Q2, Q3 actuals PLUS annual forecast
   - Will explain if data is insufficient for calculation

**Real Estate Project Tools:**
- Basic info: list_real_estate_projects, get_project_details (includes all financial data), rank_projects_by_metric
- RNAV analysis: calculate_rnav_sensitivity (sensitivity analysis with adjustments)
- RNAV valuation: All tools now include rnav_value (Revalued Net Asset Value)
- Available for: KDH, TAL, TCH projects in MongoDB (24 total projects)

**Other Analysis Tools:**
- Market data: get_transaction_volumes, analyze_market_trends (MoC data)
- Comparisons: compare_companies

**Data Format Requirements:**
- Tickers must be arrays: ["VHM"] for single, ["VHM", "DXG"] for multiple
- Historical years: integers (2023, 2024)
- Forecast years: strings ("2025", "2026")

**When user asks about:**
- "Current" or "recent" or years ≤2024: use get_historical_financials
- "Future" or "forecast" or years ≥2025: use get_financial_forecasts
- Both historical and forecast: call BOTH tools separately

**Period Notation Understanding:**
- 1H25/2H25 = First/Second half of 2025
- 1Q25-4Q25 = Quarters 1-4 of 2025
- When user asks for "2H25 PATMI" or any 2H metric:
  1. Use calculate_period_metrics tool
  2. Tool will check if Q1 2025 and Q2 2025 actuals exist
  3. If yes, calculates: 2H25 = 2025 Annual Forecast - (Q1+Q2 actuals)
  4. If no, explains: "Need Q1 and Q2 2025 actuals to calculate 2H25"
- When user asks for "4Q25 forecast":
  1. Use calculate_period_metrics tool
  2. Tool will check if Q1, Q2, Q3 2025 actuals exist
  3. If yes, calculates: 4Q25 = 2025 Annual Forecast - (Q1+Q2+Q3 actuals)
  4. If no, explains: "Need Q1-Q3 2025 actuals to derive Q4 2025"
- IMPORTANT: For 2H calculations, we need Q1+Q2 actuals (NOT Q3+Q4)"""
    
    # Add context from previous conversation if available
    if context_str:
        system_content += f"\n\n**Previous conversation context:**\n{context_str}"
    
    messages.append({
        "role": "system",
        "content": system_content
    })
    
    # Add user message
    messages.append({"role": "user", "content": user_message})
    
    # Get tool schemas
    tools = tool_system.get_openai_tools()
    
    # Initialize progress tracking
    max_rounds = 20
    tool_calls_made = []  # Track tool calls for compression
    with st.spinner("🤖 AI is analyzing..."):
        rounds = 0
        final_response = None
        tool_call_count = 0
        
        while rounds < max_rounds:
            rounds += 1
            
            # Call OpenAI
            try:
                response = st.session_state.openai_client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.5
                )
            except Exception as e:
                return f"❌ Error calling OpenAI: {str(e)}"
            
            # Get assistant message
            assistant_message = response.choices[0].message
            messages.append(assistant_message.model_dump())
            
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
                    tool_status.info(f"🔧 Executing tool #{tool_call_count}: **{function_name}**")
                    
                    # Execute the tool
                    tool_result = execute_tool_call(tool_system, function_name, function_args)
                    
                    # Check if this is a chart rendering tool
                    if function_name in ["render_chart", "create_financial_chart"] and tool_result.get("status") == "success":
                        if "chart_spec" in tool_result:
                            st.session_state.pending_charts.append(tool_result["chart_spec"])
                    
                    # Show tool result in expander
                    with tool_results_container.expander(f"Tool: {function_name}", expanded=False):
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
                # Add tool count summary
                if tool_call_count > 0:
                    final_response = f"{final_response}\n\n---\n*Analysis completed using {tool_call_count} tool{'s' if tool_call_count > 1 else ''}.*"
                break
        
        if not final_response:
            if rounds >= max_rounds:
                final_response = f"Analysis completed with {tool_call_count} tool calls. The query may be too complex."
            else:
                final_response = "Please provide a more specific question about companies, projects, or market data."
        
        # Update conversation history with compressed data
        if final_response:
            # Add user message
            st.session_state.compressed_conversation_history.append({
                "role": "user",
                "content": user_message,
                "timestamp": datetime.now().isoformat()
            })
            
            # Compress and add assistant response
            compressed_response = compress_ai_response(final_response, tool_calls_made, user_message)
            st.session_state.compressed_conversation_history.append({
                "role": "assistant_compressed",
                "data": compressed_response,
                "timestamp": datetime.now().isoformat()
            })
            
            # Keep only last 10 messages (5 exchanges)
            if len(st.session_state.compressed_conversation_history) > 10:
                st.session_state.compressed_conversation_history = st.session_state.compressed_conversation_history[-10:]
        
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
            ["gpt-4-turbo-preview", "gpt-3.5-turbo"],
            index=0
        )
        os.environ["OPENAI_MODEL"] = model
        
        # Show available tools count
        st.metric("Available Tools", len(tool_system.get_tool_list()))
        
        # Show available tools
        with st.expander("📋 Available Tools", expanded=False):
            tools = tool_system.get_tool_list()
            for tool in tools:
                st.write(f"• {tool}")
        
        # Memory indicator
        if 'compressed_conversation_history' in st.session_state:
            memory_count = len(st.session_state.compressed_conversation_history)
            st.metric("Memory", f"{memory_count}/10 messages")
            
            # Show compressed memory details
            with st.expander("💾 Memory Details", expanded=False):
                for item in st.session_state.compressed_conversation_history[-4:]:
                    if item.get("role") == "assistant_compressed":
                        data = item.get("data", {})
                        st.caption(data.get("summary", ""))
        
        # Clear history
        if st.button("🗑️ Clear History"):
            st.session_state.tool_executions = []
            st.session_state.enhanced_chat_history = []
            st.session_state.compressed_conversation_history = []
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
    
    # Initialize compressed conversation history
    if 'compressed_conversation_history' not in st.session_state:
        st.session_state.compressed_conversation_history = []
    
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
            
            # Process with OpenAI and tools
            response = chat_with_ai(user_input, tool_system)
            
            # Display response
            response_container.write(response)
            
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