"""
Real Estate AI Tool System - MCP Framework
Modular tool system for OpenAI/Claude to access and analyze real estate project data
Following the MCP (Modular Component Pattern) architecture
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
import anthropic
import streamlit as st

# Import utilities
from .mongodb_utils import (
    MongoDBHelper, 
    load_projects_data,
    get_company_assumptions,
    save_project_to_mongodb
)
from .claude_project_extractor import ClaudeProjectExtractor
from .perplexity_utils import PerplexityProjectResearcher, get_project_basic_info_perplexity

load_dotenv()

class RealEstateToolSystem:
    """
    Modular tool system for real estate analysis
    Following MCP pattern from Banking_MCP.py
    """
    
    def __init__(self, data_dir: Path = None):
        """Initialize the tool system with lazy loading"""
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / "data"
        
        self.data_dir = data_dir
        self.tools = {}
        self.tool_schemas = []
        self.data = {}
        self._data_loaded = {}
        
        # Initialize AI clients lazily
        self.claude_extractor = None
        self.perplexity_researcher = None
        self.mongo_helper = MongoDBHelper()
        self.anthropic_client = None
        
        # Initialize AI services if keys available
        self._init_ai_services()
        
        # Register all tools
        self._register_tools()
    
    def _init_ai_services(self):
        """Initialize AI services with API keys"""
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        perplexity_key = os.getenv('PERPLEXITY_API_KEY')
        
        if anthropic_key:
            self.claude_extractor = ClaudeProjectExtractor(api_key=anthropic_key)
            self.anthropic_client = anthropic.Anthropic(api_key=anthropic_key)
        
        if perplexity_key:
            self.perplexity_researcher = PerplexityProjectResearcher(api_key=perplexity_key)
    
    @lru_cache(maxsize=1)
    def _load_projects_data(self):
        """Lazy load projects data from MongoDB"""
        if 'projects' not in self.data:
            self.data['projects'] = load_projects_data()
            self._data_loaded['projects'] = True
        return self.data['projects']
    
    @lru_cache(maxsize=1)
    def _load_financial_data(self):
        """Lazy load financial statements data"""
        if 'financial' not in self.data:
            fa_path = self.data_dir / 'FA_A_processed.csv'
            if fa_path.exists():
                self.data['financial'] = pd.read_csv(fa_path)
                self._data_loaded['financial'] = True
            else:
                return pd.DataFrame()
        return self.data.get('financial', pd.DataFrame())
    
    @lru_cache(maxsize=1)
    def _load_valuation_data(self):
        """Lazy load valuation data"""
        if 'valuation' not in self.data:
            val_path = self.data_dir / 'Val_processed.csv'
            if val_path.exists():
                self.data['valuation'] = pd.read_csv(val_path)
                self._data_loaded['valuation'] = True
            else:
                return pd.DataFrame()
        return self.data.get('valuation', pd.DataFrame())
    
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
    
    def _register_tools(self):
        """Register all available tools"""
        
        # Tool 1: List Projects
        @self.tool(
            name="list_projects",
            description="List all real estate projects for one or more companies",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of company tickers (e.g., ['DXG', 'NLG'])",
                    "required": False
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of projects to return",
                    "required": False
                }
            }
        )
        def list_projects(tickers: List[str] = None, limit: int = None) -> Dict:
            """List real estate projects"""
            df = self._load_projects_data()
            
            if df.empty:
                return {"error": "No projects data available", "status": "failed"}
            
            # Filter by tickers if provided
            if tickers:
                if isinstance(tickers, str):
                    tickers = [tickers]
                tickers = [t.upper() for t in tickers]
                df = df[df['company_ticker'].isin(tickers)]
            
            if limit:
                df = df.head(limit)
            
            # Group projects by company
            result = {}
            for ticker in df['company_ticker'].unique():
                company_projects = df[df['company_ticker'] == ticker]
                result[ticker] = {
                    "count": len(company_projects),
                    "projects": company_projects['project_name'].tolist()
                }
            
            return {
                "companies": result,
                "total_projects": len(df),
                "status": "success"
            }
        
        # Tool 2: Get Project Details
        @self.tool(
            name="get_project_details",
            description="Get detailed information about specific real estate projects",
            parameters={
                "project_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of project names",
                    "required": False
                },
                "ticker": {
                    "type": "string",
                    "description": "Company ticker to filter projects",
                    "required": False
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific metrics to retrieve (e.g., ['revenue', 'asp', 'gross_margin'])",
                    "required": False
                }
            }
        )
        def get_project_details(project_names: List[str] = None, ticker: str = None, metrics: List[str] = None) -> Dict:
            """Get project details including financial metrics"""
            df = self._load_projects_data()
            
            if df.empty:
                return {"error": "No projects data available", "status": "failed"}
            
            # Filter by project names
            if project_names:
                if isinstance(project_names, str):
                    project_names = [project_names]
                # Case-insensitive matching
                mask = df['project_name'].str.lower().isin([p.lower() for p in project_names])
                df = df[mask]
            
            # Filter by ticker
            if ticker:
                df = df[df['company_ticker'] == ticker.upper()]
            
            if df.empty:
                return {"error": "No matching projects found", "status": "failed"}
            
            # Select specific metrics if requested
            if metrics:
                # Map common metric names to column names
                metric_mapping = {
                    'revenue': ['revenue_2024', 'revenue_2025', 'revenue_2026', 'revenue_2027', 'revenue_2028'],
                    'asp': 'asp_per_sqm',
                    'nsa': 'net_sellable_area',
                    'gross_margin': 'gross_margin',
                    'units': 'number_of_units',
                    'presales': ['presales_2024', 'presales_2025', 'presales_2026'],
                    'npatmi': ['npatmi_2024', 'npatmi_2025', 'npatmi_2026', 'npatmi_2027', 'npatmi_2028']
                }
                
                columns_to_include = ['project_name', 'company_ticker']
                for metric in metrics:
                    if metric in metric_mapping:
                        mapped = metric_mapping[metric]
                        if isinstance(mapped, list):
                            columns_to_include.extend(mapped)
                        else:
                            columns_to_include.append(mapped)
                
                # Only include columns that exist
                columns_to_include = [col for col in columns_to_include if col in df.columns]
                df = df[columns_to_include]
            
            return {
                "projects": df.to_dict('records'),
                "count": len(df),
                "status": "success"
            }
        
        # Tool 3: Rank Projects
        @self.tool(
            name="rank_projects",
            description="Rank real estate projects by a specific metric",
            parameters={
                "metric": {
                    "type": "string",
                    "description": "Metric to rank by (e.g., 'revenue_2024', 'asp_per_sqm', 'gross_margin', 'rnav')",
                    "required": True
                },
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by company tickers",
                    "required": False
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of top projects to return",
                    "required": False
                },
                "ascending": {
                    "type": "boolean",
                    "description": "Sort in ascending order (default: False for descending)",
                    "required": False
                }
            }
        )
        def rank_projects(metric: str, tickers: List[str] = None, top_n: int = 10, ascending: bool = False) -> Dict:
            """Rank projects by specified metric"""
            df = self._load_projects_data()
            
            if df.empty:
                return {"error": "No projects data available", "status": "failed"}
            
            # Filter by tickers
            if tickers:
                if isinstance(tickers, str):
                    tickers = [tickers]
                tickers = [t.upper() for t in tickers]
                df = df[df['company_ticker'].isin(tickers)]
            
            # Map common metric names
            metric_mapping = {
                'revenue': 'total_revenue',
                'asp': 'asp_per_sqm',
                'margin': 'gross_margin',
                'units': 'number_of_units',
                'rnav': 'rnav_value'
            }
            
            # Use mapped metric if available
            actual_metric = metric_mapping.get(metric, metric)
            
            # Check if metric exists
            if actual_metric not in df.columns:
                # Try to find similar column
                similar = [col for col in df.columns if metric.lower() in col.lower()]
                if similar:
                    actual_metric = similar[0]
                else:
                    return {
                        "error": f"Metric '{metric}' not found",
                        "available_metrics": df.columns.tolist(),
                        "status": "failed"
                    }
            
            # Remove rows with null values for the metric
            df_clean = df.dropna(subset=[actual_metric])
            
            # Sort by metric
            df_sorted = df_clean.sort_values(actual_metric, ascending=ascending)
            
            # Get top N
            if top_n:
                df_sorted = df_sorted.head(top_n)
            
            # Prepare result
            result_df = df_sorted[['project_name', 'company_ticker', actual_metric]]
            
            return {
                "ranking": result_df.to_dict('records'),
                "metric_used": actual_metric,
                "sort_order": "ascending" if ascending else "descending",
                "count": len(result_df),
                "status": "success"
            }
        
        # Tool 4: Compare Projects
        @self.tool(
            name="compare_projects",
            description="Compare multiple projects side by side",
            parameters={
                "project_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of project names to compare",
                    "required": True
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Metrics to compare (default: key metrics)",
                    "required": False
                }
            }
        )
        def compare_projects(project_names: List[str], metrics: List[str] = None) -> Dict:
            """Compare multiple projects"""
            df = self._load_projects_data()
            
            if df.empty:
                return {"error": "No projects data available", "status": "failed"}
            
            # Filter projects
            if isinstance(project_names, str):
                project_names = [project_names]
            
            mask = df['project_name'].str.lower().isin([p.lower() for p in project_names])
            df_filtered = df[mask]
            
            if df_filtered.empty:
                return {"error": "No matching projects found", "status": "failed"}
            
            # Default comparison metrics
            if not metrics:
                metrics = [
                    'asp_per_sqm', 'net_sellable_area', 'number_of_units',
                    'gross_margin', 'total_revenue', 'construction_cost_per_sqm'
                ]
            
            # Filter to available metrics
            available_metrics = [m for m in metrics if m in df_filtered.columns]
            
            # Prepare comparison data
            comparison_df = df_filtered[['project_name', 'company_ticker'] + available_metrics]
            
            return {
                "comparison": comparison_df.to_dict('records'),
                "metrics_compared": available_metrics,
                "projects_count": len(comparison_df),
                "status": "success"
            }
        
        # Tool 5: Calculate Portfolio Metrics
        @self.tool(
            name="calculate_portfolio_metrics",
            description="Calculate aggregate metrics across multiple projects or companies",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Company tickers to include",
                    "required": False
                },
                "metric_type": {
                    "type": "string",
                    "description": "Type of calculation: sum, average, weighted_average",
                    "enum": ["sum", "average", "weighted_average"],
                    "required": False
                }
            }
        )
        def calculate_portfolio_metrics(tickers: List[str] = None, metric_type: str = "sum") -> Dict:
            """Calculate portfolio-level metrics"""
            df = self._load_projects_data()
            
            if df.empty:
                return {"error": "No projects data available", "status": "failed"}
            
            # Filter by tickers
            if tickers:
                if isinstance(tickers, str):
                    tickers = [tickers]
                tickers = [t.upper() for t in tickers]
                df = df[df['company_ticker'].isin(tickers)]
            
            # Calculate metrics
            metrics = {}
            
            if metric_type == "sum":
                metrics['total_units'] = df['number_of_units'].sum() if 'number_of_units' in df.columns else 0
                metrics['total_nsa'] = df['net_sellable_area'].sum() if 'net_sellable_area' in df.columns else 0
                metrics['total_revenue'] = df['total_revenue'].sum() if 'total_revenue' in df.columns else 0
            
            elif metric_type == "average":
                metrics['avg_asp'] = df['asp_per_sqm'].mean() if 'asp_per_sqm' in df.columns else 0
                metrics['avg_gross_margin'] = df['gross_margin'].mean() if 'gross_margin' in df.columns else 0
                metrics['avg_construction_cost'] = df['construction_cost_per_sqm'].mean() if 'construction_cost_per_sqm' in df.columns else 0
            
            elif metric_type == "weighted_average":
                # Weight by net sellable area
                if 'net_sellable_area' in df.columns and 'asp_per_sqm' in df.columns:
                    total_nsa = df['net_sellable_area'].sum()
                    if total_nsa > 0:
                        metrics['weighted_avg_asp'] = (df['asp_per_sqm'] * df['net_sellable_area']).sum() / total_nsa
            
            return {
                "portfolio_metrics": metrics,
                "projects_included": len(df),
                "calculation_type": metric_type,
                "status": "success"
            }
        
        # Tool 6: Analyze Growth Trends
        @self.tool(
            name="analyze_growth_trends",
            description="Analyze revenue and profit growth trends over time",
            parameters={
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Company tickers to analyze",
                    "required": False
                },
                "project_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific projects to analyze",
                    "required": False
                },
                "metric": {
                    "type": "string",
                    "description": "Metric to analyze (revenue, presales, npatmi)",
                    "enum": ["revenue", "presales", "npatmi"],
                    "required": False
                }
            }
        )
        def analyze_growth_trends(tickers: List[str] = None, project_names: List[str] = None, metric: str = "revenue") -> Dict:
            """Analyze growth trends"""
            df = self._load_projects_data()
            
            if df.empty:
                return {"error": "No projects data available", "status": "failed"}
            
            # Filter data
            if tickers:
                if isinstance(tickers, str):
                    tickers = [tickers]
                tickers = [t.upper() for t in tickers]
                df = df[df['company_ticker'].isin(tickers)]
            
            if project_names:
                if isinstance(project_names, str):
                    project_names = [project_names]
                mask = df['project_name'].str.lower().isin([p.lower() for p in project_names])
                df = df[mask]
            
            # Determine year columns based on metric
            if metric == "revenue":
                year_cols = [col for col in df.columns if col.startswith('revenue_20')]
            elif metric == "presales":
                year_cols = [col for col in df.columns if col.startswith('presales_20')]
            elif metric == "npatmi":
                year_cols = [col for col in df.columns if col.startswith('npatmi_20')]
            else:
                year_cols = []
            
            if not year_cols:
                return {"error": f"No data available for metric: {metric}", "status": "failed"}
            
            # Calculate aggregated values by year
            yearly_data = {}
            for col in year_cols:
                year = col.split('_')[-1]
                yearly_data[year] = df[col].sum()
            
            # Calculate growth rates
            years_sorted = sorted(yearly_data.keys())
            growth_rates = {}
            
            for i in range(1, len(years_sorted)):
                prev_year = years_sorted[i-1]
                curr_year = years_sorted[i]
                
                if yearly_data[prev_year] > 0:
                    growth_rate = ((yearly_data[curr_year] - yearly_data[prev_year]) / yearly_data[prev_year]) * 100
                    growth_rates[f"{prev_year}_{curr_year}"] = round(growth_rate, 2)
            
            return {
                "metric": metric,
                "yearly_values": yearly_data,
                "growth_rates": growth_rates,
                "projects_analyzed": len(df),
                "status": "success"
            }
        
        # Tool 7: Get Company Forecasts
        @self.tool(
            name="get_company_forecasts",
            description="Get company-level financial forecasts from MongoDB",
            parameters={
                "ticker": {
                    "type": "string",
                    "description": "Company ticker",
                    "required": True
                },
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Forecast metrics to retrieve",
                    "required": False
                },
                "years": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Years to retrieve forecasts for",
                    "required": False
                }
            }
        )
        def get_company_forecasts(ticker: str, metrics: List[str] = None, years: List[int] = None) -> Dict:
            """Get company financial forecasts"""
            try:
                assumptions = get_company_assumptions(ticker.upper())
                
                if not assumptions:
                    return {"error": f"No forecast data for {ticker}", "status": "failed"}
                
                # Default metrics if not specified
                if not metrics:
                    metrics = ['revenue_growth', 'gross_margin', 'sga_margin', 'net_margin']
                
                # Default years if not specified
                if not years:
                    years = [2024, 2025, 2026, 2027, 2028]
                
                # Extract requested data
                forecast_data = {}
                for metric in metrics:
                    if metric in assumptions:
                        forecast_data[metric] = assumptions[metric]
                
                return {
                    "ticker": ticker.upper(),
                    "forecasts": forecast_data,
                    "years_available": years,
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
        # Tool 8: Search Market Insights
        @self.tool(
            name="search_market_insights",
            description="Search for market insights and news using Perplexity AI",
            parameters={
                "query": {
                    "type": "string",
                    "description": "Search query for market insights",
                    "required": True
                },
                "focus": {
                    "type": "string",
                    "description": "Focus area: market, competitor, regulatory, economic",
                    "enum": ["market", "competitor", "regulatory", "economic"],
                    "required": False
                }
            }
        )
        def search_market_insights(query: str, focus: str = None) -> Dict:
            """Search for market insights"""
            if not self.perplexity_researcher:
                return {"error": "Perplexity API not configured", "status": "failed"}
            
            try:
                # Enhance query based on focus
                if focus:
                    query = f"{focus} analysis: {query}"
                
                # Use Perplexity to search
                insights = get_project_basic_info_perplexity(query, self.perplexity_researcher.api_key)
                
                return {
                    "query": query,
                    "insights": insights,
                    "focus": focus,
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
        # Tool 9: Suggest Parameters
        @self.tool(
            name="suggest_parameters",
            description="Get AI suggestions for project parameters like ASP or construction costs",
            parameters={
                "project_name": {
                    "type": "string",
                    "description": "Project name",
                    "required": True
                },
                "parameter_type": {
                    "type": "string",
                    "description": "Parameter to suggest: asp, construction_cost, timeline",
                    "enum": ["asp", "construction_cost", "timeline"],
                    "required": True
                },
                "context": {
                    "type": "object",
                    "description": "Additional context (location, segment, etc.)",
                    "required": False
                }
            }
        )
        def suggest_parameters(project_name: str, parameter_type: str, context: Dict = None) -> Dict:
            """Suggest project parameters using AI"""
            if not self.anthropic_client:
                return {"error": "Claude API not configured", "status": "failed"}
            
            try:
                # Build context prompt
                context_str = ""
                if context:
                    context_str = f"\nContext: {json.dumps(context)}"
                
                # Create prompt based on parameter type
                prompts = {
                    "asp": f"Suggest an appropriate average selling price (ASP) per sqm for the project '{project_name}'.{context_str}\n\nProvide a specific number in VND and brief justification.",
                    "construction_cost": f"Suggest construction cost per sqm for the project '{project_name}'.{context_str}\n\nProvide a specific number in VND and brief justification.",
                    "timeline": f"Suggest a development timeline for the project '{project_name}'.{context_str}\n\nProvide start year, completion year, and key milestones."
                }
                
                prompt = prompts.get(parameter_type, "")
                
                # Get suggestion from Claude
                response = self.anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=500,
                    temperature=0.3,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                
                suggestion = response.content[0].text
                
                return {
                    "project_name": project_name,
                    "parameter_type": parameter_type,
                    "suggestion": suggestion,
                    "context": context,
                    "status": "success"
                }
                
            except Exception as e:
                return {"error": str(e), "status": "failed"}
        
        # Tool 10: Update Project Data
        @self.tool(
            name="update_project_data",
            description="Update project data in MongoDB",
            parameters={
                "project_name": {
                    "type": "string",
                    "description": "Project name to update",
                    "required": True
                },
                "updates": {
                    "type": "object",
                    "description": "Dictionary of fields to update",
                    "required": True
                }
            }
        )
        def update_project_data(project_name: str, updates: Dict) -> Dict:
            """Update project data"""
            try:
                # Load current project data
                df = self._load_projects_data()
                
                # Find project
                project_mask = df['project_name'].str.lower() == project_name.lower()
                if not project_mask.any():
                    return {"error": f"Project '{project_name}' not found", "status": "failed"}
                
                # Get project data
                project_data = df[project_mask].iloc[0].to_dict()
                
                # Apply updates
                for key, value in updates.items():
                    project_data[key] = value
                
                # Save to MongoDB
                result = save_project_to_mongodb(project_data)
                
                if result:
                    # Clear cache to reload updated data
                    if 'projects' in self.data:
                        del self.data['projects']
                    
                    return {
                        "project_name": project_name,
                        "updates": updates,
                        "status": "success",
                        "message": "Project updated successfully"
                    }
                else:
                    return {"error": "Failed to update project", "status": "failed"}
                    
            except Exception as e:
                return {"error": str(e), "status": "failed"}
    
    def execute_tool(self, tool_name: str, arguments: Dict = None) -> Dict:
        """Execute a tool by name with arguments"""
        if tool_name not in self.tools:
            return {"error": f"Unknown tool: {tool_name}", "status": "failed"}
        
        tool_func = self.tools[tool_name]
        
        # Get function signature
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
    
    def classify_intent(self, query: str) -> str:
        """Classify user intent using Claude AI"""
        if self.anthropic_client:
            try:
                response = self.anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=50,
                    temperature=0,
                    messages=[{
                        "role": "user",
                        "content": f"""Classify this query into ONE tool name:
Query: "{query}"

Available tools:
- list_projects: List projects
- get_project_details: Get specific project details
- rank_projects: Rank/sort projects by metric
- compare_projects: Compare specific projects
- calculate_portfolio_metrics: Calculate aggregate metrics
- analyze_growth_trends: Analyze trends over time
- get_company_forecasts: Get financial forecasts
- search_market_insights: Search market information
- suggest_parameters: Get AI suggestions
- update_project_data: Update project data

Respond with ONLY the tool name."""
                    }]
                )
                return response.content[0].text.strip()
            except:
                pass
        
        # Fallback to simple matching
        query_lower = query.lower()
        if 'list' in query_lower or 'show' in query_lower:
            return 'list_projects'
        elif 'rank' in query_lower or 'top' in query_lower or 'highest' in query_lower:
            return 'rank_projects'
        elif 'compare' in query_lower:
            return 'compare_projects'
        elif 'forecast' in query_lower:
            return 'get_company_forecasts'
        else:
            return 'get_project_details'


# Helper function to create singleton instance
_tool_system_instance = None

def get_tool_system() -> RealEstateToolSystem:
    """Get or create the real estate tool system instance"""
    global _tool_system_instance
    if _tool_system_instance is None:
        _tool_system_instance = RealEstateToolSystem()
    return _tool_system_instance


class GodAIAssistant:
    """
    God AI Assistant - MCP version
    Wrapper class for backward compatibility with existing code
    """
    
    def __init__(self):
        """Initialize the God AI Assistant with MCP tool system"""
        self.tool_system = get_tool_system()
        self.anthropic_client = self.tool_system.anthropic_client
    
    def process_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process user query using MCP tool system"""
        try:
            # Add to chat history
            if 'chat_history' not in st.session_state:
                st.session_state.chat_history = []
            
            st.session_state.chat_history.append({
                'role': 'user',
                'content': query,
                'timestamp': datetime.now()
            })
            
            # Classify intent
            intent = self.tool_system.classify_intent(query)
            
            # Extract entities from query
            entities = self._extract_entities(query, context)
            
            # Map intent to tool and execute
            tool_mapping = {
                'list_projects': 'list_projects',
                'get_project_details': 'get_project_details',
                'rank_projects': 'rank_projects',
                'compare_projects': 'compare_projects',
                'calculate_portfolio_metrics': 'calculate_portfolio_metrics',
                'analyze_growth_trends': 'analyze_growth_trends',
                'get_company_forecasts': 'get_company_forecasts',
                'search_market_insights': 'search_market_insights',
                'suggest_parameters': 'suggest_parameters',
                'update_project_data': 'update_project_data'
            }
            
            tool_name = tool_mapping.get(intent, 'get_project_details')
            
            # Prepare arguments based on entities and context
            arguments = self._prepare_arguments(tool_name, entities, context)
            
            # Execute tool
            result = self.tool_system.execute_tool(tool_name, arguments)
            
            # Format response
            formatted_result = self._format_response(result, tool_name, query)
            
            # Add to chat history
            st.session_state.chat_history.append({
                'role': 'assistant',
                'content': formatted_result.get('message', 'Processing complete'),
                'timestamp': datetime.now()
            })
            
            return formatted_result
            
        except Exception as e:
            return {
                'type': 'error',
                'message': f"Error processing query: {str(e)}",
                'error': str(e)
            }
    
    def _extract_entities(self, query: str, context: Dict) -> Dict:
        """Extract entities from query"""
        entities = {}
        
        # Extract tickers
        ticker_pattern = r'\b([A-Z]{3,4})\b'
        tickers = re.findall(ticker_pattern, query)
        if tickers:
            entities['tickers'] = tickers
        
        # Extract project names
        df = self.tool_system._load_projects_data()
        if not df.empty:
            for project_name in df['project_name'].unique():
                if project_name and project_name.lower() in query.lower():
                    if 'project_names' not in entities:
                        entities['project_names'] = []
                    entities['project_names'].append(project_name)
        
        # Extract years
        year_pattern = r'\b(20\d{2})\b'
        years = re.findall(year_pattern, query)
        if years:
            entities['years'] = [int(y) for y in years]
        
        # Extract metrics
        query_lower = query.lower()
        metrics = ['revenue', 'asp', 'margin', 'units', 'presales', 'npatmi']
        for metric in metrics:
            if metric in query_lower:
                entities['metric'] = metric
                break
        
        return entities
    
    def _prepare_arguments(self, tool_name: str, entities: Dict, context: Dict) -> Dict:
        """Prepare arguments for tool execution"""
        arguments = {}
        
        # Add entities to arguments
        if 'tickers' in entities:
            arguments['tickers'] = entities['tickers']
        if 'project_names' in entities:
            arguments['project_names'] = entities['project_names']
        if 'years' in entities:
            arguments['years'] = entities['years']
        if 'metric' in entities:
            arguments['metric'] = entities['metric']
        
        # Add context-specific arguments
        if context.get('selected_company'):
            if 'tickers' not in arguments:
                arguments['tickers'] = [context['selected_company']]
        
        return arguments
    
    def _format_response(self, result: Dict, tool_name: str, query: str) -> Dict:
        """Format tool response for display"""
        if result.get('status') == 'failed':
            return {
                'type': 'error',
                'message': result.get('error', 'Operation failed')
            }
        
        # Format based on tool type
        if tool_name == 'list_projects':
            companies = result.get('companies', {})
            message_parts = []
            for ticker, data in companies.items():
                message_parts.append(f"**{ticker}**: {data['count']} projects")
                for project in data['projects'][:5]:
                    message_parts.append(f"  - {project}")
            message = "\n".join(message_parts)
        
        elif tool_name == 'rank_projects':
            ranking = result.get('ranking', [])
            metric = result.get('metric_used', 'metric')
            message_parts = [f"Top projects by {metric}:"]
            for i, item in enumerate(ranking[:10], 1):
                message_parts.append(
                    f"{i}. {item['project_name']} ({item['company_ticker']}): {item.get(metric, 'N/A')}"
                )
            message = "\n".join(message_parts)
        
        else:
            # Generic formatting
            message = json.dumps(result, indent=2, default=str)
        
        return {
            'type': 'success',
            'message': message,
            'data': result,
            'tool_used': tool_name,
            'query': query
        }