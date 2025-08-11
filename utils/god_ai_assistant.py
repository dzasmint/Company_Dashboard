"""
God AI Assistant - Advanced AI orchestrator for comprehensive financial analysis
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json
import re
import plotly.graph_objects as go
import plotly.express as px
from .claude_project_extractor import ClaudeProjectExtractor
from .perplexity_utils import PerplexityProjectResearcher, get_project_basic_info_perplexity
from .mongodb_utils import MongoDBHelper, get_company_assumptions, save_project_to_mongodb
import anthropic
import os
from dotenv import load_dotenv

load_dotenv()

class GodAIAssistant:
    """Advanced AI assistant with comprehensive capabilities for financial analysis"""
    
    def __init__(self):
        """Initialize the God AI Assistant"""
        self.claude_extractor = None
        self.perplexity_researcher = None
        self.mongo_helper = MongoDBHelper()
        self.anthropic_client = None
        
        # Initialize AI clients if API keys are available
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        perplexity_key = os.getenv('PERPLEXITY_API_KEY')
        
        if anthropic_key:
            self.claude_extractor = ClaudeProjectExtractor(api_key=anthropic_key)
            self.anthropic_client = anthropic.Anthropic(api_key=anthropic_key)
        
        if perplexity_key:
            self.perplexity_researcher = PerplexityProjectResearcher(api_key=perplexity_key)
        
        # Initialize intent patterns
        self.intent_patterns = self._load_intent_patterns()
    
    def _load_intent_patterns(self) -> Dict[str, List[str]]:
        """Load intent classification patterns"""
        return {
            'LIST_PROJECTS': [
                'list', 'show', 'all projects', 'display projects', 
                'what projects', 'get projects', 'show me projects'
            ],
            'RANK_PROJECTS': [
                'largest', 'biggest', 'top', 'rnav', 'ranking', 
                'highest', 'best', 'rank by', 'sort by'
            ],
            'SUGGEST_PARAMETERS': [
                'suggest', 'recommend', 'asp', 'price', 'what should',
                'appropriate', 'estimate', 'calculate'
            ],
            'ANALYZE_GROWTH': [
                'growth', 'profit', 'revenue', 'forecast', 'which year',
                'highest growth', 'peak', 'trend', 'projection'
            ],
            'RESEARCH_INSIGHTS': [
                'research', 'market', 'insights', 'news', 'latest',
                'competitor', 'analysis', 'web search'
            ],
            'EXTRACT_DOCUMENT': [
                'extract', 'pdf', 'document', 'report', 'upload',
                'analyze report', 'parse', 'read'
            ],
            'UPDATE_PROJECT': [
                'update', 'change', 'modify', 'set', 'edit',
                'adjust', 'correct', 'fix'
            ],
            'PROJECT_DETAILS': [
                'details', 'information', 'about', 'tell me about',
                'what is', 'describe', 'show details'
            ],
            'CALCULATE_METRICS': [
                'calculate', 'compute', 'what is the', 'total',
                'sum', 'average', 'metrics'
            ]
        }
    
    def process_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process user query and return structured response"""
        try:
            # Add query to history
            if 'chat_history' not in st.session_state:
                st.session_state.chat_history = []
            
            st.session_state.chat_history.append({
                'role': 'user',
                'content': query,
                'timestamp': datetime.now()
            })
            
            # Classify intent
            intent = self.classify_intent(query)
            
            # Extract entities from query
            entities = self.extract_entities(query, context)
            
            # Execute appropriate action
            result = self.execute_action(intent, entities, query, context)
            
            # Add response to history
            st.session_state.chat_history.append({
                'role': 'assistant',
                'content': result.get('message', 'Processing complete'),
                'summary': result.get('summary', result.get('message', 'Processing complete')[:100]),
                'timestamp': datetime.now()
            })
            
            # Store result for display
            st.session_state.current_ai_result = result
            
            return result
            
        except Exception as e:
            error_result = {
                'type': 'error',
                'message': f"Error processing query: {str(e)}",
                'error': str(e)
            }
            st.session_state.current_ai_result = error_result
            return error_result
    
    def classify_intent(self, query: str) -> str:
        """Classify user intent from query"""
        query_lower = query.lower()
        
        # Check each intent pattern
        for intent, patterns in self.intent_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                return intent
        
        # If no pattern matches, use Claude for classification if available
        if self.anthropic_client:
            try:
                response = self.anthropic_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=50,
                    messages=[{
                        "role": "user",
                        "content": f"""Classify this query into one of these intents:
                        LIST_PROJECTS, RANK_PROJECTS, SUGGEST_PARAMETERS, ANALYZE_GROWTH,
                        RESEARCH_INSIGHTS, EXTRACT_DOCUMENT, UPDATE_PROJECT, PROJECT_DETAILS, CALCULATE_METRICS
                        
                        Query: {query}
                        
                        Return only the intent name."""
                    }]
                )
                intent = response.content[0].text.strip()
                if intent in self.intent_patterns.keys():
                    return intent
            except:
                pass
        
        return 'GENERAL_QUERY'
    
    def extract_entities(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract entities from query"""
        entities = {}
        
        # Extract ticker symbols (e.g., DXG, NLG, VHM, etc.)
        ticker_pattern = r'\b([A-Z]{3,4})\b'
        potential_tickers = re.findall(ticker_pattern, query)
        if potential_tickers:
            # Validate tickers against known companies in MongoDB
            from .mongodb_utils import load_companies_data
            companies_df = load_companies_data()
            if not companies_df.empty:
                valid_tickers = []
                for ticker in potential_tickers:
                    if ticker in companies_df['ticker'].values:
                        valid_tickers.append(ticker)
                if valid_tickers:
                    entities['tickers'] = valid_tickers
        
        # Extract project names - search across ALL projects in MongoDB
        from .mongodb_utils import load_projects_data
        all_projects_df = load_projects_data()
        if not all_projects_df.empty:
            for project_name in all_projects_df['project_name'].unique():
                if project_name and project_name.lower() in query.lower():
                    entities['project_name'] = project_name
                    # Also extract the ticker for this project
                    project_ticker = all_projects_df[all_projects_df['project_name'] == project_name]['company_ticker'].iloc[0]
                    if 'tickers' not in entities:
                        entities['tickers'] = []
                    if project_ticker not in entities.get('tickers', []):
                        entities['tickers'].append(project_ticker)
                    break
        
        # Extract years
        year_pattern = r'\b(20\d{2})\b'
        years = re.findall(year_pattern, query)
        if years:
            entities['years'] = [int(y) for y in years]
        
        # Extract numbers
        number_pattern = r'\b(\d+(?:\.\d+)?)\b'
        numbers = re.findall(number_pattern, query)
        if numbers:
            entities['numbers'] = [float(n) for n in numbers]
        
        # Extract detailed metrics
        metrics = [
            'rnav', 'revenue', 'asp', 'average selling price', 'nsa', 'net sellable area',
            'construction cost', 'land cost', 'gross margin', 'presales', 
            'units', 'number of units', 'total units', 'presales period',
            'revenue booking', 'gross floor area', 'gfa', 'land area',
            'sga', 'interest', 'debt', 'pat', 'pbt', 'ebitda'
        ]
        for metric in metrics:
            if metric in query.lower():
                entities['metric'] = metric
                break
        
        return entities
    
    def execute_action(self, intent: str, entities: Dict[str, Any], query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action based on intent"""
        
        # Check if query mentions specific metrics even without explicit intent
        metric = entities.get('metric')
        if metric and intent == 'GENERAL_QUERY':
            # Route to project details with metric extraction
            return self.handle_project_details(entities, context)
        
        if intent == 'LIST_PROJECTS':
            return self.handle_list_projects(entities, context)
        elif intent == 'RANK_PROJECTS':
            return self.handle_rank_projects(entities, context)
        elif intent == 'SUGGEST_PARAMETERS':
            return self.handle_suggest_parameters(entities, query, context)
        elif intent == 'ANALYZE_GROWTH':
            return self.handle_growth_analysis(entities, context)
        elif intent == 'RESEARCH_INSIGHTS':
            return self.handle_research_insights(entities, query, context)
        elif intent == 'PROJECT_DETAILS':
            return self.handle_project_details(entities, context)
        elif intent == 'CALCULATE_METRICS':
            return self.handle_calculate_metrics(entities, context)
        elif intent == 'UPDATE_PROJECT':
            return self.handle_update_project(entities, query, context)
        else:
            return self.handle_general_query(query, context)
    
    def handle_list_projects(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle project listing request - now supports querying any ticker"""
        tickers = entities.get('tickers', [])
        
        # If no tickers specified, try to use selected company
        if not tickers:
            company = context.get('selected_company')
            if company:
                tickers = [company]
        
        # Load all projects from MongoDB
        from .mongodb_utils import load_projects_data
        all_projects_df = load_projects_data()
        
        if all_projects_df.empty:
            return {
                'type': 'info',
                'message': 'No projects found in database',
                'data': None
            }
        
        # Filter by tickers if specified
        if tickers:
            projects_df = all_projects_df[all_projects_df['company_ticker'].isin(tickers)]
            company_names = ', '.join(tickers)
        else:
            projects_df = all_projects_df
            company_names = 'all companies'
        
        if projects_df.empty:
            return {
                'type': 'info',
                'message': f'No projects found for {company_names}',
                'data': None
            }
        
        # Prepare display data
        display_columns = ['company_ticker', 'project_name', 'location', 'net_sellable_area', 
                          'average_selling_price', 'construction_start_year', 'rnav_value']
        
        available_columns = [col for col in display_columns if col in projects_df.columns]
        display_df = projects_df[available_columns].copy()
        
        # Format numbers
        if 'net_sellable_area' in display_df.columns:
            display_df['net_sellable_area'] = display_df['net_sellable_area'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
        if 'average_selling_price' in display_df.columns:
            display_df['average_selling_price'] = display_df['average_selling_price'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
        if 'rnav_value' in display_df.columns:
            display_df['rnav_value'] = display_df['rnav_value'].apply(lambda x: f"{x:,.1f}B" if pd.notna(x) else "N/A")
        
        return {
            'type': 'project_list',
            'message': f"Found {len(display_df)} projects for {company_names}",
            'summary': f"Showing {len(display_df)} projects",
            'data': display_df
        }
    
    def handle_rank_projects(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle project ranking request - now searches all projects in MongoDB"""
        tickers = entities.get('tickers', [])
        
        # Load all projects from MongoDB
        from .mongodb_utils import load_projects_data
        all_projects_df = load_projects_data()
        
        if all_projects_df.empty:
            return {
                'type': 'error',
                'message': 'No projects found in database',
                'data': None
            }
        
        # Filter by tickers if specified
        if tickers:
            projects_df = all_projects_df[all_projects_df['company_ticker'].isin(tickers)]
        else:
            projects_df = all_projects_df
        
        if projects_df.empty:
            return {
                'type': 'error',
                'message': 'No projects found for specified criteria',
                'data': None
            }
        
        # Determine ranking metric
        metric = entities.get('metric', 'rnav').lower()
        
        if metric == 'rnav' and 'rnav_value' in projects_df.columns:
            sorted_df = projects_df.sort_values('rnav_value', ascending=False, na_position='last')
            metric_display = 'RNAV Value'
        elif metric == 'revenue' and 'total_revenue' in projects_df.columns:
            sorted_df = projects_df.sort_values('total_revenue', ascending=False, na_position='last')
            metric_display = 'Total Revenue'
        elif metric == 'nsa' and 'net_sellable_area' in projects_df.columns:
            sorted_df = projects_df.sort_values('net_sellable_area', ascending=False, na_position='last')
            metric_display = 'Net Sellable Area'
        else:
            # Default to RNAV
            if 'rnav_value' in projects_df.columns:
                sorted_df = projects_df.sort_values('rnav_value', ascending=False, na_position='last')
                metric_display = 'RNAV Value'
            else:
                sorted_df = projects_df
                metric_display = 'Default Order'
        
        # Get top 10
        top_projects = sorted_df.head(10)
        
        # Prepare display
        display_columns = ['company_ticker', 'project_name', 'location', 'rnav_value', 'net_sellable_area', 'average_selling_price']
        available_columns = [col for col in display_columns if col in top_projects.columns]
        display_df = top_projects[available_columns].copy()
        
        # Add ranking
        display_df.insert(0, 'Rank', range(1, len(display_df) + 1))
        
        # Format numbers
        if 'net_sellable_area' in display_df.columns:
            display_df['net_sellable_area'] = display_df['net_sellable_area'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
        if 'average_selling_price' in display_df.columns:
            display_df['average_selling_price'] = display_df['average_selling_price'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
        if 'rnav_value' in display_df.columns:
            display_df['rnav_value'] = display_df['rnav_value'].apply(lambda x: f"{x:,.1f}B" if pd.notna(x) else "N/A")
        
        return {
            'type': 'ranked_projects',
            'message': f"Top {len(display_df)} projects ranked by {metric_display}",
            'summary': f"Ranked {len(display_df)} projects",
            'data': display_df,
            'metric': metric_display
        }
    
    def handle_suggest_parameters(self, entities: Dict[str, Any], query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle parameter suggestion request"""
        project_name = entities.get('project_name')
        
        if not project_name:
            # Try to extract from query
            projects_df = context.get('project_data')
            if projects_df is not None and not projects_df.empty:
                # Get first project as default
                project_name = projects_df.iloc[0]['project_name']
        
        if not project_name:
            return {
                'type': 'error',
                'message': 'Please specify a project name for parameter suggestions',
                'data': None
            }
        
        # Use Perplexity to research if available
        if self.perplexity_researcher:
            try:
                research_result = get_project_basic_info_perplexity(
                    project_name,
                    os.getenv('PERPLEXITY_API_KEY')
                )
                
                suggestions = []
                
                # Parse research result
                if research_result and 'choices' in research_result:
                    content = research_result['choices'][0]['message']['content']
                    
                    # Extract suggested values (simplified parsing)
                    asp_match = re.search(r'average.*price.*?(\d+(?:,\d+)*(?:\.\d+)?)', content, re.IGNORECASE)
                    construction_match = re.search(r'construction.*cost.*?(\d+(?:,\d+)*(?:\.\d+)?)', content, re.IGNORECASE)
                    
                    if asp_match:
                        asp_value = float(asp_match.group(1).replace(',', ''))
                        suggestions.append({
                            'project': project_name,
                            'parameter': 'Average Selling Price',
                            'value': asp_value,
                            'unit': 'VND/sqm',
                            'source': 'Market Research'
                        })
                    
                    if construction_match:
                        const_value = float(construction_match.group(1).replace(',', ''))
                        suggestions.append({
                            'project': project_name,
                            'parameter': 'Construction Cost',
                            'value': const_value,
                            'unit': 'VND/sqm',
                            'source': 'Market Research'
                        })
                
                if suggestions:
                    return {
                        'type': 'parameter_suggestions',
                        'message': f"AI-powered suggestions for {project_name} based on market research",
                        'summary': f"Found {len(suggestions)} suggestions",
                        'suggestions': suggestions,
                        'data': pd.DataFrame(suggestions)
                    }
                    
            except Exception as e:
                st.warning(f"Could not get AI suggestions: {str(e)}")
        
        # Fallback to simple estimates
        return {
            'type': 'parameter_suggestions',
            'message': f"Default suggestions for {project_name}",
            'summary': "Using default values",
            'suggestions': [
                {
                    'project': project_name,
                    'parameter': 'Average Selling Price',
                    'value': 45000000,
                    'unit': 'VND/sqm',
                    'source': 'Default Estimate'
                },
                {
                    'project': project_name,
                    'parameter': 'Construction Cost',
                    'value': 15000000,
                    'unit': 'VND/sqm',
                    'source': 'Default Estimate'
                }
            ],
            'data': None
        }
    
    def handle_growth_analysis(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle growth analysis request - now analyzes any ticker"""
        tickers = entities.get('tickers', [])
        
        # Load all projects from MongoDB
        from .mongodb_utils import load_projects_data
        all_projects_df = load_projects_data()
        
        if all_projects_df.empty:
            return {
                'type': 'error',
                'message': 'No projects found in database',
                'data': None
            }
        
        # Filter by tickers if specified
        if tickers:
            projects_df = all_projects_df[all_projects_df['company_ticker'].isin(tickers)]
            company_names = ', '.join(tickers)
        else:
            projects_df = all_projects_df
            company_names = 'all companies'
        
        if projects_df.empty:
            return {
                'type': 'error',
                'message': f'No projects found for {company_names}',
                'data': None
            }
        
        # Analyze revenue by year
        current_year = datetime.now().year
        years = list(range(current_year, current_year + 6))
        
        yearly_revenue = {}
        project_contributions = {}
        
        for _, project in projects_df.iterrows():
            project_name = project.get('project_name', 'Unknown')
            revenue_schedule = project.get('revenue_schedule', {})
            
            if isinstance(revenue_schedule, dict):
                for year_str, revenue in revenue_schedule.items():
                    year = int(year_str)
                    if year in years:
                        if year not in yearly_revenue:
                            yearly_revenue[year] = 0
                            project_contributions[year] = []
                        yearly_revenue[year] += revenue
                        project_contributions[year].append({
                            'project': project_name,
                            'revenue': revenue
                        })
        
        if not yearly_revenue:
            return {
                'type': 'info',
                'message': 'No revenue data available for growth analysis',
                'data': None
            }
        
        # Calculate growth rates
        growth_data = []
        peak_growth_year = None
        peak_growth_rate = 0
        
        sorted_years = sorted(yearly_revenue.keys())
        for i, year in enumerate(sorted_years):
            if i > 0:
                prev_year = sorted_years[i-1]
                growth_rate = ((yearly_revenue[year] - yearly_revenue[prev_year]) / yearly_revenue[prev_year]) * 100
                growth_data.append({
                    'Year': year,
                    'Revenue': yearly_revenue[year],
                    'Growth Rate': growth_rate
                })
                
                if growth_rate > peak_growth_rate:
                    peak_growth_rate = growth_rate
                    peak_growth_year = year
            else:
                growth_data.append({
                    'Year': year,
                    'Revenue': yearly_revenue[year],
                    'Growth Rate': 0
                })
        
        # Find top contributor for peak year
        top_contributor = None
        if peak_growth_year and peak_growth_year in project_contributions:
            contributions = project_contributions[peak_growth_year]
            if contributions:
                top_contributor = max(contributions, key=lambda x: x['revenue'])
        
        # Create chart
        fig = go.Figure()
        
        # Add revenue bars
        fig.add_trace(go.Bar(
            x=[d['Year'] for d in growth_data],
            y=[d['Revenue'] for d in growth_data],
            name='Revenue',
            marker_color='lightblue',
            yaxis='y'
        ))
        
        # Add growth rate line
        fig.add_trace(go.Scatter(
            x=[d['Year'] for d in growth_data],
            y=[d['Growth Rate'] for d in growth_data],
            name='Growth Rate (%)',
            mode='lines+markers',
            marker_color='red',
            yaxis='y2'
        ))
        
        fig.update_layout(
            title='Revenue Growth Analysis',
            xaxis_title='Year',
            yaxis=dict(title='Revenue (Billion VND)', side='left'),
            yaxis2=dict(title='Growth Rate (%)', overlaying='y', side='right'),
            hovermode='x unified',
            height=400
        )
        
        analysis_title = f"Revenue Growth Analysis for {company_names}" if tickers else "Revenue Growth Analysis"
        
        return {
            'type': 'growth_analysis',
            'message': f"Growth analysis complete for {company_names}. Peak growth in {peak_growth_year} at {peak_growth_rate:.1f}%",
            'summary': f"Peak: {peak_growth_year} ({peak_growth_rate:.1f}%)",
            'data': pd.DataFrame(growth_data),
            'chart': fig,
            'peak_year': peak_growth_year,
            'growth_rate': peak_growth_rate / 100,
            'top_project': top_contributor['project'] if top_contributor else 'N/A',
            'revenue_impact': top_contributor['revenue'] if top_contributor else 0,
            'companies_analyzed': company_names
        }
    
    def handle_research_insights(self, entities: Dict[str, Any], query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle research insights request"""
        # This would integrate with Perplexity for web research
        return {
            'type': 'research_insights',
            'message': 'Research insights feature requires Perplexity API integration',
            'summary': 'Research pending',
            'data': None,
            'market_overview': 'Market research will be displayed here',
            'comparables': pd.DataFrame(),
            'news_items': []
        }
    
    def handle_project_details(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle project details request - now searches MongoDB for any ticker"""
        project_name = entities.get('project_name')
        tickers = entities.get('tickers', [])
        metric = entities.get('metric', None)
        
        # Load all projects from MongoDB
        from .mongodb_utils import load_projects_data
        all_projects_df = load_projects_data()
        
        if all_projects_df.empty:
            return {
                'type': 'error',
                'message': 'No projects found in database',
                'data': None
            }
        
        # Filter by ticker if specified
        if tickers:
            projects_df = all_projects_df[all_projects_df['company_ticker'].isin(tickers)]
        else:
            projects_df = all_projects_df
        
        # Filter by project name if specified
        if project_name:
            projects_df = projects_df[projects_df['project_name'] == project_name]
        
        if projects_df.empty:
            return {
                'type': 'error',
                'message': f'No projects found for criteria',
                'data': None
            }
        
        # If specific metric requested, extract that
        if metric:
            return self._extract_project_metrics(projects_df, metric)
        
        # Otherwise return general project details
        if len(projects_df) == 1:
            # Single project - show detailed info
            project_data = projects_df.iloc[0].to_dict()
            
            # Format key metrics
            key_metrics = {
                'Project Name': project_data.get('project_name', 'N/A'),
                'Company': f"{project_data.get('company_ticker', 'N/A')} - {project_data.get('company_name', 'N/A')}",
                'Location': project_data.get('location', 'N/A'),
                'Total Units': f"{project_data.get('total_units', 0):,.0f}",
                'Net Sellable Area': f"{project_data.get('net_sellable_area', 0):,.0f} sqm",
                'Average Selling Price': f"{project_data.get('average_selling_price', 0):,.0f} VND/sqm",
                'Construction Cost': f"{project_data.get('construction_cost_per_sqm', 0):,.0f} VND/sqm",
                'Land Cost': f"{project_data.get('land_cost_per_sqm', 0):,.0f} VND/sqm",
                'RNAV Value': f"{project_data.get('rnav_value', 0):,.1f} Billion VND" if project_data.get('rnav_value') else 'Not calculated',
                'Total Revenue': f"{project_data.get('total_revenue', 0):,.0f} Billion VND" if project_data.get('total_revenue') else 'N/A',
                'Gross Margin': self._calculate_gross_margin(project_data),
                'Construction Start': project_data.get('construction_start_year', 'N/A'),
                'Sales Start': project_data.get('sale_start_year', 'N/A'),
                'Completion Year': project_data.get('project_completion_year', 'N/A')
            }
            
            details_df = pd.DataFrame([
                {'Metric': key, 'Value': value}
                for key, value in key_metrics.items()
            ])
            
            return {
                'type': 'project_details',
                'message': f"Details for {project_data.get('project_name')}",
                'summary': f"Showing details for {project_data.get('project_name')}",
                'data': details_df,
                'raw_data': project_data
            }
        else:
            # Multiple projects - show summary table
            summary_df = projects_df[[
                'company_ticker', 'project_name', 'location', 
                'net_sellable_area', 'average_selling_price', 'rnav_value'
            ]].copy()
            
            # Format numbers
            summary_df['net_sellable_area'] = summary_df['net_sellable_area'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
            summary_df['average_selling_price'] = summary_df['average_selling_price'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
            summary_df['rnav_value'] = summary_df['rnav_value'].apply(lambda x: f"{x:,.1f}B" if pd.notna(x) else "N/A")
            
            return {
                'type': 'project_summary',
                'message': f"Found {len(summary_df)} projects",
                'summary': f"Showing {len(summary_df)} projects",
                'data': summary_df
            }
    
    def handle_calculate_metrics(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle metrics calculation request - now searches all projects"""
        tickers = entities.get('tickers', [])
        
        # Load all projects from MongoDB
        from .mongodb_utils import load_projects_data
        all_projects_df = load_projects_data()
        
        if all_projects_df.empty:
            return {
                'type': 'error',
                'message': 'No projects found in database',
                'data': None
            }
        
        # Filter by tickers if specified
        if tickers:
            projects_df = all_projects_df[all_projects_df['company_ticker'].isin(tickers)]
        else:
            projects_df = all_projects_df
        
        if projects_df.empty:
            return {
                'type': 'error',
                'message': 'No projects found for specified criteria',
                'data': None
            }
        
        # Calculate summary metrics
        metrics = {}
        
        if 'rnav_value' in projects_df.columns:
            metrics['Total RNAV'] = projects_df['rnav_value'].sum()
            metrics['Average RNAV'] = projects_df['rnav_value'].mean()
        
        if 'net_sellable_area' in projects_df.columns:
            metrics['Total NSA'] = projects_df['net_sellable_area'].sum()
        
        if 'average_selling_price' in projects_df.columns:
            metrics['Avg ASP'] = projects_df['average_selling_price'].mean()
        
        metrics['Total Projects'] = len(projects_df)
        
        # Create metrics display
        metrics_df = pd.DataFrame([
            {'Metric': key, 'Value': f"{value:,.0f}" if isinstance(value, (int, float)) else value}
            for key, value in metrics.items()
        ])
        
        return {
            'type': 'metrics',
            'message': 'Calculated portfolio metrics',
            'summary': f"Calculated {len(metrics)} metrics",
            'data': metrics_df,
            'metrics': metrics
        }
    
    def handle_update_project(self, entities: Dict[str, Any], query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle project update request"""
        return {
            'type': 'info',
            'message': 'Project update feature - Please use the Project Pipeline tab to modify projects',
            'summary': 'Use Pipeline tab for updates',
            'data': None
        }
    
    def _calculate_gross_margin(self, project_data: dict) -> str:
        """Calculate gross margin for a project"""
        try:
            asp = project_data.get('average_selling_price', 0)
            construction_cost = project_data.get('construction_cost_per_sqm', 0)
            land_cost = project_data.get('land_cost_per_sqm', 0)
            
            if asp > 0:
                total_cost = construction_cost + land_cost
                gross_margin = ((asp - total_cost) / asp) * 100
                return f"{gross_margin:.1f}%"
            return "N/A"
        except:
            return "N/A"
    
    def _extract_project_metrics(self, projects_df: pd.DataFrame, metric: str) -> Dict[str, Any]:
        """Extract specific metrics from projects"""
        metric_lower = metric.lower()
        
        if 'rnav' in metric_lower:
            # Extract RNAV information
            rnav_df = projects_df[['company_ticker', 'project_name', 'rnav_value']].copy()
            rnav_df = rnav_df[rnav_df['rnav_value'].notna()]
            rnav_df = rnav_df.sort_values('rnav_value', ascending=False)
            
            # Format values
            rnav_df['rnav_value'] = rnav_df['rnav_value'].apply(lambda x: f"{x:,.1f} Billion VND")
            
            # Find largest RNAV project
            if not rnav_df.empty:
                largest = rnav_df.iloc[0]
                message = f"Largest RNAV project: {largest['project_name']} ({largest['company_ticker']}) - {largest['rnav_value']}"
            else:
                message = "No RNAV values calculated yet"
            
            return {
                'type': 'metric_rnav',
                'message': message,
                'summary': f"RNAV analysis for {len(rnav_df)} projects",
                'data': rnav_df
            }
        
        elif 'gross margin' in metric_lower or 'margin' in metric_lower:
            # Calculate and show gross margins
            margins_data = []
            for _, project in projects_df.iterrows():
                margin = self._calculate_gross_margin(project.to_dict())
                if margin != "N/A":
                    margins_data.append({
                        'Company': project['company_ticker'],
                        'Project': project['project_name'],
                        'ASP': f"{project.get('average_selling_price', 0):,.0f}",
                        'Construction Cost': f"{project.get('construction_cost_per_sqm', 0):,.0f}",
                        'Land Cost': f"{project.get('land_cost_per_sqm', 0):,.0f}",
                        'Gross Margin': margin
                    })
            
            if margins_data:
                margins_df = pd.DataFrame(margins_data)
                # Sort by margin (extract percentage value)
                margins_df['margin_value'] = margins_df['Gross Margin'].str.replace('%', '').astype(float)
                margins_df = margins_df.sort_values('margin_value', ascending=False)
                margins_df = margins_df.drop('margin_value', axis=1)
                
                best_margin = margins_df.iloc[0]
                message = f"Highest gross margin: {best_margin['Project']} ({best_margin['Company']}) - {best_margin['Gross Margin']}"
            else:
                margins_df = pd.DataFrame()
                message = "No gross margin data available"
            
            return {
                'type': 'metric_gross_margin',
                'message': message,
                'summary': f"Gross margin analysis for {len(margins_df)} projects",
                'data': margins_df
            }
        
        elif 'presales' in metric_lower or 'presale' in metric_lower:
            # Extract presales information
            presales_data = []
            for _, project in projects_df.iterrows():
                presales_dist = project.get('presales_distribution', {})
                if presales_dist:
                    total_presales = sum(float(v) for v in presales_dist.values())
                    presales_years = list(presales_dist.keys())
                    presales_data.append({
                        'Company': project['company_ticker'],
                        'Project': project['project_name'],
                        'Presales Start': min(presales_years) if presales_years else 'N/A',
                        'Presales End': max(presales_years) if presales_years else 'N/A',
                        'Total Presales %': f"{total_presales:.0f}%",
                        'Years': len(presales_years)
                    })
            
            if presales_data:
                presales_df = pd.DataFrame(presales_data)
                message = f"Found presales data for {len(presales_df)} projects"
            else:
                presales_df = pd.DataFrame()
                message = "No presales data available"
            
            return {
                'type': 'metric_presales',
                'message': message,
                'summary': f"Presales analysis for {len(presales_data)} projects",
                'data': presales_df
            }
        
        elif 'units' in metric_lower or 'unit' in metric_lower:
            # Extract unit information
            units_df = projects_df[['company_ticker', 'project_name', 'total_units', 'average_unit_size']].copy()
            units_df = units_df[units_df['total_units'].notna()]
            units_df = units_df.sort_values('total_units', ascending=False)
            
            # Format values
            units_df['total_units'] = units_df['total_units'].apply(lambda x: f"{x:,.0f}")
            units_df['average_unit_size'] = units_df['average_unit_size'].apply(lambda x: f"{x:,.0f} sqm" if pd.notna(x) else "N/A")
            
            if not units_df.empty:
                largest = units_df.iloc[0]
                message = f"Largest project by units: {largest['project_name']} ({largest['company_ticker']}) - {largest['total_units']} units"
            else:
                message = "No unit data available"
            
            return {
                'type': 'metric_units',
                'message': message,
                'summary': f"Unit analysis for {len(units_df)} projects",
                'data': units_df
            }
        
        elif 'asp' in metric_lower or 'average selling price' in metric_lower or 'price' in metric_lower:
            # Extract ASP information
            asp_df = projects_df[['company_ticker', 'project_name', 'location', 'average_selling_price']].copy()
            asp_df = asp_df[asp_df['average_selling_price'].notna()]
            asp_df = asp_df.sort_values('average_selling_price', ascending=False)
            
            # Format values
            asp_df['average_selling_price'] = asp_df['average_selling_price'].apply(lambda x: f"{x:,.0f} VND/sqm")
            
            if not asp_df.empty:
                highest = asp_df.iloc[0]
                message = f"Highest ASP: {highest['project_name']} ({highest['company_ticker']}) - {highest['average_selling_price']}"
            else:
                message = "No ASP data available"
            
            return {
                'type': 'metric_asp',
                'message': message,
                'summary': f"ASP analysis for {len(asp_df)} projects",
                'data': asp_df
            }
        
        else:
            # Generic metric extraction
            return {
                'type': 'metric_generic',
                'message': f"Metric '{metric}' not specifically handled",
                'summary': f"Showing {len(projects_df)} projects",
                'data': projects_df[['company_ticker', 'project_name', 'location']]
            }
    
    def handle_general_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle general queries using Claude if available"""
        if self.anthropic_client:
            try:
                # Prepare context information
                context_info = f"""
                Current Company: {context.get('selected_company', 'None')}
                Projects Loaded: {len(context.get('project_data', [])) if context.get('project_data') is not None else 0}
                """
                
                response = self.anthropic_client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=500,
                    messages=[{
                        "role": "user",
                        "content": f"""You are a financial analyst AI assistant. 
                        Context: {context_info}
                        User Query: {query}
                        
                        Provide a helpful response. If the query requires specific data or actions,
                        suggest what the user should do."""
                    }]
                )
                
                return {
                    'type': 'general_response',
                    'message': response.content[0].text,
                    'summary': response.content[0].text[:100],
                    'data': None
                }
            except Exception as e:
                pass
        
        # Fallback response
        help_message = """I can help you with:
• List all projects
• Rank projects by RNAV
• Suggest parameters for projects
• Analyze growth trends
• Calculate portfolio metrics

Try asking: "Show all projects" or "What's the largest RNAV?" """
        
        return {
            'type': 'info',
            'message': help_message,
            'summary': 'Help message',
            'data': None
        }