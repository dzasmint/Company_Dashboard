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
        description="Get historical financial statements from parquet data (2016-current year, quarterly and annual)",
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
                "description": "Historical years to retrieve (2016 to latest available)",
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
                "description": "Specific quarters (e.g., ['2023Q1', '2023Q2', '2023Q3'])",
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
            # Extract year from quarterly DATE (e.g., '2023Q1' -> 2023)
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
        name="get_valuation_analysis",
        description="Get comprehensive valuation analysis including RNAV, P/E, P/B multiples and comparisons. USAGE GUIDANCE: (1) If user asks about specific metrics (e.g., 'What is the P/E?'), display only the requested metrics. (2) If user asks about RNAV, show RNAV metrics and consider using get_rnav_breakdown for detailed project breakdown. (3) If user asks for complete valuation or comparison, display ALL metrics in a formatted table. (4) Always provide analysis based on what you display.",
        parameters={
            "ticker": {
                "type": "string",
                "description": "Company ticker",
                "required": True
            }
        }
    )
    def get_valuation_analysis(ticker: str) -> Dict:
        """Get comprehensive valuation analysis with all key metrics"""
        
        ticker = ticker.upper()
        
        if tool_system.vietnam_stocks_db is None:
            return {"error": "MongoDB not connected", "status": "failed"}
        
        try:
            forecast_collection = tool_system.vietnam_stocks_db['CompanyForecast']
            
            # Get saved forecast with valuation data
            forecast_doc = forecast_collection.find_one({"ticker": ticker})
            
            if not forecast_doc or 'valuation_data' not in forecast_doc:
                return {"error": f"No valuation data for {ticker}", "status": "failed"}
            
            valuation_data = forecast_doc.get('valuation_data', {})
            multiples = valuation_data.get('multiples', {})
            
            # Get current year and next year
            current_year = datetime.now().year
            next_year = current_year + 1
            
            # Extract all required metrics
            current_price = valuation_data.get('current_price', 0)
            rnav_per_share = valuation_data.get('rnav_per_share', 0)
            
            # Calculate RNAV upside
            rnav_upside = ((rnav_per_share / current_price - 1) * 100) if current_price > 0 else 0
            
            # Get all P/E and P/B multiples
            trailing_pe = multiples.get('trailing_PE')
            trailing_pb = multiples.get('trailing_PB')
            current_year_pe = multiples.get(f'{current_year}F_PE')
            current_year_pb = multiples.get(f'{current_year}F_PB')
            next_year_pe = multiples.get(f'{next_year}F_PE')
            next_year_pb = multiples.get(f'{next_year}F_PB')
            mean_pe = multiples.get('mean_PE')
            mean_pb = multiples.get('mean_PB')
            
            # Calculate comparisons vs historical mean
            current_pe_vs_mean = ((current_year_pe / mean_pe - 1) * 100) if current_year_pe and mean_pe else None
            current_pb_vs_mean = ((current_year_pb / mean_pb - 1) * 100) if current_year_pb and mean_pb else None
            next_pe_vs_mean = ((next_year_pe / mean_pe - 1) * 100) if next_year_pe and mean_pe else None
            next_pb_vs_mean = ((next_year_pb / mean_pb - 1) * 100) if next_year_pb and mean_pb else None
            
            # Format the comprehensive result
            result = {
                "ticker": ticker,
                "current_price": round(current_price, 0),
                "rnav_per_share": round(rnav_per_share, 0),
                "rnav_upside_pct": round(rnav_upside, 1),
                "trailing_pe": round(trailing_pe, 1) if trailing_pe else None,
                "trailing_pb": round(trailing_pb, 1) if trailing_pb else None,
                f"current_year_{current_year}_pe": round(current_year_pe, 1) if current_year_pe else None,
                f"current_year_{current_year}_pb": round(current_year_pb, 1) if current_year_pb else None,
                f"next_year_{next_year}_pe": round(next_year_pe, 1) if next_year_pe else None,
                f"next_year_{next_year}_pb": round(next_year_pb, 1) if next_year_pb else None,
                "historical_mean_pe": round(mean_pe, 1) if mean_pe else None,
                "historical_mean_pb": round(mean_pb, 1) if mean_pb else None,
                "current_year_pe_vs_mean_pct": round(current_pe_vs_mean, 1) if current_pe_vs_mean else None,
                "current_year_pb_vs_mean_pct": round(current_pb_vs_mean, 1) if current_pb_vs_mean else None,
                "next_year_pe_vs_mean_pct": round(next_pe_vs_mean, 1) if next_pe_vs_mean else None,
                "next_year_pb_vs_mean_pct": round(next_pb_vs_mean, 1) if next_pb_vs_mean else None,
                "last_updated": forecast_doc.get('last_updated', '').isoformat() if forecast_doc.get('last_updated') else None
            }
            
            return {
                "data": result,
                "status": "success",
                "guidance": {
                    "metrics_available": [
                        "current_price", "rnav_per_share", "rnav_upside_pct",
                        "trailing_pe", "trailing_pb",
                        f"current_year_{current_year}_pe", f"current_year_{current_year}_pb",
                        f"next_year_{next_year}_pe", f"next_year_{next_year}_pb",
                        "historical_mean_pe", "historical_mean_pb",
                        "current_year_pe_vs_mean_pct", "current_year_pb_vs_mean_pct",
                        "next_year_pe_vs_mean_pct", "next_year_pb_vs_mean_pct"
                    ],
                    "display_instruction": "Display metrics based on user's request: specific metrics only if asked, or complete table for full valuation analysis",
                    "rnav_note": "For detailed RNAV breakdown by project, use get_rnav_breakdown tool"
                }
            }
            
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    @tool_system.tool(
        name="get_rnav_breakdown",
        description="Get detailed RNAV breakdown by individual real estate project and balance sheet items. Use this when user wants to see how RNAV is calculated or wants project-level detail. This complements get_valuation_analysis by providing the detailed breakdown.",
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
                elif item_name and item_name.startswith('  '):  # Project items are indented with 2 spaces
                    if include_projects:
                        # Clean up the project name and add to projects list
                        project_item = item.copy()
                        project_item['project_name'] = item_name.strip()  # Add cleaned name
                        projects.append(project_item)
            
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
        name="get_company_total_score",
        description="Score company comprehensively (1-10 scale) based on: 1) RNAV upside (25% weight), 2) Valuation multiples - trailing and forward P/E & P/B (30% weight), 3) 3-year PATMI CAGR growth (25% weight), 4) Financial leverage - debt/equity ratios (20% weight). IMPORTANT: ALWAYS display the FULL breakdown showing: total score, recommendation, and ALL four component scores with their weighted contributions. Show the detailed data for each component so users understand how the score was calculated. Use when user asks for company scoring, rating, or comprehensive evaluation.",
        parameters={
            "ticker": {
                "type": "string",
                "description": "Company ticker to score",
                "required": True
            }
        }
    )
    def get_company_total_score(ticker: str) -> Dict:
        """Score company based on RNAV, multiples, growth, and leverage"""
        
        ticker = ticker.upper()
        current_year = datetime.now().year
        
        # Initialize scoring components (each out of 10, then weighted)
        scores = {
            "rnav_upside": {"score": 0, "weight": 0.25, "data": {}},
            "valuation_multiples": {"score": 0, "weight": 0.30, "data": {}},
            "growth": {"score": 0, "weight": 0.25, "data": {}},
            "leverage": {"score": 0, "weight": 0.20, "data": {}}
        }
        
        # 1. RNAV Upside Score (25% weight)
        try:
            rnav_result = get_rnav_breakdown(ticker)
            if rnav_result.get('status') == 'success' and 'data' in rnav_result:
                data = rnav_result['data']  # Extract the nested data
                rnav_upside = data.get('upside_pct', 0)  # Fixed field name
                
                # Scoring: >50% upside = 10, 0% = 5, <-30% = 1
                if rnav_upside >= 50:
                    scores["rnav_upside"]["score"] = 10
                elif rnav_upside >= 30:
                    scores["rnav_upside"]["score"] = 8 + (rnav_upside - 30) * 0.1  # 30-50% → 8-10
                elif rnav_upside >= 0:
                    scores["rnav_upside"]["score"] = 5 + (rnav_upside / 30) * 3  # 0-30% → 5-8
                elif rnav_upside >= -30:
                    scores["rnav_upside"]["score"] = 1 + ((rnav_upside + 30) / 30) * 4  # -30-0% → 1-5
                else:
                    scores["rnav_upside"]["score"] = 1
                
                scores["rnav_upside"]["data"] = {
                    "rnav_per_share": data.get('rnav_per_share', 0),
                    "current_price": data.get('current_price', 0),
                    "upside_pct": rnav_upside
                }
        except:
            scores["rnav_upside"]["data"]["error"] = "RNAV data not available"
        
        # 2. Valuation Multiples Score (30% weight)
        try:
            val_data = get_valuation_analysis(ticker)
            if val_data.get('status') == 'success' and 'data' in val_data:
                multiples_scores = []
                data = val_data['data']  # Extract the nested data
                
                # Trailing P/E
                trailing_pe = data.get('trailing_pe', 0) or 0
                mean_pe = data.get('historical_mean_pe', 0) or 0  # Fixed field name
                if trailing_pe > 0 and mean_pe > 0:
                    pe_vs_mean = (trailing_pe / mean_pe)
                    if pe_vs_mean <= 0.7:  # 30% below mean
                        multiples_scores.append(10)
                    elif pe_vs_mean <= 1.0:  # Below mean
                        multiples_scores.append(7 + (1.0 - pe_vs_mean) * 10)  # 7-10
                    elif pe_vs_mean <= 1.3:  # Up to 30% above mean
                        multiples_scores.append(4 + (1.3 - pe_vs_mean) * 10)  # 4-7
                    else:
                        multiples_scores.append(max(1, 4 - (pe_vs_mean - 1.3) * 3))  # 1-4
                
                # Trailing P/B
                trailing_pb = data.get('trailing_pb', 0) or 0
                mean_pb = data.get('historical_mean_pb', 0) or 0  # Fixed field name
                if trailing_pb > 0 and mean_pb > 0:
                    pb_vs_mean = (trailing_pb / mean_pb)
                    if pb_vs_mean <= 0.7:
                        multiples_scores.append(10)
                    elif pb_vs_mean <= 1.0:
                        multiples_scores.append(7 + (1.0 - pb_vs_mean) * 10)
                    elif pb_vs_mean <= 1.3:
                        multiples_scores.append(4 + (1.3 - pb_vs_mean) * 10)
                    else:
                        multiples_scores.append(max(1, 4 - (pb_vs_mean - 1.3) * 3))
                
                # Current year P/E - Fixed field name
                current_pe = data.get(f'current_year_{current_year}_pe', 0) or 0
                if current_pe > 0:
                    if current_pe <= 10:
                        multiples_scores.append(10)
                    elif current_pe <= 15:
                        multiples_scores.append(7 + (15 - current_pe) * 0.6)
                    elif current_pe <= 25:
                        multiples_scores.append(4 + (25 - current_pe) * 0.3)
                    else:
                        multiples_scores.append(max(1, 4 - (current_pe - 25) * 0.1))
                
                # Next year P/E - Fixed field name
                next_pe = data.get(f'next_year_{current_year + 1}_pe', 0) or 0
                if next_pe > 0:
                    if next_pe <= 8:
                        multiples_scores.append(10)
                    elif next_pe <= 12:
                        multiples_scores.append(7 + (12 - next_pe) * 0.75)
                    elif next_pe <= 20:
                        multiples_scores.append(4 + (20 - next_pe) * 0.375)
                    else:
                        multiples_scores.append(max(1, 4 - (next_pe - 20) * 0.15))
                
                # Current year P/B - Fixed field name
                current_pb = data.get(f'current_year_{current_year}_pb', 0) or 0
                if current_pb > 0:
                    if current_pb <= 1.0:
                        multiples_scores.append(10)
                    elif current_pb <= 1.5:
                        multiples_scores.append(7 + (1.5 - current_pb) * 6)
                    elif current_pb <= 2.5:
                        multiples_scores.append(4 + (2.5 - current_pb) * 3)
                    else:
                        multiples_scores.append(max(1, 4 - (current_pb - 2.5) * 1))
                
                # Next year P/B - Fixed field name
                next_pb = data.get(f'next_year_{current_year + 1}_pb', 0) or 0
                if next_pb > 0:
                    if next_pb <= 0.8:
                        multiples_scores.append(10)
                    elif next_pb <= 1.2:
                        multiples_scores.append(7 + (1.2 - next_pb) * 7.5)
                    elif next_pb <= 2.0:
                        multiples_scores.append(4 + (2.0 - next_pb) * 3.75)
                    else:
                        multiples_scores.append(max(1, 4 - (next_pb - 2.0) * 1.5))
                
                if multiples_scores:
                    scores["valuation_multiples"]["score"] = sum(multiples_scores) / len(multiples_scores)
                
                scores["valuation_multiples"]["data"] = {
                    "trailing_pe": trailing_pe,
                    "trailing_pb": trailing_pb,
                    "current_year_pe": current_pe,
                    "next_year_pe": next_pe,
                    "current_year_pb": current_pb,
                    "next_year_pb": next_pb,
                    "mean_pe": mean_pe,
                    "mean_pb": mean_pb
                }
        except:
            scores["valuation_multiples"]["data"]["error"] = "Valuation data not available"
        
        # 3. Growth Score - 3-year PATMI CAGR (25% weight)
        try:
            # Get forecast data from MongoDB
            if tool_system.vietnam_stocks_db is not None:
                forecast_doc = tool_system.vietnam_stocks_db['CompanyForecast'].find_one({"ticker": ticker})
                if forecast_doc and 'forecast_data' in forecast_doc:
                    start_year = str(current_year)
                    end_year = str(current_year + 3)
                    
                    start_patmi = forecast_doc['forecast_data'].get(start_year, {}).get('pnl', {}).get('npatmi', 0)
                    end_patmi = forecast_doc['forecast_data'].get(end_year, {}).get('pnl', {}).get('npatmi', 0)
                    
                    if start_patmi > 0 and end_patmi > 0:
                        cagr = ((end_patmi / start_patmi) ** (1/3) - 1) * 100
                        
                        # Scoring: >25% = 10, 15% = 7, 5% = 4, <0% = 1
                        if cagr >= 25:
                            scores["growth"]["score"] = 10
                        elif cagr >= 15:
                            scores["growth"]["score"] = 7 + (cagr - 15) * 0.3
                        elif cagr >= 5:
                            scores["growth"]["score"] = 4 + (cagr - 5) * 0.3
                        elif cagr >= 0:
                            scores["growth"]["score"] = 1 + (cagr / 5) * 3
                        else:
                            scores["growth"]["score"] = max(1, 1 + cagr * 0.05)
                        
                        scores["growth"]["data"] = {
                            "patmi_cagr_3y": round(cagr, 1),
                            "period": f"{current_year}-{current_year + 3}",
                            "start_patmi": round(start_patmi / 1e9, 2),  # Convert to billions
                            "end_patmi": round(end_patmi / 1e9, 2)
                        }
                    else:
                        scores["growth"]["data"]["error"] = "Invalid PATMI values for growth calculation"
                else:
                    scores["growth"]["data"]["error"] = "No forecast data available in MongoDB"
            else:
                scores["growth"]["data"]["error"] = "MongoDB not connected"
        except Exception as e:
            scores["growth"]["data"]["error"] = f"Growth calculation error: {str(e)}"
        
        # 4. Leverage Score (20% weight)
        try:
            # Get balance sheet ratios
            leverage_data = calculate_balance_sheet_ratios(
                ticker=ticker,
                year_start=current_year,
                year_end=current_year,
                ratios=["debt_to_equity", "net_debt_to_equity"]
            )
            
            if leverage_data.get('status') == 'success' and 'data' in leverage_data:
                # Handle nested structure: result['data']['data'][year]
                nested_data = leverage_data['data'].get('data', {})
                year_data = nested_data.get(current_year, {})  # Use int year, not string
                ratios = year_data.get('ratios', {})
                
                debt_to_equity = ratios.get('debt_to_equity', 999)
                net_debt_to_equity = ratios.get('net_debt_to_equity', 999)
                
                leverage_scores = []
                
                # Total Debt to Equity scoring
                if debt_to_equity < 999:
                    if debt_to_equity <= 0.3:
                        leverage_scores.append(10)
                    elif debt_to_equity <= 0.6:
                        leverage_scores.append(8 + (0.6 - debt_to_equity) * 6.67)
                    elif debt_to_equity <= 1.0:
                        leverage_scores.append(5 + (1.0 - debt_to_equity) * 7.5)
                    elif debt_to_equity <= 2.0:
                        leverage_scores.append(2 + (2.0 - debt_to_equity) * 3)
                    else:
                        leverage_scores.append(1)
                
                # Net Debt to Equity scoring
                if net_debt_to_equity < 999:
                    if net_debt_to_equity <= 0:  # Net cash position
                        leverage_scores.append(10)
                    elif net_debt_to_equity <= 0.3:
                        leverage_scores.append(8 + (0.3 - net_debt_to_equity) * 6.67)
                    elif net_debt_to_equity <= 0.8:
                        leverage_scores.append(5 + (0.8 - net_debt_to_equity) * 6)
                    elif net_debt_to_equity <= 1.5:
                        leverage_scores.append(2 + (1.5 - net_debt_to_equity) * 4.29)
                    else:
                        leverage_scores.append(1)
                
                if leverage_scores:
                    scores["leverage"]["score"] = sum(leverage_scores) / len(leverage_scores)
                
                scores["leverage"]["data"] = {
                    "debt_to_equity": round(debt_to_equity, 2),
                    "net_debt_to_equity": round(net_debt_to_equity, 2)
                }
        except:
            scores["leverage"]["data"]["error"] = "Leverage data not available"
        
        # Calculate weighted total score
        total_score = 0
        total_weight = 0
        
        for component, data in scores.items():
            weighted_score = data["score"] * data["weight"]
            total_score += weighted_score
            total_weight += data["weight"] if data["score"] > 0 else 0
        
        # Normalize if not all components available
        if total_weight > 0 and total_weight < 1.0:
            total_score = total_score / total_weight
        
        # Ensure score is between 1 and 10
        total_score = max(1, min(10, total_score))
        
        # Investment recommendation based on score
        if total_score >= 8:
            recommendation = "STRONG BUY"
            recommendation_rationale = "Excellent across all metrics - compelling investment opportunity"
        elif total_score >= 6.5:
            recommendation = "BUY"
            recommendation_rationale = "Attractive valuation with good fundamentals"
        elif total_score >= 5:
            recommendation = "HOLD"
            recommendation_rationale = "Fair valuation, mixed signals"
        elif total_score >= 3.5:
            recommendation = "REDUCE"
            recommendation_rationale = "Below average metrics, consider reducing position"
        else:
            recommendation = "SELL"
            recommendation_rationale = "Poor metrics across multiple factors"
        
        return {
            "ticker": ticker,
            "total_score": round(total_score, 1),
            "recommendation": recommendation,
            "recommendation_rationale": recommendation_rationale,
            "display_instruction": "IMPORTANT: Display ALL components below in a clear table or formatted list",
            "score_breakdown": {
                "rnav_upside": {
                    "score": round(scores["rnav_upside"]["score"], 1),
                    "weight": scores["rnav_upside"]["weight"],
                    "weighted_contribution": round(scores["rnav_upside"]["score"] * scores["rnav_upside"]["weight"], 2),
                    "data": scores["rnav_upside"]["data"]
                },
                "valuation_multiples": {
                    "score": round(scores["valuation_multiples"]["score"], 1),
                    "weight": scores["valuation_multiples"]["weight"],
                    "weighted_contribution": round(scores["valuation_multiples"]["score"] * scores["valuation_multiples"]["weight"], 2),
                    "data": scores["valuation_multiples"]["data"]
                },
                "growth": {
                    "score": round(scores["growth"]["score"], 1),
                    "weight": scores["growth"]["weight"],
                    "weighted_contribution": round(scores["growth"]["score"] * scores["growth"]["weight"], 2),
                    "data": scores["growth"]["data"]
                },
                "leverage": {
                    "score": round(scores["leverage"]["score"], 1),
                    "weight": scores["leverage"]["weight"],
                    "weighted_contribution": round(scores["leverage"]["score"] * scores["leverage"]["weight"], 2),
                    "data": scores["leverage"]["data"]
                }
            },
            "scoring_methodology": {
                "scale": "1-10 (1=worst, 10=best)",
                "components": {
                    "rnav_upside": "25% weight - Based on RNAV per share vs current price",
                    "valuation_multiples": "30% weight - Trailing & forward P/E and P/B ratios",
                    "growth": "25% weight - 3-year PATMI CAGR forecast",
                    "leverage": "20% weight - Debt/Equity and Net Debt/Equity ratios"
                }
            },
            "status": "success"
        }
    
    @tool_system.tool(
        name="calculate_balance_sheet_ratios",
        description="ALWAYS USE THIS TOOL for ANY balance sheet ratios, leverage metrics, debt analysis, liquidity ratios, or solvency questions. Calculates ALL balance sheet and leverage ratios including: current ratio (liquidity), quick ratio, debt/equity, net debt/equity, debt/assets, debt/EBITDA, EBITDA/interest (coverage), assets/equity (leverage multiplier), liabilities/assets. Can analyze trends over time (historical data + forecasts). USE THIS for questions about: leverage, gearing, debt levels, liquidity, solvency, balance sheet strength, financial stability, debt capacity, interest coverage. Supports both annual and quarterly data. For quarterly: use year_start and year_end with period_type='quarterly' to get all quarters in range, OR use quarters parameter for specific quarters.",
        parameters={
            "ticker": {
                "type": "string",
                "description": "Company ticker",
                "required": True
            },
            "year_start": {
                "type": "integer",
                "description": "Start year. For quarterly: 2023 means Q1'23 onwards. For annual: 2023 means full year 2023. Required unless using specific quarters parameter",
                "required": False
            },
            "year_end": {
                "type": "integer",
                "description": "End year. For quarterly: year means through Q4. For annual: returns full year. If not provided, returns single year",
                "required": False
            },
            "period_type": {
                "type": "string",
                "enum": ["annual", "quarterly"],
                "description": "Period type: 'annual' for yearly data, 'quarterly' for quarterly data. When using quarterly with year_start and year_end, returns all quarters in range",
                "required": False
            },
            "quarters": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional: specific quarters to retrieve (e.g., ['2023Q1', '2023Q2']). Use this OR year_start/year_end, not both. Format: YYYYQn",
                "required": False
            },
            "ratios": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific ratios to calculate. Options: 'current_ratio' (liquidity), 'ebitda_interest_coverage' (debt service ability), 'liabilities_to_assets' (leverage %), 'assets_to_equity' (leverage multiplier), 'debt_to_equity' (gearing), 'net_debt_to_equity' (net gearing), 'total_debt' (absolute debt in billions), 'debt_to_ebitda' (debt payback years). LEAVE EMPTY to calculate ALL ratios - recommended for comprehensive analysis.",
                "required": False
            }
        }
    )
    def calculate_balance_sheet_ratios(ticker: str, year_start: int = None, year_end: int = None, 
                                      period_type: str = "annual", quarters: List[str] = None,
                                      ratios: List[str] = None) -> Dict:
        """Calculate balance sheet ratios from both historical and forecast data"""
        
        ticker = ticker.upper()
        
        # Validate inputs
        if quarters is None and year_start is None:
            return {"error": "Either year_start or quarters must be provided", "status": "failed"}
        
        # Define year range only if not using specific quarters
        if quarters is None:
            if year_start is None:
                return {"error": "year_start is required when not using specific quarters", "status": "failed"}
            if year_end is None:
                year_end = year_start
            if year_end < year_start:
                return {"error": "End year must be >= start year", "status": "failed"}
        
        # Define all available ratios if not specified
        if not ratios:
            ratios = ['current_ratio', 'ebitda_interest_coverage', 'liabilities_to_assets', 
                     'assets_to_equity', 'debt_to_equity', 'net_debt_to_equity', 
                     'total_debt', 'debt_to_ebitda']
        
        # Dynamically determine historical cutoff based on available data
        if period_type == "quarterly":
            df_historical = tool_system._load_quarterly_financial_statements()
        else:
            df_historical = tool_system._load_financial_statements_csv()
            
        # Dynamic fallback based on current year
        current_year = datetime.now().year
        historical_cutoff = current_year - 1  # Assume data up to last year by default
        if not df_historical.empty:
            # Get the maximum year available in historical data for this ticker
            df_ticker = df_historical[df_historical['TICKER'] == ticker]
            if not df_ticker.empty:
                if period_type == "quarterly":
                    # For quarterly data, use YEAR column which has integer years
                    # or extract year from DATE column if it contains quarter strings
                    if 'YEAR' in df_ticker.columns:
                        historical_cutoff = int(df_ticker['YEAR'].max())
                    elif 'DATE' in df_ticker.columns:
                        # Extract year from quarter strings like "2024Q1"
                        max_date = df_ticker['DATE'].max()
                        if isinstance(max_date, str) and 'Q' in max_date:
                            historical_cutoff = int(max_date[:4])
                        else:
                            historical_cutoff = int(max_date)
                else:
                    # For annual data, check if we have complete year data
                    # If we only have partial year (e.g., Q2 2025), the last complete year is 2024
                    year_col = 'DATE' if 'DATE' in df_ticker.columns else 'YEAR'
                    max_year = int(df_ticker[year_col].max())
                    
                    # Check if we have quarterly data to determine if current year is complete
                    df_quarterly = tool_system._load_quarterly_financial_statements()
                    if not df_quarterly.empty:
                        df_ticker_q = df_quarterly[df_quarterly['TICKER'] == ticker]
                        if not df_ticker_q.empty and 'DATE' in df_ticker_q.columns:
                            # Check if we have Q4 data for the max year
                            q4_check = f"{max_year}Q4"
                            if q4_check in df_ticker_q['DATE'].values:
                                historical_cutoff = max_year  # Complete year data available
                            else:
                                historical_cutoff = max_year - 1  # Only partial year data
                        else:
                            historical_cutoff = max_year
                    else:
                        historical_cutoff = max_year
        
        current_year = datetime.now().year
        
        # Build the years_requested string based on what was provided
        if quarters:
            years_requested = f"Quarters: {', '.join(quarters)}"
        elif year_start is not None and year_end is not None and year_end != year_start:
            years_requested = f"{year_start}-{year_end}"
        elif year_start is not None:
            years_requested = str(year_start)
        else:
            years_requested = "Not specified"
        
        results = {
            "ticker": ticker,
            "period_type": period_type,
            "years_requested": years_requested,
            "historical_data_cutoff": historical_cutoff,
            "data_sources": {
                "historical": f"CSV data (up to {historical_cutoff})" + (" - quarterly available" if period_type == "quarterly" else ""),
                "forecast": f"MongoDB data ({historical_cutoff + 1} onwards) - annual only"
            },
            "data": {}
        }
        
        # If quarterly periods are specified, process them
        if quarters and period_type == "quarterly":
            for quarter in quarters:
                # Parse quarter like "2023Q1"
                try:
                    year = int(quarter[:4])
                    q_num = quarter[4:]
                    
                    if year <= historical_cutoff:
                        # Get quarterly historical data
                        # The DATE column contains the full quarter string like "YYYYQ#"
                        df_quarter = df_historical[(df_historical['TICKER'] == ticker) & 
                                                  (df_historical['DATE'] == quarter)]
                        
                        if not df_quarter.empty:
                            bs_data = {}
                            for _, row in df_quarter.iterrows():
                                keycode = row.get('KEYCODE', '')
                                value = row.get('VALUE', 0)  # Column name is uppercase
                                _map_historical_keycode(keycode, value, bs_data)
                            
                            results["data"][quarter] = {
                                "period": quarter,
                                "source": "historical_quarterly",
                                "ratios": _calculate_ratios(bs_data, ratios)
                            }
                        else:
                            results["data"][quarter] = {
                                "period": quarter,
                                "error": f"No quarterly data for {quarter}"
                            }
                    else:
                        results["data"][quarter] = {
                            "period": quarter,
                            "error": f"Quarterly data not available for forecast years (>{historical_cutoff})"
                        }
                except (ValueError, IndexError):
                    results["data"][quarter] = {
                        "period": quarter,
                        "error": f"Invalid quarter format: {quarter}"
                    }
        
        # Process annual data or quarterly for year ranges
        elif period_type == "quarterly" and not quarters:
            # Generate all quarters for the year range
            if year_start is None:
                return {"error": "year_start is required when not using specific quarters", "status": "failed"}
            for year in range(year_start, year_end + 1):
                # First, try to get historical quarterly data
                quarters_found = []
                for q in ['Q1', 'Q2', 'Q3', 'Q4']:
                    quarter = f"{year}{q}"
                    # The DATE column contains the full quarter string like "YYYYQ#"
                    df_quarter = df_historical[(df_historical['TICKER'] == ticker) & 
                                              (df_historical['DATE'] == quarter)]
                    
                    if not df_quarter.empty:
                        bs_data = {}
                        for _, row in df_quarter.iterrows():
                            keycode = row.get('KEYCODE', '')
                            value = row.get('VALUE', 0)  # Column name is uppercase
                            _map_historical_keycode(keycode, value, bs_data)
                        
                        results["data"][quarter] = {
                            "period": quarter,
                            "source": "historical_quarterly",
                            "ratios": _calculate_ratios(bs_data, ratios)
                        }
                        quarters_found.append(q)
                    else:
                        # Mark as no historical data (might have forecast annual)
                        results["data"][quarter] = {
                            "period": quarter,
                            "error": f"No quarterly data for {quarter}"
                        }
                
                # For years > historical_cutoff or years with partial quarters, also try to get annual forecast
                # This ensures we show annual forecast even when some historical quarters exist
                if year > historical_cutoff or (year == historical_cutoff and len(quarters_found) < 4):
                    annual_data = _process_forecast_year(ticker, year, ratios, tool_system)
                    if "error" not in annual_data:
                        annual_data["note"] = f"Annual forecast for {year} (historical quarters: {', '.join(quarters_found) if quarters_found else 'none'})"
                        results["data"][str(year)] = annual_data
                    elif year > historical_cutoff:
                        # Only add annual forecast error if beyond historical cutoff
                        results["data"][str(year)] = annual_data
        
        # Process annual data
        else:
            # Load historical data once (outside the loop for efficiency)
            df = df_historical if not df_historical.empty else pd.DataFrame()
            
            if year_start is None:
                return {"error": "year_start is required for annual data", "status": "failed"}
            
            for year in range(year_start, year_end + 1):
                year_str = str(year)
                year_data = {"year": year, "source": None, "ratios": {}}
                
                # Determine data source
                if year <= historical_cutoff:
                    # Get historical data from CSV
                    year_data["source"] = "historical"
                    
                    if not df.empty:
                        # Filter for ticker and year (column is DATE for annual data)
                        year_col = 'DATE' if 'DATE' in df.columns else 'YEAR'
                        df_year = df[(df['TICKER'] == ticker) & (df[year_col] == year)]
                        
                        if not df_year.empty:
                            # Extract balance sheet items from historical data
                            bs_data = {}
                            for _, row in df_year.iterrows():
                                keycode = row.get('KEYCODE', '')
                                value = row.get('VALUE', 0)  # Column name is uppercase
                                
                                # Map historical KEYCODEs to our structure
                                _map_historical_keycode(keycode, value, bs_data)
                            
                            # Calculate ratios for historical data
                            year_data["ratios"] = _calculate_ratios(bs_data, ratios)
                        else:
                            year_data["error"] = f"No historical data for {year}"
                
                else:
                    # Get forecast data from MongoDB
                    year_data["source"] = "forecast"
                    
                    if tool_system.vietnam_stocks_db is None:
                        year_data["error"] = "MongoDB not connected for forecast data"
                    else:
                        try:
                            forecast_collection = tool_system.vietnam_stocks_db['CompanyForecast']
                            forecast_doc = forecast_collection.find_one({"ticker": ticker})
                            
                            if forecast_doc and 'forecast_data' in forecast_doc:
                                if year_str in forecast_doc['forecast_data']:
                                    forecast_year = forecast_doc['forecast_data'][year_str]
                                    bs = forecast_year.get('balance_sheet', {})
                                    pnl = forecast_year.get('pnl', {})
                                    
                                    # Extract forecast balance sheet items
                                    bs_data = {
                                        'current_assets': bs.get('assets', {}).get('current_assets', 0),
                                        'current_liabilities': bs.get('liabilities', {}).get('current_liabilities', 0),
                                        'total_liabilities': bs.get('liabilities', {}).get('total_liabilities', 0),
                                        'total_assets': bs.get('assets', {}).get('total_assets', 0),
                                        'total_equity': bs.get('equity', {}).get('total_equity', 0),
                                        'short_term_debt': bs.get('liabilities', {}).get('short_term_debt', 0),
                                        'long_term_debt': bs.get('liabilities', {}).get('long_term_debt', 0),
                                        'cash': bs.get('assets', {}).get('cash_and_equivalents', 0),
                                        'st_investment': bs.get('assets', {}).get('short_term_investment', 0),
                                        'ebitda': pnl.get('ebitda', 0),
                                        'interest_expense': pnl.get('interest_expense', 0)
                                    }
                                    
                                    # Calculate ratios for forecast data
                                    year_data["ratios"] = _calculate_ratios(bs_data, ratios)
                                else:
                                    year_data["error"] = f"No forecast data for {year}"
                            else:
                                year_data["error"] = f"No forecast document for {ticker}"
                        except Exception as e:
                            year_data["error"] = str(e)
                
                results["data"][year] = year_data
        
        # Add summary statistics if multiple years
        if year_end > year_start:
            results["summary"] = _calculate_ratio_trends(results["data"], ratios)
        
        return {
            "data": results,
            "status": "success"
        }
    
    def _map_historical_keycode(keycode: str, value: float, bs_data: Dict):
        """Helper to map historical KEYCODEs to standardized structure"""
        if keycode == 'Current_Assets':
            bs_data['current_assets'] = value
        elif keycode == 'Current_Liabilities':
            bs_data['current_liabilities'] = value
        elif keycode == 'Total_Liabilities':
            bs_data['total_liabilities'] = value
        elif keycode in ['Total_Assets', 'Total_Asset']:  # Handle both variations
            bs_data['total_assets'] = value
        elif keycode in ['Total_Equity', 'TOTAL_Equity']:  # Handle both variations
            bs_data['total_equity'] = value
        elif keycode in ['Short_term_Debt', 'ST_Debt']:  # Handle both variations
            bs_data['short_term_debt'] = value
        elif keycode in ['Long_term_Debt', 'LT_Debt']:  # Handle both variations
            bs_data['long_term_debt'] = value
        elif keycode in ['Cash_and_Cash_Equivalents', 'Cash']:  # Handle both variations
            if 'cash' not in bs_data:
                bs_data['cash'] = 0
            bs_data['cash'] += value  # Accumulate cash values
        elif keycode == 'Cash_Equivalent':  # Additional cash component
            if 'cash' not in bs_data:
                bs_data['cash'] = 0
            bs_data['cash'] += value  # Add to cash total
        elif keycode in ['Short_term_Investment', 'Short_Investment']:  # Handle both variations
            bs_data['st_investment'] = value
        elif keycode == 'EBITDA':
            bs_data['ebitda'] = value
        elif keycode == 'Interest_Expense':
            bs_data['interest_expense'] = value
    
    def _process_forecast_year(ticker: str, year: int, ratios: List[str], tool_system) -> Dict:
        """Helper to process forecast year data from MongoDB"""
        year_data = {"year": year, "source": "forecast", "ratios": {}}
        
        if tool_system.vietnam_stocks_db is None:
            year_data["error"] = "MongoDB not connected for forecast data"
            return year_data
        
        try:
            forecast_collection = tool_system.vietnam_stocks_db['CompanyForecast']
            forecast_doc = forecast_collection.find_one({"ticker": ticker.upper()})
            
            if forecast_doc and 'forecast_data' in forecast_doc:
                year_str = str(year)
                if year_str in forecast_doc['forecast_data']:
                    forecast_year = forecast_doc['forecast_data'][year_str]
                    bs = forecast_year.get('balance_sheet', {})
                    pnl = forecast_year.get('pnl', {})
                    
                    # Extract forecast balance sheet items
                    bs_data = {
                        'current_assets': bs.get('assets', {}).get('current_assets', 0),
                        'current_liabilities': bs.get('liabilities', {}).get('current_liabilities', 0),
                        'total_liabilities': bs.get('liabilities', {}).get('total_liabilities', 0),
                        'total_assets': bs.get('assets', {}).get('total_assets', 0),
                        'total_equity': bs.get('equity', {}).get('total_equity', 0),
                        'short_term_debt': bs.get('liabilities', {}).get('short_term_debt', 0),
                        'long_term_debt': bs.get('liabilities', {}).get('long_term_debt', 0),
                        'cash': bs.get('assets', {}).get('cash_and_equivalents', 0),
                        'st_investment': bs.get('assets', {}).get('short_term_investment', 0),
                        'ebitda': pnl.get('ebitda', 0),
                        'interest_expense': pnl.get('interest_expense', 0)
                    }
                    
                    # Calculate ratios for forecast data
                    year_data["ratios"] = _calculate_ratios(bs_data, ratios)
                else:
                    year_data["error"] = f"No forecast data for {year}"
            else:
                year_data["error"] = f"No forecast document for {ticker}"
        except Exception as e:
            year_data["error"] = str(e)
        
        return year_data
    
    def _calculate_ratios(bs_data: Dict, ratios: List[str]) -> Dict:
        """Helper function to calculate requested ratios"""
        calculated = {}
        
        # 1. Current Ratio
        if 'current_ratio' in ratios:
            current_assets = bs_data.get('current_assets', 0)
            current_liabilities = bs_data.get('current_liabilities', 0)
            if current_liabilities > 0:
                calculated['current_ratio'] = round(current_assets / current_liabilities, 2)
            else:
                calculated['current_ratio'] = None
        
        # 2. EBITDA/Interest Expense
        if 'ebitda_interest_coverage' in ratios:
            ebitda = bs_data.get('ebitda', 0)
            interest_expense = abs(bs_data.get('interest_expense', 0))
            if interest_expense > 0:
                calculated['ebitda_interest_coverage'] = round(ebitda / interest_expense, 2)
            else:
                calculated['ebitda_interest_coverage'] = "No interest expense"
        
        # 3. Total Liabilities / Total Assets
        if 'liabilities_to_assets' in ratios:
            total_liabilities = bs_data.get('total_liabilities', 0)
            total_assets = bs_data.get('total_assets', 0)
            if total_assets > 0:
                calculated['liabilities_to_assets'] = round(total_liabilities / total_assets, 3)
            else:
                calculated['liabilities_to_assets'] = None
        
        # 4. Total Assets / Total Equity (Equity Multiplier)
        if 'assets_to_equity' in ratios:
            total_assets = bs_data.get('total_assets', 0)
            total_equity = bs_data.get('total_equity', 0)
            if total_equity > 0:
                calculated['assets_to_equity'] = round(total_assets / total_equity, 2)
            else:
                calculated['assets_to_equity'] = None
        
        # 5. Total Debt / Total Equity
        if 'debt_to_equity' in ratios:
            st_debt = bs_data.get('short_term_debt', 0)
            lt_debt = bs_data.get('long_term_debt', 0)
            total_debt = st_debt + lt_debt
            total_equity = bs_data.get('total_equity', 0)
            if total_equity > 0:
                calculated['debt_to_equity'] = round(total_debt / total_equity, 3)
            else:
                calculated['debt_to_equity'] = None
        
        # 6. Net Debt / Total Equity
        if 'net_debt_to_equity' in ratios:
            st_debt = bs_data.get('short_term_debt', 0)
            lt_debt = bs_data.get('long_term_debt', 0)
            cash = bs_data.get('cash', 0)
            st_investment = bs_data.get('st_investment', 0)
            net_debt = st_debt + lt_debt - cash - st_investment
            total_equity = bs_data.get('total_equity', 0)
            if total_equity > 0:
                calculated['net_debt_to_equity'] = round(net_debt / total_equity, 3)
            else:
                calculated['net_debt_to_equity'] = None
        
        # 7. Total Debt (absolute value in billions)
        if 'total_debt' in ratios:
            st_debt = bs_data.get('short_term_debt', 0)
            lt_debt = bs_data.get('long_term_debt', 0)
            total_debt = st_debt + lt_debt
            calculated['total_debt_bn'] = round(total_debt / 1e9, 2)
        
        # 8. Total Debt / EBITDA
        if 'debt_to_ebitda' in ratios:
            st_debt = bs_data.get('short_term_debt', 0)
            lt_debt = bs_data.get('long_term_debt', 0)
            total_debt = st_debt + lt_debt
            ebitda = bs_data.get('ebitda', 0)
            if ebitda > 0:
                calculated['debt_to_ebitda'] = round(total_debt / ebitda, 2)
            else:
                calculated['debt_to_ebitda'] = None
        
        return calculated
    
    def _calculate_ratio_trends(year_data: Dict, ratios: List[str]) -> Dict:
        """Calculate trends and averages for multi-year data"""
        trends = {}
        
        for ratio in ratios:
            values = []
            years = []
            
            for year, data in sorted(year_data.items()):
                if 'ratios' in data and ratio in data['ratios']:
                    value = data['ratios'][ratio]
                    if value is not None and value != "No interest expense":
                        values.append(value)
                        years.append(year)
            
            if values:
                trends[ratio] = {
                    "average": round(sum(values) / len(values), 3),
                    "min": min(values),
                    "max": max(values),
                    "trend": "improving" if len(values) > 1 and values[-1] < values[0] else "deteriorating" if len(values) > 1 and values[-1] > values[0] else "stable"
                }
        
        return trends
    
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
        description="""Get financial forecast data from MongoDB CompanyForecast (forecast years onwards). ALL VALUES ARE IN BILLIONS VND.
        
IMPORTANT TOKEN USAGE:
- Default (2 years, P&L): ~600 tokens
- 1 year all statements: ~800 tokens  
- 3 years all statements: ~1,800 tokens
- All years (avoid): ~5,500 tokens
- With breakdown: +2-3x tokens

BEST PRACTICES:
- Specify 1-3 years explicitly
- Use statement_type='pnl' for income statement only
- Only use include_breakdown=True when user asks for project details""",
        parameters={
            "ticker": {
                "type": "string",
                "description": "Company ticker (available: DXG, KDH, NTL, TAL, TCH)",
                "required": True
            },
            "years": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Forecast years (e.g., ['2025', '2026']). ALWAYS specify 1-3 years. Default: current+next year",
                "required": False
            },
            "statement_type": {
                "type": "string",
                "enum": ["pnl", "balance_sheet", "cash_flow", "all"],
                "description": "Financial statement type. Use 'pnl' for most queries. Default: 'pnl'",
                "required": False
            },
            "include_breakdown": {
                "type": "boolean",
                "description": "Include project-level breakdown (adds significant data). Default: false",
                "required": False
            }
        }
    )
    def get_financial_forecasts(ticker: str, years: List[str] = None, 
                                statement_type: str = "pnl", 
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
            
            # Smart default: If no years specified, use current and next year only
            if years is None:
                import datetime
                current_year = datetime.now().year
                
                # Get historical cutoff dynamically (same logic as in calculate_balance_sheet_ratios)
                historical_cutoff = current_year - 1  # Default: assume data up to last year
                try:
                    # Check if we have any historical data to determine cutoff
                    if available_years:
                        # First available forecast year minus 1 is the historical cutoff
                        first_forecast_year = int(min(available_years))
                        historical_cutoff = first_forecast_year - 1
                except:
                    pass
                
                # Use first two forecast years as default
                forecast_start = historical_cutoff + 1
                years = [str(forecast_start), str(forecast_start + 1)]
            
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
            
            # Add data size warning if response is large
            import json
            response = {
                "ticker": ticker,
                "forecast_data": result_data,
                "available_years": available_years,
                "years_requested": years,
                "statement_type": statement_type,
                "summary": summary,
                "assumptions": forecast_doc.get('assumptions', []),
                "last_updated": forecast_doc.get('last_updated', 'Unknown'),
                "status": "success"
            }
            
            # Check response size and add warning
            try:
                response_size = len(json.dumps(response, default=str))
                if response_size > 12000:  # ~3000 tokens
                    response["data_size_warning"] = f"Large response ({response_size} chars, ~{response_size//4} tokens). Consider using fewer years or specific statement_type."
            except:
                pass
                
            return response
            
        except Exception as e:
            return {"error": str(e), "status": "failed"}
    
    
    @tool_system.tool(
        name="get_forecast_summary",
        description="Get lightweight forecast summary with key metrics only (optimized for low token usage)",
        parameters={
            "ticker": {
                "type": "string",
                "description": "Company ticker (available: DXG, KDH, NTL, TAL, TCH)",
                "required": True
            },
            "years": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Forecast years (e.g., ['2025', '2026']). Default: current+next year",
                "required": False
            }
        }
    )
    def get_forecast_summary(ticker: str, years: List[str] = None) -> Dict:
        """Get lightweight forecast summary with key metrics only"""
        
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
                    "status": "failed"
                }
            
            # Smart default: current and next year
            if years is None:
                # Get available years from forecast data
                available_years = forecast_doc.get('forecast_years', [])
                
                # Determine historical cutoff dynamically
                import datetime
                current_year = datetime.now().year
                historical_cutoff = current_year - 1  # Assume data up to last year by default
                try:
                    if available_years:
                        # First available forecast year minus 1 is the historical cutoff
                        first_forecast_year = int(min(available_years))
                        historical_cutoff = first_forecast_year - 1
                except:
                    pass
                
                # Use first two forecast years as default
                forecast_start = historical_cutoff + 1
                years = [str(forecast_start), str(forecast_start + 1)]
            
            forecast_data = forecast_doc.get('forecast_data', {})
            
            # Extract only key metrics
            summary_data = {}
            for year in years:
                if year in forecast_data:
                    year_data = forecast_data[year]
                    
                    # Key P&L metrics (handle nested structure)
                    pnl = year_data.get('pnl', {})
                    
                    # Key balance sheet metrics (handle nested structure)
                    bs = year_data.get('balance_sheet', {})
                    assets = bs.get('assets', {}) if isinstance(bs.get('assets'), dict) else {}
                    liabilities = bs.get('liabilities', {}) if isinstance(bs.get('liabilities'), dict) else {}
                    equity = bs.get('equity', {}) if isinstance(bs.get('equity'), dict) else {}
                    
                    # Extract values with proper error handling
                    revenue = pnl.get('net_revenue', 0) if isinstance(pnl, dict) else 0
                    gross_profit = pnl.get('gross_profit', 0) if isinstance(pnl, dict) else 0
                    ebitda = pnl.get('ebitda', 0) if isinstance(pnl, dict) else 0
                    npatmi = pnl.get('npatmi', 0) if isinstance(pnl, dict) else 0
                    total_assets = assets.get('total_assets', 0)
                    total_equity = equity.get('total_equity', 0)
                    net_debt_value = bs.get('net_debt', 0) if isinstance(bs, dict) else 0
                    
                    summary_data[year] = {
                        "revenue": round(revenue / 1e9, 1) if revenue else 0,
                        "gross_profit": round(gross_profit / 1e9, 1) if gross_profit else 0,
                        "ebitda": round(ebitda / 1e9, 1) if ebitda else 0,
                        "npatmi": round(npatmi / 1e9, 1) if npatmi else 0,
                        "gross_margin": round(gross_profit / revenue * 100, 1) if revenue > 0 else 0,
                        "net_margin": round(npatmi / revenue * 100, 1) if revenue > 0 else 0,
                        "total_assets": round(total_assets / 1e9, 1) if total_assets else 0,
                        "total_equity": round(total_equity / 1e9, 1) if total_equity else 0,
                        "net_debt": round(net_debt_value / 1e9, 1),
                        "roe": round(npatmi / total_equity * 100, 1) if total_equity > 0 else 0
                    }
            
            # Calculate growth rates if multiple years
            growth_metrics = {}
            if len(years) >= 2 and all(y in summary_data for y in years[:2]):
                y1, y2 = years[0], years[1]
                for metric in ['revenue', 'npatmi']:
                    val1 = summary_data[y1].get(metric, 0)
                    val2 = summary_data[y2].get(metric, 0)
                    if val1 > 0:
                        growth = ((val2 / val1) - 1) * 100
                        growth_metrics[f"{metric}_growth_{y1}_{y2}"] = round(growth, 1)
            
            return {
                "ticker": ticker,
                "years": years,
                "summary": summary_data,
                "growth_rates": growth_metrics,
                "units": "billions VND",
                "status": "success",
                "token_efficient": True,
                "note": "This is a lightweight summary. Use get_financial_forecasts for detailed data."
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
    