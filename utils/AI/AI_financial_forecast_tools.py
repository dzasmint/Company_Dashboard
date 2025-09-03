"""
AI financial forecast tools
Extracted from enhanced_ai_assistant.py
Contains financial forecast analysis tools
"""

from typing import Dict, List
import pandas as pd
from datetime import datetime

def register_financial_forecast_tools(tool_system):
    """Register financial forecast analysis tools with the tool system

    Args:
        tool_system: The EnhancedAIToolSystem instance to register tools with
    """
    @tool_system.tool(
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
            df = tool_system._load_quarterly_financial_statements()
            data_type = "quarterly"
        elif period_type == "both":
            # Load both annual and quarterly data
            df_annual = tool_system._load_financial_statements_csv()
            df_quarterly = tool_system._load_quarterly_financial_statements()
            
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
            df = tool_system._load_financial_statements_csv()
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
    
    @tool_system.tool(
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
        period_info = tool_system._parse_period_notation(period)
        if not period_info["year"]:
            return {
                "error": f"Invalid period notation: {period}",
                "example_formats": ["1H25", "2H24", "1Q25", "4Q24"],
                "status": "failed"
            }
        
        year = period_info["year"]
        
        # Check data availability
        availability = tool_system._check_data_availability(ticker, year, [metric])
        
        # Perform calculation based on period type
        if period_info["type"] == "half":
            half_num = period_info["period_num"]
            
            if half_num == 1:  # First half (Q1 + Q2)
                if availability["can_calculate_1H"]:
                    # Sum Q1 and Q2
                    df_q = tool_system._load_quarterly_financial_statements()
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
                    if tool_system.vietnam_stocks_db is not None:
                        collection = tool_system.vietnam_stocks_db['CompanyForecast']
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
                                df_q = tool_system._load_quarterly_financial_statements()
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
                    df_q = tool_system._load_quarterly_financial_statements()
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
                df_q = tool_system._load_quarterly_financial_statements()
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
                    if tool_system.vietnam_stocks_db is not None:
                        collection = tool_system.vietnam_stocks_db['CompanyForecast']
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
                                df_q = tool_system._load_quarterly_financial_statements()
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
    
    @tool_system.tool(
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
        df = tool_system._load_valuation_csv()
        
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
    
    @tool_system.tool(
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
        
        if tool_system.vietnam_stocks_db is None:
            return {"error": "MongoDB not connected", "status": "failed"}
        
        try:
            forecast_collection = tool_system.vietnam_stocks_db['CompanyForecast']
            
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
                comparison = tool_system._compare_valuation_metrics(results)
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
    
    @tool_system.tool(
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
        
        if tool_system.vietnam_stocks_db is None:
            return {"error": "MongoDB not connected", "status": "failed"}
        
        try:
            forecast_collection = tool_system.vietnam_stocks_db['CompanyForecast']
            
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
    
    @tool_system.tool(
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
        
        if tool_system.vietnam_stocks_db is None:
            return {"error": "MongoDB not connected", "status": "failed"}
        
        try:
            forecast_collection = tool_system.vietnam_stocks_db['CompanyForecast']
            
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
    
    @tool_system.tool(
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
    
    @tool_system.tool(
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
            forecast_doc = tool_system.vietnam_stocks_db['CompanyForecast'].find_one({"ticker": ticker}) if tool_system.vietnam_stocks_db is not None else None
            
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
            forecast_doc = tool_system.vietnam_stocks_db['CompanyForecast'].find_one({"ticker": ticker}) if tool_system.vietnam_stocks_db is not None else None
            
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
    
    @tool_system.tool(
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
        
        if tool_system.vietnam_stocks_db is None:
            return {"error": "MongoDB not connected", "status": "failed"}
        
        try:
            forecast_collection = tool_system.vietnam_stocks_db['CompanyForecast']
            
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
    
    @tool_system.tool(
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
            df = tool_system._load_quarterly_financial_statements()
        else:
            df = tool_system._load_financial_statements_csv()

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
    
    @tool_system.tool(
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
        df = tool_system._load_financial_statements_csv()
        
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
        if include_project_margins and tool_system.vietnam_stocks_db:
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
    
    @tool_system.tool(
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
        if tool_system.vietnam_stocks_db is None:
            return {"error": "MongoDB not connected", "status": "failed"}
        
        try:
            collection = tool_system.vietnam_stocks_db['CompanyForecast']
            
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
    
    
    @tool_system.tool(
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
        
        if tool_system.vietnam_stocks_db is None:
            return {"error": "MongoDB not connected", "status": "failed"}
        
        ticker = ticker.upper()
        
        try:
            # Get company forecast
            forecast_collection = tool_system.vietnam_stocks_db['CompanyForecast']
            company_doc = forecast_collection.find_one({'ticker': ticker}, {'_id': 0})
            
            if not company_doc or year not in company_doc.get('forecast_data', {}):
                return {"error": f"No forecast data for {ticker} in {year}", "status": "failed"}
            
            year_data = company_doc['forecast_data'][year]
            company_pnl = year_data.get('pnl', {})
            project_breakdown = year_data.get('project_breakdown', {})
            
            # Get project details from RealEstateProjects
            projects_collection = tool_system.vietnam_stocks_db['RealEstateProjects']
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
    
    @tool_system.tool(
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
        
        if tool_system.vietnam_stocks_db is None:
            return {"error": "MongoDB not connected", "status": "failed"}
        
        ticker = ticker.upper()
        
        try:
            collection = tool_system.vietnam_stocks_db['CompanyForecast']
            
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
                            'npat_growth': tool_system._calculate_growth(
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
    