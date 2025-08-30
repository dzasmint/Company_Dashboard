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
            self.data['historical_year'] = pd.read_parquet(self.data_dir / 'dfsectoryear.parquet')
            self._data_loaded['historical_year'] = True
        return self.data['historical_year']
    
    @lru_cache(maxsize=1)
    def _load_historical_quarter(self):
        """Lazy load historical quarter data"""
        if 'historical_quarter' not in self.data:
            self.data['historical_quarter'] = pd.read_parquet(self.data_dir / 'dfsectorquarter.parquet')
            self._data_loaded['historical_quarter'] = True
        return self.data['historical_quarter']
    
    @lru_cache(maxsize=1)
    def _load_forecast(self):
        """Lazy load forecast data"""
        if 'forecast' not in self.data:
            self.data['forecast'] = pd.read_parquet(self.data_dir / 'dfsectorforecast.parquet')
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
            if (self.data_dir / 'banking_comments.parquet').exists():
                self.data['comments'] = pd.read_parquet(self.data_dir / 'banking_comments.parquet')
                self._data_loaded['comments'] = True
            else:
                return None
        return self.data.get('comments')
    
    @lru_cache(maxsize=1)
    def _load_quarterly_analysis(self):
        """Lazy load quarterly analysis data"""
        if 'quarterly_analysis' not in self.data:
            if (self.data_dir / 'quarterly_analysis_results.parquet').exists():
                self.data['quarterly_analysis'] = pd.read_parquet(self.data_dir / 'quarterly_analysis_results.parquet')
                self._data_loaded['quarterly_analysis'] = True
            else:
                return None
        return self.data.get('quarterly_analysis')
    
    @lru_cache(maxsize=1)
    def _load_valuation(self):
        """Lazy load valuation data - this is a large file (52K lines)"""
        if 'valuation' not in self.data:
            if (self.data_dir / 'Valuation_banking.parquet').exists():
                self.data['valuation'] = pd.read_parquet(self.data_dir / 'Valuation_banking.parquet')
                self._data_loaded['valuation'] = True
            else:
                return None
        return self.data.get('valuation')
    
    @lru_cache(maxsize=1)
    def _load_earnings_quality_quarterly(self):
        """Lazy load quarterly earnings quality data"""
        if 'earnings_quality_quarterly' not in self.data:
            if (self.data_dir / 'earnings_quality_quarterly.parquet').exists():
                self.data['earnings_quality_quarterly'] = pd.read_parquet(self.data_dir / 'earnings_quality_quarterly.parquet')
                self._data_loaded['earnings_quality_quarterly'] = True
            else:
                return None
        return self.data.get('earnings_quality_quarterly')
    
    @lru_cache(maxsize=1)
    def _load_earnings_quality_yearly(self):
        """Lazy load yearly earnings quality data"""
        if 'earnings_quality_yearly' not in self.data:
            if (self.data_dir / 'earnings_quality_yearly.parquet').exists():
                self.data['earnings_quality_yearly'] = pd.read_parquet(self.data_dir / 'earnings_quality_yearly.parquet')
                self._data_loaded['earnings_quality_yearly'] = True
            else:
                return None
        return self.data.get('earnings_quality_yearly')
    
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
        
        
        # Tool 2: List All Banks (Deprecated - merged into get_bank_info)
        # Use get_bank_info() with no parameters instead
        
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
                "period": {"type": "string", "description": "Single period like 2024-Q3, 2024, or YTD format like 2025-YTD", "required": False},
                "periods": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Multiple periods like [\"2025-Q1\", \"2025-Q2\", \"2025-Q3\"] for getting multiple quarters at once",
                    "required": False
                },
                "metric": {
                    "type": "string",
                    "description": "Single metric to query (e.g., 'NIM', 'NPL', 'PBT', 'ROA'). Use this OR metric_group for efficiency.",
                    "required": False
                },
                "metric_group": {
                    "type": "string", 
                    "description": "Metric group: all, profitability, asset_quality, growth. Use metric for single indicators to save cost.",
                    "enum": ["all", "profitability", "asset_quality", "growth"],
                    "required": False
                }
            }
        )
        def query_historical_data(frequency: str, tickers = None, period: str = None, periods = None, metric: str = None, metric_group: str = "all") -> Dict:
            """Query historical data for one or multiple banks"""
            # Check if YTD format is being used - force quarterly if so
            has_ytd = (period and "YTD" in period) or (periods and any("YTD" in str(p) for p in periods if p))
            
            # Determine if quarterly or yearly based on frequency parameter
            # Override to quarterly if YTD is detected
            if has_ytd:
                is_quarterly = True  # Force quarterly for YTD queries
                df = self._load_historical_quarter()
            else:
                is_quarterly = (frequency == "quarterly")
                df = self._load_historical_quarter() if is_quarterly else self._load_historical_year()
            
            # Apply ticker filter if specified
            if tickers:
                if isinstance(tickers, str):
                    tickers = [tickers]
                # Special handling for sector tickers which use mixed case
                processed_tickers = []
                for t in tickers:
                    if t.lower() == 'sector':
                        processed_tickers.append('Sector')
                    elif t.upper() == 'SOCB':
                        processed_tickers.append('SOCB')
                    elif t.upper() in ['PRIVATE_1', 'PRIVATE_2', 'PRIVATE_3']:
                        # Private sectors use underscore format
                        processed_tickers.append(t.title())  # Converts to Private_1, Private_2, etc.
                    else:
                        processed_tickers.append(t.upper())
                df = df[df['TICKER'].isin(processed_tickers)]
            
            # Handle YTD format in period
            if period and "YTD" in period and is_quarterly:
                year = period.split("-")[0]
                # Get current date to determine which quarters to include
                from datetime import datetime
                current_month = datetime.now().month
                current_year = datetime.now().year
                
                # Determine quarters to include based on current date
                if int(year) == current_year:
                    # For current year, only include completed quarters
                    if current_month >= 10:
                        periods = [f"{year}-Q1", f"{year}-Q2", f"{year}-Q3"]
                    elif current_month >= 7:
                        periods = [f"{year}-Q1", f"{year}-Q2"]
                    elif current_month >= 4:
                        periods = [f"{year}-Q1"]
                    else:
                        periods = []  # No completed quarters yet
                else:
                    # For past years, get all available quarters
                    periods = [f"{year}-Q1", f"{year}-Q2", f"{year}-Q3", f"{year}-Q4"]
            
            
            # Handle multiple periods
            if periods and is_quarterly:
                df = df[df['Date_Quarter'].isin(periods)]
            elif period:
                if is_quarterly:
                    df = df[df['Date_Quarter'] == period]
                else:
                    # For yearly, period should be a year number
                    # Skip if it contains YTD (should have been handled above)
                    if "YTD" not in period:
                        df = df[df['Year'] == int(period)]
            
            if df.empty:
                return {"error": "No data found", "status": "failed"}
            
            # Select metrics - single metric takes precedence over metric_group
            if metric:
                # Query single metric for efficiency
                if metric in df.columns:
                    id_cols = ['TICKER', 'Year' if 'Year' in df.columns else 'Date_Quarter']
                    df = df[id_cols + [metric]]
                else:
                    return {"error": f"Metric '{metric}' not found in data", "status": "failed"}
            elif metric_group != "all":
                # Query metric group
                metric_groups = {
                    "profitability": ["ROA", "ROE", "NIM", "CIR", "PBT", "TOI"],
                    "asset_quality": ["NPL", "New NPL", "NPL Coverage ratio", "GROUP 2"],
                    "growth": ["Loan", "Deposit", "Total Assets", "NPATMI", "PBT"]
                }
                metrics = metric_groups.get(metric_group, [])
                available_metrics = [m for m in metrics if m in df.columns]
                if available_metrics:
                    id_cols = ['TICKER', 'Year' if 'Year' in df.columns else 'Date_Quarter']
                    df = df[id_cols + available_metrics]
            
            # Return summary
            result = {
                "records": len(df),
                "data": df.to_dict('records'),  # Return all records, not just head
                "columns": df.columns.tolist(),
                "status": "success"
            }
            
            # Add period information if multiple periods were queried
            if periods:
                result["periods_included"] = periods
            
            return result
        
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
        
        
        # Tool 10 removed - get_sector_performance is now redundant
        # Use query_historical_data with sector tickers instead:
        # - 'Sector' for overall banking sector
        # - 'SOCB' for state-owned banks
        # - 'Private_1', 'Private_2', 'Private_3' for private bank tiers
        
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
        
        # Tool 7: Get Commentary (Universal - handles single or multiple)
        @self.tool(
            name="get_commentary",
            description="Get detailed commentary by analysts for one or multiple banks for fundamental insights",
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
        
        # Tool 2: Get Bank/Sector Information (handles banks, sectors, and component queries)
        @self.tool(
            name="get_bank_sector_info",
            description="Get bank sector information. Can: 1) List all banks by sector (no params), 2) Get sector for specific banks, 3) Get component banks within a sector (pass SOCB, Private_1, Private_2, Private_3, or Sector)",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Bank tickers OR sector names (SOCB, Private_1, etc.) - omit to list all banks by sector",
                    "required": False
                }
            }
        )
        def get_bank_sector_info(tickers=None) -> Dict:
            """Get bank/sector information with component bank queries"""
            bank_types = self._load_bank_types()
            
            # Define known sector names
            sector_names = ['SOCB', 'Private_1', 'Private_2', 'Private_3', 'Sector']
            
            # If no tickers provided, return all banks grouped by sector
            if tickers is None:
                sectors = {}
                for sector in bank_types['Type'].unique():
                    # Get component banks (excluding the sector aggregate ticker itself)
                    all_banks = bank_types[bank_types['Type'] == sector]['TICKER'].tolist()
                    # Filter out the sector aggregate ticker if it exists
                    component_banks = [b for b in all_banks if b not in sector_names]
                    sectors[sector] = component_banks
                
                return {
                    "sectors": sectors,
                    "total_banks": len([b for b in bank_types['TICKER'] if b not in sector_names]),
                    "status": "success"
                }
            
            # Convert single ticker to list for uniform processing
            if isinstance(tickers, str):
                tickers = [tickers]
            
            results = []
            
            for ticker in tickers:
                # Handle case variations for sectors
                if ticker.upper() in [s.upper() for s in sector_names]:
                    # Find the correct case version
                    correct_sector = next((s for s in sector_names if s.upper() == ticker.upper()), ticker)
                    
                    if correct_sector == 'Sector':
                        # Special case: 'Sector' means all banks
                        all_banks = bank_types['TICKER'].tolist()
                        component_banks = [b for b in all_banks if b not in sector_names]
                        results.append({
                            "query": ticker,
                            "type": "sector",
                            "sector_name": "Sector (All Banks)",
                            "component_banks": component_banks,
                            "bank_count": len(component_banks)
                        })
                    else:
                        # Get banks in this specific sector
                        sector_banks = bank_types[bank_types['Type'] == correct_sector]['TICKER'].tolist()
                        # Remove the sector aggregate ticker itself
                        component_banks = [b for b in sector_banks if b != correct_sector]
                        results.append({
                            "query": ticker,
                            "type": "sector",
                            "sector_name": correct_sector,
                            "component_banks": component_banks,
                            "bank_count": len(component_banks)
                        })
                else:
                    # It's a bank ticker - get its sector
                    ticker_upper = ticker.upper()
                    bank_info = bank_types[bank_types['TICKER'] == ticker_upper]
                    
                    if not bank_info.empty:
                        sector = bank_info.iloc[0]['Type']
                        results.append({
                            "query": ticker,
                            "type": "bank",
                            "ticker": ticker_upper,
                            "sector": sector
                        })
                    else:
                        results.append({
                            "query": ticker,
                            "type": "error",
                            "error": f"'{ticker}' not found"
                        })
            
            # Return simplified format for single query
            if len(tickers) == 1 and len(results) == 1:
                result = results[0]
                if result["type"] == "error":
                    return {"error": result["error"], "status": "failed"}
                elif result["type"] == "sector":
                    return {
                        "sector": result["sector_name"],
                        "component_banks": result["component_banks"],
                        "bank_count": result["bank_count"],
                        "status": "success"
                    }
                else:  # bank
                    return {
                        "ticker": result["ticker"],
                        "sector": result["sector"],
                        "status": "success"
                    }
            
            # Return batch format for multiple queries
            return {
                "results": results,
                "requested": len(tickers),
                "successful": len([r for r in results if r["type"] != "error"]),
                "status": "success" if any(r["type"] != "error" for r in results) else "failed"
            }
        
        # Tool 6: Calculate Growth Metrics (Removed - redundant)
        # OpenAI can calculate growth from raw data returned by query_historical_data
        # For pre-calculated growth metrics, use get_earnings_drivers which has QoQ, YoY, T12M impacts
        
        # Tool 10: Get Earnings Drivers
        @self.tool(
            name="get_earnings_drivers",
            description="Get detailed earnings drivers impact analysis showing what's driving profit changes for one or multiple banks. For cost items, positive score means less cost (good), negative means more cost (bad).",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of bank tickers - use [\"VCB\"] for single, [\"VCB\", \"ACB\"] for multiple"
                },
                "period": {
                    "type": "string",
                    "description": "Period in format YYYY-Q# for quarterly (e.g., 2025-Q2) or YYYY for yearly (e.g., 2024)"
                },
                "timeframe": {
                    "type": "string",
                    "description": "Comparison timeframe",
                    "enum": ["QoQ", "YoY", "T12M"],
                    "required": False
                },
                "frequency": {
                    "type": "string",
                    "description": "Data frequency",
                    "enum": ["quarterly", "yearly"],
                    "required": False
                }
            }
        )
        def get_earnings_drivers(tickers, period: str, timeframe: str = "QoQ", frequency: str = "quarterly") -> Dict:
            """Get earnings drivers analysis for one or multiple banks"""
            # Convert single ticker to list for uniform processing
            if isinstance(tickers, str):
                tickers = [tickers]
            
            # Load appropriate data based on frequency
            if frequency == "yearly":
                df = self._load_earnings_quality_yearly()
                period_col = 'Year'
                # Yearly data doesn't have QoQ/YoY/T12M suffixes
                suffix = ""
            else:
                df = self._load_earnings_quality_quarterly()
                period_col = 'Date_Quarter'
                # Map timeframe to column suffix
                suffix_map = {
                    "QoQ": "_QoQ",
                    "YoY": "_YoY", 
                    "T12M": "_T12M"
                }
                suffix = suffix_map.get(timeframe, "_QoQ")
            
            if df is None:
                return {"error": "Earnings quality data not available", "status": "failed"}
            
            results = {}
            
            for ticker in tickers:
                ticker = ticker.upper()
                
                # Filter data for ticker and period
                ticker_data = df[(df['TICKER'] == ticker) & (df[period_col] == period)]
                
                if ticker_data.empty:
                    results[ticker] = {
                        "error": f"No data found for {ticker} in {period}",
                        "status": "failed"
                    }
                    continue
                
                # Extract impact columns based on suffix
                data_row = ticker_data.iloc[0]
                
                # Helper function to get value with suffix
                def get_value(col_base, use_suffix=True):
                    col_name = f"{col_base}{suffix}" if use_suffix and suffix else col_base
                    if col_name in data_row.index:
                        value = data_row[col_name]
                        if pd.notna(value):
                            return float(value)
                    return None
                
                # Extract all impact values (return numeric values directly)
                pbt_growth = get_value('PBT_Growth_%')
                revenue_impact = get_value('Top_Line_Impact')
                cost_impact = get_value('Cost_Cutting_Impact')
                nonrec_impact = get_value('Non_Recurring_Impact')
                nii_impact = get_value('NII_Impact')
                fee_impact = get_value('Fee_Impact')
                opex_impact = get_value('OPEX_Impact')
                provision_impact = get_value('Provision_Impact')
                loan_impact = get_value('Loan_Impact')
                nim_impact = get_value('NIM_Impact')
                total_impact = get_value('Total_Impact')
                
                # Helper to round values for cleaner JSON
                def clean_value(value):
                    if value is None:
                        return None
                    return round(value, 1)
                
                # Create simplified, flat structure
                earnings_analysis = {
                    "ticker": ticker,
                    "period": period,
                    "timeframe": timeframe if frequency == "quarterly" else "YoY",
                    "pbt_growth": clean_value(pbt_growth),
                    "revenue_impact": clean_value(revenue_impact),
                    "cost_impact": clean_value(cost_impact),
                    "non_recurring": clean_value(nonrec_impact),
                    "details": {
                        "nii": clean_value(nii_impact),
                        "loan": clean_value(loan_impact),
                        "nim": clean_value(nim_impact),
                        "fees": clean_value(fee_impact),
                        "opex": clean_value(opex_impact),
                        "provisions": clean_value(provision_impact)
                    },
                    "status": "success"
                }
                
                results[ticker] = earnings_analysis
            
            # Return simplified format for single ticker
            if len(tickers) == 1 and len(results) == 1:
                return results[tickers[0]]
            
            # Return batch format for multiple tickers
            return {
                "period": period,
                "timeframe": timeframe if frequency == "quarterly" else "YoY",
                "frequency": frequency,
                "results": results,
                "requested": len(tickers),
                "successful": sum(1 for r in results.values() if r.get("status") == "success"),
                "status": "success" if any(r.get("status") == "success" for r in results.values()) else "failed"
            }
        
        # Tool 11: Render Chart
        @self.tool(
            name="render_chart",
            description="""Create a chart visualization from processed data. 
            INSTRUCTIONS FOR USE:
            1. ALWAYS gather data first using other tools (get_financial_data, get_valuation_metrics, etc.)
            2. Structure data with clear x-axis labels and y-values
            3. Specify y_format: 'percent' for rates/ratios, 'number' for counts, 'currency' for monetary values
            4. Available chart types: line, bar, scatter, area

            IMPORTANT:
            - Only pass processed, chart-ready data
            - Do NOT include raw data tables in your text response
            """,
            parameters={
                "chart_type": {
                    "type": "string",
                    "enum": ["line", "bar", "scatter", "area"],
                    "description": "Type of chart to render"
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