"""
Enhanced AI Assistant - Comprehensive MCP Framework for Financial Analysis
Integrates all data sources: CSV files, MongoDB collections, and AI services
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Callable, Tuple
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

# Import utilities
from .mongodb_utils import (
    init_mongodb_connection,
    load_projects_data,
    get_company_assumptions,
    save_project_to_mongodb
)
from .perplexity_utils import get_project_basic_info_perplexity

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
        """Load financial statements from parquet"""
        if 'financial_csv' not in self.data:
            fa_path = self.data_dir / 'FA_A_processed.parquet'
            if fa_path.exists():
                self.data['financial_csv'] = pd.read_parquet(fa_path)
                self._data_loaded['financial_csv'] = True
            else:
                return pd.DataFrame()
        return self.data.get('financial_csv', pd.DataFrame())
    
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
        self._register_market_tools()
        self._register_portfolio_tools()
        self._register_ai_tools()
    
    def _register_financial_tools(self):
        """Register company financial analysis tools"""
        
        @self.tool(
            name="get_historical_financials",
            description="Get historical financial statements from CSV data (2016-2024)",
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
                }
            }
        )
        def get_historical_financials(tickers: List[str], metrics: List[str] = None, 
                                     years: List[int] = None) -> Dict:
            """Get historical financial statements from CSV data only"""
            
            # Normalize tickers
            tickers = [t.upper() for t in tickers]
            
            # Load CSV data
            df = self._load_financial_statements_csv()
            
            if df.empty:
                return {"error": "Historical financial data not available", "status": "failed"}
            
            # Filter by tickers
            df = df[df['TICKER'].isin(tickers)]
            
            if df.empty:
                return {
                    "error": f"No data found for tickers: {tickers}",
                    "status": "failed"
                }
            
            # Filter by years if specified
            if years:
                df = df[df['DATE'].isin(years)]
            
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
                    'npat_margin': 'NPAT_Margin'
                }
                
                mapped_metrics = []
                for m in metrics:
                    mapped = metric_mapping.get(m.lower(), m)
                    mapped_metrics.append(mapped)
                
                df = df[df['KEYCODE'].isin(mapped_metrics)]
            
            # Pivot data for better readability
            if not df.empty and len(df['KEYCODE'].unique()) > 1:
                pivot_df = df.pivot_table(
                    index=['TICKER', 'DATE'],
                    columns='KEYCODE',
                    values='VALUE',
                    aggfunc='first'
                ).reset_index()
                
                return {
                    "data": pivot_df.to_dict('records'),
                    "source": "historical_csv",
                    "records": len(pivot_df),
                    "years_range": f"{df['DATE'].min()}-{df['DATE'].max()}",
                    "status": "success"
                }
            else:
                return {
                    "data": df.to_dict('records'),
                    "source": "historical_csv",
                    "records": len(df),
                    "years_range": f"{df['DATE'].min()}-{df['DATE'].max()}" if not df.empty else "N/A",
                    "status": "success"
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
            name="analyze_financial_trends",
            description="Analyze financial trends and calculate growth rates",
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
                    "enum": ["yoy", "cagr", "qoq"],
                    "description": "Type of growth calculation",
                    "required": False
                }
            }
        )
        def analyze_financial_trends(ticker: str, metrics: List[str] = None,
                                    period_type: str = "yoy") -> Dict:
            """Analyze financial trends"""
            
            ticker = ticker.upper()
            
            # Load financial data
            df = self._load_financial_statements_csv()
            
            if df.empty:
                return {"error": "Financial data not available", "status": "failed"}
            
            # Filter by ticker
            df = df[df['TICKER'] == ticker]
            
            # Default metrics if not specified
            if not metrics:
                metrics = ['Net_Revenue', 'EBITDA', 'NPATMI']
            
            trends = {}
            
            for metric in metrics:
                metric_df = df[df['KEYCODE'] == metric].sort_values('DATE')
                
                if not metric_df.empty:
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
                "status": "success"
            }
        
        @self.tool(
            name="compare_companies",
            description="Compare financial metrics across multiple companies",
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
                }
            }
        )
        def compare_companies(tickers: List[str], metrics: List[str] = None,
                            year: int = None) -> Dict:
            """Compare companies on financial metrics"""
            
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
                
                return {
                    "comparison": comparison_df.to_dict('records'),
                    "year": year,
                    "metrics": metrics,
                    "status": "success"
                }
            
            return {
                "error": "No data found for comparison",
                "status": "failed"
            }
        
        @self.tool(
            name="get_financial_forecasts",
            description="Get financial forecast data from MongoDB CompanyForecast (2025-2030+)",
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
                
                # Filter by statement type
                result_data = {}
                for year, year_data in forecast_data.items():
                    if statement_type == "all":
                        result_data[year] = {
                            'pnl': year_data.get('pnl', {}),
                            'balance_sheet': year_data.get('balance_sheet', {}),
                            'cash_flow': year_data.get('cash_flow', {})
                        }
                    else:
                        result_data[year] = {statement_type: year_data.get(statement_type, {})}
                    
                    # Add project breakdown if requested (includes PAT/PATMI now)
                    if include_breakdown and 'project_breakdown' in year_data:
                        result_data[year]['project_breakdown'] = year_data['project_breakdown']
                        
                        # Add profitability metrics if available
                        if 'profitability_metrics' in year_data:
                            result_data[year]['profitability_metrics'] = year_data['profitability_metrics']
                
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
            description="Get detailed information about specific projects",
            parameters={
                "project_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Project names to retrieve",
                    "required": True
                },
                "include_financials": {
                    "type": "boolean",
                    "description": "Include financial projections",
                    "required": False
                }
            }
        )
        def get_project_details(project_names: List[str], include_financials: bool = True) -> Dict:
            """Get detailed project information"""
            
            df = self._load_real_estate_projects()
            
            if df.empty:
                return {"error": "No projects data available", "status": "failed"}
            
            # Filter projects (case-insensitive)
            mask = df['project_name'].str.lower().isin([p.lower() for p in project_names])
            projects_df = df[mask]
            
            if projects_df.empty:
                return {"error": f"Projects not found: {project_names}", "status": "failed"}
            
            # Select columns based on request
            if include_financials:
                # Include all financial columns
                cols = projects_df.columns.tolist()
            else:
                # Basic info only (including RNAV)
                cols = ['project_name', 'company_ticker', 'location', 'total_units',
                       'net_sellable_area', 'average_selling_price', 'rnav_value',
                       'construction_start_year', 'project_completion_year']
                # Filter cols to only include those that exist
                cols = [c for c in cols if c in projects_df.columns]
            
            projects_data = projects_df[cols].to_dict('records')
            
            return {
                "projects": projects_data,
                "count": len(projects_data),
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
            df_sorted = df_clean.sort_values(column, ascending=False).head(top_n)
            
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
            name="get_project_financial_statements",
            description="Get detailed financial statements for real estate projects including cash flows and debt schedules",
            parameters={
                "project_name": {
                    "type": "string",
                    "description": "Project name to retrieve financial statements for",
                    "required": True
                },
                "statement_type": {
                    "type": "string",
                    "description": "Type of statement (comprehensive, summary, cash_collection, presales)",
                    "required": False
                }
            }
        )
        def get_project_financial_statements(project_name: str, statement_type: str = "comprehensive") -> Dict:
            """Get project financial statements from MongoDB"""
            
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            try:
                collection = self.vietnam_stocks_db['RealEstateProjects']
                
                # Find project
                project = collection.find_one({"project_name": {"$regex": f"^{project_name}$", "$options": "i"}})
                
                if not project:
                    return {"error": f"Project {project_name} not found", "status": "failed"}
                
                result = {
                    "project_name": project['project_name'],
                    "company_ticker": project['company_ticker'],
                    "rnav_value": project.get('rnav_value'),
                    "status": "success"
                }
                
                # Return requested statement type
                if statement_type == "comprehensive" and 'comprehensive_financial_statements' in project:
                    result["financial_statements"] = project['comprehensive_financial_statements']
                    result["years"] = list(project['comprehensive_financial_statements'].keys())
                elif statement_type == "summary" and 'financial_statements_summary' in project:
                    result["summary"] = project['financial_statements_summary']
                elif statement_type == "cash_collection" and 'cash_collection_schedules' in project:
                    result["cash_collection"] = project['cash_collection_schedules']
                elif statement_type == "presales":
                    result["presales"] = {}
                    if 'low_rise_presales_distribution' in project:
                        result["presales"]["low_rise"] = project['low_rise_presales_distribution']
                    if 'high_rise_presales_distribution' in project:
                        result["presales"]["high_rise"] = project['high_rise_presales_distribution']
                else:
                    # Return all available financial data
                    result["available_data"] = []
                    if 'comprehensive_financial_statements' in project:
                        result["available_data"].append("comprehensive_financial_statements")
                    if 'financial_statements_summary' in project:
                        result["available_data"].append("financial_statements_summary")
                    if 'cash_collection_schedules' in project:
                        result["available_data"].append("cash_collection_schedules")
                    if 'presales_distribution' in project:
                        result["available_data"].append("presales_distribution")
                
                return result
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
        @self.tool(
            name="analyze_company_forecast_assumptions",
            description="Get forecast assumptions and methodology for company financial projections",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker",
                    "required": True
                }
            }
        )
        def analyze_company_forecast_assumptions(ticker: str) -> Dict:
            """Get forecast assumptions from CompanyForecast collection"""
            
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            ticker = ticker.upper()
            
            try:
                collection = self.vietnam_stocks_db['CompanyForecast']
                
                # Get forecast document
                doc = collection.find_one({"ticker": ticker})
                
                if not doc:
                    return {"error": f"No forecast data for {ticker}", "status": "failed"}
                
                result = {
                    "ticker": ticker,
                    "forecast_years": doc.get('forecast_years', []),
                    "last_updated": doc.get('last_updated'),
                    "status": "success"
                }
                
                # Add assumptions if available
                if 'assumptions' in doc:
                    result["assumptions"] = doc['assumptions']
                    result["assumptions_count"] = len(doc['assumptions'])
                
                if 'assumptions_updated' in doc:
                    result["assumptions_updated"] = doc['assumptions_updated']
                
                # Analyze growth rates from forecast data
                if 'forecast_data' in doc and len(doc['forecast_data']) > 1:
                    years = sorted(doc['forecast_data'].keys())
                    if len(years) >= 2:
                        first_year = years[0]
                        last_year = years[-1]
                        
                        # Calculate revenue CAGR if available
                        if (first_year in doc['forecast_data'] and last_year in doc['forecast_data']):
                            first_data = doc['forecast_data'][first_year]
                            last_data = doc['forecast_data'][last_year]
                            
                            if 'pnl' in first_data and 'pnl' in last_data:
                                first_rev = first_data['pnl'].get('net_revenue', 0)
                                last_rev = last_data['pnl'].get('net_revenue', 0)
                                
                                if first_rev > 0 and last_rev > 0:
                                    years_diff = int(last_year) - int(first_year)
                                    cagr = ((last_rev / first_rev) ** (1 / years_diff) - 1) * 100
                                    result["revenue_cagr"] = f"{cagr:.1f}%"
                                    result["revenue_growth"] = {
                                        "from": f"{first_rev:,.0f}B VND",
                                        "to": f"{last_rev:,.0f}B VND",
                                        "period": f"{first_year}-{last_year}"
                                    }
                
                return result
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
    
        # New profitability analysis tools
        @self.tool(
            name="get_project_profitability_details",
            description="Get detailed PAT and PATMI data for real estate projects from RealEstateProjects collection",
            parameters={
                "project_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of project names to analyze",
                    "required": True
                },
                "years": {
                    "type": "array", 
                    "items": {"type": "string"},
                    "description": "Years to retrieve (e.g., ['2025', '2026'])",
                    "required": False
                },
                "include_ownership": {
                    "type": "boolean",
                    "description": "Include ownership and minority interest details",
                    "required": False
                }
            }
        )
        def get_project_profitability_details(project_names: List[str], years: List[str] = None, 
                                             include_ownership: bool = True) -> Dict:
            """Get detailed profitability from RealEstateProjects comprehensive_financial_statements"""
            
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            try:
                collection = self.vietnam_stocks_db['RealEstateProjects']
                results = []
                
                for project_name in project_names:
                    project = collection.find_one(
                        {"project_name": {"$regex": f"^{project_name}$", "$options": "i"}},
                        {'_id': 0}
                    )
                    
                    if not project:
                        continue
                    
                    project_data = {
                        "project_name": project['project_name'],
                        "company_ticker": project.get('company_ticker'),
                        "ownership": project.get('project_ownership', 1.0),
                        "profitability": {}
                    }
                    
                    # Extract from comprehensive_financial_statements
                    if 'comprehensive_financial_statements' in project:
                        statements = project['comprehensive_financial_statements']
                        
                        for year_str, year_data in statements.items():
                            if years and year_str not in years:
                                continue
                                
                            project_data['profitability'][year_str] = {
                                'revenue': year_data.get('revenue_recognition', 0) / 1e9,
                                'pbt': year_data.get('pbt', 0) / 1e9,
                                'pat': year_data.get('pat', 0) / 1e9,
                                'tax': year_data.get('tax', 0) / 1e9
                            }
                            
                            # Calculate PATMI if ownership is provided
                            if include_ownership:
                                pat = year_data.get('pat', 0) / 1e9
                                ownership = project.get('project_ownership', 1.0)
                                minority_interest = pat * (1 - ownership) if pat > 0 else 0
                                patmi = pat - minority_interest
                                
                                project_data['profitability'][year_str].update({
                                    'minority_interest': minority_interest,
                                    'patmi': patmi,
                                    'pat_margin': (pat / (year_data.get('revenue_recognition', 1) / 1e9) * 100) if year_data.get('revenue_recognition', 0) > 0 else 0,
                                    'patmi_margin': (patmi / (year_data.get('revenue_recognition', 1) / 1e9) * 100) if year_data.get('revenue_recognition', 0) > 0 else 0
                                })
                    
                    # Add RNAV if available
                    if 'rnav_value' in project:
                        project_data['rnav_value'] = project['rnav_value'] / 1e9
                    
                    results.append(project_data)
                
                return {
                    "projects": results,
                    "count": len(results),
                    "source": "RealEstateProjects",
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
        @self.tool(
            name="compare_project_vs_company_profitability", 
            description="Compare project-level profitability with company-level aggregated data",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker to analyze",
                    "required": True
                },
                "year": {
                    "type": "string",
                    "description": "Year to compare (e.g., '2025')",
                    "required": True
                }
            }
        )
        def compare_project_vs_company_profitability(ticker: str, year: str) -> Dict:
            """Compare individual project PAT/PATMI with company totals"""
            
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
                
                comparison = {
                    "ticker": ticker,
                    "year": year,
                    "company_level": {
                        "total_revenue": company_pnl.get('net_revenue', 0) / 1e9,
                        "total_pat": company_pnl.get('pat', 0) / 1e9,
                        "total_patmi": company_pnl.get('npatmi', 0) / 1e9,
                        "minority_interest": company_pnl.get('minority_interest', 0) / 1e9
                    },
                    "project_breakdown": {},
                    "variance_analysis": {}
                }
                
                # Add project-level data
                total_project_pat = 0
                total_project_patmi = 0
                
                if 'pat' in project_breakdown:
                    for project_name, pat_value in project_breakdown['pat'].items():
                        pat_billions = pat_value / 1e9
                        patmi_billions = project_breakdown.get('patmi', {}).get(project_name, 0) / 1e9
                        
                        comparison['project_breakdown'][project_name] = {
                            'pat': pat_billions,
                            'patmi': patmi_billions,
                            'pat_contribution': (pat_billions / comparison['company_level']['total_pat'] * 100) if comparison['company_level']['total_pat'] != 0 else 0
                        }
                        
                        total_project_pat += pat_billions
                        total_project_patmi += patmi_billions
                
                # Calculate variance
                comparison['variance_analysis'] = {
                    'projects_total_pat': total_project_pat,
                    'projects_total_patmi': total_project_patmi,
                    'other_business_pat': comparison['company_level']['total_pat'] - total_project_pat,
                    'other_business_patmi': comparison['company_level']['total_patmi'] - total_project_patmi,
                    'projects_contribution_pct': (total_project_pat / comparison['company_level']['total_pat'] * 100) if comparison['company_level']['total_pat'] != 0 else 0
                }
                
                return {
                    "comparison": comparison,
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
                
        @self.tool(
            name="analyze_minority_interest_impact",
            description="Analyze minority interest impact on profitability",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker",
                    "required": True
                },
                "year": {
                    "type": "string", 
                    "description": "Year to analyze",
                    "required": False
                }
            }
        )
        def analyze_minority_interest_impact(ticker: str, year: str = None) -> Dict:
            """Analyze minority interest impact on PAT to PATMI conversion"""
            
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            ticker = ticker.upper()
            
            try:
                # Get projects with ownership data
                projects_collection = self.vietnam_stocks_db['RealEstateProjects']
                projects = list(projects_collection.find({'company_ticker': ticker}, {'_id': 0}))
                
                analysis = {
                    "ticker": ticker,
                    "projects_with_minority": [],
                    "ownership_summary": {},
                    "minority_impact": {}
                }
                
                for project in projects:
                    ownership = project.get('project_ownership', 1.0)
                    
                    if ownership < 1.0:
                        project_analysis = {
                            "project_name": project['project_name'],
                            "ownership": ownership * 100,
                            "minority_stake": (1 - ownership) * 100
                        }
                        
                        # Get PAT data if year specified
                        if year and 'comprehensive_financial_statements' in project:
                            if year in project['comprehensive_financial_statements']:
                                year_data = project['comprehensive_financial_statements'][year]
                                pat = year_data.get('pat', 0) / 1e9
                                minority_interest = pat * (1 - ownership) if pat > 0 else 0
                                
                                project_analysis.update({
                                    'pat': pat,
                                    'minority_interest': minority_interest,
                                    'patmi': pat - minority_interest,
                                    'dilution_pct': (minority_interest / pat * 100) if pat > 0 else 0
                                })
                        
                        analysis['projects_with_minority'].append(project_analysis)
                
                # Summary statistics
                if analysis['projects_with_minority']:
                    avg_ownership = sum(p['ownership'] for p in analysis['projects_with_minority']) / len(analysis['projects_with_minority'])
                    
                    analysis['ownership_summary'] = {
                        'total_projects': len(projects),
                        'projects_with_minority': len(analysis['projects_with_minority']),
                        'average_ownership': avg_ownership,
                        'average_minority_stake': 100 - avg_ownership
                    }
                    
                    if year:
                        total_minority = sum(p.get('minority_interest', 0) for p in analysis['projects_with_minority'])
                        total_pat = sum(p.get('pat', 0) for p in analysis['projects_with_minority'])
                        
                        analysis['minority_impact'][year] = {
                            'total_minority_interest': total_minority,
                            'total_pat': total_pat,
                            'impact_on_pat': (total_minority / total_pat * 100) if total_pat > 0 else 0
                        }
                
                return {
                    "analysis": analysis,
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
        @self.tool(
            name="get_consolidated_profitability_breakdown",
            description="Get waterfall breakdown from Revenue to PATMI from CompanyForecast",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker",
                    "required": True
                },
                "year": {
                    "type": "string",
                    "description": "Year to analyze",
                    "required": True
                },
                "include_project_details": {
                    "type": "boolean",
                    "description": "Include project-level breakdown",
                    "required": False
                }
            }
        )
        def get_consolidated_profitability_breakdown(ticker: str, year: str, 
                                                    include_project_details: bool = True) -> Dict:
            """Get comprehensive profitability waterfall from CompanyForecast"""
            
            if self.vietnam_stocks_db is None:
                return {"error": "MongoDB not connected", "status": "failed"}
            
            ticker = ticker.upper()
            
            try:
                # Get company forecast
                collection = self.vietnam_stocks_db['CompanyForecast']
                company_doc = collection.find_one({'ticker': ticker}, {'_id': 0})
                
                if not company_doc or year not in company_doc.get('forecast_data', {}):
                    return {"error": f"No forecast data for {ticker} in {year}", "status": "failed"}
                
                year_data = company_doc['forecast_data'][year]
                pnl = year_data.get('pnl', {})
                project_breakdown = year_data.get('project_breakdown', {})
                profitability_metrics = year_data.get('profitability_metrics', {})
                
                # Build waterfall
                waterfall = {
                    "ticker": ticker,
                    "year": year,
                    "waterfall": [
                        {"step": "Net Revenue", "value": pnl.get('net_revenue', 0) / 1e9},
                        {"step": "- Total COGS", "value": pnl.get('total_cogs', 0) / 1e9},
                        {"step": "= Gross Profit", "value": pnl.get('gross_profit', 0) / 1e9},
                        {"step": "- SG&A", "value": pnl.get('sga', 0) / 1e9},
                        {"step": "= EBITDA", "value": pnl.get('ebitda', 0) / 1e9},
                        {"step": "- Interest Expense", "value": pnl.get('interest_expense', 0) / 1e9},
                        {"step": "= PBT", "value": pnl.get('pbt', 0) / 1e9},
                        {"step": "- Tax", "value": pnl.get('tax', 0) / 1e9},
                        {"step": "= PAT", "value": pnl.get('pat', 0) / 1e9},
                        {"step": "- Minority Interest", "value": pnl.get('minority_interest', 0) / 1e9},
                        {"step": "= PATMI", "value": pnl.get('npatmi', 0) / 1e9}
                    ],
                    "margins": profitability_metrics.get('consolidated_margins', {})
                }
                
                # Add project breakdown if requested
                if include_project_details and project_breakdown:
                    project_summary = {}
                    
                    # Aggregate by project
                    for metric in ['revenue', 'pat', 'patmi']:
                        if metric in project_breakdown:
                            for project, value in project_breakdown[metric].items():
                                if project not in project_summary:
                                    project_summary[project] = {}
                                project_summary[project][metric] = value / 1e9
                    
                    # Calculate margins for each project
                    for project, metrics in project_summary.items():
                        if metrics.get('revenue', 0) > 0:
                            metrics['pat_margin'] = (metrics.get('pat', 0) / metrics['revenue'] * 100)
                            metrics['patmi_margin'] = (metrics.get('patmi', 0) / metrics['revenue'] * 100)
                    
                    waterfall['project_details'] = project_summary
                    
                    # Add project vs other split
                    total_project_revenue = sum(p.get('revenue', 0) for p in project_summary.values())
                    total_project_pat = sum(p.get('pat', 0) for p in project_summary.values())
                    total_project_patmi = sum(p.get('patmi', 0) for p in project_summary.values())
                    
                    waterfall['business_split'] = {
                        'projects': {
                            'revenue': total_project_revenue,
                            'pat': total_project_pat,
                            'patmi': total_project_patmi,
                            'revenue_contribution': (total_project_revenue / (pnl.get('net_revenue', 1) / 1e9) * 100) if pnl.get('net_revenue', 0) > 0 else 0
                        },
                        'other_business': {
                            'revenue': pnl.get('net_revenue', 0) / 1e9 - total_project_revenue,
                            'pat': pnl.get('pat', 0) / 1e9 - total_project_pat,
                            'patmi': pnl.get('npatmi', 0) / 1e9 - total_project_patmi
                        }
                    }
                
                return {
                    "breakdown": waterfall,
                    "source": "CompanyForecast",
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
    
    def _register_market_tools(self):
        """Register market analysis tools (MoC data)"""
        
        @self.tool(
            name="get_transaction_volumes",
            description="Get real estate transaction volumes from MoC data",
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
                    "description": "Quarters to retrieve (e.g., ['2024-Q1', '2024-Q2'])",
                    "required": False
                }
            }
        )
        def get_transaction_volumes(metric_type: str = None, quarters: List[str] = None) -> Dict:
            """Get transaction volume data"""
            
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
            if quarters:
                query['quarter'] = {"$in": quarters}
            
            # Execute query
            cursor = collection.find(query, {"_id": 0}).sort("date", 1)
            data = list(cursor)
            
            # Calculate QoQ growth
            if data:
                for i in range(1, len(data)):
                    if data[i-1].get('value') and data[i].get('value'):
                        prev_val = data[i-1]['value']
                        curr_val = data[i]['value']
                        if prev_val > 0:
                            data[i]['qoq_growth'] = round((curr_val - prev_val) / prev_val * 100, 2)
            
            return {
                "data": data,
                "metric_type": metric_type,
                "quarters": len(data),
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
            description="Get real estate inventory levels",
            parameters={
                "inventory_type": {
                    "type": "string",
                    "enum": ["apartment", "individual_house", "land", "total"],
                    "description": "Type of inventory",
                    "required": False
                }
            }
        )
        def get_inventory_levels(inventory_type: str = None) -> Dict:
            """Get inventory level data"""
            
            if self.moc_db is None:
                return {"error": "MoC database not available", "status": "failed"}
            
            collection = self.moc_db['inventory']
            
            # Build query
            query = {}
            if inventory_type:
                query['inventory_type'] = inventory_type
            
            # Execute query
            cursor = collection.find(query, {"_id": 0}).sort("date", 1)
            data = list(cursor)
            
            # Get latest values
            latest_by_type = {}
            for record in data:
                inv_type = record.get('inventory_type')
                if inv_type:
                    latest_by_type[inv_type] = record
            
            return {
                "data": data,
                "latest_by_type": latest_by_type,
                "records": len(data),
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
    
    def _register_portfolio_tools(self):
        """Register portfolio and aggregation tools"""
        
        @self.tool(
            name="calculate_portfolio_metrics",
            description="Calculate aggregate metrics across companies or projects",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Companies to include",
                    "required": True
                },
                "metric_type": {
                    "type": "string",
                    "enum": ["financial", "projects", "combined"],
                    "description": "Type of metrics to calculate",
                    "required": False
                }
            }
        )
        def calculate_portfolio_metrics(tickers: List[str], metric_type: str = "combined") -> Dict:
            """Calculate portfolio-level metrics"""
            
            tickers = [t.upper() for t in tickers]
            results = {}
            
            # Financial metrics
            if metric_type in ["financial", "combined"]:
                df = self._load_financial_statements_csv()
                if not df.empty:
                    df = df[df['TICKER'].isin(tickers)]
                    latest_year = df['DATE'].max()
                    df_latest = df[df['DATE'] == latest_year]
                    
                    # Calculate aggregates
                    revenue_df = df_latest[df_latest['KEYCODE'] == 'Net_Revenue']
                    ebitda_df = df_latest[df_latest['KEYCODE'] == 'EBITDA']
                    npat_df = df_latest[df_latest['KEYCODE'] == 'NPATMI']
                    
                    results["financial_aggregates"] = {
                        "total_revenue": revenue_df['VALUE'].sum(),
                        "total_ebitda": ebitda_df['VALUE'].sum(),
                        "total_npat": npat_df['VALUE'].sum(),
                        "year": latest_year,
                        "companies": len(tickers)
                    }
            
            # Project metrics
            if metric_type in ["projects", "combined"]:
                projects_df = self._load_real_estate_projects()
                if not projects_df.empty:
                    projects_df = projects_df[projects_df['company_ticker'].isin(tickers)]
                    
                    results["project_aggregates"] = {
                        "total_projects": len(projects_df),
                        "total_units": projects_df['total_units'].sum(),
                        "total_nsa": projects_df['net_sellable_area'].sum(),
                        "avg_asp": projects_df['average_selling_price'].mean(),
                        "companies": projects_df['company_ticker'].nunique()
                    }
            
            return {
                "portfolio": results,
                "tickers": tickers,
                "metric_type": metric_type,
                "status": "success"
            }
        
        @self.tool(
            name="generate_financial_summary",
            description="Generate comprehensive financial summary for companies",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker",
                    "required": True
                },
                "include_projects": {
                    "type": "boolean",
                    "description": "Include real estate projects",
                    "required": False
                }
            }
        )
        def generate_financial_summary(ticker: str, include_projects: bool = True) -> Dict:
            """Generate comprehensive financial summary"""
            
            ticker = ticker.upper()
            summary = {"ticker": ticker}
            
            # Financial statements summary
            fin_df = self._load_financial_statements_csv()
            if not fin_df.empty:
                ticker_df = fin_df[fin_df['TICKER'] == ticker]
                if not ticker_df.empty:
                    latest_year = ticker_df['DATE'].max()
                    latest_df = ticker_df[ticker_df['DATE'] == latest_year]
                    
                    key_metrics = ['Net_Revenue', 'EBITDA', 'NPATMI', 'Gross_Margin', 
                                 'EBITDA_Margin', 'NPAT_Margin']
                    
                    financials = {}
                    for metric in key_metrics:
                        metric_data = latest_df[latest_df['KEYCODE'] == metric]
                        if not metric_data.empty:
                            financials[metric] = {
                                "value": metric_data.iloc[0]['VALUE'],
                                "yoy": metric_data.iloc[0].get('YoY')
                            }
                    
                    summary["financials"] = {
                        "year": latest_year,
                        "metrics": financials
                    }
            
            # Valuation summary
            val_df = self._load_valuation_csv()
            if not val_df.empty:
                ticker_val = val_df[val_df['TICKER'] == ticker]
                if not ticker_val.empty:
                    latest_val = ticker_val.iloc[-1]
                    summary["valuation"] = {
                        "date": latest_val.get('TRADE_DATE'),
                        "P/E": latest_val.get('P/E'),
                        "P/B": latest_val.get('P/B'),
                        "EV/EBITDA": latest_val.get('EV/EBITDA')
                    }
            
            # Projects summary
            if include_projects:
                projects_df = self._load_real_estate_projects()
                if not projects_df.empty:
                    ticker_projects = projects_df[projects_df['company_ticker'] == ticker]
                    if not ticker_projects.empty:
                        summary["projects"] = {
                            "count": len(ticker_projects),
                            "total_units": ticker_projects['total_units'].sum(),
                            "total_nsa": ticker_projects['net_sellable_area'].sum(),
                            "project_list": ticker_projects['project_name'].tolist()
                        }
            
            summary["status"] = "success"
            return summary
    
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
            
            # Gather data for analysis using the tool
            summary = self.execute_tool('generate_financial_summary', {'ticker': ticker, 'include_projects': True})
            
            if summary.get("status") != "success":
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


class EnhancedAIAssistant:
    """Enhanced AI Assistant with comprehensive data access"""
    
    def __init__(self):
        """Initialize the enhanced assistant"""
        self.tool_system = get_enhanced_tool_system()
        self.anthropic_client = self.tool_system.anthropic_client
    
    def process_query(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process user query using enhanced tool system"""
        try:
            # Classify intent
            intent = self._classify_intent(query)
            
            # Extract entities
            entities = self._extract_entities(query)
            
            # Map to appropriate tool
            tool_name, arguments = self._map_to_tool(intent, entities, context)
            
            # Execute tool
            result = self.tool_system.execute_tool(tool_name, arguments)
            
            # Format response
            formatted_result = self._format_response(result, tool_name, query)
            
            return formatted_result
            
        except Exception as e:
            return {
                'type': 'error',
                'message': f"Error processing query: {str(e)}",
                'error': str(e)
            }
    
    def _classify_intent(self, query: str) -> str:
        """Classify query intent"""
        query_lower = query.lower()
        
        # Financial analysis
        if any(word in query_lower for word in ['financial', 'revenue', 'ebitda', 'profit', 'margin']):
            return 'financial_analysis'
        
        # Project related
        elif any(word in query_lower for word in ['project', 'real estate', 'development']):
            return 'project_analysis'
        
        # Market data
        elif any(word in query_lower for word in ['transaction', 'credit', 'inventory', 'market']):
            return 'market_analysis'
        
        # Comparison
        elif any(word in query_lower for word in ['compare', 'versus', 'vs', 'difference']):
            return 'comparison'
        
        # Ranking
        elif any(word in query_lower for word in ['rank', 'top', 'best', 'highest', 'largest']):
            return 'ranking'
        
        else:
            return 'general'
    
    def _extract_entities(self, query: str) -> Dict:
        """Extract entities from query"""
        entities = {}
        
        # Extract tickers
        ticker_pattern = r'\b([A-Z]{3,4})\b'
        tickers = re.findall(ticker_pattern, query)
        if tickers:
            entities['tickers'] = tickers
        
        # Extract years
        year_pattern = r'\b(20\d{2})\b'
        years = re.findall(year_pattern, query)
        if years:
            entities['years'] = [int(y) for y in years]
        
        # Extract quarters
        quarter_pattern = r'\b(\d{4}-Q[1-4])\b'
        quarters = re.findall(quarter_pattern, query)
        if quarters:
            entities['quarters'] = quarters
        
        return entities
    
    def _map_to_tool(self, intent: str, entities: Dict, context: Dict = None) -> Tuple[str, Dict]:
        """Map intent and entities to appropriate tool"""
        
        # Default arguments from entities
        arguments = entities.copy()
        
        # Add context if available
        if context and context.get('selected_company'):
            if 'tickers' not in arguments:
                arguments['tickers'] = [context['selected_company']]
        
        # Map based on intent
        if intent == 'financial_analysis':
            if 'tickers' in entities:
                return 'get_financial_statements', arguments
            else:
                return 'analyze_financial_trends', arguments
        
        elif intent == 'project_analysis':
            return 'list_real_estate_projects', arguments
        
        elif intent == 'market_analysis':
            return 'analyze_market_trends', arguments
        
        elif intent == 'comparison':
            return 'compare_companies', arguments
        
        elif intent == 'ranking':
            return 'rank_projects_by_metric', {'metric': 'revenue', **arguments}
        
        else:
            # Default to financial summary
            if 'tickers' in entities and len(entities['tickers']) == 1:
                return 'generate_financial_summary', {'ticker': entities['tickers'][0]}
            else:
                return 'get_financial_statements', arguments
    
    def _format_response(self, result: Dict, tool_name: str, query: str) -> Dict:
        """Format tool response for display"""
        if result.get('status') == 'failed':
            return {
                'type': 'error',
                'message': result.get('error', 'Operation failed'),
                'tool': tool_name
            }
        
        # Success response
        return {
            'type': 'success',
            'data': result,
            'tool_used': tool_name,
            'query': query,
            'message': f"Successfully processed using {tool_name}"
        }


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
    Send message to OpenAI and handle tool calls
    Similar to Bank_Sample/7_DucGPT_Chatbot.py implementation
    """
    # Initialize OpenAI client if not exists
    if 'openai_client' not in st.session_state:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            st.session_state.openai_client = OpenAI(api_key=api_key)
        else:
            st.session_state.openai_client = None
    
    if not st.session_state.openai_client:
        return "❌ OpenAI API key not configured. Please set OPENAI_API_KEY in your .env file."
    
    # Prepare messages
    messages = []
    
    # Add system message for real estate and financial analysis
    messages.append({
        "role": "system",
        "content": """You are a comprehensive financial analyst assistant specializing in Vietnamese real estate and financial markets.
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

**Real Estate Project Tools:**
- Basic info: list_real_estate_projects, get_project_details, rank_projects_by_metric
- Financial details: get_project_financial_statements (comprehensive statements, cash flows, presales)
- RNAV valuation: All tools now include rnav_value (Revalued Net Asset Value)
- Available for: KDH, TAL, TCH projects in MongoDB (24 total projects)

**Other Analysis Tools:**
- Forecast assumptions: analyze_company_forecast_assumptions (for DXG, KDH, NTL, TAL, TCH)
- Market data: get_transaction_volumes, analyze_market_trends (MoC data)
- Comparisons: compare_companies, generate_financial_summary

**Data Format Requirements:**
- Tickers must be arrays: ["VHM"] for single, ["VHM", "DXG"] for multiple
- Historical years: integers (2023, 2024)
- Forecast years: strings ("2025", "2026")

**When user asks about:**
- "Current" or "recent" or years ≤2024: use get_historical_financials
- "Future" or "forecast" or years ≥2025: use get_financial_forecasts
- Both historical and forecast: call BOTH tools separately"""
    })
    
    # Add user message
    messages.append({"role": "user", "content": user_message})
    
    # Get tool schemas
    tools = tool_system.get_openai_tools()
    
    # Initialize progress tracking
    max_rounds = 20
    with st.spinner("🤖 AI is analyzing..."):
        rounds = 0
        final_response = None
        tool_call_count = 0
        
        while rounds < max_rounds:
            rounds += 1
            
            # Call OpenAI
            try:
                response = st.session_state.openai_client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview"),
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
                    tool_status.info(f"🔧 Executing tool #{tool_call_count}: **{function_name}**")
                    
                    # Execute the tool
                    tool_result = execute_tool_call(tool_system, function_name, function_args)
                    
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
        
        return final_response


def render_enhanced_ai_interface():
    """Render the enhanced AI interface in Streamlit"""
    
    st.header("🚀 Enhanced AI Assistant")
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
        
        # Clear history
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
    
    # Chat messages container
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