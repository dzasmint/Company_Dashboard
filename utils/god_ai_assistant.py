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
        
        # Extract project names
        if context.get('project_data') is not None:
            projects = context['project_data']
            if isinstance(projects, pd.DataFrame) and not projects.empty:
                for project_name in projects['project_name'].unique():
                    if project_name.lower() in query.lower():
                        entities['project_name'] = project_name
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
        
        # Extract metrics
        metrics = ['rnav', 'revenue', 'asp', 'nsa', 'construction cost', 'land cost']
        for metric in metrics:
            if metric in query.lower():
                entities['metric'] = metric
                break
        
        return entities
    
    def execute_action(self, intent: str, entities: Dict[str, Any], query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action based on intent"""
        
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
        """Handle project listing request"""
        company = context.get('selected_company')
        
        if not company:
            return {
                'type': 'error',
                'message': 'Please select a company first',
                'data': None
            }
        
        # Get projects from context or MongoDB
        projects_df = context.get('project_data')
        
        if projects_df is None or projects_df.empty:
            # Try to load from MongoDB
            projects = self.mongo_helper.get_real_estate_projects(company)
            if projects:
                projects_df = pd.DataFrame(projects)
            else:
                return {
                    'type': 'info',
                    'message': f'No projects found for {company}. Use AI Project Discovery to find projects.',
                    'data': None
                }
        
        # Prepare display data
        display_columns = ['project_name', 'location', 'net_sellable_area', 
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
            'message': f"Found {len(display_df)} projects for {company}",
            'summary': f"Showing {len(display_df)} projects",
            'data': display_df
        }
    
    def handle_rank_projects(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle project ranking request"""
        projects_df = context.get('project_data')
        
        if projects_df is None or projects_df.empty:
            return {
                'type': 'error',
                'message': 'No project data available. Please load projects first.',
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
        display_columns = ['project_name', 'location', 'rnav_value', 'net_sellable_area', 'average_selling_price']
        available_columns = [col for col in display_columns if col in top_projects.columns]
        display_df = top_projects[available_columns].copy()
        
        # Add ranking
        display_df.insert(0, 'Rank', range(1, len(display_df) + 1))
        
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
        """Handle growth analysis request"""
        projects_df = context.get('project_data')
        
        if projects_df is None or projects_df.empty:
            return {
                'type': 'error',
                'message': 'No project data available for analysis',
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
        
        return {
            'type': 'growth_analysis',
            'message': f"Growth analysis complete. Peak growth in {peak_growth_year} at {peak_growth_rate:.1f}%",
            'summary': f"Peak: {peak_growth_year} ({peak_growth_rate:.1f}%)",
            'data': pd.DataFrame(growth_data),
            'chart': fig,
            'peak_year': peak_growth_year,
            'growth_rate': peak_growth_rate / 100,
            'top_project': top_contributor['project'] if top_contributor else 'N/A',
            'revenue_impact': top_contributor['revenue'] if top_contributor else 0
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
        """Handle project details request"""
        project_name = entities.get('project_name')
        projects_df = context.get('project_data')
        
        if not project_name or projects_df is None:
            return {
                'type': 'error',
                'message': 'Please specify a project name',
                'data': None
            }
        
        # Find project
        project = projects_df[projects_df['project_name'] == project_name]
        
        if project.empty:
            return {
                'type': 'error',
                'message': f'Project {project_name} not found',
                'data': None
            }
        
        # Get project details
        project_data = project.iloc[0].to_dict()
        
        # Format for display
        details_df = pd.DataFrame([
            {'Attribute': key, 'Value': value}
            for key, value in project_data.items()
            if not isinstance(value, (dict, list))
        ])
        
        return {
            'type': 'project_details',
            'message': f"Details for {project_name}",
            'summary': f"Showing details for {project_name}",
            'data': details_df
        }
    
    def handle_calculate_metrics(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle metrics calculation request"""
        projects_df = context.get('project_data')
        
        if projects_df is None or projects_df.empty:
            return {
                'type': 'error',
                'message': 'No project data available for calculations',
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