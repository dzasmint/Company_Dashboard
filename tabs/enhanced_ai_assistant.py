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
        self._register_financial_tools()
        self._register_real_estate_tools()
        self._register_forecast_analysis_tools()
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
    
    def _register_financial_tools(self):
        """Register company financial analysis tools"""
        
        @self.tool(
            name="get_historical_financials",
            description="Get historical financial statements from parquet data (2016-2024, quarterly and annual)",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Company tickers (e.g., ['VHM', 'DXG'])",
                    "required": True
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Financial metrics KEYCODEs (e.g., ['Net_Revenue', 'EBITDA', 'NPATMI'])",
                    "required": False
                },
                "years": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Historical years to retrieve (2016-2024)",
                    "required": False
                },
                "period_type": {
                    "type": "string",
                    "enum": ["annual", "quarterly", "both"],
                    "description": "Period type: 'annual' for yearly data, 'quarterly' for quarterly data, 'both' for all",
                    "required": False
                },
                "quarters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific quarters (e.g., ['2024Q1', '2024Q2', '2024Q3'])",
                    "required": False
                }
            }
        )
        def get_historical_financials(tickers: List[str], metrics: List[str] = None, 
                                     years: List[int] = None, period_type: str = "annual",
                                     quarters: List[str] = None) -> Dict:
            """Get historical financial statements from CSV data (annual or quarterly)"""
            
            # Normalize tickers
            tickers = [t.upper() for t in tickers]
            
            # Load appropriate data based on period_type
            if period_type == "quarterly" or quarters:
                # Load quarterly data
                df = self._load_quarterly_financial_statements()
                data_type = "quarterly"
            elif period_type == "both":
                # Load both annual and quarterly data
                df_annual = self._load_financial_statements_csv()
                df_quarterly = self._load_quarterly_financial_statements()
                
                # Combine both datasets
                if not df_annual.empty and not df_quarterly.empty:
                    # Add period type column for clarity
                    df_annual['PERIOD'] = 'Annual'
                    df_quarterly['PERIOD'] = 'Quarterly'
                    df = pd.concat([df_annual, df_quarterly], ignore_index=True)
                    data_type = "both"
                elif not df_annual.empty:
                    df = df_annual
                    data_type = "annual"
                else:
                    df = df_quarterly
                    data_type = "quarterly"
            else:
                # Default to annual data
                df = self._load_financial_statements_csv()
                data_type = "annual"
            
            if df.empty:
                return {"error": "Historical financial data not available", "status": "failed"}
            
            # Filter by tickers
            df = df[df['TICKER'].isin(tickers)]
            
            if df.empty:
                return {
                    "error": f"No data found for tickers: {tickers}",
                    "status": "failed"
                }
            
            # Filter by years if specified (for annual data)
            if years and data_type in ["annual", "both"]:
                if data_type == "annual":
                    df = df[df['DATE'].isin(years)]
                else:
                    # For combined data, filter annual records by years
                    mask = (df['PERIOD'] == 'Quarterly') | (df['DATE'].isin(years))
                    df = df[mask]
            
            # Filter by quarters if specified (for quarterly data)
            if quarters and data_type in ["quarterly", "both"]:
                if data_type == "quarterly":
                    df = df[df['DATE'].isin(quarters)]
                else:
                    # For combined data, filter quarterly records by quarters
                    mask = (df['PERIOD'] == 'Annual') | (df['DATE'].isin(quarters))
                    df = df[mask]
            
            # Filter by year from quarters (e.g., get all quarters for specific years)
            if years and data_type == "quarterly" and not quarters:
                # Extract year from quarterly DATE (e.g., '2024Q1' -> 2024)
                df['YEAR_NUM'] = df['DATE'].str[:4].astype(int)
                df = df[df['YEAR_NUM'].isin(years)]
                df = df.drop('YEAR_NUM', axis=1)
            
            # Filter by metrics if specified
            if metrics:
                # Map common names to KEYCODEs
                metric_mapping = {
                    'revenue': 'Net_Revenue',
                    'ebitda': 'EBITDA',
                    'npat': 'NPAT',
                    'npatmi': 'NPATMI',
                    'gross_profit': 'Gross_Profit',
                    'gross_margin': 'Gross_Margin',
                    'operating_cash_flow': 'Opt_CF',
                    'ebitda_margin': 'EBITDA_Margin',
                    'npat_margin': 'NPAT_Margin',
                    'total_assets': 'Total_Assets',
                    'total_debt': 'Total_Debt',
                    'equity': 'Equity',
                    'cogs': 'COGS',
                    'sga': 'SGA',
                    'interest_expense': 'Interest_Expense'
                }
                
                mapped_metrics = []
                for m in metrics:
                    mapped = metric_mapping.get(m.lower(), m)
                    mapped_metrics.append(mapped)
                
                df = df[df['KEYCODE'].isin(mapped_metrics)]
            
            # Pivot data for better readability
            if not df.empty and len(df['KEYCODE'].unique()) > 1:
                # Determine index columns based on data type
                index_cols = ['TICKER', 'DATE']
                if 'PERIOD' in df.columns:
                    index_cols.append('PERIOD')
                
                pivot_df = df.pivot_table(
                    index=index_cols,
                    columns='KEYCODE',
                    values='VALUE',
                    aggfunc='first'
                ).reset_index()
                
                return {
                    "data": pivot_df.to_dict('records'),
                    "source": f"historical_{data_type}",
                    "records": len(pivot_df),
                    "period_type": data_type,
                    "date_range": f"{df['DATE'].min()}-{df['DATE'].max()}",
                    "status": "success"
                }
            else:
                return {
                    "data": df.to_dict('records'),
                    "source": f"historical_{data_type}",
                    "records": len(df),
                    "period_type": data_type,
                    "date_range": f"{df['DATE'].min()}-{df['DATE'].max()}" if not df.empty else "N/A",
                    "status": "success"
                }
        
        @self.tool(
            name="calculate_period_metrics",
            description="""Calculate metrics for specific periods (half-year, quarters) using available data.
            Handles derived calculations like 2H25 PATMI = 2025 Forecast - (1Q25 + 2Q25 actual).
            Supports period notations: 1H25, 2H25, 1Q25-4Q25, etc.""",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker",
                    "required": True
                },
                "metric": {
                    "type": "string",
                    "description": "Financial metric (e.g., NPATMI, Net_Revenue, EBITDA)",
                    "required": True
                },
                "period": {
                    "type": "string",
                    "description": "Period notation (e.g., 2H25, 4Q25, 1H24)",
                    "required": True
                },
                "calculation_method": {
                    "type": "string",
                    "enum": ["derive", "sum", "auto"],
                    "description": "Method: derive (from forecast), sum (add quarters), auto (best available)",
                    "required": False
                }
            }
        )
        def calculate_period_metrics(ticker: str, metric: str, period: str, 
                                    calculation_method: str = "auto") -> Dict:
            """Calculate metrics for specific periods using available data"""
            
            ticker = ticker.upper()
            
            # Parse the period notation
            period_info = self._parse_period_notation(period)
            if not period_info["year"]:
                return {
                    "error": f"Invalid period notation: {period}",
                    "example_formats": ["1H25", "2H24", "1Q25", "4Q24"],
                    "status": "failed"
                }
            
            year = period_info["year"]
            
            # Check data availability
            availability = self._check_data_availability(ticker, year, [metric])
            
            # Perform calculation based on period type
            if period_info["type"] == "half":
                half_num = period_info["period_num"]
                
                if half_num == 1:  # First half (Q1 + Q2)
                    if availability["can_calculate_1H"]:
                        # Sum Q1 and Q2
                        df_q = self._load_quarterly_financial_statements()
                        q1_data = df_q[(df_q['TICKER'] == ticker) & 
                                      (df_q['DATE'] == f"{year}Q1") & 
                                      (df_q['KEYCODE'] == metric)]
                        q2_data = df_q[(df_q['TICKER'] == ticker) & 
                                      (df_q['DATE'] == f"{year}Q2") & 
                                      (df_q['KEYCODE'] == metric)]
                        
                        if not q1_data.empty and not q2_data.empty:
                            # Convert to billions VND for consistency
                            value = (q1_data['VALUE'].iloc[0] + q2_data['VALUE'].iloc[0]) / 1e9
                            return {
                                "period": f"1H{year}",
                                "metric": metric,
                                "value": value,
                                "calculation": f"Q1{year} + Q2{year}",
                                "method": "sum_quarters",
                                "data_source": "historical_quarterly",
                                "status": "success"
                            }
                    
                    return {
                        "error": f"Cannot calculate 1H{year} {metric}",
                        "reason": f"Missing quarters: {', '.join([q for q in [f'{year}Q1', f'{year}Q2'] if q not in availability['quarters_available']])}",
                        "available_quarters": availability["quarters_available"],
                        "status": "failed"
                    }
                
                else:  # Second half (derive from annual or sum Q3+Q4)
                    # Try to derive from annual forecast minus 1H actual
                    if availability["annual_forecast"] and availability["can_calculate_1H"]:
                        # Get annual forecast
                        if self.vietnam_stocks_db is not None:
                            collection = self.vietnam_stocks_db['CompanyForecast']
                            forecast = collection.find_one({'ticker': ticker})
                            if forecast and year in forecast.get('forecast_data', {}):
                                # Try different locations for the metric
                                pnl = forecast['forecast_data'][year].get('pnl', {})
                                # Handle different naming conventions for NPATMI
                                if metric == 'NPATMI':
                                    annual_value = pnl.get('npatmi') or pnl.get('NPATMI') or pnl.get('patmi')
                                else:
                                    annual_value = pnl.get(metric.lower()) or pnl.get(metric)
                                
                                if annual_value:
                                    # Get 1H actual
                                    df_q = self._load_quarterly_financial_statements()
                                    q1_data = df_q[(df_q['TICKER'] == ticker) & 
                                                  (df_q['DATE'] == f"{year}Q1") & 
                                                  (df_q['KEYCODE'] == metric)]
                                    q2_data = df_q[(df_q['TICKER'] == ticker) & 
                                                  (df_q['DATE'] == f"{year}Q2") & 
                                                  (df_q['KEYCODE'] == metric)]
                                    
                                    if not q1_data.empty and not q2_data.empty:
                                        # Both annual_value (from MongoDB) and quarterly values are in raw VND
                                        h1_value_raw = q1_data['VALUE'].iloc[0] + q2_data['VALUE'].iloc[0]
                                        h2_value_raw = annual_value - h1_value_raw
                                        
                                        # Convert to billions for display
                                        h1_value = h1_value_raw / 1e9
                                        h2_value = h2_value_raw / 1e9
                                        annual_value_bn = annual_value / 1e9
                                        
                                        return {
                                            "period": f"2H{year}",
                                            "metric": metric,
                                            "value": h2_value,
                                            "calculation": f"{year} Forecast ({annual_value_bn:.2f}B) - 1H{year} Actual ({h1_value:.2f}B)",
                                            "method": "derive_from_forecast",
                                            "data_source": "forecast_minus_actual",
                                            "status": "success"
                                        }
                    
                    # Try to sum Q3 and Q4 if available
                    if f"{year}Q3" in availability["quarters_available"] and f"{year}Q4" in availability["quarters_available"]:
                        df_q = self._load_quarterly_financial_statements()
                        q3_data = df_q[(df_q['TICKER'] == ticker) & 
                                      (df_q['DATE'] == f"{year}Q3") & 
                                      (df_q['KEYCODE'] == metric)]
                        q4_data = df_q[(df_q['TICKER'] == ticker) & 
                                      (df_q['DATE'] == f"{year}Q4") & 
                                      (df_q['KEYCODE'] == metric)]
                        
                        if not q3_data.empty and not q4_data.empty:
                            # Convert to billions VND for consistency
                            value = (q3_data['VALUE'].iloc[0] + q4_data['VALUE'].iloc[0]) / 1e9
                            return {
                                "period": f"2H{year}",
                                "metric": metric,
                                "value": value,
                                "calculation": f"Q3{year} + Q4{year}",
                                "method": "sum_quarters",
                                "data_source": "historical_quarterly",
                                "status": "success"
                            }
                    
                    return {
                        "error": f"Cannot calculate 2H{year} {metric}",
                        "reason": "Need either (1) annual forecast + 1H actual, or (2) Q3 and Q4 actuals",
                        "available_data": {
                            "annual_forecast": availability["annual_forecast"],
                            "1H_actual": availability["can_calculate_1H"],
                            "Q3_Q4_actual": f"{year}Q3" in availability["quarters_available"] and f"{year}Q4" in availability["quarters_available"]
                        },
                        "status": "failed"
                    }
            
            elif period_info["type"] == "quarter":
                quarter_str = period_info["required_quarters"][0]
                quarter_num = period_info["period_num"]
                
                # Check if quarter data exists
                if quarter_str in availability["quarters_available"]:
                    df_q = self._load_quarterly_financial_statements()
                    q_data = df_q[(df_q['TICKER'] == ticker) & 
                                 (df_q['DATE'] == quarter_str) & 
                                 (df_q['KEYCODE'] == metric)]
                    
                    if not q_data.empty:
                        return {
                            "period": quarter_str,
                            "metric": metric,
                            "value": q_data['VALUE'].iloc[0] / 1e9,  # Convert to billions VND
                            "method": "direct",
                            "data_source": "historical_quarterly",
                            "status": "success"
                        }
                
                # Try to derive from annual forecast if Q4
                if quarter_num == 4 and availability["annual_forecast"]:
                    # Check if Q1-Q3 are available
                    q1_q3_available = all(f"{year}Q{i}" in availability["quarters_available"] for i in range(1, 4))
                    
                    if q1_q3_available:
                        # Get annual forecast
                        if self.vietnam_stocks_db is not None:
                            collection = self.vietnam_stocks_db['CompanyForecast']
                            forecast = collection.find_one({'ticker': ticker})
                            if forecast and year in forecast.get('forecast_data', {}):
                                # Try different locations for the metric
                                pnl = forecast['forecast_data'][year].get('pnl', {})
                                # Handle different naming conventions for NPATMI
                                if metric == 'NPATMI':
                                    annual_value = pnl.get('npatmi') or pnl.get('NPATMI') or pnl.get('patmi')
                                else:
                                    annual_value = pnl.get(metric.lower()) or pnl.get(metric)
                                
                                if annual_value:
                                    # Sum Q1-Q3
                                    df_q = self._load_quarterly_financial_statements()
                                    q1_q3_sum_raw = 0
                                    for q in range(1, 4):
                                        q_data = df_q[(df_q['TICKER'] == ticker) & 
                                                     (df_q['DATE'] == f"{year}Q{q}") & 
                                                     (df_q['KEYCODE'] == metric)]
                                        if not q_data.empty:
                                            q1_q3_sum_raw += q_data['VALUE'].iloc[0]  # Keep in raw VND
                                    
                                    # Both annual_value and q1_q3_sum are in raw VND
                                    q4_value_raw = annual_value - q1_q3_sum_raw
                                    
                                    # Convert to billions for display
                                    q4_value = q4_value_raw / 1e9
                                    annual_value_bn = annual_value / 1e9
                                    q1_q3_sum_bn = q1_q3_sum_raw / 1e9
                                    
                                    return {
                                        "period": f"Q4{year}",
                                        "metric": metric,
                                        "value": q4_value,
                                        "calculation": f"{year} Forecast ({annual_value_bn:.2f}B) - (Q1+Q2+Q3) ({q1_q3_sum_bn:.2f}B)",
                                        "method": "derive_from_forecast",
                                        "data_source": "forecast_minus_actual",
                                        "status": "success"
                                    }
                
                return {
                    "error": f"Cannot calculate {quarter_str} {metric}",
                    "reason": f"Quarter data not available and cannot derive",
                    "available_quarters": availability["quarters_available"],
                    "suggestion": f"Need Q1-Q3 {year} actuals and {year} forecast to derive Q4" if quarter_num == 4 else f"Need actual {quarter_str} data",
                    "status": "failed"
                }
            
            return {
                "error": f"Unsupported period type: {period_info['type']}",
                "status": "failed"
            }
        
        @self.tool(
            name="get_valuation_metrics",
            description="Get valuation metrics (P/E, P/B, EV/EBITDA) for companies",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Company tickers",
                    "required": True
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Valuation metrics (P/E, P/B, P/S, EV/EBITDA)",
                    "required": False
                },
                "date_range": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "string"},
                        "end": {"type": "string"}
                    },
                    "description": "Date range (YYYY-MM-DD format)",
                    "required": False
                }
            }
        )
        def get_valuation_metrics(tickers: List[str], metrics: List[str] = None,
                                 date_range: Dict = None) -> Dict:
            """Get valuation metrics"""
            
            tickers = [t.upper() for t in tickers]
            
            # Load valuation data
            df = self._load_valuation_csv()
            
            if df.empty:
                return {"error": "Valuation data not available", "status": "failed"}
            
            # Filter by tickers
            df = df[df['TICKER'].isin(tickers)]
            
            # Filter by date range
            if date_range:
                if 'start' in date_range:
                    df = df[df['TRADE_DATE'] >= date_range['start']]
                if 'end' in date_range:
                    df = df[df['TRADE_DATE'] <= date_range['end']]
            
            # Filter by metrics
            if metrics:
                cols = ['TICKER', 'TRADE_DATE']
                for metric in metrics:
                    if metric in df.columns:
                        cols.append(metric)
                df = df[cols]
            
            # Get latest values for each ticker
            latest_df = df.sort_values('TRADE_DATE').groupby('TICKER').last().reset_index()
            
            return {
                "latest_values": latest_df.to_dict('records'),
                "historical_data": df.head(100).to_dict('records'),
                "records": len(df),
                "status": "success"
            }
        
        @self.tool(
            name="get_company_valuation_metrics",
            description="Get comprehensive valuation metrics including RNAV, P/E, P/B from saved forecast data",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of company tickers",
                    "required": True
                },
                "include_rnav": {
                    "type": "boolean",
                    "description": "Include RNAV analysis",
                    "required": False
                },
                "include_multiples": {
                    "type": "boolean",
                    "description": "Include P/E and P/B multiples",
                    "required": False
                },
                "include_comparison": {
                    "type": "boolean",
                    "description": "Include peer comparison",
                    "required": False
                }
            }
        )
        def get_company_valuation_metrics(tickers: List[str], include_rnav: bool = True, 
                                         include_multiples: bool = True, include_comparison: bool = False) -> Dict:
            """Get comprehensive valuation metrics from saved data"""
            
            tickers = [t.upper() for t in tickers]
            results = {}
            
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            try:
                forecast_collection = self.vietnam_stocks_db['CompanyForecast']
                
                for ticker in tickers:
                    # Get saved forecast with valuation data
                    forecast_doc = forecast_collection.find_one({"ticker": ticker})
                    
                    if not forecast_doc:
                        results[ticker] = {"error": f"No forecast data for {ticker}"}
                        continue
                    
                    valuation_data = forecast_doc.get('valuation_data', {})
                    
                    if not valuation_data:
                        results[ticker] = {"error": f"No valuation data saved for {ticker}"}
                        continue
                    
                    ticker_result = {
                        "current_price": valuation_data.get('current_price', 0),
                        "last_updated": forecast_doc.get('last_updated', '').isoformat() if forecast_doc.get('last_updated') else None
                    }
                    
                    # Add RNAV metrics
                    if include_rnav:
                        rnav_per_share = valuation_data.get('rnav_per_share', 0)
                        current_price = valuation_data.get('current_price', 0)
                        
                        ticker_result['rnav'] = {
                            "rnav_per_share": rnav_per_share,
                            "upside_pct": ((rnav_per_share / current_price - 1) * 100) if current_price > 0 else 0,
                            "has_details": len(valuation_data.get('rnav_details', [])) > 0
                        }
                    
                    # Add multiples
                    if include_multiples and 'multiples' in valuation_data:
                        multiples = valuation_data['multiples']
                        current_year = datetime.now().year
                        next_year = current_year + 1
                        
                        ticker_result['multiples'] = {
                            "trailing_PE": multiples.get('trailing_PE'),
                            "trailing_PB": multiples.get('trailing_PB'),
                            f"{current_year}F_PE": multiples.get(f'{current_year}F_PE'),
                            f"{current_year}F_PB": multiples.get(f'{current_year}F_PB'),
                            f"{next_year}F_PE": multiples.get(f'{next_year}F_PE'),
                            f"{next_year}F_PB": multiples.get(f'{next_year}F_PB'),
                            "mean_PE": multiples.get('mean_PE'),
                            "mean_PB": multiples.get('mean_PB')
                        }
                        
                        # Calculate vs mean percentages
                        if multiples.get(f'{current_year}F_PE') and multiples.get('mean_PE'):
                            pe_vs_mean = ((multiples.get(f'{current_year}F_PE') / multiples.get('mean_PE') - 1) * 100)
                            ticker_result['multiples']['PE_vs_mean_pct'] = round(pe_vs_mean, 1)
                        
                        if multiples.get(f'{current_year}F_PB') and multiples.get('mean_PB'):
                            pb_vs_mean = ((multiples.get(f'{current_year}F_PB') / multiples.get('mean_PB') - 1) * 100)
                            ticker_result['multiples']['PB_vs_mean_pct'] = round(pb_vs_mean, 1)
                    
                    results[ticker] = ticker_result
                
                # Add comparison if requested
                if include_comparison and len(tickers) > 1:
                    comparison = self._compare_valuation_metrics(results)
                    results['comparison'] = comparison
                
                return {
                    "data": results,
                    "tickers": tickers,
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
        def _compare_valuation_metrics(self, results: Dict) -> Dict:
            """Helper to compare valuation metrics across companies"""
            comparison = {
                "rnav_upside_ranking": [],
                "pe_ranking": [],
                "pb_ranking": [],
                "most_attractive": None
            }
            
            # Rank by RNAV upside
            rnav_data = []
            for ticker, data in results.items():
                if isinstance(data, dict) and 'rnav' in data:
                    rnav_data.append({
                        "ticker": ticker,
                        "upside_pct": data['rnav'].get('upside_pct', 0)
                    })
            
            if rnav_data:
                rnav_data.sort(key=lambda x: x['upside_pct'], reverse=True)
                comparison['rnav_upside_ranking'] = rnav_data
            
            # Rank by P/E (lower is better)
            pe_data = []
            current_year = datetime.now().year
            for ticker, data in results.items():
                if isinstance(data, dict) and 'multiples' in data:
                    pe_value = data['multiples'].get(f'{current_year}F_PE')
                    if pe_value:
                        pe_data.append({
                            "ticker": ticker,
                            "pe": pe_value,
                            "vs_mean_pct": data['multiples'].get('PE_vs_mean_pct', 0)
                        })
            
            if pe_data:
                pe_data.sort(key=lambda x: x['pe'])
                comparison['pe_ranking'] = pe_data
            
            # Determine most attractive overall
            if rnav_data and pe_data:
                # Simple scoring: high RNAV upside + low P/E
                scores = {}
                for ticker in results.keys():
                    if isinstance(results[ticker], dict) and 'error' not in results[ticker]:
                        score = 0
                        # RNAV score
                        rnav_rank = next((i for i, x in enumerate(rnav_data) if x['ticker'] == ticker), len(rnav_data))
                        score += (len(rnav_data) - rnav_rank) * 2  # Weight RNAV more
                        
                        # P/E score
                        pe_rank = next((i for i, x in enumerate(pe_data) if x['ticker'] == ticker), len(pe_data))
                        score += (len(pe_data) - pe_rank)
                        
                        scores[ticker] = score
                
                if scores:
                    most_attractive = max(scores, key=scores.get)
                    comparison['most_attractive'] = {
                        "ticker": most_attractive,
                        "score": scores[most_attractive],
                        "reason": "Highest combined score from RNAV upside and P/E valuation"
                    }
            
            return comparison
        
        @self.tool(
            name="get_rnav_breakdown",
            description="Get detailed RNAV breakdown by project and balance sheet items",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker",
                    "required": True
                },
                "include_projects": {
                    "type": "boolean",
                    "description": "Include project-by-project breakdown",
                    "required": False
                },
                "include_balance_sheet": {
                    "type": "boolean",
                    "description": "Include balance sheet adjustments",
                    "required": False
                }
            }
        )
        def get_rnav_breakdown(ticker: str, include_projects: bool = True, 
                              include_balance_sheet: bool = True) -> Dict:
            """Get detailed RNAV breakdown"""
            
            ticker = ticker.upper()
            
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            try:
                forecast_collection = self.vietnam_stocks_db['CompanyForecast']
                
                # Get saved forecast with valuation data
                forecast_doc = forecast_collection.find_one({"ticker": ticker})
                
                if not forecast_doc or 'valuation_data' not in forecast_doc:
                    return {"error": f"No valuation data for {ticker}", "status": "failed"}
                
                valuation_data = forecast_doc['valuation_data']
                rnav_details = valuation_data.get('rnav_details', [])
                
                if not rnav_details:
                    return {"error": f"No RNAV breakdown available for {ticker}", "status": "failed"}
                
                result = {
                    "ticker": ticker,
                    "rnav_per_share": valuation_data.get('rnav_per_share', 0),
                    "current_price": valuation_data.get('current_price', 0)
                }
                
                # Separate projects and balance sheet items
                projects = []
                balance_sheet_items = []
                summary_items = []
                
                for item in rnav_details:
                    item_name = item.get('item', '')
                    
                    if 'TOTAL' in item_name or 'SUB-TOTAL' in item_name or 'RNAV/share' in item_name or 'Outstanding Shares' in item_name:
                        summary_items.append(item)
                    elif any(bs_item in item_name for bs_item in ['Cash', 'Investment', 'Debt']):
                        if include_balance_sheet:
                            balance_sheet_items.append(item)
                    elif item_name and item_name.strip().startswith('  '):  # Project items are indented
                        if include_projects:
                            projects.append(item)
                
                if include_projects and projects:
                    result['projects'] = projects
                    result['total_project_rnav'] = sum(p.get('rnav_to_company', 0) for p in projects if p.get('rnav_to_company'))
                
                if include_balance_sheet and balance_sheet_items:
                    result['balance_sheet_adjustments'] = balance_sheet_items
                    result['net_bs_adjustment'] = sum(item.get('rnav_to_company', 0) for item in balance_sheet_items if item.get('rnav_to_company'))
                
                result['summary'] = summary_items
                
                # Calculate upside
                if result['current_price'] > 0:
                    result['upside_pct'] = ((result['rnav_per_share'] / result['current_price'] - 1) * 100)
                
                return {
                    "data": result,
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
        @self.tool(
            name="get_forward_multiples",
            description="Get forward P/E and P/B multiples for current and next year",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker",
                    "required": True
                },
                "years": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Specific years to get multiples for",
                    "required": False
                }
            }
        )
        def get_forward_multiples(ticker: str, years: List[int] = None) -> Dict:
            """Get forward valuation multiples"""
            
            ticker = ticker.upper()
            
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            try:
                forecast_collection = self.vietnam_stocks_db['CompanyForecast']
                
                # Get saved forecast with valuation data
                forecast_doc = forecast_collection.find_one({"ticker": ticker})
                
                if not forecast_doc or 'valuation_data' not in forecast_doc:
                    return {"error": f"No valuation data for {ticker}", "status": "failed"}
                
                valuation_data = forecast_doc['valuation_data']
                multiples = valuation_data.get('multiples', {})
                
                if not years:
                    current_year = datetime.now().year
                    years = [current_year, current_year + 1]
                
                result = {
                    "ticker": ticker,
                    "current_price": valuation_data.get('current_price', 0),
                    "multiples": {}
                }
                
                # Get multiples for requested years
                for year in years:
                    year_key = f"{year}F"
                    result['multiples'][year] = {
                        "PE": multiples.get(f'{year_key}_PE'),
                        "PB": multiples.get(f'{year_key}_PB')
                    }
                
                # Add trailing and mean for comparison
                result['trailing'] = {
                    "PE": multiples.get('trailing_PE'),
                    "PB": multiples.get('trailing_PB')
                }
                
                result['historical_mean'] = {
                    "PE": multiples.get('mean_PE'),
                    "PB": multiples.get('mean_PB')
                }
                
                # Calculate vs mean
                current_year = datetime.now().year
                if multiples.get(f'{current_year}F_PE') and multiples.get('mean_PE'):
                    result['vs_mean'] = {
                        "PE_pct": ((multiples.get(f'{current_year}F_PE') / multiples.get('mean_PE') - 1) * 100),
                        "PB_pct": ((multiples.get(f'{current_year}F_PB') / multiples.get('mean_PB') - 1) * 100) if multiples.get(f'{current_year}F_PB') and multiples.get('mean_PB') else None
                    }
                
                return {
                    "data": result,
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
        @self.tool(
            name="compare_valuation_metrics",
            description="Compare valuation metrics across multiple companies",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of company tickers to compare",
                    "required": True
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Metrics to compare (rnav_upside, pe_current, pb_current, pe_next, pb_next)",
                    "required": False
                },
                "sort_by": {
                    "type": "string",
                    "description": "Metric to sort by",
                    "required": False
                },
                "include_ranking": {
                    "type": "boolean",
                    "description": "Include ranking analysis",
                    "required": False
                }
            }
        )
        def compare_valuation_metrics(tickers: List[str], metrics: List[str] = None,
                                     sort_by: str = 'rnav_upside', include_ranking: bool = True) -> Dict:
            """Compare valuation metrics across companies"""
            
            if not metrics:
                metrics = ['rnav_upside', 'pe_current', 'pb_current', 'pe_next', 'pb_next']
            
            tickers = [t.upper() for t in tickers]
            
            # Get valuation metrics for all tickers
            valuation_data = get_company_valuation_metrics(tickers, include_rnav=True, include_multiples=True, include_comparison=False)
            
            if valuation_data.get('status') != 'success':
                return valuation_data
            
            comparison_data = []
            current_year = datetime.now().year
            next_year = current_year + 1
            
            for ticker in tickers:
                ticker_data = valuation_data['data'].get(ticker, {})
                
                if 'error' in ticker_data:
                    continue
                
                row = {"ticker": ticker}
                
                # Add requested metrics
                if 'rnav_upside' in metrics and 'rnav' in ticker_data:
                    row['rnav_upside'] = ticker_data['rnav'].get('upside_pct', 0)
                
                if 'multiples' in ticker_data:
                    multiples = ticker_data['multiples']
                    
                    if 'pe_current' in metrics:
                        row['pe_current'] = multiples.get(f'{current_year}F_PE')
                    
                    if 'pb_current' in metrics:
                        row['pb_current'] = multiples.get(f'{current_year}F_PB')
                    
                    if 'pe_next' in metrics:
                        row['pe_next'] = multiples.get(f'{next_year}F_PE')
                    
                    if 'pb_next' in metrics:
                        row['pb_next'] = multiples.get(f'{next_year}F_PB')
                    
                    # Add vs mean metrics
                    row['pe_vs_mean'] = multiples.get('PE_vs_mean_pct')
                    row['pb_vs_mean'] = multiples.get('PB_vs_mean_pct')
                
                comparison_data.append(row)
            
            # Sort by requested metric
            if sort_by and comparison_data:
                # For P/E and P/B, lower is better
                reverse = sort_by == 'rnav_upside'
                comparison_data.sort(key=lambda x: x.get(sort_by, float('inf') if not reverse else float('-inf')), reverse=reverse)
            
            result = {
                "comparison": comparison_data,
                "metrics": metrics,
                "sorted_by": sort_by
            }
            
            # Add ranking if requested
            if include_ranking:
                rankings = {}
                
                # Rank each metric
                for metric in metrics:
                    if metric == 'rnav_upside':
                        # Higher is better
                        sorted_data = sorted(comparison_data, key=lambda x: x.get(metric, float('-inf')), reverse=True)
                    else:
                        # Lower is better for multiples
                        sorted_data = sorted(comparison_data, key=lambda x: x.get(metric, float('inf')))
                    
                    rankings[metric] = [d['ticker'] for d in sorted_data if metric in d]
                
                result['rankings'] = rankings
                
                # Determine most attractive overall
                if len(comparison_data) > 1:
                    scores = {}
                    for row in comparison_data:
                        ticker = row['ticker']
                        score = 0
                        
                        # Score based on rankings
                        for metric, ranking in rankings.items():
                            if ticker in ranking:
                                rank = ranking.index(ticker)
                                weight = 2 if metric == 'rnav_upside' else 1
                                score += (len(ranking) - rank) * weight
                        
                        scores[ticker] = score
                    
                    best_ticker = max(scores, key=scores.get)
                    result['most_attractive'] = {
                        "ticker": best_ticker,
                        "score": scores[best_ticker],
                        "scores_detail": scores
                    }
            
            return {
                "data": result,
                "status": "success"
            }
        
        @self.tool(
            name="analyze_valuation_attractiveness",
            description="Analyze overall valuation attractiveness considering multiple factors",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker",
                    "required": True
                },
                "include_rnav": {
                    "type": "boolean",
                    "description": "Include RNAV analysis",
                    "required": False
                },
                "include_growth": {
                    "type": "boolean",
                    "description": "Include earnings growth analysis",
                    "required": False
                },
                "include_leverage": {
                    "type": "boolean",
                    "description": "Include leverage/gearing analysis",
                    "required": False
                },
                "include_peer_comparison": {
                    "type": "boolean",
                    "description": "Include sector peer comparison",
                    "required": False
                }
            }
        )
        def analyze_valuation_attractiveness(ticker: str, include_rnav: bool = True,
                                           include_growth: bool = True, include_leverage: bool = True,
                                           include_peer_comparison: bool = False) -> Dict:
            """Analyze comprehensive valuation attractiveness"""
            
            ticker = ticker.upper()
            attractiveness_score = 0
            max_score = 0
            analysis = {}
            
            # Get valuation metrics
            valuation = get_company_valuation_metrics([ticker], include_rnav=True, include_multiples=True)
            
            if valuation.get('status') != 'success' or ticker not in valuation.get('data', {}):
                return {"error": f"Cannot get valuation data for {ticker}", "status": "failed"}
            
            ticker_data = valuation['data'][ticker]
            
            # 1. RNAV Analysis (max 30 points)
            if include_rnav and 'rnav' in ticker_data:
                max_score += 30
                rnav_upside = ticker_data['rnav'].get('upside_pct', 0)
                analysis['rnav'] = {
                    "upside_pct": rnav_upside,
                    "score": min(30, max(0, rnav_upside * 0.75))  # 40% upside = 30 points
                }
                attractiveness_score += analysis['rnav']['score']
            
            # 2. Valuation Multiples (max 30 points)
            if 'multiples' in ticker_data:
                max_score += 30
                multiples = ticker_data['multiples']
                multiples_score = 0
                
                current_year = datetime.now().year
                next_year = current_year + 1
                
                # Get the actual multiples from database
                current_pe = multiples.get(f'{current_year}F_PE')
                next_pe = multiples.get(f'{next_year}F_PE')
                current_pb = multiples.get(f'{current_year}F_PB')
                next_pb = multiples.get(f'{next_year}F_PB')
                mean_pe = multiples.get('mean_PE')
                mean_pb = multiples.get('mean_PB')
                
                # Calculate vs mean percentages
                pe_current_vs_mean = 0
                pe_next_vs_mean = 0
                pb_current_vs_mean = 0
                pb_next_vs_mean = 0
                
                # P/E comparisons (15 points total)
                if current_pe and mean_pe and mean_pe > 0:
                    pe_current_vs_mean = ((current_pe / mean_pe) - 1) * 100
                    if pe_current_vs_mean < 0:  # Trading below mean
                        multiples_score += min(7.5, abs(pe_current_vs_mean) * 0.25)
                
                if next_pe and mean_pe and mean_pe > 0:
                    pe_next_vs_mean = ((next_pe / mean_pe) - 1) * 100
                    if pe_next_vs_mean < 0:  # Trading below mean
                        multiples_score += min(7.5, abs(pe_next_vs_mean) * 0.25)
                
                # P/B comparisons (15 points total)
                if current_pb and mean_pb and mean_pb > 0:
                    pb_current_vs_mean = ((current_pb / mean_pb) - 1) * 100
                    if pb_current_vs_mean < 0:  # Trading below mean
                        multiples_score += min(7.5, abs(pb_current_vs_mean) * 0.25)
                
                if next_pb and mean_pb and mean_pb > 0:
                    pb_next_vs_mean = ((next_pb / mean_pb) - 1) * 100
                    if pb_next_vs_mean < 0:  # Trading below mean
                        multiples_score += min(7.5, abs(pb_next_vs_mean) * 0.25)
                
                analysis['multiples'] = {
                    "current_year_PE": current_pe,
                    "next_year_PE": next_pe,
                    "mean_PE": mean_pe,
                    "pe_current_vs_mean": pe_current_vs_mean,
                    "pe_next_vs_mean": pe_next_vs_mean,
                    "current_year_PB": current_pb,
                    "next_year_PB": next_pb,
                    "mean_PB": mean_pb,
                    "pb_current_vs_mean": pb_current_vs_mean,
                    "pb_next_vs_mean": pb_next_vs_mean,
                    "score": multiples_score
                }
                attractiveness_score += multiples_score
            
            # 3. Earnings Growth (max 20 points) - Calculate 3-year forward CAGR
            if include_growth:
                max_score += 20
                
                # Get forecast data for growth analysis
                forecast_doc = self.vietnam_stocks_db['CompanyForecast'].find_one({"ticker": ticker}) if self.vietnam_stocks_db is not None else None
                
                if forecast_doc and 'forecast_data' in forecast_doc:
                    forecast_data = forecast_doc['forecast_data']
                    current_year = datetime.now().year
                    
                    # Use current year and 3 years forward
                    target_years = [current_year, current_year + 1, current_year + 2, current_year + 3]
                    
                    # Check if we have data for the required years
                    available_years = [year for year in target_years if str(year) in forecast_data]
                    
                    if len(available_years) >= 2:
                        # Use first and last available years within our target range
                        first_year = str(available_years[0])
                        last_year = str(available_years[-1])
                        
                        first_npatmi = forecast_data.get(first_year, {}).get('pnl', {}).get('npatmi', 0)
                        last_npatmi = forecast_data.get(last_year, {}).get('pnl', {}).get('npatmi', 0)
                        
                        if first_npatmi > 0 and last_npatmi > 0:
                            years_diff = available_years[-1] - available_years[0]
                            cagr = ((last_npatmi / first_npatmi) ** (1 / years_diff) - 1) * 100 if years_diff > 0 else 0
                            
                            # 20% CAGR = 20 points
                            growth_score = min(20, max(0, cagr))
                            
                            analysis['growth'] = {
                                "earnings_cagr": cagr,
                                "period": f"{available_years[0]}-{available_years[-1]}",
                                "years_used": years_diff,
                                "score": growth_score
                            }
                            attractiveness_score += growth_score
            
            # 4. Leverage Analysis (max 20 points)
            if include_leverage:
                max_score += 20
                
                # Get balance sheet data
                forecast_doc = self.vietnam_stocks_db['CompanyForecast'].find_one({"ticker": ticker}) if self.vietnam_stocks_db is not None else None
                
                if forecast_doc and 'forecast_data' in forecast_doc:
                    current_year = str(datetime.now().year)
                    year_data = forecast_doc['forecast_data'].get(current_year, {})
                    
                    if 'balance_sheet' in year_data:
                        bs = year_data['balance_sheet']
                        
                        # Calculate debt/equity ratio
                        total_debt = bs.get('liabilities', {}).get('total_debt', 0)
                        total_equity = bs.get('equity', {}).get('total_equity', 0)
                        
                        if total_equity > 0:
                            debt_to_equity = total_debt / total_equity
                            
                            # Lower D/E is better: D/E < 0.5 = 20 points, D/E > 2 = 0 points
                            if debt_to_equity <= 0.5:
                                leverage_score = 20
                            elif debt_to_equity >= 2:
                                leverage_score = 0
                            else:
                                leverage_score = 20 * (2 - debt_to_equity) / 1.5
                            
                            analysis['leverage'] = {
                                "debt_to_equity": debt_to_equity,
                                "score": leverage_score
                            }
                            attractiveness_score += leverage_score
            
            # Calculate final score and recommendation
            final_score = (attractiveness_score / max_score * 10) if max_score > 0 else 0
            
            # Determine recommendation
            if final_score >= 7:
                recommendation = "STRONG BUY"
                recommendation_rationale = "Excellent valuation with high RNAV upside and attractive multiples"
            elif final_score >= 5.5:
                recommendation = "BUY"
                recommendation_rationale = "Attractive valuation with good upside potential"
            elif final_score >= 4:
                recommendation = "HOLD"
                recommendation_rationale = "Fair valuation, limited upside"
            else:
                recommendation = "SELL/AVOID"
                recommendation_rationale = "Unattractive valuation, consider alternatives"
            
            return {
                "ticker": ticker,
                "attractiveness_score": round(final_score, 1),
                "max_score": 10,
                "recommendation": recommendation,
                "recommendation_rationale": recommendation_rationale,
                "detailed_analysis": analysis,
                "score_breakdown": {
                    "actual": attractiveness_score,
                    "maximum": max_score,
                    "percentage": round(attractiveness_score / max_score * 100, 1) if max_score > 0 else 0
                },
                "status": "success"
            }
        
        @self.tool(
            name="calculate_gearing_metrics",
            description="Calculate leverage and gearing metrics (debt/equity, interest coverage, etc.)",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker",
                    "required": True
                },
                "include_net_debt": {
                    "type": "boolean",
                    "description": "Include net debt calculation",
                    "required": False
                },
                "include_debt_to_equity": {
                    "type": "boolean",
                    "description": "Include debt to equity ratio",
                    "required": False
                },
                "include_interest_coverage": {
                    "type": "boolean",
                    "description": "Include interest coverage ratio",
                    "required": False
                }
            }
        )
        def calculate_gearing_metrics(ticker: str, include_net_debt: bool = True,
                                     include_debt_to_equity: bool = True,
                                     include_interest_coverage: bool = True) -> Dict:
            """Calculate leverage and gearing metrics"""
            
            ticker = ticker.upper()
            
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            try:
                forecast_collection = self.vietnam_stocks_db['CompanyForecast']
                
                # Get saved forecast data
                forecast_doc = forecast_collection.find_one({"ticker": ticker})
                
                if not forecast_doc or 'forecast_data' not in forecast_doc:
                    return {"error": f"No forecast data for {ticker}", "status": "failed"}
                
                current_year = str(datetime.now().year)
                year_data = forecast_doc['forecast_data'].get(current_year, {})
                
                if not year_data:
                    return {"error": f"No data for {current_year}", "status": "failed"}
                
                result = {
                    "ticker": ticker,
                    "year": current_year,
                    "metrics": {}
                }
                
                bs = year_data.get('balance_sheet', {})
                pnl = year_data.get('pnl', {})
                
                # Get key balance sheet items
                cash = bs.get('assets', {}).get('cash_and_equivalents', 0)
                st_debt = bs.get('liabilities', {}).get('short_term_debt', 0)
                lt_debt = bs.get('liabilities', {}).get('long_term_debt', 0)
                total_debt = bs.get('liabilities', {}).get('total_debt', st_debt + lt_debt)
                total_equity = bs.get('equity', {}).get('total_equity', 0)
                total_assets = bs.get('assets', {}).get('total_assets', 0)
                
                # 1. Net Debt
                if include_net_debt:
                    net_debt = total_debt - cash
                    result['metrics']['net_debt'] = {
                        "value": net_debt / 1e9,  # Convert to billions
                        "cash": cash / 1e9,
                        "total_debt": total_debt / 1e9,
                        "net_debt_to_equity": (net_debt / total_equity) if total_equity > 0 else None
                    }
                
                # 2. Debt to Equity
                if include_debt_to_equity and total_equity > 0:
                    debt_to_equity = total_debt / total_equity
                    result['metrics']['debt_to_equity'] = {
                        "value": debt_to_equity,
                        "interpretation": "Low leverage" if debt_to_equity < 0.5 else "Moderate leverage" if debt_to_equity < 1.5 else "High leverage"
                    }
                    
                    # Additional ratios
                    result['metrics']['debt_to_assets'] = total_debt / total_assets if total_assets > 0 else None
                    result['metrics']['equity_ratio'] = total_equity / total_assets if total_assets > 0 else None
                
                # 3. Interest Coverage
                if include_interest_coverage:
                    ebitda = pnl.get('ebitda', 0)
                    interest_expense = pnl.get('interest_expense', 0)
                    
                    if interest_expense != 0:
                        interest_coverage = abs(ebitda / interest_expense)
                        result['metrics']['interest_coverage'] = {
                            "value": interest_coverage,
                            "ebitda": ebitda / 1e9,
                            "interest_expense": abs(interest_expense) / 1e9,
                            "interpretation": "Strong" if interest_coverage > 5 else "Adequate" if interest_coverage > 2 else "Weak"
                        }
                    else:
                        result['metrics']['interest_coverage'] = {
                            "value": "No debt/interest",
                            "ebitda": ebitda / 1e9,
                            "interest_expense": 0
                        }
                
                # Add historical comparison if available
                previous_year = str(int(current_year) - 1)
                if previous_year in forecast_doc['forecast_data']:
                    prev_bs = forecast_doc['forecast_data'][previous_year].get('balance_sheet', {})
                    prev_total_debt = prev_bs.get('liabilities', {}).get('total_debt', 0)
                    prev_total_equity = prev_bs.get('equity', {}).get('total_equity', 0)
                    
                    if prev_total_equity > 0:
                        prev_debt_to_equity = prev_total_debt / prev_total_equity
                        result['year_over_year'] = {
                            "debt_to_equity_change": debt_to_equity - prev_debt_to_equity if total_equity > 0 else None,
                            "debt_growth": ((total_debt / prev_total_debt - 1) * 100) if prev_total_debt > 0 else None,
                            "equity_growth": ((total_equity / prev_total_equity - 1) * 100) if prev_total_equity > 0 else None
                        }
                
                return {
                    "data": result,
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
        @self.tool(
            name="analyze_financial_trends",
            description="Analyze financial trends and calculate growth rates (annual and quarterly)",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker",
                    "required": True
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Metrics to analyze",
                    "required": False
                },
                "period_type": {
                    "type": "string",
                    "enum": ["yoy", "cagr", "qoq", "ttm"],
                    "description": "Type of growth calculation (yoy=year-over-year, qoq=quarter-over-quarter, ttm=trailing twelve months)",
                    "required": False
                },
                "data_frequency": {
                    "type": "string",
                    "enum": ["annual", "quarterly"],
                    "description": "Use annual or quarterly data",
                    "required": False
                }
            }
        )
        def analyze_financial_trends(ticker: str, metrics: List[str] = None,
                                    period_type: str = "yoy", 
                                    data_frequency: str = "annual") -> Dict:
            """Analyze financial trends with support for quarterly data"""
            
            ticker = ticker.upper()
            
            # Load appropriate data based on frequency
            if data_frequency == "quarterly":
                df = self._load_quarterly_financial_statements()
            else:
                df = self._load_financial_statements_csv()
            
            if df.empty:
                return {"error": f"{data_frequency.capitalize()} financial data not available", "status": "failed"}
            
            # Filter by ticker
            df = df[df['TICKER'] == ticker]
            
            if df.empty:
                return {"error": f"No data found for {ticker}", "status": "failed"}
            
            # Default metrics if not specified
            if not metrics:
                metrics = ['Net_Revenue', 'EBITDA', 'NPATMI', 'Gross_Profit']
            
            trends = {}
            
            for metric in metrics:
                metric_df = df[df['KEYCODE'] == metric].sort_values('DATE')
                
                if not metric_df.empty:
                    if data_frequency == "quarterly":
                        # Handle quarterly data
                        values = []
                        for _, row in metric_df.iterrows():
                            date_str = row['DATE']
                            value = row['VALUE']
                            
                            # Calculate QoQ if requested
                            qoq_growth = None
                            if period_type == "qoq" and len(values) > 0:
                                prev_value = values[-1]['VALUE']
                                if prev_value != 0:
                                    qoq_growth = ((value - prev_value) / abs(prev_value)) * 100
                            
                            # Calculate YoY for quarterly data
                            yoy_growth = None
                            if period_type in ["yoy", "ttm"]:
                                # Find same quarter last year
                                year = int(date_str[:4])
                                quarter = date_str[4:]
                                prev_year_date = f"{year-1}{quarter}"
                                prev_year_row = metric_df[metric_df['DATE'] == prev_year_date]
                                if not prev_year_row.empty:
                                    prev_value = prev_year_row.iloc[0]['VALUE']
                                    if prev_value != 0:
                                        yoy_growth = ((value - prev_value) / abs(prev_value)) * 100
                            
                            values.append({
                                'DATE': date_str,
                                'VALUE': value,
                                'YoY': yoy_growth,
                                'QoQ': qoq_growth
                            })
                        
                        # Calculate TTM if requested
                        if period_type == "ttm" and len(values) >= 4:
                            ttm_values = []
                            for i in range(3, len(values)):
                                ttm_sum = sum(values[j]['VALUE'] for j in range(i-3, i+1))
                                ttm_values.append({
                                    'DATE': values[i]['DATE'],
                                    'TTM_VALUE': ttm_sum,
                                    'TTM_YoY': values[i].get('YoY')
                                })
                            
                            trends[metric] = {
                                "values": values[-8:],  # Last 2 years of quarterly data
                                "ttm_values": ttm_values[-4:],  # Last year of TTM
                                "latest_ttm": ttm_values[-1]['TTM_VALUE'] if ttm_values else None
                            }
                        else:
                            trends[metric] = {
                                "values": values[-8:],  # Last 2 years of quarterly data
                                "latest_qoq": values[-1].get('QoQ') if values else None,
                                "latest_yoy": values[-1].get('YoY') if values else None
                            }
                    else:
                        # Handle annual data (existing logic)
                        values = metric_df[['DATE', 'VALUE', 'YoY']].to_dict('records')
                        
                        # Calculate CAGR if requested
                        if period_type == "cagr" and len(values) > 1:
                            first_val = values[0]['VALUE']
                            last_val = values[-1]['VALUE']
                            n_years = values[-1]['DATE'] - values[0]['DATE']
                            
                            if first_val > 0 and n_years > 0:
                                cagr = (pow(last_val / first_val, 1/n_years) - 1) * 100
                                trends[metric] = {
                                    "values": values,
                                    "cagr": round(cagr, 2),
                                    "period": f"{values[0]['DATE']}-{values[-1]['DATE']}"
                                }
                        else:
                            trends[metric] = {
                                "values": values,
                                "latest_yoy": values[-1].get('YoY') if values else None
                            }
            
            return {
                "ticker": ticker,
                "trends": trends,
                "period_type": period_type,
                "data_frequency": data_frequency,
                "status": "success"
            }
        
        @self.tool(
            name="compare_companies",
            description="Compare financial metrics and project margins across multiple companies",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Companies to compare",
                    "required": True
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Metrics to compare",
                    "required": False
                },
                "year": {
                    "type": "integer",
                    "description": "Year for comparison",
                    "required": False
                },
                "include_project_margins": {
                    "type": "boolean",
                    "description": "Include project-level margin comparison",
                    "required": False
                }
            }
        )
        def compare_companies(tickers: List[str], metrics: List[str] = None,
                            year: int = None, include_project_margins: bool = False) -> Dict:
            """Compare companies on financial metrics and project margins"""
            
            tickers = [t.upper() for t in tickers]
            
            # Load financial data
            df = self._load_financial_statements_csv()
            
            if df.empty:
                return {"error": "Financial data not available", "status": "failed"}
            
            # Filter by tickers
            df = df[df['TICKER'].isin(tickers)]
            
            # Use latest year if not specified
            if not year:
                year = df['DATE'].max()
            
            df = df[df['DATE'] == year]
            
            # Default metrics
            if not metrics:
                metrics = ['Net_Revenue', 'EBITDA_Margin', 'NPAT_Margin', 'ROE', 'ROA']
            
            # Filter and pivot
            df = df[df['KEYCODE'].isin(metrics)]
            
            result = {}
            
            if not df.empty:
                comparison_df = df.pivot_table(
                    index='TICKER',
                    columns='KEYCODE',
                    values='VALUE',
                    aggfunc='first'
                ).reset_index()
                
                # Calculate rankings
                for col in comparison_df.columns:
                    if col != 'TICKER':
                        comparison_df[f'{col}_rank'] = comparison_df[col].rank(ascending=False)
                
                result["comparison"] = comparison_df.to_dict('records')
                result["year"] = year
                result["metrics"] = metrics
            
            # Add project margin comparison if requested
            if include_project_margins and self.vietnam_stocks_db:
                try:
                    margin_comparison = {}
                    year_str = str(year)
                    
                    for ticker in tickers:
                        # Get company forecast from MongoDB
                        from utils.mongodb_utils import load_company_forecast
                        forecast_doc = load_company_forecast(ticker)
                        
                        if forecast_doc and 'forecast_data' in forecast_doc:
                            if year_str in forecast_doc['forecast_data']:
                                year_data = forecast_doc['forecast_data'][year_str]
                                
                                # Extract enhanced margin data
                                if 'profitability_metrics' in year_data:
                                    metrics = year_data['profitability_metrics']
                                    
                                    margin_comparison[ticker] = {
                                        "consolidated_margins": metrics.get('consolidated_margins', {}),
                                        "aggregated_project_margins": metrics.get('aggregated_project_margins', {}),
                                        "project_count": len(metrics.get('project_margins', {}))
                                    }
                                    
                                    # Add best performing project
                                    if 'project_margins' in metrics:
                                        best_project = max(
                                            metrics['project_margins'].items(),
                                            key=lambda x: x[1].get('patmi_margin', 0),
                                            default=(None, {})
                                        )
                                        if best_project[0]:
                                            margin_comparison[ticker]["best_project"] = {
                                                "name": best_project[0],
                                                "patmi_margin": best_project[1].get('patmi_margin', 0)
                                            }
                    
                    if margin_comparison:
                        result["project_margin_comparison"] = margin_comparison
                        
                        # Add margin rankings
                        margin_rankings = {}
                        for margin_type in ['gross_margin', 'pbt_margin', 'pat_margin', 'patmi_margin']:
                            rankings = []
                            for ticker, data in margin_comparison.items():
                                cons_margin = data.get('consolidated_margins', {}).get(margin_type, 0)
                                if cons_margin > 0:
                                    rankings.append((ticker, cons_margin))
                            
                            if rankings:
                                rankings.sort(key=lambda x: x[1], reverse=True)
                                margin_rankings[margin_type] = rankings
                        
                        result["margin_rankings"] = margin_rankings
                
                except Exception as e:
                    result["margin_comparison_error"] = str(e)
            
            result["status"] = "success"
            return result
        
        @self.tool(
            name="get_financial_forecasts",
            description="Get financial forecast data from MongoDB CompanyForecast (2025-2030+). ALL VALUES ARE IN BILLIONS VND",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker (available: DXG, KDH, NTL, TAL, TCH)",
                    "required": True
                },
                "years": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Forecast years (e.g., ['2025', '2026'])",
                    "required": False
                },
                "statement_type": {
                    "type": "string",
                    "enum": ["pnl", "balance_sheet", "cash_flow", "all"],
                    "description": "Financial statement type",
                    "required": False
                },
                "include_breakdown": {
                    "type": "boolean",
                    "description": "Include project-level breakdown",
                    "required": False
                }
            }
        )
        def get_financial_forecasts(ticker: str, years: List[str] = None, 
                                   statement_type: str = "all", 
                                   include_breakdown: bool = False) -> Dict:
            """Get financial forecast data from MongoDB CompanyForecast collection"""
            
            ticker = ticker.upper()
            
            # Check MongoDB connection
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            try:
                collection = self.vietnam_stocks_db['CompanyForecast']
                
                # Get forecast document
                forecast_doc = collection.find_one({'ticker': ticker}, {'_id': 0})
                
                if not forecast_doc:
                    return {
                        "error": f"No forecast data for {ticker}",
                        "available_tickers": ["DXG", "KDH", "NTL", "TAL", "TCH"],
                        "status": "failed"
                    }
                
                # Extract forecast data
                forecast_data = forecast_doc.get('forecast_data', {})
                available_years = forecast_doc.get('forecast_years', [])
                
                # Filter by years if specified
                if years:
                    forecast_data = {year: data for year, data in forecast_data.items() 
                                   if year in years}
                
                # Filter by statement type and convert from raw VND to billions
                result_data = {}
                for year, year_data in forecast_data.items():
                    if statement_type == "all":
                        # Convert P&L values from raw VND to billions
                        pnl_converted = {}
                        for key, value in year_data.get('pnl', {}).items():
                            if isinstance(value, (int, float)) and key not in ['tax_rate']:
                                pnl_converted[key] = value / 1e9  # Convert to billions
                            else:
                                pnl_converted[key] = value
                        
                        # Convert Balance Sheet values from raw VND to billions
                        bs_converted = {}
                        bs_data = year_data.get('balance_sheet', {})
                        for section, items in bs_data.items():
                            if isinstance(items, dict):
                                bs_converted[section] = {}
                                for key, value in items.items():
                                    if isinstance(value, (int, float)):
                                        bs_converted[section][key] = value / 1e9
                                    else:
                                        bs_converted[section][key] = value
                            elif isinstance(items, (int, float)):
                                bs_converted[section] = items / 1e9
                            else:
                                bs_converted[section] = items
                        
                        # Convert Cash Flow values from raw VND to billions
                        cf_converted = {}
                        cf_data = year_data.get('cash_flow', {})
                        for section, items in cf_data.items():
                            if isinstance(items, dict):
                                cf_converted[section] = {}
                                for key, value in items.items():
                                    if isinstance(value, (int, float)):
                                        cf_converted[section][key] = value / 1e9
                                    else:
                                        cf_converted[section][key] = value
                            elif isinstance(items, (int, float)):
                                cf_converted[section] = items / 1e9
                            else:
                                cf_converted[section] = items
                        
                        result_data[year] = {
                            'pnl': pnl_converted,
                            'balance_sheet': bs_converted,
                            'cash_flow': cf_converted
                        }
                    else:
                        # Convert single statement type
                        statement_data = year_data.get(statement_type, {})
                        converted_data = {}
                        
                        if statement_type == 'pnl':
                            for key, value in statement_data.items():
                                if isinstance(value, (int, float)) and key not in ['tax_rate']:
                                    converted_data[key] = value / 1e9
                                else:
                                    converted_data[key] = value
                        else:
                            # For balance_sheet and cash_flow (nested structure)
                            for section, items in statement_data.items():
                                if isinstance(items, dict):
                                    converted_data[section] = {}
                                    for key, value in items.items():
                                        if isinstance(value, (int, float)):
                                            converted_data[section][key] = value / 1e9
                                        else:
                                            converted_data[section][key] = value
                                elif isinstance(items, (int, float)):
                                    converted_data[section] = items / 1e9
                                else:
                                    converted_data[section] = items
                        
                        result_data[year] = {statement_type: converted_data}
                    
                    # Add project breakdown if requested (convert to billions)
                    if include_breakdown and 'project_breakdown' in year_data:
                        breakdown_converted = {}
                        for metric, projects in year_data['project_breakdown'].items():
                            breakdown_converted[metric] = {}
                            for project, value in projects.items():
                                if isinstance(value, (int, float)):
                                    breakdown_converted[metric][project] = value / 1e9
                                else:
                                    breakdown_converted[metric][project] = value
                        result_data[year]['project_breakdown'] = breakdown_converted
                        
                        # Add profitability metrics if available (keep as percentages)
                        if 'profitability_metrics' in year_data:
                            result_data[year]['profitability_metrics'] = year_data['profitability_metrics']
                            
                            # Highlight new enhanced margins in the response
                            if 'aggregated_project_margins' in year_data['profitability_metrics']:
                                result_data[year]['aggregated_project_margins'] = year_data['profitability_metrics']['aggregated_project_margins']
                            if 'project_margins' in year_data['profitability_metrics']:
                                result_data[year]['project_margins'] = year_data['profitability_metrics']['project_margins']
                
                # Extract key metrics for summary
                summary = {}
                if forecast_data:
                    first_year = list(forecast_data.keys())[0]
                    last_year = list(forecast_data.keys())[-1]
                    
                    # Calculate CAGR for revenue if available
                    if first_year in forecast_data and last_year in forecast_data:
                        first_revenue = forecast_data[first_year].get('pnl', {}).get('net_revenue', 0)
                        last_revenue = forecast_data[last_year].get('pnl', {}).get('net_revenue', 0)
                        if first_revenue > 0 and last_revenue > 0:
                            n_years = int(last_year) - int(first_year)
                            if n_years > 0:
                                cagr = (pow(last_revenue / first_revenue, 1/n_years) - 1) * 100
                                summary['revenue_cagr'] = round(cagr, 2)
                
                return {
                    "ticker": ticker,
                    "forecast_data": result_data,
                    "available_years": available_years,
                    "years_requested": years if years else "all",
                    "statement_type": statement_type,
                    "summary": summary,
                    "assumptions": forecast_doc.get('assumptions', []),
                    "last_updated": forecast_doc.get('last_updated', 'Unknown'),
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
        @self.tool(
            name="analyze_project_margins",
            description="Analyze detailed project-level margins including gross, SG&A, PBT, PAT, and PATMI margins",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker symbol",
                    "required": True
                },
                "years": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of years to analyze",
                    "required": False
                },
                "margin_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Types of margins to analyze: gross, sga, pbt, pat, patmi",
                    "required": False
                },
                "include_aggregated": {
                    "type": "boolean",
                    "description": "Include aggregated project margins",
                    "required": False
                }
            }
        )
        def analyze_project_margins(ticker: str, years: List[str] = None, 
                                   margin_types: List[str] = None,
                                   include_aggregated: bool = True) -> Dict:
            """Analyze comprehensive project margins with new enhanced schema"""
            
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            ticker = ticker.upper()
            
            try:
                # Get company forecast
                from utils.mongodb_utils import load_company_forecast
                forecast_doc = load_company_forecast(ticker)
                
                if not forecast_doc or 'forecast_data' not in forecast_doc:
                    return {"error": f"No forecast data for {ticker}", "status": "failed"}
                
                forecast_data = forecast_doc['forecast_data']
                
                # Use provided years or all available years
                if not years:
                    years = list(forecast_data.keys())
                
                # Default to all margin types
                if not margin_types:
                    margin_types = ['gross', 'sga', 'pbt', 'pat', 'patmi']
                
                result = {
                    "ticker": ticker,
                    "years_analyzed": years,
                    "margin_types": margin_types,
                    "project_margins": {},
                    "aggregated_margins": {} if include_aggregated else None,
                    "consolidated_margins": {},
                    "margin_comparison": {}
                }
                
                for year in years:
                    if year not in forecast_data:
                        continue
                    
                    year_data = forecast_data[year]
                    metrics = year_data.get('profitability_metrics', {})
                    
                    # Extract project-level margins (NEW enhanced data)
                    if 'project_margins' in metrics:
                        result['project_margins'][year] = {}
                        for project, margins in metrics['project_margins'].items():
                            result['project_margins'][year][project] = {
                                m: round(margins.get(f'{m}_margin', 0), 2) 
                                for m in margin_types
                            }
                    
                    # Extract aggregated project margins (NEW)
                    if include_aggregated and 'aggregated_project_margins' in metrics:
                        agg = metrics['aggregated_project_margins']
                        result['aggregated_margins'][year] = {
                            'revenue': round(agg.get('total_projects_revenue', 0) / 1e9, 2),
                            'gross_profit': round(agg.get('total_projects_gross_profit', 0) / 1e9, 2),
                            'margins': {
                                m: round(agg.get(f'total_projects_{m}_margin', 0), 2)
                                for m in margin_types
                            }
                        }
                    
                    # Extract consolidated margins
                    if 'consolidated_margins' in metrics:
                        cons = metrics['consolidated_margins']
                        result['consolidated_margins'][year] = {
                            m: round(cons.get(f'{m}_margin', 0), 2)
                            for m in margin_types
                        }
                    
                    # Compare project vs company margins
                    if include_aggregated and 'aggregated_project_margins' in metrics and 'consolidated_margins' in metrics:
                        agg_margins = metrics['aggregated_project_margins']
                        cons_margins = metrics['consolidated_margins']
                        result['margin_comparison'][year] = {}
                        for m in margin_types:
                            proj_margin = agg_margins.get(f'total_projects_{m}_margin', 0)
                            cons_margin = cons_margins.get(f'{m}_margin', 0)
                            result['margin_comparison'][year][m] = {
                                'projects': round(proj_margin, 2),
                                'consolidated': round(cons_margin, 2),
                                'difference': round(proj_margin - cons_margin, 2)
                            }
                
                # Add trend analysis
                if len(years) > 1:
                    result['trends'] = self._calculate_margin_trends(result)
                
                # Add insights
                result['insights'] = self._generate_margin_insights(result)
                
                return result
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
        def _calculate_margin_trends(self, margin_data: Dict) -> Dict:
            """Calculate margin trends over time"""
            trends = {}
            
            # Calculate consolidated margin trends
            if margin_data.get('consolidated_margins'):
                cons_margins = margin_data['consolidated_margins']
                years = sorted(cons_margins.keys())
                if len(years) >= 2:
                    first_year = years[0]
                    last_year = years[-1]
                    
                    for margin_type in ['gross', 'sga', 'pbt', 'pat', 'patmi']:
                        if margin_type in cons_margins[first_year] and margin_type in cons_margins[last_year]:
                            first_val = cons_margins[first_year].get(margin_type, 0)
                            last_val = cons_margins[last_year].get(margin_type, 0)
                            change = last_val - first_val
                            trends[f'{margin_type}_margin_change'] = round(change, 2)
            
            # Calculate project margin trends
            if margin_data.get('aggregated_margins'):
                agg_margins = margin_data['aggregated_margins']
                years = sorted(agg_margins.keys())
                if len(years) >= 2:
                    first_year = years[0]
                    last_year = years[-1]
                    
                    for margin_type in ['gross', 'sga', 'pbt', 'pat', 'patmi']:
                        if 'margins' in agg_margins[first_year] and 'margins' in agg_margins[last_year]:
                            first_val = agg_margins[first_year]['margins'].get(margin_type, 0)
                            last_val = agg_margins[last_year]['margins'].get(margin_type, 0)
                            change = last_val - first_val
                            trends[f'project_{margin_type}_margin_change'] = round(change, 2)
            
            return trends
        
        def _generate_margin_insights(self, margin_data: Dict) -> List[str]:
            """Generate insights from margin analysis"""
            insights = []
            
            # Check for best performing projects
            if margin_data.get('project_margins'):
                for year in margin_data['project_margins']:
                    year_margins = margin_data['project_margins'][year]
                    if year_margins:
                        # Find best gross margin project
                        best_gross = max(year_margins.items(), 
                                       key=lambda x: x[1].get('gross', 0) if x[1] else 0)
                        if best_gross[1].get('gross', 0) > 0:
                            insights.append(f"In {year}, {best_gross[0]} has the highest gross margin at {best_gross[1]['gross']}%")
                        
                        # Find best PATMI margin project
                        if 'patmi' in margin_data['margin_types']:
                            best_patmi = max(year_margins.items(),
                                           key=lambda x: x[1].get('patmi', 0) if x[1] else 0)
                            if best_patmi[1].get('patmi', 0) > 0:
                                insights.append(f"In {year}, {best_patmi[0]} has the highest PATMI margin at {best_patmi[1]['patmi']}%")
            
            # Check margin trends
            if margin_data.get('trends'):
                trends = margin_data['trends']
                for key, value in trends.items():
                    if 'margin_change' in key and abs(value) > 2:  # Significant change > 2%
                        margin_type = key.replace('_margin_change', '').replace('project_', '')
                        direction = "improved" if value > 0 else "declined"
                        insights.append(f"{margin_type.upper()} margin {direction} by {abs(value)}% over the period")
            
            # Compare project vs company margins
            if margin_data.get('margin_comparison'):
                for year in margin_data['margin_comparison']:
                    year_comp = margin_data['margin_comparison'][year]
                    for margin_type in year_comp:
                        diff = year_comp[margin_type].get('difference', 0)
                        if abs(diff) > 5:  # Significant difference > 5%
                            better = "higher" if diff > 0 else "lower"
                            insights.append(f"Project {margin_type} margins are {abs(diff)}% {better} than company average in {year}")
            
            return insights[:5]  # Return top 5 insights
        
        @self.tool(
            name="analyze_project_contribution_to_forecast", 
            description="Analyze how individual real estate projects contribute to the company's forecast revenue and profitability",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker to analyze",
                    "required": True
                },
                "year": {
                    "type": "string",
                    "description": "Year to analyze (e.g., '2025')",
                    "required": True
                }
            }
        )
        def analyze_project_contribution_to_forecast(ticker: str, year: str) -> Dict:
            """Analyze breakdown of project contributions to company forecast"""
            
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            ticker = ticker.upper()
            
            try:
                # Get company forecast
                forecast_collection = self.vietnam_stocks_db['CompanyForecast']
                company_doc = forecast_collection.find_one({'ticker': ticker}, {'_id': 0})
                
                if not company_doc or year not in company_doc.get('forecast_data', {}):
                    return {"error": f"No forecast data for {ticker} in {year}", "status": "failed"}
                
                year_data = company_doc['forecast_data'][year]
                company_pnl = year_data.get('pnl', {})
                project_breakdown = year_data.get('project_breakdown', {})
                
                # Get project details from RealEstateProjects
                projects_collection = self.vietnam_stocks_db['RealEstateProjects']
                projects = list(projects_collection.find({'company_ticker': ticker}, {'_id': 0}))
                
                result = {
                    "ticker": ticker,
                    "year": year,
                    "company_totals": {
                        "total_revenue": company_pnl.get('net_revenue', 0) / 1e9,
                        "total_pat": company_pnl.get('pat', 0) / 1e9,
                        "total_patmi": company_pnl.get('npatmi', 0) / 1e9,
                        "minority_interest": company_pnl.get('minority_interest', 0) / 1e9
                    },
                    "project_contributions": {},
                    "summary": {}
                }
                
                # Add project-level contribution data
                total_project_revenue = 0
                total_project_pat = 0
                total_project_patmi = 0
                
                # Process revenue contributions
                if 'revenue' in project_breakdown:
                    for project_name, revenue_value in project_breakdown['revenue'].items():
                        revenue_billions = revenue_value / 1e9
                        total_project_revenue += revenue_billions
                        
                        if project_name not in result['project_contributions']:
                            result['project_contributions'][project_name] = {}
                        
                        result['project_contributions'][project_name]['revenue'] = revenue_billions
                        result['project_contributions'][project_name]['revenue_contribution_pct'] = (
                            (revenue_billions / result['company_totals']['total_revenue'] * 100) 
                            if result['company_totals']['total_revenue'] != 0 else 0
                        )
                
                # Process PAT contributions
                if 'pat' in project_breakdown:
                    for project_name, pat_value in project_breakdown['pat'].items():
                        pat_billions = pat_value / 1e9
                        patmi_billions = project_breakdown.get('patmi', {}).get(project_name, 0) / 1e9
                        total_project_pat += pat_billions
                        total_project_patmi += patmi_billions
                        
                        if project_name not in result['project_contributions']:
                            result['project_contributions'][project_name] = {}
                        
                        result['project_contributions'][project_name].update({
                            'pat': pat_billions,
                            'patmi': patmi_billions,
                            'pat_contribution_pct': (
                                (pat_billions / result['company_totals']['total_pat'] * 100) 
                                if result['company_totals']['total_pat'] != 0 else 0
                            )
                        })
                
                # Calculate summary statistics
                result['summary'] = {
                    'total_projects_contributing': len(result['project_contributions']),
                    'projects_total_revenue': total_project_revenue,
                    'projects_total_pat': total_project_pat,
                    'projects_total_patmi': total_project_patmi,
                    'other_business_revenue': result['company_totals']['total_revenue'] - total_project_revenue,
                    'other_business_pat': result['company_totals']['total_pat'] - total_project_pat,
                    'other_business_patmi': result['company_totals']['total_patmi'] - total_project_patmi,
                    'projects_revenue_contribution_pct': (
                        (total_project_revenue / result['company_totals']['total_revenue'] * 100) 
                        if result['company_totals']['total_revenue'] != 0 else 0
                    ),
                    'projects_pat_contribution_pct': (
                        (total_project_pat / result['company_totals']['total_pat'] * 100) 
                        if result['company_totals']['total_pat'] != 0 else 0
                    )
                }
                
                # Sort projects by PAT contribution
                sorted_projects = sorted(
                    result['project_contributions'].items(),
                    key=lambda x: x[1].get('pat', 0),
                    reverse=True
                )
                result['project_contributions'] = dict(sorted_projects)
                
                return {
                    "analysis": result,
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
    
    def _register_real_estate_tools(self):
        """Register real estate project tools"""
        
        @self.tool(
            name="list_real_estate_projects",
            description="List real estate projects with filtering options",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Company tickers",
                    "required": False
                },
                "location": {
                    "type": "string",
                    "description": "Project location filter",
                    "required": False
                },
                "min_units": {
                    "type": "integer",
                    "description": "Minimum number of units",
                    "required": False
                }
            }
        )
        def list_real_estate_projects(tickers: List[str] = None, location: str = None,
                                     min_units: int = None) -> Dict:
            """List real estate projects"""
            
            df = self._load_real_estate_projects()
            
            if df.empty:
                return {"error": "No projects data available", "status": "failed"}
            
            # Apply filters
            if tickers:
                tickers = [t.upper() for t in tickers]
                df = df[df['company_ticker'].isin(tickers)]
            
            if location:
                df = df[df['location'].str.contains(location, case=False, na=False)]
            
            if min_units:
                df = df[df['total_units'] >= min_units]
            
            # Group by company
            summary = {}
            for ticker in df['company_ticker'].unique():
                company_projects = df[df['company_ticker'] == ticker]
                # Include RNAV if available
                project_cols = ['project_name', 'location', 'total_units']
                if 'rnav_value' in company_projects.columns:
                    project_cols.append('rnav_value')
                
                summary[ticker] = {
                    "count": len(company_projects),
                    "total_units": company_projects['total_units'].sum(),
                    "total_nsa": company_projects['net_sellable_area'].sum(),
                    "total_rnav": company_projects['rnav_value'].sum() if 'rnav_value' in company_projects.columns else None,
                    "projects": company_projects[project_cols].to_dict('records')
                }
            
            return {
                "summary": summary,
                "total_projects": len(df),
                "filters_applied": {
                    "tickers": tickers,
                    "location": location,
                    "min_units": min_units
                },
                "status": "success"
            }
        
        @self.tool(
            name="get_project_details",
            description="Get detailed information about specific projects. IMPORTANT: presales_distribution and revenue_distribution contain PERCENTAGES (not actual units/amounts). cash_collection_schedule may be percentages or absolute amounts. The tool returns calculated actual values in presales_info, revenue_info, and cash_collection_info fields with both percentages and absolute amounts.",
            parameters={
                "project_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Project names to retrieve",
                    "required": False
                },
                "ticker": {
                    "type": "string",
                    "description": "Company ticker to filter projects",
                    "required": False
                },
                "include_financials": {
                    "type": "boolean",
                    "description": "Include detailed financial projections and schedules",
                    "required": False
                },
                "include_assumptions": {
                    "type": "boolean",
                    "description": "Include AI-generated assumptions",
                    "required": False
                }
            }
        )
        def get_project_details(project_names: List[str] = None, ticker: str = None,
                              include_financials: bool = True, 
                              include_assumptions: bool = False) -> Dict:
            """Get detailed project information from MongoDB RealEstateProjects collection"""
            
            # Try MongoDB first
            if self.vietnam_stocks_db is not None:
                try:
                    collection = self.vietnam_stocks_db['RealEstateProjects']
                    
                    # Build query
                    query = {}
                    if project_names:
                        # Case-insensitive search
                        query['project_name'] = {
                            "$in": [{"$regex": f"^{name}$", "$options": "i"} for name in project_names]
                        }
                    if ticker:
                        query['company_ticker'] = ticker.upper()
                    
                    # Retrieve projects
                    projects = list(collection.find(query, {'_id': 0}))
                    
                    if not projects:
                        # Fallback to CSV
                        df = self._load_real_estate_projects()
                        if not df.empty:
                            if project_names:
                                mask = df['project_name'].str.lower().isin([p.lower() for p in project_names])
                                df = df[mask]
                            if ticker:
                                df = df[df['company_ticker'] == ticker.upper()]
                            
                            if not df.empty:
                                return {
                                    "projects": df.to_dict('records'),
                                    "count": len(df),
                                    "source": "csv_fallback",
                                    "status": "success"
                                }
                        
                        return {"error": f"No projects found", "status": "failed"}
                    
                    # Process retrieved projects
                    result_projects = []
                    for project in projects:
                        project_data = {
                            "project_name": project.get('project_name'),
                            "company_ticker": project.get('company_ticker'),
                            "location": project.get('location'),
                            "total_units": project.get('total_units'),
                            "net_sellable_area": project.get('net_sellable_area'),
                            "average_selling_price": project.get('average_selling_price'),
                            "construction_start_year": project.get('construction_start_year'),
                            "project_completion_year": project.get('project_completion_year'),
                            "project_type": project.get('project_type'),
                            "ownership_percentage": project.get('ownership_percentage', 100),
                            "land_cost_per_sqm": project.get('land_cost_per_sqm'),
                            "construction_cost_per_sqm": project.get('construction_cost_per_sqm'),
                            "last_updated": project.get('last_updated')
                        }
                        
                        # Add financial details if requested
                        if include_financials:
                            # Get presales distribution (these are PERCENTAGES, not units)
                            presales_dist_pct = project.get('presales_distribution', {})
                            total_units = project.get('total_units', 0)
                            
                            # Calculate actual presold units from percentages
                            presales_units_by_year = {}
                            cumulative_presold = 0
                            current_year = datetime.now().year
                            
                            for year_str, percentage in presales_dist_pct.items():
                                year = int(year_str)
                                units_this_year = (total_units * percentage / 100) if total_units else 0
                                presales_units_by_year[year_str] = {
                                    "percentage": percentage,
                                    "units": int(units_this_year),
                                    "description": f"{percentage}% of total units ({int(units_this_year)} units)"
                                }
                                if year <= current_year:
                                    cumulative_presold += units_this_year
                            
                            # Get revenue distribution (also PERCENTAGES)
                            revenue_dist_pct = project.get('revenue_distribution', {})
                            total_revenue = project.get('total_revenue', 0)
                            
                            # Calculate actual revenue amounts from percentages
                            revenue_by_year = {}
                            cumulative_revenue = 0
                            
                            for year_str, percentage in revenue_dist_pct.items():
                                year = int(year_str)
                                revenue_this_year = (total_revenue * percentage / 100) if total_revenue else 0
                                revenue_by_year[year_str] = {
                                    "percentage": percentage,
                                    "revenue_vnd": revenue_this_year,
                                    "revenue_billion_vnd": revenue_this_year / 1e9 if revenue_this_year else 0,
                                    "description": f"{percentage}% of total revenue ({revenue_this_year/1e9:.1f}B VND)"
                                }
                                if year <= current_year:
                                    cumulative_revenue += revenue_this_year
                            
                            # Get cash collection schedules (complex structure based on presale year)
                            cash_collection_schedules = project.get('cash_collection_schedules', {})
                            
                            # Calculate actual cash collection amounts
                            # Logic from project_pipeline_real_estate.py:
                            # Each presale year has its own collection schedule
                            # Actual cash = presale_amount * (collection_percentage / 100)
                            
                            cash_collection_by_year = {}
                            cumulative_cash_collected = 0
                            
                            # First, calculate presales amounts by year (in VND)
                            presales_amounts_by_year = {}
                            for year_str, percentage in presales_dist_pct.items():
                                presale_amount = (total_revenue * percentage / 100) if total_revenue else 0
                                presales_amounts_by_year[int(year_str)] = presale_amount
                            
                            # Now calculate cash collection based on collection schedules
                            for presale_year, presale_amount in presales_amounts_by_year.items():
                                # Get the collection schedule for this presale year
                                schedule = cash_collection_schedules.get(presale_year, {})
                                if not schedule:
                                    # If no schedule, assume 100% collection in presale year
                                    schedule = {presale_year: 100}
                                
                                for collection_year_str, collection_pct in schedule.items():
                                    collection_year = int(collection_year_str)
                                    cash_amount = presale_amount * (collection_pct / 100)
                                    
                                    if collection_year not in cash_collection_by_year:
                                        cash_collection_by_year[collection_year] = 0
                                    cash_collection_by_year[collection_year] += cash_amount
                            
                            # Format cash collection data for output
                            cash_collection_formatted = {}
                            for year, amount in sorted(cash_collection_by_year.items()):
                                cash_collection_formatted[str(year)] = {
                                    "cash_collected_vnd": amount,
                                    "cash_collected_billion_vnd": amount / 1e9 if amount else 0,
                                    "description": f"{amount/1e9:.1f}B VND collected"
                                }
                                if year <= current_year:
                                    cumulative_cash_collected += amount
                            
                            project_data.update({
                                # Original percentage data with clear labeling
                                "presales_distribution_percentages": presales_dist_pct,
                                "presales_distribution_note": "IMPORTANT: presales_distribution contains PERCENTAGES, not unit counts",
                                
                                # Calculated actual units
                                "presales_info": {
                                    "total_units_in_project": total_units,
                                    "presales_by_year": presales_units_by_year,
                                    "total_presold_units_to_date": int(cumulative_presold),
                                    "percentage_presold_to_date": (cumulative_presold / total_units * 100) if total_units else 0,
                                    "remaining_units_to_sell": int(total_units - cumulative_presold) if total_units else 0
                                },
                                
                                # Revenue distribution (also PERCENTAGES)
                                "revenue_distribution_percentages": revenue_dist_pct,
                                "revenue_distribution_note": "Revenue distribution also contains PERCENTAGES of total revenue recognized each year",
                                
                                # Calculated actual revenue amounts
                                "revenue_info": {
                                    "total_revenue_vnd": total_revenue,
                                    "total_revenue_billion_vnd": total_revenue / 1e9 if total_revenue else 0,
                                    "revenue_by_year": revenue_by_year,
                                    "cumulative_revenue_to_date_vnd": cumulative_revenue,
                                    "cumulative_revenue_to_date_billion_vnd": cumulative_revenue / 1e9 if cumulative_revenue else 0,
                                    "percentage_revenue_recognized_to_date": (cumulative_revenue / total_revenue * 100) if total_revenue else 0
                                },
                                
                                # Cash collection schedule with calculations
                                "cash_collection_schedules_raw": cash_collection_schedules,
                                "cash_collection_note": "Cash collection is calculated from presales amounts using collection schedules per presale year",
                                "cash_collection_info": {
                                    "cash_collection_by_year": cash_collection_formatted,
                                    "total_cash_to_collect": total_revenue,
                                    "total_cash_to_collect_billion_vnd": total_revenue / 1e9 if total_revenue else 0,
                                    "cumulative_cash_collected_vnd": cumulative_cash_collected,
                                    "cumulative_cash_collected_billion_vnd": cumulative_cash_collected / 1e9 if cumulative_cash_collected else 0,
                                    "percentage_cash_collected_to_date": (cumulative_cash_collected / total_revenue * 100) if total_revenue else 0,
                                    "remaining_cash_to_collect_vnd": total_revenue - cumulative_cash_collected if total_revenue else 0,
                                    "remaining_cash_to_collect_billion_vnd": (total_revenue - cumulative_cash_collected) / 1e9 if total_revenue else 0
                                },
                                "construction_schedule": project.get('construction_schedule', {})
                            })
                            
                            # Calculate and add advanced financial metrics
                            # Use saved IRR if available, otherwise calculate it
                            project_irr = project.get('project_irr')  # Try to get saved IRR first
                            if project_irr is None:
                                project_irr = self._calculate_project_irr(project)
                            
                            cumulative_interest = self._calculate_cumulative_interest(project)
                            total_debt = project.get('total_debt', 0) or 0
                            cash_burden = total_debt + cumulative_interest
                            
                            project_data.update({
                                "total_revenue": project.get('total_revenue'),
                                "total_cogs": project.get('total_cogs'),
                                "gross_margin": project.get('gross_margin'),
                                "rnav_value": project.get('rnav_value'),
                                "npv": project.get('npv'),
                                "irr": project_irr,
                                "irr_percentage": f"{project_irr:.2%}" if project_irr else "N/A",
                                "total_debt": total_debt,
                                "cumulative_interest": cumulative_interest,
                                "cash_burden": cash_burden,
                                "debt_to_revenue_ratio": (total_debt / project.get('total_revenue', 1)) if project.get('total_revenue') else None
                            })
                        
                        # Add AI assumptions if requested
                        if include_assumptions:
                            project_data["ai_assumptions"] = project.get('ai_assumptions', {})
                        
                        result_projects.append(project_data)
                    
                    return {
                        "projects": result_projects,
                        "count": len(result_projects),
                        "source": "RealEstateProjects",
                        "include_financials": include_financials,
                        "include_assumptions": include_assumptions,
                        "status": "success"
                    }
                    
                except Exception as e:
                    # Fallback to CSV on error
                    pass
            
            # Fallback to CSV
            df = self._load_real_estate_projects()
            
            if df.empty:
                return {"error": "No projects data available", "status": "failed"}
            
            # Filter projects
            if project_names:
                mask = df['project_name'].str.lower().isin([p.lower() for p in project_names])
                df = df[mask]
            if ticker:
                df = df[df['company_ticker'] == ticker.upper()]
            
            if df.empty:
                return {"error": f"Projects not found", "status": "failed"}
            
            # Select columns based on request
            if include_financials:
                cols = df.columns.tolist()
            else:
                cols = ['project_name', 'company_ticker', 'location', 'total_units',
                       'net_sellable_area', 'average_selling_price', 'rnav_value',
                       'construction_start_year', 'project_completion_year']
                cols = [c for c in cols if c in df.columns]
            
            projects_data = df[cols].to_dict('records')
            
            return {
                "projects": projects_data,
                "count": len(projects_data),
                "source": "csv",
                "include_financials": include_financials,
                "status": "success"
            }
        
        @self.tool(
            name="rank_projects_by_metric",
            description="Rank real estate projects by specified metric",
            parameters={
                "metric": {
                    "type": "string",
                    "description": "Metric to rank by (rnav, revenue, units, nsa, margin, asp)",
                    "required": True
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of top projects to return",
                    "required": False
                },
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by companies",
                    "required": False
                }
            }
        )
        def rank_projects_by_metric(metric: str, top_n: int = 10, 
                                   tickers: List[str] = None) -> Dict:
            """Rank projects by metric"""
            
            df = self._load_real_estate_projects()
            
            if df.empty:
                return {"error": "No projects data available", "status": "failed"}
            
            # Filter by tickers if specified
            if tickers:
                tickers = [t.upper() for t in tickers]
                df = df[df['company_ticker'].isin(tickers)]
            
            # Map metric names to columns
            metric_mapping = {
                'rnav': 'rnav_value',
                'revenue': 'total_revenue_potential',
                'units': 'total_units',
                'nsa': 'net_sellable_area',
                'margin': 'gross_margin',
                'asp': 'average_selling_price',
                'construction_cost': 'construction_cost_per_sqm',
                'land_cost': 'land_cost_per_sqm'
            }
            
            column = metric_mapping.get(metric.lower())
            if not column or column not in df.columns:
                # Try to find revenue columns
                revenue_cols = [col for col in df.columns if 'revenue' in col.lower()]
                if revenue_cols:
                    column = revenue_cols[0]
                else:
                    return {
                        "error": f"Metric '{metric}' not found",
                        "available_metrics": list(metric_mapping.keys()),
                        "status": "failed"
                    }
            
            # Remove rows with null values and sort
            df_clean = df.dropna(subset=[column])
            # For debt metrics, show lowest first (best); for others, highest first
            ascending = True if metric.lower() in ['total_debt', 'cumulative_interest', 'cash_burden'] else False
            df_sorted = df_clean.sort_values(column, ascending=ascending).head(top_n)
            
            # Prepare ranking data
            ranking = df_sorted[['project_name', 'company_ticker', column]].copy()
            ranking['rank'] = range(1, len(ranking) + 1)
            
            return {
                "ranking": ranking.to_dict('records'),
                "metric": metric,
                "column_used": column,
                "top_n": top_n,
                "status": "success"
            }
        
        @self.tool(
            name="calculate_rnav_sensitivity",
            description="Calculate RNAV sensitivity to parameter changes (ASP, costs, WACC, etc.) by regenerating full financial statements",
            parameters={
                "project_name": {
                    "type": "string",
                    "description": "Project name for sensitivity analysis",
                    "required": True
                },
                "adjustments": {
                    "type": "object",
                    "description": "Parameter adjustments",
                    "properties": {
                        "asp_change_pct": {"type": "number", "description": "ASP change % for both segments"},
                        "low_rise_asp_change_pct": {"type": "number", "description": "Low-rise ASP change %"},
                        "high_rise_asp_change_pct": {"type": "number", "description": "High-rise ASP change %"},
                        "construction_cost_change_pct": {"type": "number", "description": "Construction cost change %"},
                        "land_cost_change_pct": {"type": "number", "description": "Land cost change %"},
                        "sga_pct_change": {"type": "number", "description": "SG&A percentage point change"},
                        "wacc_change_bps": {"type": "number", "description": "WACC change in basis points"},
                        "cost_of_debt_change_bps": {"type": "number", "description": "Cost of debt change in basis points"}
                    },
                    "required": True
                },
                "output_format": {
                    "type": "string",
                    "description": "Output format (detailed, summary, comparison)",
                    "required": False
                }
            }
        )
        def calculate_rnav_sensitivity(project_name: str, adjustments: Dict, output_format: str = "summary") -> Dict:
            """Calculate RNAV sensitivity by regenerating full financial statements"""
            
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            try:
                collection = self.vietnam_stocks_db['RealEstateProjects']
                
                # Find project
                project = collection.find_one({"project_name": {"$regex": f"^{project_name}$", "$options": "i"}})
                
                if not project:
                    return {"error": f"Project {project_name} not found", "status": "failed"}
                
                # Store original RNAV
                base_rnav = project.get('rnav_value', 0)
                
                # Apply adjustments to project parameters
                adjusted_project = project.copy()
                
                # Apply ASP changes
                if 'asp_change_pct' in adjustments:
                    # Apply to both segments
                    adjusted_project['low_rise_asp'] = project.get('low_rise_asp', 0) * (1 + adjustments['asp_change_pct'] / 100)
                    adjusted_project['high_rise_asp'] = project.get('high_rise_asp', 0) * (1 + adjustments['asp_change_pct'] / 100)
                
                if 'low_rise_asp_change_pct' in adjustments:
                    adjusted_project['low_rise_asp'] = project.get('low_rise_asp', 0) * (1 + adjustments['low_rise_asp_change_pct'] / 100)
                
                if 'high_rise_asp_change_pct' in adjustments:
                    adjusted_project['high_rise_asp'] = project.get('high_rise_asp', 0) * (1 + adjustments['high_rise_asp_change_pct'] / 100)
                
                # Apply cost changes
                if 'construction_cost_change_pct' in adjustments:
                    adjusted_project['construction_cost_per_sqm'] = project.get('construction_cost_per_sqm', 0) * (1 + adjustments['construction_cost_change_pct'] / 100)
                
                if 'land_cost_change_pct' in adjustments:
                    adjusted_project['land_cost_per_sqm'] = project.get('land_cost_per_sqm', 0) * (1 + adjustments['land_cost_change_pct'] / 100)
                
                # Apply financial parameter changes
                if 'sga_pct_change' in adjustments:
                    adjusted_project['sga_percentage'] = project.get('sga_percentage', 8.0) + adjustments['sga_pct_change']
                
                if 'wacc_change_bps' in adjustments:
                    adjusted_project['wacc_rate'] = project.get('wacc_rate', 0.12) + adjustments['wacc_change_bps'] / 10000
                
                if 'cost_of_debt_change_bps' in adjustments:
                    adjusted_project['cost_of_debt'] = project.get('cost_of_debt', 0.08) + adjustments['cost_of_debt_change_bps'] / 10000
                
                # Recalculate presales schedule with adjusted ASP
                presales_start = int(adjusted_project.get('sale_start_year', 2024))
                sales_years = int(adjusted_project.get('sales_years', 3))
                presales_end = presales_start + sales_years - 1
                price_increment = float(adjusted_project.get('price_increment_factor', 0))
                
                presales_schedule = {}
                for i, year in enumerate(range(presales_start, presales_end + 1)):
                    # Low-rise presales
                    low_dist = adjusted_project.get('low_rise_presales_distribution', {})
                    low_pct = low_dist.get(str(year), 0) / 100 if low_dist else 0
                    low_nsa = float(adjusted_project.get('low_rise_nsa', 0)) * low_pct
                    low_asp = float(adjusted_project.get('low_rise_asp', 0)) * (1 + price_increment) ** i
                    low_presale = low_nsa * low_asp
                    
                    # High-rise presales
                    high_dist = adjusted_project.get('high_rise_presales_distribution', {})
                    high_pct = high_dist.get(str(year), 0) / 100 if high_dist else 0
                    high_nsa = float(adjusted_project.get('high_rise_nsa', 0)) * high_pct
                    high_asp = float(adjusted_project.get('high_rise_asp', 0)) * (1 + price_increment) ** i
                    high_presale = high_nsa * high_asp
                    
                    presales_schedule[year] = low_presale + high_presale
                
                # Import balance sheet manager
                import sys
                import os
                sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from balance_sheet_manager import generate_balance_sheet_schedules
                from utils.RNAV_utils import RNAV_Calculation
                
                # Calculate total costs with adjustments
                total_construction = float(adjusted_project.get('gross_floor_area', 0)) * float(adjusted_project.get('construction_cost_per_sqm', 0))
                total_land = float(adjusted_project.get('land_area', 0)) * float(adjusted_project.get('land_cost_per_sqm', 0))
                
                # Get timeline parameters
                const_start = int(adjusted_project.get('construction_start_year', 2025))
                const_years = int(adjusted_project.get('construction_years', 3))
                const_end = const_start + const_years - 1
                
                land_payment_start = int(adjusted_project.get('land_payment_start_year', const_start))
                land_payment_years = int(adjusted_project.get('land_payment_years', 1))
                
                revenue_booking_start = int(adjusted_project.get('revenue_booking_start_year', const_end))
                revenue_booking_end = int(adjusted_project.get('project_completion_year', const_end + 1))
                
                # Generate balance sheet with adjusted parameters
                bs_df = generate_balance_sheet_schedules(
                    total_debt=float(adjusted_project.get('total_debt', 0)),
                    total_construction_cost=total_construction,
                    total_land_cost=total_land,
                    land_payment_start_year=land_payment_start,
                    land_payment_years=land_payment_years,
                    presales_schedule=presales_schedule,
                    interest_rate=float(adjusted_project.get('cost_of_debt', 0.08)),
                    sga_percentage=float(adjusted_project.get('sga_percentage', 0.08)),
                    debt_disbursement_start_year=const_start,
                    debt_disbursement_end_year=const_end,
                    debt_repayment_start_year=revenue_booking_end,
                    debt_repayment_end_year=revenue_booking_end,
                    revenue_booking_start_year=revenue_booking_start,
                    revenue_booking_end_year=revenue_booking_end,
                    cash_collection_schedules=adjusted_project.get('cash_collection_schedules')
                )
                
                # Extract cash flows from balance sheet (matching actual RNAV calculation)
                project_start = min([y for y in bs_df['Year'] if isinstance(y, int)])
                project_end = max([y for y in bs_df['Year'] if isinstance(y, int)])
                current_year = 2024  # Use current year
                
                selling_progress = []
                construction_payment = []
                land_payment = []
                sga_payment = []
                tax_expense = []
                
                for year in range(project_start, project_end + 1):
                    year_data = bs_df[bs_df["Year"] == year]
                    if not year_data.empty:
                        selling_progress.append(float(year_data["Cash_Inflow_Presales"].iloc[0]) / 1e9)
                        construction_payment.append(float(year_data["Cash_Outflow_Construction"].iloc[0]) / 1e9)
                        land_payment.append(float(year_data["Cash_Outflow_Land"].iloc[0]) / 1e9)
                        sga_payment.append(float(year_data["Cash_Outflow_SGA"].iloc[0]) / 1e9)
                        tax_expense.append(float(year_data["Cash_Outflow_Tax"].iloc[0]) / 1e9)
                    else:
                        selling_progress.append(0.0)
                        construction_payment.append(0.0)
                        land_payment.append(0.0)
                        sga_payment.append(0.0)
                        tax_expense.append(0.0)
                
                # Calculate new RNAV
                df_rnav = RNAV_Calculation(
                    selling_progress,
                    construction_payment,
                    sga_payment,
                    tax_expense,
                    land_payment,
                    float(adjusted_project.get('wacc_rate', 0.12)),
                    int(project_start),
                    int(current_year)
                )
                
                # Extract RNAV value
                total_row = df_rnav[df_rnav["Year"] == "Total RNAV"]
                if not total_row.empty:
                    new_rnav = float(total_row["Discounted Cash Flow"].iloc[0]) * 1e9
                else:
                    # Fallback to sum of discounted cash flows
                    numeric_rows = df_rnav[df_rnav["Year"] != "Total RNAV"]
                    new_rnav = float(numeric_rows["Discounted Cash Flow"].sum()) * 1e9
                
                # Prepare result based on output format
                result = {
                    "project_name": project_name,
                    "base_rnav": base_rnav,
                    "adjusted_rnav": new_rnav,
                    "change_amount": new_rnav - base_rnav,
                    "change_percentage": ((new_rnav - base_rnav) / base_rnav * 100) if base_rnav != 0 else 0,
                    "adjustments_applied": adjustments,
                    "status": "success"
                }
                
                if output_format == "detailed":
                    # Add detailed cash flow comparison
                    result["cash_flows"] = {
                        "total_inflow": sum(selling_progress) * 1e9,
                        "total_construction": sum(construction_payment) * 1e9,
                        "total_land": sum(land_payment) * 1e9,
                        "total_sga": sum(sga_payment) * 1e9,
                        "total_tax": sum(tax_expense) * 1e9
                    }
                    result["rnav_details"] = df_rnav.to_dict('records')
                
                elif output_format == "comparison":
                    # Add year-by-year comparison
                    result["yearly_comparison"] = []
                    for i, year in enumerate(range(project_start, project_end + 1)):
                        result["yearly_comparison"].append({
                            "year": year,
                            "cash_inflow": selling_progress[i] * 1e9 if i < len(selling_progress) else 0,
                            "net_cash_flow": (selling_progress[i] + construction_payment[i] + land_payment[i] + 
                                             sga_payment[i] + tax_expense[i]) * 1e9 if i < len(selling_progress) else 0
                        })
                
                return result
                
            except Exception as e:
                return {
                    "error": f"Error calculating sensitivity: {str(e)}",
                    "status": "failed"
                }
        
    
    def _register_forecast_analysis_tools(self):
        """Register forecast analysis tools"""
        
        @self.tool(
            name="get_comprehensive_forecast_details",
            description="Get comprehensive forecast data including all financial statements, project details, and interest income calculations. ALL VALUES ARE IN BILLIONS VND",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker",
                    "required": True
                },
                "years": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Forecast years to retrieve (2025-2030)",
                    "required": False
                },
                "include_project_breakdown": {
                    "type": "boolean",
                    "description": "Include detailed project-level breakdown",
                    "required": False
                },
                "include_assumptions": {
                    "type": "boolean",
                    "description": "Include all forecast assumptions",
                    "required": False
                },
                "include_valuation": {
                    "type": "boolean",
                    "description": "Include valuation metrics (RNAV, P/E, P/B)",
                    "required": False
                }
            }
        )
        def get_comprehensive_forecast_details(ticker: str, years: List[int] = None, 
                                              include_project_breakdown: bool = True,
                                              include_assumptions: bool = True,
                                              include_valuation: bool = True) -> Dict:
            """Get comprehensive forecast details from MongoDB CompanyForecast collection"""
            
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            ticker = ticker.upper()
            
            try:
                collection = self.vietnam_stocks_db['CompanyForecast']
                
                # Get forecast document
                doc = collection.find_one({'ticker': ticker}, {'_id': 0})
                
                if not doc:
                    return {"error": f"No forecast data found for {ticker}", "status": "failed"}
                
                # Filter years if specified
                if years:
                    years_str = [str(y) for y in years]
                else:
                    # Get all available years
                    years_str = list(doc.get('forecast_data', {}).keys())
                
                result = {
                    "ticker": ticker,
                    "company_name": doc.get('company_name', ticker),
                    "last_updated": doc.get('last_updated', 'N/A'),
                    "years": years_str
                }
                
                # Add assumptions if requested
                if include_assumptions:
                    result['assumptions'] = doc.get('assumptions', {})
                
                # Process each year's data
                forecast_data = {}
                for year in years_str:
                    if year not in doc.get('forecast_data', {}):
                        continue
                    
                    year_data = doc['forecast_data'][year]
                    
                    # Get P&L data (stored as 'pnl' not 'consolidated_pnl')
                    pnl_data = year_data.get('pnl', year_data.get('consolidated_pnl', {}))
                    
                    # Get balance sheet data
                    bs_data = year_data.get('balance_sheet', year_data.get('consolidated_balance_sheet', {}))
                    
                    # Get cash flow data
                    cf_data = year_data.get('cash_flow', year_data.get('consolidated_cash_flow', {}))
                    
                    # Comprehensive financial statements
                    forecast_data[year] = {
                        'consolidated_pnl': pnl_data,
                        'consolidated_balance_sheet': bs_data,
                        'consolidated_cash_flow': cf_data,
                        'interest_income': pnl_data.get('interest_income', 0),
                        'key_metrics': {
                            'revenue': pnl_data.get('net_revenue', pnl_data.get('revenue', 0)),
                            'gross_profit': pnl_data.get('gross_profit', 0),
                            'ebitda': pnl_data.get('ebitda', 0),
                            'npat': pnl_data.get('pat', pnl_data.get('npat', 0)),
                            'npatmi': pnl_data.get('npatmi', 0),
                            'total_assets': bs_data.get('total_assets', bs_data.get('assets', {}).get('total_assets', 0)),
                            'total_equity': bs_data.get('total_equity', bs_data.get('equity', {}).get('total_equity', 0)),
                            'total_debt': bs_data.get('total_debt', bs_data.get('liabilities', {}).get('total_debt', 0)),
                            'cash_balance': bs_data.get('cash', bs_data.get('assets', {}).get('cash', 0)),
                            'operating_cash_flow': cf_data.get('operating_cash_flow', cf_data.get('operating_activities', {}).get('total', 0))
                        },
                        'units': 'billion_vnd'  # Clarify units
                    }
                    
                    # Add project breakdown if requested
                    if include_project_breakdown and 'project_breakdown' in year_data:
                        project_breakdown = year_data['project_breakdown']
                        
                        # Summarize project data
                        project_summary = {}
                        for project_name, project_data in project_breakdown.items():
                            project_summary[project_name] = {
                                'revenue': project_data.get('revenue', 0),
                                'cogs': project_data.get('cogs', 0),
                                'gross_profit': project_data.get('gross_profit', 0),
                                'inventory_change': project_data.get('inventory_change', 0),
                                'debt_change': project_data.get('debt_change', 0),
                                'prepayment_change': project_data.get('prepayment_change', 0),
                                'cash_change': project_data.get('cash_change', 0),
                                'presales': project_data.get('presales', 0),
                                'cash_collection': project_data.get('cash_collection', 0)
                            }
                        
                        forecast_data[year]['project_breakdown'] = project_summary
                
                result['forecast_data'] = forecast_data
                
                # Calculate growth rates
                if len(years_str) > 1:
                    growth_rates = {}
                    sorted_years = sorted(years_str)
                    for i in range(1, len(sorted_years)):
                        prev_year = sorted_years[i-1]
                        curr_year = sorted_years[i]
                        
                        prev_revenue = forecast_data.get(prev_year, {}).get('key_metrics', {}).get('revenue', 0)
                        curr_revenue = forecast_data.get(curr_year, {}).get('key_metrics', {}).get('revenue', 0)
                        
                        if prev_revenue > 0:
                            growth_rates[f"{prev_year}-{curr_year}"] = {
                                'revenue_growth': ((curr_revenue - prev_revenue) / prev_revenue) * 100,
                                'npat_growth': self._calculate_growth(
                                    forecast_data.get(prev_year, {}).get('key_metrics', {}).get('npat', 0),
                                    forecast_data.get(curr_year, {}).get('key_metrics', {}).get('npat', 0)
                                )
                            }
                    
                    result['growth_rates'] = growth_rates
                
                # Add valuation data if requested
                if include_valuation and 'valuation_data' in doc:
                    valuation = doc['valuation_data']
                    result['valuation'] = {
                        "current_price": valuation.get('current_price', 0),
                        "rnav_per_share": valuation.get('rnav_per_share', 0),
                        "rnav_upside_pct": ((valuation.get('rnav_per_share', 0) / valuation.get('current_price', 1) - 1) * 100) if valuation.get('current_price', 0) > 0 else 0,
                        "multiples": valuation.get('multiples', {}),
                        "has_rnav_details": len(valuation.get('rnav_details', [])) > 0
                    }
                
                return {
                    "data": result,
                    "source": "CompanyForecast",
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
    
    def _calculate_growth(self, prev_value: float, curr_value: float) -> float:
        """Helper to calculate growth rate"""
        if prev_value == 0:
            return 0 if curr_value == 0 else 100
        return ((curr_value - prev_value) / abs(prev_value)) * 100
    
    def _register_forecast_analysis_tools(self):
        """Register additional forecast analysis tools"""
        
        @self.tool(
            name="analyze_balance_sheet_changes",
            description="Analyze balance sheet changes including inventory, debt, prepayment, and cash movements by project. ALL VALUES ARE IN BILLIONS VND",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker",
                    "required": True
                },
                "year": {
                    "type": "integer",
                    "description": "Year to analyze (2025-2030)",
                    "required": True
                },
                "change_type": {
                    "type": "string",
                    "enum": ["inventory", "debt", "prepayment", "cash", "all"],
                    "description": "Type of change to analyze",
                    "required": False
                }
            }
        )
        def analyze_balance_sheet_changes(ticker: str, year: int, change_type: str = "all") -> Dict:
            """Analyze balance sheet changes from CompanyForecast collection"""
            
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            ticker = ticker.upper()
            year_str = str(year)
            
            try:
                collection = self.vietnam_stocks_db['CompanyForecast']
                
                # Get forecast document
                doc = collection.find_one({'ticker': ticker}, {'_id': 0})
                
                if not doc or year_str not in doc.get('forecast_data', {}):
                    return {"error": f"No forecast data found for {ticker} in {year}", "status": "failed"}
                
                year_data = doc['forecast_data'][year_str]
                project_breakdown = year_data.get('project_breakdown', {})
                
                if not project_breakdown:
                    return {"error": f"No project breakdown available for {ticker} in {year}", "status": "failed"}
                
                # Analyze changes
                result = {
                    "ticker": ticker,
                    "year": year,
                    "changes": {}
                }
                
                # Define change types to analyze
                if change_type == "all":
                    change_types = ["inventory", "debt", "prepayment", "cash"]
                else:
                    change_types = [change_type]
                
                for change in change_types:
                    change_key = f"{change}_change"
                    project_changes = {}
                    total_change = 0
                    
                    for project_name, project_data in project_breakdown.items():
                        change_value = project_data.get(change_key, 0)
                        if change_value != 0:  # Only include non-zero changes
                            project_changes[project_name] = {
                                "value": change_value / 1e9,  # Convert raw to billions
                                "direction": "increase" if change_value > 0 else "decrease",
                                "percentage_of_total": 0  # Will calculate after totaling
                            }
                            total_change += change_value
                    
                    # Calculate percentages
                    if total_change != 0:
                        for project in project_changes:
                            project_changes[project]["percentage_of_total"] = \
                                (project_changes[project]["value"] / abs(total_change)) * 100
                    
                    result["changes"][change] = {
                        "total_change": total_change / 1e9,  # Convert raw to billions
                        "project_breakdown": project_changes,
                        "num_projects": len(project_changes),
                        "largest_contributor": max(project_changes.items(), 
                                                  key=lambda x: abs(x[1]["value"]))[0] if project_changes else None
                    }
                
                # Add consolidated balance sheet changes (convert raw to billions)
                consolidated_bs = year_data.get('consolidated_balance_sheet', {})
                result["consolidated_changes"] = {
                    "total_assets": consolidated_bs.get('assets', {}).get('total_assets', 0) / 1e9,
                    "total_liabilities": consolidated_bs.get('liabilities', {}).get('total_liabilities', 0) / 1e9,
                    "total_equity": consolidated_bs.get('equity', {}).get('total_equity', 0) / 1e9,
                    "cash": consolidated_bs.get('assets', {}).get('cash', 0) / 1e9,
                    "inventory": consolidated_bs.get('assets', {}).get('inventory', 0) / 1e9,
                    "total_debt": consolidated_bs.get('liabilities', {}).get('total_debt', 0) / 1e9,
                    "customer_prepayment": consolidated_bs.get('liabilities', {}).get('customer_prepayment', 0) / 1e9
                }
                
                return {
                    "data": result,
                    "source": "CompanyForecast",
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
        @self.tool(
            name="get_project_cash_flow_breakdown",
            description="Get detailed cash flow breakdown by project including presales, cash collection, and operating cash flow. ALL VALUES ARE IN BILLIONS VND",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker",
                    "required": True
                },
                "year": {
                    "type": "integer",
                    "description": "Year to analyze (2025-2030)",
                    "required": True
                },
                "project_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific projects to analyze (optional)",
                    "required": False
                }
            }
        )
        def get_project_cash_flow_breakdown(ticker: str, year: int, 
                                           project_names: List[str] = None) -> Dict:
            """Get detailed project cash flow breakdown from CompanyForecast"""
            
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            ticker = ticker.upper()
            year_str = str(year)
            
            try:
                collection = self.vietnam_stocks_db['CompanyForecast']
                
                # Get forecast document
                doc = collection.find_one({'ticker': ticker}, {'_id': 0})
                
                if not doc or year_str not in doc.get('forecast_data', {}):
                    return {"error": f"No forecast data found for {ticker} in {year}", "status": "failed"}
                
                year_data = doc['forecast_data'][year_str]
                project_breakdown = year_data.get('project_breakdown', {})
                
                if not project_breakdown:
                    return {"error": f"No project breakdown available for {ticker} in {year}", "status": "failed"}
                
                # Filter projects if specified
                if project_names:
                    project_breakdown = {
                        name: data for name, data in project_breakdown.items()
                        if name in project_names
                    }
                
                # Analyze cash flows by project
                result = {
                    "ticker": ticker,
                    "year": year,
                    "projects": {}
                }
                
                total_presales = 0
                total_cash_collection = 0
                total_operating_cf = 0
                
                for project_name, project_data in project_breakdown.items():
                    # Extract cash flow components
                    presales = project_data.get('presales', 0)
                    cash_collection = project_data.get('cash_collection', 0)
                    revenue = project_data.get('revenue', 0)
                    cogs = project_data.get('cogs', 0)
                    
                    # Calculate operating cash flow components
                    inventory_change = project_data.get('inventory_change', 0)
                    prepayment_change = project_data.get('prepayment_change', 0)
                    debt_change = project_data.get('debt_change', 0)
                    
                    # Operating CF = Cash collection - COGS paid
                    # Note: This is simplified; actual may include other working capital changes
                    operating_cf = cash_collection - (cogs - inventory_change)
                    
                    # Convert raw values to billions for display
                    project_cf = {
                        "presales": presales / 1e9,
                        "cash_collection": cash_collection / 1e9,
                        "revenue_recognized": revenue / 1e9,
                        "cogs": cogs / 1e9,
                        "gross_profit": (revenue - cogs) / 1e9 if revenue > 0 else 0,
                        "inventory_change": inventory_change / 1e9,
                        "prepayment_change": prepayment_change / 1e9,
                        "debt_change": debt_change / 1e9,
                        "operating_cash_flow": operating_cf / 1e9,
                        "cash_conversion_rate": (cash_collection / revenue * 100) if revenue > 0 else 0
                    }
                    
                    result["projects"][project_name] = project_cf
                    
                    # Add to totals
                    total_presales += presales
                    total_cash_collection += cash_collection
                    total_operating_cf += operating_cf
                
                # Add summary (convert totals to billions)
                result["summary"] = {
                    "total_presales": total_presales / 1e9,
                    "total_cash_collection": total_cash_collection / 1e9,
                    "total_operating_cash_flow": total_operating_cf / 1e9,
                    "num_projects": len(result["projects"]),
                    "average_cash_conversion": (total_cash_collection / sum(
                        p["revenue_recognized"] * 1e9 for p in result["projects"].values()  # Convert back to raw for calculation
                    ) * 100) if sum(p["revenue_recognized"] for p in result["projects"].values()) > 0 else 0
                }
                
                # Add consolidated cash flow for comparison (convert to billions)
                consolidated_cf = year_data.get('consolidated_cash_flow', {})
                if consolidated_cf:
                    result["consolidated_comparison"] = {
                        "operating_activities_total": consolidated_cf.get('operating_activities', {}).get('total', 0) / 1e9,
                        "investing_activities_total": consolidated_cf.get('investing_activities', {}).get('total', 0) / 1e9,
                        "financing_activities_total": consolidated_cf.get('financing_activities', {}).get('total', 0) / 1e9,
                        "net_cash_flow": consolidated_cf.get('net_cash_flow', 0) / 1e9
                    }
                
                return {
                    "data": result,
                    "source": "CompanyForecast",
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
    
    def _register_market_tools(self):
        """Register market analysis tools (MoC data)"""
        
        @self.tool(
            name="get_transaction_volumes",
            description="Get real estate transaction volumes from MoC data (quarterly)",
            parameters={
                "metric_type": {
                    "type": "string",
                    "enum": ["apartment", "land", "total"],
                    "description": "Type of transaction",
                    "required": False
                },
                "quarters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Quarters to retrieve (formats: '1Q24', '2Q23' or '2024-Q1', '2023-Q2')",
                    "required": False
                },
                "years": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Years to filter (e.g., [2023, 2024])",
                    "required": False
                },
                "last_n_quarters": {
                    "type": "integer",
                    "description": "Get last N quarters of data",
                    "required": False
                }
            }
        )
        def get_transaction_volumes(metric_type: str = None, quarters: List[str] = None,
                                   years: List[int] = None, last_n_quarters: int = None) -> Dict:
            """Get transaction volume data with enhanced quarterly extraction"""
            
            if self.moc_db is None:
                # Fallback to CSV
                df = self._load_moc_data_csv()
                if not df.empty:
                    # Process CSV data
                    return {
                        "data": df.head(20).to_dict('records'),
                        "source": "csv",
                        "status": "success"
                    }
                return {"error": "MoC data not available", "status": "failed"}
            
            collection = self.moc_db['transaction_volume']
            
            # Build query
            query = {}
            if metric_type:
                query['metric_type'] = metric_type
            
            # Handle different quarter formats
            if quarters:
                # Convert formats like '2024-Q1' to '1Q24'
                converted_quarters = []
                for q in quarters:
                    if '-Q' in q:
                        # Format: 2024-Q1 -> 1Q24
                        year, quarter = q.split('-Q')
                        converted_q = f"{quarter}Q{year[-2:]}"
                        converted_quarters.append(converted_q)
                    else:
                        # Already in format like 1Q24
                        converted_quarters.append(q)
                query['quarter'] = {"$in": converted_quarters}
            
            # Filter by years if specified
            if years:
                query['year'] = {"$in": years}
            
            # Get all data first for last_n_quarters processing
            if last_n_quarters:
                # Get all quarters sorted by date
                all_quarters = collection.distinct('quarter')
                all_quarters_sorted = sorted(all_quarters, 
                                            key=lambda x: (int('20' + x[2:]), int(x[0])))
                last_quarters = all_quarters_sorted[-last_n_quarters:]
                if 'quarter' in query:
                    # Combine with existing quarter filter
                    existing = query['quarter'].get('$in', [])
                    query['quarter'] = {"$in": list(set(existing + last_quarters))}
                else:
                    query['quarter'] = {"$in": last_quarters}
            
            # Execute query
            cursor = collection.find(query, {"_id": 0}).sort("date", 1)
            data = list(cursor)
            
            # Enhance data with formatted quarter and QoQ growth
            if data:
                for i, record in enumerate(data):
                    # Add formatted quarter (e.g., 1Q24 -> 2024-Q1)
                    if 'quarter' in record:
                        q = record['quarter']
                        quarter_num = q[0]
                        year = '20' + q[2:]
                        record['formatted_quarter'] = f"{year}-Q{quarter_num}"
                    
                    # Calculate QoQ growth
                    if i > 0 and data[i-1].get('value') and record.get('value'):
                        prev_val = data[i-1]['value']
                        curr_val = record['value']
                        if prev_val > 0:
                            record['qoq_growth'] = round((curr_val - prev_val) / prev_val * 100, 2)
                        else:
                            record['qoq_growth'] = None
                    else:
                        record['qoq_growth'] = None
                    
                    # Add YoY growth if same quarter last year exists
                    if 'quarter' in record and 'year' in record:
                        quarter_num = record['quarter'][0]
                        curr_year = record['year']
                        prev_year_quarter = f"{quarter_num}Q{str(curr_year-1)[-2:]}"
                        
                        # Find previous year same quarter
                        for prev_record in data:
                            if prev_record.get('quarter') == prev_year_quarter:
                                if prev_record.get('value') and record.get('value'):
                                    prev_val = prev_record['value']
                                    curr_val = record['value']
                                    if prev_val > 0:
                                        record['yoy_growth'] = round((curr_val - prev_val) / prev_val * 100, 2)
                                break
            
            # Calculate summary statistics
            summary = {}
            if data:
                values = [d['value'] for d in data if d.get('value')]
                if values:
                    summary = {
                        'total_records': len(data),
                        'min_value': min(values),
                        'max_value': max(values),
                        'avg_value': round(sum(values) / len(values), 2),
                        'latest_quarter': data[-1].get('formatted_quarter', data[-1].get('quarter')),
                        'latest_value': data[-1].get('value'),
                        'latest_qoq': data[-1].get('qoq_growth'),
                        'latest_yoy': data[-1].get('yoy_growth')
                    }
            
            return {
                "data": data,
                "metric_type": metric_type,
                "summary": summary,
                "source": "MoCDB",
                "status": "success"
            }
        
        @self.tool(
            name="get_credit_outstanding",
            description="Get real estate credit outstanding data",
            parameters={
                "credit_type": {
                    "type": "string",
                    "description": "Type of credit (construction, hotel, industrial, etc.)",
                    "required": False
                },
                "year": {
                    "type": "integer",
                    "description": "Year to filter",
                    "required": False
                }
            }
        )
        def get_credit_outstanding(credit_type: str = None, year: int = None) -> Dict:
            """Get credit outstanding data"""
            
            if self.moc_db is None:
                return {"error": "MoC database not available", "status": "failed"}
            
            collection = self.moc_db['credit_outstanding']
            
            # Build query
            query = {}
            if credit_type:
                query['credit_type'] = credit_type
            if year:
                query['year'] = year
            
            # Get available credit types
            credit_types = collection.distinct('credit_type')
            
            # Execute query
            cursor = collection.find(query, {"_id": 0}).sort("date", 1)
            data = list(cursor)
            
            # Calculate totals by quarter
            quarter_totals = {}
            for record in data:
                q = record.get('quarter')
                val = record.get('value', 0)
                if q:
                    if q not in quarter_totals:
                        quarter_totals[q] = 0
                    quarter_totals[q] += val
            
            return {
                "data": data,
                "credit_types": credit_types,
                "quarter_totals": quarter_totals,
                "records": len(data),
                "status": "success"
            }
        
        @self.tool(
            name="get_inventory_levels",
            description="Get real estate inventory levels (quarterly data)",
            parameters={
                "inventory_type": {
                    "type": "string",
                    "enum": ["apartment", "individual_house", "land", "total"],
                    "description": "Type of inventory",
                    "required": False
                },
                "quarters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Quarters to retrieve (formats: '1Q24' or '2024-Q1')",
                    "required": False
                },
                "last_n_quarters": {
                    "type": "integer",
                    "description": "Get last N quarters of data",
                    "required": False
                }
            }
        )
        def get_inventory_levels(inventory_type: str = None, quarters: List[str] = None,
                               last_n_quarters: int = None) -> Dict:
            """Get inventory level data with enhanced quarterly extraction"""
            
            if self.moc_db is None:
                return {"error": "MoC database not available", "status": "failed"}
            
            collection = self.moc_db['inventory']
            
            # Build query
            query = {}
            if inventory_type:
                query['inventory_type'] = inventory_type
            
            # Handle different quarter formats
            if quarters:
                # Convert formats like '2024-Q1' to '1Q24'
                converted_quarters = []
                for q in quarters:
                    if '-Q' in q:
                        # Format: 2024-Q1 -> 1Q24
                        year, quarter = q.split('-Q')
                        converted_q = f"{quarter}Q{year[-2:]}"
                        converted_quarters.append(converted_q)
                    else:
                        # Already in format like 1Q24
                        converted_quarters.append(q)
                query['quarter'] = {"$in": converted_quarters}
            
            # Get last N quarters if specified
            if last_n_quarters:
                # Get all quarters sorted by date
                all_quarters = collection.distinct('quarter')
                all_quarters_sorted = sorted(all_quarters, 
                                            key=lambda x: (int('20' + x[2:]), int(x[0])))
                last_quarters = all_quarters_sorted[-last_n_quarters:]
                if 'quarter' in query:
                    # Combine with existing quarter filter
                    existing = query['quarter'].get('$in', [])
                    query['quarter'] = {"$in": list(set(existing + last_quarters))}
                else:
                    query['quarter'] = {"$in": last_quarters}
            
            # Execute query
            cursor = collection.find(query, {"_id": 0}).sort("date", 1)
            data = list(cursor)
            
            # Enhance data with formatted quarter and growth metrics
            if data:
                for i, record in enumerate(data):
                    # Add formatted quarter
                    if 'quarter' in record:
                        q = record['quarter']
                        quarter_num = q[0]
                        year = '20' + q[2:]
                        record['formatted_quarter'] = f"{year}-Q{quarter_num}"
                    
                    # Calculate QoQ change
                    if i > 0 and data[i-1].get('value') and record.get('value'):
                        if data[i-1].get('inventory_type') == record.get('inventory_type'):
                            prev_val = data[i-1]['value']
                            curr_val = record['value']
                            record['qoq_change'] = curr_val - prev_val
                            if prev_val > 0:
                                record['qoq_growth'] = round((curr_val - prev_val) / prev_val * 100, 2)
            
            # Get latest values by type
            latest_by_type = {}
            for record in data:
                inv_type = record.get('inventory_type')
                if inv_type:
                    latest_by_type[inv_type] = record
            
            # Calculate summary
            summary = {}
            if data:
                # Group by inventory type for summary
                by_type = {}
                for record in data:
                    inv_type = record.get('inventory_type', 'unknown')
                    if inv_type not in by_type:
                        by_type[inv_type] = []
                    by_type[inv_type].append(record)
                
                for inv_type, records in by_type.items():
                    values = [r['value'] for r in records if r.get('value')]
                    if values and records:
                        summary[inv_type] = {
                            'latest_quarter': records[-1].get('formatted_quarter', records[-1].get('quarter')),
                            'latest_value': records[-1].get('value'),
                            'latest_qoq_change': records[-1].get('qoq_change'),
                            'latest_qoq_growth': records[-1].get('qoq_growth'),
                            'min_value': min(values),
                            'max_value': max(values),
                            'avg_value': round(sum(values) / len(values), 2)
                        }
            
            return {
                "data": data,
                "latest_by_type": latest_by_type,
                "summary": summary,
                "records": len(data),
                "source": "MoCDB",
                "status": "success"
            }
        
        @self.tool(
            name="analyze_market_trends",
            description="Analyze market trends from MoC data",
            parameters={
                "analysis_type": {
                    "type": "string",
                    "enum": ["transaction", "credit", "inventory", "all"],
                    "description": "Type of analysis",
                    "required": False
                },
                "period": {
                    "type": "string",
                    "description": "Period for analysis (e.g., '2024')",
                    "required": False
                }
            }
        )
        def analyze_market_trends(analysis_type: str = "all", period: str = None) -> Dict:
            """Comprehensive market trend analysis"""
            
            results = {}
            
            # Transaction volume trends
            if analysis_type in ["transaction", "all"]:
                trans_result = get_transaction_volumes()
                if trans_result.get("status") == "success":
                    trans_data = trans_result.get("data", [])
                    if trans_data:
                        # Calculate trend
                        apartment_trend = [d for d in trans_data if d.get('metric_type') == 'apartment']
                        land_trend = [d for d in trans_data if d.get('metric_type') == 'land']
                        
                        results["transaction_trends"] = {
                            "apartment_latest": apartment_trend[-1] if apartment_trend else None,
                            "land_latest": land_trend[-1] if land_trend else None,
                            "total_quarters": len(set(d.get('quarter') for d in trans_data))
                        }
            
            # Credit trends
            if analysis_type in ["credit", "all"]:
                credit_result = get_credit_outstanding()
                if credit_result.get("status") == "success":
                    results["credit_trends"] = {
                        "total_by_quarter": credit_result.get("quarter_totals", {}),
                        "credit_types": credit_result.get("credit_types", [])
                    }
            
            # Inventory trends
            if analysis_type in ["inventory", "all"]:
                inv_result = get_inventory_levels()
                if inv_result.get("status") == "success":
                    results["inventory_trends"] = inv_result.get("latest_by_type", {})
            
            return {
                "analysis": results,
                "analysis_type": analysis_type,
                "period": period,
                "status": "success"
            }
    
    def _register_ai_tools(self):
        """Register AI-enhanced tools"""
        
        @self.tool(
            name="search_market_insights",
            description="Search for market insights using Perplexity AI",
            parameters={
                "query": {
                    "type": "string",
                    "description": "Search query",
                    "required": True
                },
                "context": {
                    "type": "string",
                    "description": "Additional context for the search",
                    "required": False
                }
            }
        )
        def search_market_insights(query: str, context: str = None) -> Dict:
            """Search market insights using AI"""
            
            perplexity_key = os.getenv('PERPLEXITY_API_KEY')
            if not perplexity_key:
                return {"error": "Perplexity API not configured", "status": "failed"}
            
            try:
                # Enhance query with context
                full_query = query
                if context:
                    full_query = f"{context}: {query}"
                
                # Call Perplexity API
                insights = get_project_basic_info_perplexity(full_query, perplexity_key)
                
                return {
                    "query": query,
                    "insights": insights,
                    "context": context,
                    "status": "success"
                }
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
        @self.tool(
            name="generate_analysis",
            description="Generate AI-powered financial analysis",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker",
                    "required": True
                },
                "analysis_type": {
                    "type": "string",
                    "enum": ["fundamental", "valuation", "growth", "comprehensive"],
                    "description": "Type of analysis",
                    "required": False
                }
            }
        )
        def generate_analysis(ticker: str, analysis_type: str = "comprehensive") -> Dict:
            """Generate AI-powered analysis"""
            
            if not self.anthropic_client:
                return {"error": "Claude API not configured", "status": "failed"}
            
            ticker = ticker.upper()
            
            # Gather financial data directly
            summary = {"ticker": ticker}
            include_projects = True  # Always include projects if available
            
            # Financial statements summary
            fin_result = self.tools.get('get_historical_financials', lambda: {})(tickers=[ticker])
            if fin_result.get('status') == 'success' and fin_result.get('data'):
                summary['financials'] = fin_result.get('data')
            
            # Valuation metrics
            val_result = self.tools.get('get_valuation_metrics', lambda: {})(ticker=ticker)
            if val_result.get('status') == 'success' and val_result.get('valuation_metrics'):
                summary['valuation'] = val_result.get('valuation_metrics')
            
            # Projects if real estate company
            if include_projects:
                projects_result = self.tools.get('list_real_estate_projects', lambda: {})(ticker=ticker)
                if projects_result.get('status') == 'success' and projects_result.get('projects'):
                    summary['projects'] = projects_result.get('projects')
            
            if not summary.get('financials') and not summary.get('valuation'):
                return {"error": "Unable to gather data for analysis", "status": "failed"}
            
            # Create prompt based on analysis type
            prompt = f"""Analyze {ticker} based on the following data:

Financial Metrics:
{json.dumps(summary.get('financials', {}), indent=2)}

Valuation:
{json.dumps(summary.get('valuation', {}), indent=2)}

Projects:
{json.dumps(summary.get('projects', {}), indent=2)}

Provide a {analysis_type} analysis including:
1. Key strengths and opportunities
2. Risk factors
3. Investment thesis
4. Recommendation

Be concise and data-driven."""
            
            try:
                # Generate analysis using Claude
                response = self.anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=1000,
                    temperature=0.3,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                
                analysis_text = response.content[0].text
                
                return {
                    "ticker": ticker,
                    "analysis_type": analysis_type,
                    "analysis": analysis_text,
                    "data_used": summary,
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
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
        
        @self.tool(
            name="render_chart",
            description="""Create a chart visualization from processed data. 
            INSTRUCTIONS FOR USE:
            1. ALWAYS gather data first using other tools (get_historical_financials, get_valuation_metrics, etc.)
            2. Structure data with clear x-axis labels and y-values
            3. Specify y_format: 'percent' for rates/ratios, 'number' for counts, 'currency' for monetary values
            4. Available chart types: line, bar, stacked_bar, scatter, area
            
            IMPORTANT:
            - Only pass processed, chart-ready data
            - Do NOT include raw data tables in your text response
            - For stacked_bar: provide multiple series that will be stacked
            """,
            parameters={
                "chart_type": {
                    "type": "string",
                    "enum": ["line", "bar", "stacked_bar", "scatter", "area"],
                    "description": "Type of chart to render (use stacked_bar for stacked bar charts)"
                },
                "data": {
                    "type": "object",
                    "properties": {
                        "x": {
                            "type": "array",
                            "description": "X-axis labels (dates, categories, etc.)",
                            "items": {"type": "string"}
                        },
                        "series": {
                            "type": "array",
                            "description": "Data series to plot",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Series name for legend"},
                                    "y": {
                                        "type": "array", 
                                        "description": "Y-axis values",
                                        "items": {"type": "number"}
                                    }
                                }
                            }
                        }
                    },
                    "required": ["x", "series"]
                },
                "title": {
                    "type": "string",
                    "description": "Chart title"
                },
                "x_label": {
                    "type": "string",
                    "description": "X-axis label",
                    "required": False
                },
                "y_label": {
                    "type": "string",
                    "description": "Y-axis label",
                    "required": False
                },
                "y_format": {
                    "type": "string",
                    "enum": ["percent", "number", "currency"],
                    "description": "Format for y-axis values",
                    "required": False
                }
            }
        )
        def render_chart(chart_type: str, data: Dict, title: str, x_label: str = "", y_label: str = "", y_format: str = "number") -> Dict:
            """Prepare chart specification for rendering"""
            import uuid
            
            # Validate data structure
            if not data or "x" not in data or "series" not in data:
                return {"error": "Invalid data structure. Must have 'x' and 'series' fields", "status": "failed"}
            
            if not data["series"] or len(data["series"]) == 0:
                return {"error": "No data series provided", "status": "failed"}
            
            # Generate unique chart ID
            chart_id = str(uuid.uuid4())[:8]
            
            # Prepare chart specification
            chart_spec = {
                "chart_id": chart_id,
                "chart_type": chart_type,
                "data": data,
                "title": title,
                "x_label": x_label or "",
                "y_label": y_label or "",
                "y_format": y_format,
                "timestamp": datetime.now().isoformat()
            }
            
            # Store chart spec in class attribute for retrieval
            if not hasattr(self, '_pending_charts'):
                self._pending_charts = {}
            self._pending_charts[chart_id] = chart_spec
            
            # Return marker for the chat interface to detect
            return {
                "type": "chart",
                "chart_id": chart_id,
                "chart_spec": chart_spec,  # Include spec in response
                "message": f"Chart '{title}' prepared for rendering",
                "status": "success"
            }
        
        # Keep the original create_financial_chart for backward compatibility but updated
        @self.tool(
            name="create_financial_chart",
            description="Create interactive financial charts using structured data format (alternative to render_chart)",
            parameters={
                "chart_type": {
                    "type": "string",
                    "enum": ["line", "bar", "waterfall", "scatter", "area", "combo"],
                    "description": "Type of chart to create",
                    "required": True
                },
                "data": {
                    "type": "object",
                    "description": "Data to visualize (as returned by other tools)",
                    "required": True
                },
                "title": {
                    "type": "string",
                    "description": "Chart title",
                    "required": False
                },
                "x_axis": {
                    "type": "string",
                    "description": "Column name for x-axis",
                    "required": False
                },
                "y_axis": {
                    "type": "string",
                    "description": "Column name(s) for y-axis",
                    "required": False
                },
                "options": {
                    "type": "object",
                    "description": "Additional chart options",
                    "required": False
                }
            }
        )
        def create_financial_chart(chart_type: str, data: Dict = None, title: str = None,
                                  x_axis: str = None, y_axis: str = None,
                                  options: Dict = None) -> Dict:
            """Create interactive financial charts - converts to render_chart format"""
            
            try:
                # Validate data parameter
                if data is None:
                    return {"error": "Data parameter is required", "status": "failed"}
                
                if not data:
                    return {"error": "Data parameter cannot be empty", "status": "failed"}
                
                # Convert data to DataFrame if needed
                if isinstance(data, dict):
                    if 'data' in data:
                        df = pd.DataFrame(data['data'])
                    elif 'values' in data:
                        df = pd.DataFrame(data['values'])
                    else:
                        df = pd.DataFrame([data])
                else:
                    df = pd.DataFrame(data)
                
                # Determine axes if not specified
                if x_axis is None and 'DATE' in df.columns:
                    x_axis = 'DATE'
                elif x_axis is None and len(df.columns) > 0:
                    x_axis = df.columns[0]
                
                if y_axis is None and 'VALUE' in df.columns:
                    y_axis = 'VALUE'
                elif y_axis is None and len(df.columns) > 1:
                    y_axis = df.columns[1]
                
                # Convert to render_chart format
                x_values = df[x_axis].astype(str).tolist() if x_axis in df.columns else []
                
                series_data = []
                if isinstance(y_axis, list):
                    for col in y_axis:
                        if col in df.columns:
                            series_data.append({
                                "name": col,
                                "y": df[col].tolist()
                            })
                elif y_axis in df.columns:
                    series_data.append({
                        "name": y_axis,
                        "y": df[y_axis].tolist()
                    })
                
                # Map chart types that aren't supported in render_chart
                mapped_chart_type = chart_type
                if chart_type == "waterfall":
                    mapped_chart_type = "bar"
                elif chart_type == "combo":
                    # For combo charts with multiple series, use stacked_bar
                    mapped_chart_type = "stacked_bar" if len(series_data) > 1 else "bar"
                
                # Prepare data in render_chart format
                chart_data = {
                    "x": x_values,
                    "series": series_data
                }
                
                # Determine y_format
                y_format = "number"
                if options and "y_format" in options:
                    y_format = options["y_format"]
                elif y_axis and isinstance(y_axis, str):
                    if any(kw in y_axis.lower() for kw in ["margin", "ratio", "rate", "percent"]):
                        y_format = "percent"
                    elif any(kw in y_axis.lower() for kw in ["revenue", "profit", "cost", "price"]):
                        y_format = "currency"
                
                # Call render_chart with converted data
                return render_chart(
                    chart_type=mapped_chart_type,
                    data=chart_data,
                    title=title or f"{chart_type.capitalize()} Chart",
                    x_label=x_axis,
                    y_label=y_axis if isinstance(y_axis, str) else "Value",
                    y_format=y_format
                )
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
    
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