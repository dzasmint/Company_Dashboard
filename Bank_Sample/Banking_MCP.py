"""
Banking MCP Tool System
Provides modular tools for OpenAI to access and analyze banking data
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
import json
from functools import wraps
from scipy import stats
import requests
from datetime import datetime, timedelta
from functools import lru_cache


class BankingToolSystem:
    """
    Modular tool system for banking analysis
    Easy to extend with new tools using decorator pattern
    """
    
    def __init__(self, data_dir: Path = None):
        """Initialize the tool system with lazy loading"""
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "Data"
        
        self.data_dir = data_dir
        self.tools = {}
        self.tool_schemas = []
        self.data = {}
        self._data_loaded = {}  # Track which data files are loaded
        
        # Don't load data upfront - use lazy loading instead
        # self._load_data()  # REMOVED - now lazy loaded
        
        # Register all tools
        self._register_tools()
    
    @lru_cache(maxsize=1)
    def _load_historical_year(self):
        """Lazy load historical year data"""
        if 'historical_year' not in self.data:
            self.data['historical_year'] = pd.read_csv(self.data_dir / 'dfsectoryear.csv')
            self._data_loaded['historical_year'] = True
        return self.data['historical_year']
    
    @lru_cache(maxsize=1)
    def _load_historical_quarter(self):
        """Lazy load historical quarter data"""
        if 'historical_quarter' not in self.data:
            self.data['historical_quarter'] = pd.read_csv(self.data_dir / 'dfsectorquarter.csv')
            self._data_loaded['historical_quarter'] = True
        return self.data['historical_quarter']
    
    @lru_cache(maxsize=1)
    def _load_forecast(self):
        """Lazy load forecast data"""
        if 'forecast' not in self.data:
            self.data['forecast'] = pd.read_csv(self.data_dir / 'dfsectorforecast.csv')
            self._data_loaded['forecast'] = True
        return self.data['forecast']
    
    @lru_cache(maxsize=1)
    def _load_bank_types(self):
        """Lazy load bank types data"""
        if 'bank_types' not in self.data:
            self.data['bank_types'] = pd.read_excel(self.data_dir / 'Bank_Type.xlsx')
            self._data_loaded['bank_types'] = True
        return self.data['bank_types']
    
    @lru_cache(maxsize=1)
    def _load_comments(self):
        """Lazy load comments data"""
        if 'comments' not in self.data:
            if (self.data_dir / 'banking_comments.xlsx').exists():
                self.data['comments'] = pd.read_excel(self.data_dir / 'banking_comments.xlsx')
                self._data_loaded['comments'] = True
            else:
                return None
        return self.data.get('comments')
    
    @lru_cache(maxsize=1)
    def _load_quarterly_analysis(self):
        """Lazy load quarterly analysis data"""
        if 'quarterly_analysis' not in self.data:
            if (self.data_dir / 'quarterly_analysis_results.xlsx').exists():
                self.data['quarterly_analysis'] = pd.read_excel(self.data_dir / 'quarterly_analysis_results.xlsx')
                self._data_loaded['quarterly_analysis'] = True
            else:
                return None
        return self.data.get('quarterly_analysis')
    
    @lru_cache(maxsize=1)
    def _load_valuation(self):
        """Lazy load valuation data - this is a large file (52K lines)"""
        if 'valuation' not in self.data:
            if (self.data_dir / 'Valuation_banking.csv').exists():
                self.data['valuation'] = pd.read_csv(self.data_dir / 'Valuation_banking.csv')
                self._data_loaded['valuation'] = True
            else:
                return None
        return self.data.get('valuation')
    
    def tool(self, name: str, description: str, parameters: Dict = None):
        """
        Decorator to register a tool with OpenAI schema
        Makes it easy to add new tools
        """
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
            # Clean parameters by removing 'required' field from individual params
            clean_params = {}
            required_params = []
            
            if parameters:
                for param_name, param_def in parameters.items():
                    # Check if this parameter is required (default True if not specified)
                    is_required = param_def.get("required", True)
                    if is_required:
                        required_params.append(param_name)
                    
                    # Create clean parameter definition without 'required' field
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
    
    def _register_tools(self):
        """Register all available tools"""
        
        # Tool 1: Get Data Availability
        @self.tool(
            name="get_data_availability",
            description="MANDATORY: You MUST call this first for ANY query about 'latest', 'recent', 'current' to determine actual data periods",
            parameters={}
        )
        def get_data_availability() -> Dict:
            """Get available data periods"""
            quarterly = self._load_historical_quarter()
            yearly = self._load_historical_year()
            forecast = self._load_forecast()
            
            # Get unique periods
            q_periods = sorted(quarterly['Date_Quarter'].unique())[-8:]
            y_periods = sorted(yearly['Year'].unique())[-5:]
            f_periods = sorted(forecast['Year'].unique())
            
            return {
                "current_date": datetime.now().strftime("%Y-%m-%d"),
                "latest_quarterly": q_periods[-1] if q_periods else None,
                "latest_yearly": str(y_periods[-1]) if y_periods else None,
                "recent_quarters": q_periods,
                "recent_years": [str(y) for y in y_periods],
                "forecast_years": [str(y) for y in f_periods],
                "status": "success"
            }
        
        
        # Tool 3: List All Banks
        @self.tool(
            name="list_all_banks",
            description="List all available banks grouped by sector",
            parameters={}
        )
        def list_all_banks() -> Dict:
            """List all banks by sector"""
            bank_types = self._load_bank_types()
            
            sectors = {}
            for sector in bank_types['Type'].unique():
                banks = bank_types[bank_types['Type'] == sector]['TICKER'].tolist()
                sectors[sector] = banks
            
            return {
                "sectors": sectors,
                "total_banks": len(bank_types),
                "status": "success"
            }
        
        # Tool 4: Query Historical Data (Universal - handles single or multiple)
        @self.tool(
            name="query_historical_data",
            description="Query simple historical banking metrics for one or multiple banks. For detailed fundamental analysis, use get_ai_commentary tool",
            parameters={
                "frequency": {
                    "type": "string",
                    "description": "Data frequency - specify 'quarterly' for quarterly data or 'yearly' for yearly data",
                    "enum": ["quarterly", "yearly"],
                    "required": True
                },
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bank tickers - use [\"VCB\"] for single, [\"VCB\", \"ACB\"] for multiple",
                    "required": False
                },
                "period": {"type": "string", "description": "Period like 2024-Q3 or 2024", "required": False},
                "metric_group": {
                    "type": "string", 
                    "description": "Metric group: all, profitability, asset_quality, growth",
                    "enum": ["all", "profitability", "asset_quality", "growth"],
                    "required": False
                }
            }
        )
        def query_historical_data(frequency: str, tickers = None, period: str = None, metric_group: str = "all") -> Dict:
            """Query historical data for one or multiple banks"""
            # Determine if quarterly or yearly based on frequency parameter
            is_quarterly = (frequency == "quarterly")
            df = self._load_historical_quarter() if is_quarterly else self._load_historical_year()
            
            # Apply ticker filter if specified
            if tickers:
                if isinstance(tickers, str):
                    tickers = [tickers]
                tickers = [t.upper() for t in tickers]
                df = df[df['TICKER'].isin(tickers)]
            
            if period:
                if is_quarterly:
                    df = df[df['Date_Quarter'] == period]
                else:
                    df = df[df['Year'] == int(period)]
            
            if df.empty:
                return {"error": "No data found", "status": "failed"}
            
            # Select metrics based on group
            metric_groups = {
                "profitability": ["ROA", "ROE", "NIM", "CIR"],
                "asset_quality": ["NPL", "NPL Coverage ratio", "Provision/ Total Loan", "GROUP 2"],
                "growth": ["Loan", "Deposit", "Total Assets", "NPATMI"]
            }
            
            if metric_group != "all":
                metrics = metric_groups.get(metric_group, [])
                available_metrics = [m for m in metrics if m in df.columns]
                if available_metrics:
                    id_cols = ['TICKER', 'Year' if 'Year' in df.columns else 'Date_Quarter']
                    df = df[id_cols + available_metrics]
            
            # Return summary
            return {
                "records": len(df),
                "data": df.head(10).to_dict('records'),
                "columns": df.columns.tolist(),
                "status": "success"
            }
        
        # Tool 5: Query Forecast Data (Universal - handles single or multiple)
        @self.tool(
            name="query_forecast_data",
            description="Get simple forecast metrics with historical context for one or multiple banks",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bank tickers - use [\"VCB\"] for single, [\"VCB\", \"ACB\"] for multiple",
                    "required": False
                }
            }
        )
        def query_forecast_data(tickers = None) -> Dict:
            """Query all forecast data with historical context for one or multiple banks"""
            # Get forecast data
            forecast_df = self._load_forecast().copy()
            historical_df = self._load_historical_year().copy()
            
            # Dynamically determine the latest historical year
            latest_historical_year = historical_df['Year'].max()
            
            # Get available forecast years
            forecast_years = sorted(forecast_df['Year'].unique())
            
            # Handle single ticker or array
            if tickers:
                if isinstance(tickers, str):
                    tickers = [tickers]
                tickers = [t.upper() for t in tickers]
                forecast_df = forecast_df[forecast_df['TICKER'].isin(tickers)]
                historical_df = historical_df[historical_df['TICKER'].isin(tickers)]
            
            # ALWAYS get ALL forecast years - no year filtering
            
            if forecast_df.empty:
                return {"error": "No forecast data found", "status": "failed"}
            
            # Get latest historical data for comparison
            latest_historical = historical_df[historical_df['Year'] == latest_historical_year]
            
            # Only simple key metrics - for detailed analysis use get_ai_commentary
            key_metrics = ["Loan", "NPL", "ROA", "ROE", "NIM", "PBT"]
            available_metrics = [m for m in key_metrics if m in forecast_df.columns and m in historical_df.columns]
            
            # Prepare response
            response = {
                "latest_actual_year": int(latest_historical_year),
                "forecast_years": [int(y) for y in forecast_years],
                "requested_tickers": tickers if tickers else "All",
                "metrics_included": available_metrics
            }
            
            # Add actual historical data
            if not latest_historical.empty:
                historical_data = latest_historical[['TICKER', 'Year'] + available_metrics].to_dict('records')
                response["actual_data"] = {
                    "year": int(latest_historical_year),
                    "records": len(historical_data),
                    "data": historical_data
                }
            
            # Add forecast data
            forecast_data = forecast_df[['TICKER', 'Year'] + available_metrics].to_dict('records')
            response["forecast_data"] = {
                "years": sorted(forecast_df['Year'].unique().tolist()),
                "records": len(forecast_data),
                "data": forecast_data
            }
            
            # Calculate growth rates if single ticker
            if tickers and len(tickers) == 1 and not latest_historical.empty and len(forecast_data) > 0:
                comparison = {}
                historical_record = latest_historical.iloc[0] if len(latest_historical) > 0 else None
                
                for forecast_record in forecast_data:
                    forecast_year = forecast_record['Year']
                    year_comparison = {}
                    
                    for metric in available_metrics:
                        if historical_record is not None and metric in historical_record:
                            hist_val = historical_record[metric]
                            forecast_val = forecast_record.get(metric)
                            
                            if hist_val and forecast_val and hist_val != 0:
                                growth = ((forecast_val - hist_val) / hist_val) * 100
                                year_comparison[metric] = {
                                    "actual": float(hist_val),
                                    "forecast": float(forecast_val),
                                    "growth_pct": round(growth, 2)
                                }
                    
                    if year_comparison:
                        comparison[f"year_{forecast_year}"] = year_comparison
                
                if comparison:
                    response["comparison"] = comparison
            
            response["status"] = "success"
            response["note"] = "For comprehensive forecast analysis and insights, use get_ai_commentary tool"
            return response
        
        
        
        # Tool 10: Compare Banks
        @self.tool(
            name="compare_banks",
            description="Compare multiple banks on specific metrics",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bank tickers to compare"
                },
                "metrics": {
                    "type": "array", 
                    "items": {"type": "string"},
                    "description": "List of metrics to compare",
                    "required": False
                },
                "period": {"type": "string", "description": "Period for comparison", "required": False}
            }
        )
        def compare_banks(tickers: List[str], metrics: List[str] = None, period: str = None) -> Dict:
            """Compare multiple banks"""
            if not metrics:
                metrics = ["ROA", "ROE", "NPL", "NIM", "Loan", "Deposit"]
            
            tickers = [t.upper() for t in tickers]
            
            # Get data
            df = self._load_historical_year()
            
            if period:
                df = df[df['Year'] == int(period)]
            else:
                # Get latest year for each bank
                df = df.sort_values('Year').groupby('TICKER').last()
                df = df.reset_index()
            
            # Filter for requested banks
            df = df[df['TICKER'].isin(tickers)]
            
            if df.empty:
                return {"error": "No data found for comparison", "status": "failed"}
            
            # Select available metrics
            available_metrics = [m for m in metrics if m in df.columns]
            comparison_df = df[['TICKER'] + available_metrics]
            
            # Calculate rankings
            rankings = {}
            for metric in available_metrics:
                if metric in ["NPL", "CIR"]:  # Lower is better
                    rankings[metric] = comparison_df[metric].rank(ascending=True)
                else:  # Higher is better
                    rankings[metric] = comparison_df[metric].rank(ascending=False)
            
            rankings_df = pd.DataFrame(rankings)
            rankings_df['TICKER'] = comparison_df['TICKER'].values
            
            return {
                "comparison": comparison_df.to_dict('records'),
                "rankings": rankings_df.to_dict('records'),
                "metrics_compared": available_metrics,
                "status": "success"
            }
        
        
        # Tool 11: Get Sector Performance
        @self.tool(
            name="get_sector_performance",
            description="Get aggregated performance metrics for a sector",
            parameters={
                "sector": {"type": "string", "description": "Sector name (SOCB, Private_1, Private_2, Private_3, Sector)"},
                "period": {"type": "string", "description": "Period for analysis", "required": False}
            }
        )
        def get_sector_performance(sector: str, period: str = None) -> Dict:
            """Get sector performance"""
            df = self._load_historical_year()
            
            # Filter by sector
            if sector != "Sector":
                # Get banks in this sector
                bank_types = self._load_bank_types()
                sector_banks = bank_types[bank_types['Type'] == sector]['TICKER'].tolist()
                df = df[df['TICKER'].isin(sector_banks)]
            else:
                # Use the pre-aggregated Sector row
                df = df[df['TICKER'] == 'Sector']
            
            if period:
                df = df[df['Year'] == int(period)]
            else:
                df = df[df['Year'] == df['Year'].max()]
            
            if df.empty:
                return {"error": f"No data for sector {sector}", "status": "failed"}
            
            # Key sector metrics
            metrics = ["Total Assets", "Loan", "Deposit", "NPL", "ROA", "ROE", "NIM"]
            available = [m for m in metrics if m in df.columns]
            
            if sector != "Sector" and len(df) > 1:
                # Calculate averages for the sector
                result = {
                    "sector": sector,
                    "banks_count": len(df),
                    "period": period or str(df['Year'].iloc[0]),
                    "metrics": {}
                }
                
                for metric in available:
                    result["metrics"][metric] = {
                        "mean": float(df[metric].mean()),
                        "median": float(df[metric].median()),
                        "min": float(df[metric].min()),
                        "max": float(df[metric].max())
                    }
            else:
                # Return the aggregated data
                result = {
                    "sector": sector,
                    "period": period or str(df['Year'].iloc[0]),
                    "data": df[available].iloc[0].to_dict()
                }
            
            result["status"] = "success"
            return result
        
        # Helper function for single stock performance (internal use)
        def get_stock_performance_single(ticker: str, start_date: str, end_date: str) -> Dict:
            """Get stock price performance for a single ticker"""
            ticker = ticker.upper()
            
            try:
                # Parse dates
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                
                # Calculate days between dates (add some buffer days)
                days_diff = (end_dt - start_dt).days + 30
                
                # TCBS API endpoint
                url = "https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term"
                
                # Calculate timestamps
                from_timestamp = int((end_dt - timedelta(days=days_diff)).timestamp())
                to_timestamp = int((end_dt + timedelta(days=5)).timestamp())  # Add buffer for end date
                
                # API parameters
                params = {
                    "ticker": ticker,
                    "type": "stock",
                    "resolution": "D",
                    "from": str(from_timestamp),
                    "to": str(to_timestamp)
                }
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json"
                }
                
                # Fetch data
                response = requests.get(url, params=params, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if 'data' in data and data['data']:
                    # Convert to DataFrame
                    df = pd.DataFrame(data['data'])
                    
                    # Convert timestamp to datetime
                    if 'tradingDate' in df.columns:
                        if df['tradingDate'].dtype == 'object' and isinstance(df['tradingDate'].iloc[0], str) and 'T' in df['tradingDate'].iloc[0]:
                            df['tradingDate'] = pd.to_datetime(df['tradingDate'])
                        else:
                            df['tradingDate'] = pd.to_datetime(df['tradingDate'], unit='ms')
                    
                    # Convert to date only for comparison
                    df['date'] = df['tradingDate'].dt.date
                    
                    # Sort by date
                    df = df.sort_values('date')
                    
                    # Find closest dates to requested dates
                    start_date_obj = start_dt.date()
                    end_date_obj = end_dt.date()
                    
                    # Get data for start date (or closest available)
                    start_data = df[df['date'] <= start_date_obj].tail(1)
                    if start_data.empty:
                        start_data = df.head(1)  # Use first available if no earlier data
                    
                    # Get data for end date (or closest available)
                    end_data = df[df['date'] <= end_date_obj].tail(1)
                    if end_data.empty:
                        end_data = df.tail(1)  # Use last available if no data up to end date
                    
                    if not start_data.empty and not end_data.empty:
                        start_price = float(start_data.iloc[0]['close'])
                        end_price = float(end_data.iloc[0]['close'])
                        start_actual_date = str(start_data.iloc[0]['date'])
                        end_actual_date = str(end_data.iloc[0]['date'])
                        
                        # Calculate performance
                        if start_price > 0:
                            performance_pct = ((end_price - start_price) / start_price) * 100
                        else:
                            performance_pct = 0
                        
                        return {
                            "ticker": ticker,
                            "start_date": start_actual_date,
                            "start_price": start_price,
                            "end_date": end_actual_date,
                            "end_price": end_price,
                            "performance_pct": round(performance_pct, 2),
                            "status": "success"
                        }
                    else:
                        return {"error": "Insufficient data for the requested date range", "status": "failed"}
                else:
                    return {"error": f"No price data available for {ticker}", "status": "failed"}
                    
            except ValueError as e:
                return {"error": f"Invalid date format. Use YYYY-MM-DD: {str(e)}", "status": "failed"}
            except requests.exceptions.RequestException as e:
                return {"error": f"Error fetching stock data: {str(e)}", "status": "failed"}
            except Exception as e:
                return {"error": f"Unexpected error: {str(e)}", "status": "failed"}
        
        # Tool 7: Get AI Commentary (Universal - handles single or multiple)
        @self.tool(
            name="get_ai_commentary",
            description="Get AI-generated commentary for one or multiple banks",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bank tickers - use [\"VCB\"] for single or [\"Sector\"] for sector analysis"
                },
                "quarter": {"type": "string", "description": "Quarter like 2024-Q3"}
            }
        )
        def get_ai_commentary(tickers, quarter: str) -> Dict:
            """Get AI commentary for one or multiple banks"""
            # Convert single ticker to list for uniform processing
            if isinstance(tickers, str):
                tickers = [tickers]
            
            results = {}
            errors = []
            
            for ticker in tickers:
                ticker = ticker.upper()
                
                if ticker == "SECTOR":
                    # Get sector analysis
                    df = self._load_quarterly_analysis()
                    if df is None:
                        errors.append(f"Quarterly analysis data not available")
                        continue
                    analysis = df[df['QUARTER'] == quarter] if 'QUARTER' in df.columns else pd.DataFrame()
                    
                    if not analysis.empty:
                        results[ticker] = {
                            "type": "sector",
                            "quarter": quarter,
                            "analysis": analysis.iloc[0].to_dict()
                        }
                    else:
                        errors.append(f"No sector analysis for {quarter}")
                else:
                    # Get bank-specific commentary
                    df = self._load_comments()
                    if df is None:
                        errors.append(f"Comments data not available")
                        continue
                    comment = df[(df['TICKER'] == ticker) & (df['QUARTER'] == quarter)]
                    
                    if not comment.empty:
                        results[ticker] = {
                            "type": "bank",
                            "ticker": ticker,
                            "quarter": quarter,
                            "comment": comment.iloc[0]['COMMENT'],
                            "generated_at": str(comment.iloc[0].get('GENERATED_AT', ''))
                        }
                    else:
                        errors.append(f"No commentary for {ticker} in {quarter}")
            
            # Return simplified format for single ticker
            if len(tickers) == 1:
                if len(results) == 1:
                    single_result = list(results.values())[0]
                    single_result["status"] = "success"
                    return single_result
                elif errors:
                    return {"error": errors[0], "status": "failed"}
            
            # Return batch format for multiple tickers
            return {
                "results": results,
                "requested": len(tickers),
                "found": len(results),
                "errors": errors if errors else None,
                "status": "success" if results else "failed"
            }
        
        # Tool 8: Get Valuation Analysis (Universal - handles single or multiple)
        @self.tool(
            name="get_valuation_analysis",
            description="Get valuation analysis with Z-score and percentiles for one or multiple banks",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bank tickers - use [\"VCB\"] for single, [\"VCB\", \"ACB\"] for multiple"
                },
                "metric": {
                    "type": "string", 
                    "description": "Valuation metric",
                    "enum": ["PE", "PB"],
                    "required": False
                }
            }
        )
        def get_valuation_analysis(tickers, metric: str = "PB") -> Dict:
            """Get valuation analysis for one or multiple banks"""
            # Lazy load the large valuation file only when needed
            df = self._load_valuation()
            if df is None:
                return {"error": "Valuation data not available", "status": "failed"}
            
            # Convert single ticker to list for uniform processing
            if isinstance(tickers, str):
                tickers = [tickers]
            
            # df already loaded above
            
            # Map metric names
            metric_map = {
                "PE": "PE_RATIO",
                "PB": "PX_TO_BOOK_RATIO"
            }
            
            col_name = metric_map.get(metric, "PX_TO_BOOK_RATIO")
            
            if col_name not in df.columns:
                return {"error": f"Metric {metric} not found", "status": "failed"}
            
            results = {}
            comparison_data = []
            
            for ticker in tickers:
                ticker = ticker.upper()
                bank_data = df[df['TICKER'] == ticker][col_name].dropna()
                
                if not bank_data.empty:
                    current = bank_data.iloc[-1]
                    mean = bank_data.mean()
                    std = bank_data.std()
                    z_score = (current - mean) / std if std != 0 else 0
                    percentile = stats.percentileofscore(bank_data, current)
                    
                    results[ticker] = {
                        "current_value": float(current),
                        "mean": float(mean),
                        "median": float(bank_data.median()),
                        "std": float(std),
                        "z_score": float(z_score),
                        "percentile_rank": float(percentile),
                        "min": float(bank_data.min()),
                        "max": float(bank_data.max()),
                        "interpretation": "Undervalued" if z_score < -1 else "Overvalued" if z_score > 1 else "Fair valued"
                    }
                    
                    comparison_data.append({
                        "ticker": ticker,
                        "current": float(current),
                        "z_score": float(z_score),
                        "percentile": float(percentile),
                        "interpretation": results[ticker]["interpretation"]
                    })
            
            # Sort by z_score for ranking
            comparison_data = sorted(comparison_data, key=lambda x: x["z_score"])
            
            # Return simplified format for single ticker
            if len(tickers) == 1 and len(results) == 1:
                ticker = tickers[0]
                single_result = results[ticker].copy()
                single_result["ticker"] = ticker
                single_result["metric"] = metric
                single_result["status"] = "success"
                return single_result
            
            # Return batch format for multiple tickers
            return {
                "metric": metric,
                "detailed_results": results,
                "comparison": comparison_data,
                "most_undervalued": comparison_data[0]["ticker"] if comparison_data else None,
                "most_overvalued": comparison_data[-1]["ticker"] if comparison_data else None,
                "requested": len(tickers),
                "found": len(results),
                "status": "success" if results else "failed"
            }
        
        # Tool 9: Get Stock Performance (Universal - handles single or multiple)
        @self.tool(
            name="get_stock_performance",
            description="Get stock price performance between two dates for one or multiple banks",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of stock tickers - use [\"VCB\"] for single, [\"VCB\", \"ACB\"] for multiple"
                },
                "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                "end_date": {"type": "string", "description": "End date in YYYY-MM-DD format"}
            }
        )
        def get_stock_performance(tickers, start_date: str, end_date: str) -> Dict:
            """Get stock performance for one or multiple banks"""
            import concurrent.futures
            
            # Convert single ticker to list for uniform processing
            if isinstance(tickers, str):
                tickers = [tickers]
            
            def fetch_single_stock(ticker):
                """Helper function to fetch single stock data"""
                return ticker, get_stock_performance_single(ticker, start_date, end_date)
            
            results = {}
            performance_comparison = []
            
            # Use ThreadPoolExecutor for parallel API calls
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                # Submit all tasks
                futures = [executor.submit(fetch_single_stock, ticker.upper()) for ticker in tickers]
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(futures):
                    ticker, result = future.result()
                    results[ticker] = result
                    
                    if result.get("status") == "success":
                        performance_comparison.append({
                            "ticker": ticker,
                            "start_price": result["start_price"],
                            "end_price": result["end_price"],
                            "performance_pct": result["performance_pct"]
                        })
            
            # Sort by performance
            performance_comparison = sorted(performance_comparison, 
                                          key=lambda x: x["performance_pct"], 
                                          reverse=True)
            
            # Calculate summary statistics
            if performance_comparison:
                performances = [p["performance_pct"] for p in performance_comparison]
                summary = {
                    "best_performer": performance_comparison[0]["ticker"],
                    "worst_performer": performance_comparison[-1]["ticker"],
                    "average_performance": round(sum(performances) / len(performances), 2),
                    "median_performance": round(sorted(performances)[len(performances)//2], 2)
                }
            else:
                summary = None
            
            # Return simplified format for single ticker
            if len(tickers) == 1 and tickers[0] in results:
                single_result = results[tickers[0]].copy()
                return single_result
            
            # Return batch format for multiple tickers
            return {
                "period": {"start": start_date, "end": end_date},
                "detailed_results": results,
                "ranking": performance_comparison,
                "summary": summary,
                "requested": len(tickers),
                "successful": len(performance_comparison),
                "status": "success" if performance_comparison else "failed"
            }
        
        # Tool 2: Get Bank Information (Universal - handles single or multiple)
        @self.tool(
            name="get_bank_info",
            description="Get bank sector classification for one or multiple banks",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bank tickers - use [\"VCB\"] for single, [\"VCB\", \"ACB\"] for multiple"
                }
            }
        )
        def get_bank_info(tickers) -> Dict:
            """Get sector classification for one or multiple banks"""
            # Convert single ticker to list for uniform processing
            if isinstance(tickers, str):
                tickers = [tickers]
            
            bank_types = self._load_bank_types()
            
            results = {}
            by_sector = {}
            
            for ticker in tickers:
                ticker = ticker.upper()
                bank_info = bank_types[bank_types['TICKER'] == ticker]
                
                if not bank_info.empty:
                    sector = bank_info.iloc[0]['Type']
                    results[ticker] = sector
                    
                    # Group by sector
                    if sector not in by_sector:
                        by_sector[sector] = []
                    by_sector[sector].append(ticker)
            
            # Return simplified format for single ticker
            if len(tickers) == 1:
                if len(results) == 1:
                    ticker = tickers[0]
                    return {
                        "ticker": ticker,
                        "sector": results[ticker],
                        "status": "success"
                    }
                else:
                    return {"error": f"Bank {tickers[0]} not found", "status": "failed"}
            
            # Return batch format for multiple tickers
            return {
                "banks": results,
                "by_sector": by_sector,
                "requested": len(tickers),
                "found": len(results),
                "status": "success" if results else "failed"
            }
        
        # Tool 6: Calculate Growth Metrics (Universal - handles single or multiple)
        @self.tool(
            name="calculate_growth_metrics",
            description="Calculate growth rates and CAGR for metrics for one or multiple banks",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bank tickers - use [\"VCB\"] for single, [\"VCB\", \"ACB\"] for multiple"
                },
                "metric": {"type": "string", "description": "Metric name (e.g., Loan, Deposit)"},
                "periods": {"type": "integer", "description": "Number of periods to analyze", "required": False}
            }
        )
        def calculate_growth_metrics(tickers, metric: str, periods: int = 5) -> Dict:
            """Calculate growth metrics for one or multiple banks"""
            # Convert single ticker to list for uniform processing
            if isinstance(tickers, str):
                tickers = [tickers]
            
            df = self._load_historical_year()
            
            results = {}
            comparison = []
            
            for ticker in tickers:
                ticker = ticker.upper()
                bank_data = df[df['TICKER'] == ticker].sort_values('Year').tail(periods + 1)
                
                if not bank_data.empty and metric in bank_data.columns:
                    values = bank_data[metric].values
                    years = bank_data['Year'].values
                    
                    growth_rates = []
                    for i in range(1, len(values)):
                        if values[i-1] != 0:
                            growth = ((values[i] - values[i-1]) / values[i-1]) * 100
                            growth_rates.append({
                                "year": int(years[i]),
                                "value": float(values[i]),
                                "growth_rate": float(growth)
                            })
                    
                    # Calculate CAGR
                    cagr = None
                    if len(values) >= 2 and values[0] > 0:
                        n_years = len(values) - 1
                        cagr = (pow(values[-1] / values[0], 1/n_years) - 1) * 100
                    
                    avg_growth = np.mean([g["growth_rate"] for g in growth_rates]) if growth_rates else None
                    
                    results[ticker] = {
                        "growth_data": growth_rates,
                        "cagr": cagr,
                        "average_growth": avg_growth,
                        "latest_value": float(values[-1]) if len(values) > 0 else None
                    }
                    
                    if cagr is not None:
                        comparison.append({
                            "ticker": ticker,
                            "cagr": round(cagr, 2),
                            "avg_growth": round(avg_growth, 2) if avg_growth else None,
                            "latest_value": float(values[-1])
                        })
            
            # Sort by CAGR
            comparison = sorted(comparison, key=lambda x: x["cagr"], reverse=True)
            
            # Return simplified format for single ticker
            if len(tickers) == 1 and len(results) == 1:
                ticker = tickers[0]
                single_result = results[ticker].copy()
                single_result["ticker"] = ticker
                single_result["metric"] = metric
                single_result["periods"] = periods
                single_result["status"] = "success"
                return single_result
            
            # Return batch format for multiple tickers
            return {
                "metric": metric,
                "periods": periods,
                "detailed_results": results,
                "ranking": comparison,
                "best_growth": comparison[0]["ticker"] if comparison else None,
                "requested": len(tickers),
                "analyzed": len(results),
                "status": "success" if results else "failed"
            }
    
    def execute_tool(self, tool_name: str, arguments: Dict = None) -> Dict:
        """Execute a tool by name with arguments"""
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}", "status": "failed"}
        
        tool_func = self.tools[tool_name]
        
        # Get the actual function (unwrapped) to inspect parameters
        import inspect
        sig = inspect.signature(tool_func)
        
        # Filter arguments to only include those the function accepts
        filtered_args = {}
        for param_name in sig.parameters:
            if param_name != 'self' and arguments and param_name in arguments:
                filtered_args[param_name] = arguments[param_name]
        
        try:
            result = tool_func(**filtered_args)
            return result
        except Exception as e:
            return {"error": f"Error executing {tool_name}: {str(e)}", "status": "failed"}
    
    def get_openai_tools(self) -> List[Dict]:
        """Get tool schemas for OpenAI"""
        return self.tool_schemas
    
    def get_tool_list(self) -> List[str]:
        """Get list of available tool names"""
        return list(self.tools.keys())


# Helper function to create a singleton instance
_tool_system_instance = None

def get_tool_system() -> BankingToolSystem:
    """Get or create the banking tool system instance"""
    global _tool_system_instance
    if _tool_system_instance is None:
        _tool_system_instance = BankingToolSystem()
    return _tool_system_instance