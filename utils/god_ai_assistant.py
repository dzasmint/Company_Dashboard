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
                'what projects', 'get projects', 'show me projects',
                'projects from', 'projects for', 'kdh projects', 'nlg projects',
                'vhm projects', 'dxg projects'
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
            
            # Extract entities from query (this will include extraction debug)
            entities, extraction_debug = self.extract_entities_with_debug(query, context)
            
            # Build comprehensive debug info
            debug_info = []
            debug_info.append("="*50)
            debug_info.append("🔍 **GOD AI DEBUG INFORMATION**")
            debug_info.append("="*50)
            debug_info.append(f"**Query:** '{query}'")
            debug_info.append(f"**Intent Classified:** {intent}")
            
            # Add extraction debug details
            debug_info.extend(extraction_debug)
            
            debug_info.append(f"\n**Extracted Entities Summary:**")
            debug_info.append(f"  - Tickers: {entities.get('tickers', 'None')}")
            debug_info.append(f"  - Metric: {entities.get('metric', 'None')}")
            debug_info.append(f"  - Project Name: {entities.get('project_name', 'None')}")
            debug_info.append(f"  - Years: {entities.get('years', 'None')}")
            debug_info.append(f"\n**Context:**")
            debug_info.append(f"  - Selected Company: {context.get('selected_company', 'None')}")
            debug_info.append(f"  - Has Project Data: {'Yes' if context.get('project_data') is not None else 'No'}")
            debug_info.append("="*50)
            
            # Execute appropriate action
            result = self.execute_action(intent, entities, query, context)
            
            # Prepend debug info to the result message
            if result.get('message'):
                result['message'] = "\n".join(debug_info) + "\n\n" + result['message']
            else:
                result['message'] = "\n".join(debug_info)
            
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
        """Classify user intent using Claude AI for intelligent understanding"""
        
        # Use Claude Sonnet for intelligent intent classification
        if self.anthropic_client:
            try:
                response = self.anthropic_client.messages.create(
                    model="claude-3-5-sonnet-20241022",  # Use Sonnet for better understanding
                    max_tokens=200,
                    temperature=0,  # Deterministic for consistent routing
                    messages=[{
                        "role": "user",
                        "content": f"""Analyze this user query and classify it into the most appropriate intent.

User Query: "{query}"

Available intents and their purposes:
- LIST_PROJECTS: User wants to see/list/display projects for one or more companies
- PROJECT_DETAILS: User asks about specific project details, metrics, or financial data (revenue, profit, margins, ASP, etc.) for specific projects
- RANK_PROJECTS: User wants to rank/sort/find top/highest/largest/best projects by some metric (e.g., "which project has highest gross margin", "top 5 by revenue", "largest RNAV")
- COMPARE_PROJECTS: User wants to compare specific projects side-by-side (e.g., "compare Project A vs Project B", "compare margins between X and Y")
- CALCULATE_METRICS: User wants to calculate aggregate metrics across multiple projects or portfolio-level calculations
- ANALYZE_GROWTH: User asks about growth trends, revenue progression over time, or year-over-year analysis
- CREATE_CHART: User wants to chart/plot/visualize/graph financial data (revenue, presales, NPATMI, P&L) over time for one or more projects
- SUGGEST_PARAMETERS: User needs AI suggestions for project parameters like ASP or construction costs
- RESEARCH_INSIGHTS: User wants market research, news, or external insights
- UPDATE_PROJECT: User wants to modify or update project data
- GENERAL_QUERY: General questions that don't fit other categories

Important distinctions:
- If user asks "which project has the highest/largest/best X" or "rank by X" → RANK_PROJECTS
- If user asks "what is the X of project Y" → PROJECT_DETAILS
- If user asks to "compare X vs Y" or "compare between" specific projects → COMPARE_PROJECTS
- If user asks about comparing or ranking all/multiple projects → RANK_PROJECTS
- If user asks to "chart", "plot", "visualize", "graph" any financial metric → CREATE_CHART

Respond with ONLY the intent name."""
                    }]
                )
                intent = response.content[0].text.strip().upper()
                
                # Validate the intent
                valid_intents = [
                    'LIST_PROJECTS', 'PROJECT_DETAILS', 'RANK_PROJECTS', 
                    'CALCULATE_METRICS', 'ANALYZE_GROWTH', 'CREATE_CHART',
                    'SUGGEST_PARAMETERS', 'RESEARCH_INSIGHTS', 'UPDATE_PROJECT', 
                    'GENERAL_QUERY'
                ]
                
                if intent in valid_intents:
                    return intent
                    
            except Exception as e:
                # Log error but continue with fallback
                pass
        
        # Fallback to simple pattern matching if Claude is not available
        query_lower = query.lower()
        
        # Quick fallback patterns
        if any(word in query_lower for word in ['chart', 'plot', 'visualize', 'graph', 'draw']):
            return 'CREATE_CHART'
        elif any(word in query_lower for word in ['list', 'show', 'display', 'what projects']):
            return 'LIST_PROJECTS'
        elif any(word in query_lower for word in ['revenue', 'profit', 'margin', 'asp', 'cost', 'financial']):
            return 'PROJECT_DETAILS'
        elif any(word in query_lower for word in ['rank', 'top', 'largest', 'biggest', 'best']):
            return 'RANK_PROJECTS'
        elif any(word in query_lower for word in ['growth', 'trend', 'over time', 'progression']):
            return 'ANALYZE_GROWTH'
        
        return 'GENERAL_QUERY'
    
    def extract_entities_with_debug(self, query: str, context: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """Extract entities from query and return debug info"""
        entities, debug_msgs = self._extract_entities_internal(query, context, with_debug=True)
        return entities, debug_msgs
    
    def extract_entities(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract entities from query (backward compatible)"""
        entities, _ = self._extract_entities_internal(query, context, with_debug=False)
        return entities
    
    def _extract_entities_internal(self, query: str, context: Dict[str, Any], with_debug: bool = False) -> Tuple[Dict[str, Any], List[str]]:
        """Extract entities from query"""
        entities = {}
        extraction_debug = []
        extraction_debug.append("\n🔎 **ENTITY EXTRACTION**")
        extraction_debug.append(f"Query: '{query}'")
        
        # Extract ticker symbols (e.g., DXG, NLG, VHM, KDH, etc.)
        ticker_pattern = r'\b([A-Z]{3,4})\b'
        potential_tickers = re.findall(ticker_pattern, query)
        extraction_debug.append(f"Potential tickers found: {potential_tickers}")
        
        if potential_tickers:
            valid_tickers = []
            
            # Load tickers from CSV files for validation
            try:
                # Try to load from financial statements CSV
                import os
                import sys
                from pathlib import Path
                
                # Add parent directory to path for imports
                current_dir = Path(__file__).parent.parent
                sys.path.append(str(current_dir))
                
                # Load financial data to get all valid tickers
                csv_path = current_dir / 'data' / 'FA_A_processed.csv'
                if csv_path.exists():
                    df_fa = pd.read_csv(csv_path)
                    if 'TICKER' in df_fa.columns:
                        csv_tickers = set(df_fa['TICKER'].unique())
                    else:
                        csv_tickers = set()
                else:
                    csv_tickers = set()
                
                # Also check Val_processed.csv for additional tickers
                val_csv_path = current_dir / 'data' / 'Val_processed.csv'
                if val_csv_path.exists():
                    df_val = pd.read_csv(val_csv_path)
                    if 'TICKER' in df_val.columns:
                        csv_tickers.update(df_val['TICKER'].unique())
                
                # Validate potential tickers against CSV data
                for ticker in potential_tickers:
                    # Accept ticker if it's in CSV files
                    if ticker in csv_tickers:
                        if ticker not in valid_tickers:  # Avoid duplicates
                            valid_tickers.append(ticker)
                    # Also accept if it looks like a valid ticker format (fallback)
                    elif len(ticker) in [3, 4] and ticker.isupper():
                        if ticker not in valid_tickers:
                            valid_tickers.append(ticker)
                
            except Exception as e:
                # If CSV loading fails, accept any 3-4 letter uppercase string
                for ticker in potential_tickers:
                    if len(ticker) in [3, 4] and ticker.isupper():
                        if ticker not in valid_tickers:
                            valid_tickers.append(ticker)
            
            extraction_debug.append(f"Valid tickers after validation: {valid_tickers}")
            if valid_tickers:
                entities['tickers'] = valid_tickers
        
        # Extract project names - search across ALL projects in MongoDB
        extraction_debug.append("Searching for project names in query...")
        from .mongodb_utils import load_projects_data
        all_projects_df = load_projects_data()
        matched_projects = []
        if not all_projects_df.empty:
            for project_name in all_projects_df['project_name'].unique():
                if project_name and project_name.lower() in query.lower():
                    matched_projects.append(project_name)
                    extraction_debug.append(f"Found project name: {project_name}")
                    # Also extract the ticker for this project
                    project_ticker = all_projects_df[all_projects_df['project_name'] == project_name]['company_ticker'].iloc[0]
                    if 'tickers' not in entities:
                        entities['tickers'] = []
                    if project_ticker not in entities.get('tickers', []):
                        entities['tickers'].append(project_ticker)
                        extraction_debug.append(f"Added ticker {project_ticker} from project")
            
            # Store project names based on how many were found
            if matched_projects:
                if len(matched_projects) == 1:
                    entities['project_name'] = matched_projects[0]
                else:
                    # Multiple projects for comparison
                    entities['project_names'] = matched_projects
                    entities['project_name'] = matched_projects[0]  # Keep first as default
                    extraction_debug.append(f"Multiple projects detected for comparison: {matched_projects}")
        
        # Extract years
        year_pattern = r'\b(20\d{2})\b'
        years = re.findall(year_pattern, query)
        if years:
            entities['years'] = [int(y) for y in years]
            extraction_debug.append(f"Years found: {entities['years']}")
        
        # Extract numbers
        number_pattern = r'\b(\d+(?:\.\d+)?)\b'
        numbers = re.findall(number_pattern, query)
        if numbers:
            entities['numbers'] = [float(n) for n in numbers]
        
        # Extract detailed metrics - expanded list
        # Check for multi-word metrics first, then single words
        query_lower = query.lower()
        metrics = [
            # Multi-word metrics first (more specific)
            'gross margin', 'net margin', 'profit margin',
            'total revenue', 'net profit', 'net income', 
            'average selling price', 'net sellable area',
            'construction cost', 'land cost', 'gross floor area',
            'number of units', 'total units', 'presales period',
            'revenue booking', 'all metrics',
            # Single word metrics
            'rnav', 'revenue', 'sales', 'asp', 'nsa', 
            'presales', 'presale', 'booking',
            'units', 'gfa', 'land area', 'sga', 'interest', 'debt', 
            'pat', 'profit', 'pbt', 'ebitda', 'npatmi',
            'financial', 'summary', 'overview', 'trends', 'margin'
        ]
        
        metric_found = None
        for metric in metrics:
            if metric in query_lower:
                metric_found = metric
                extraction_debug.append(f"Metric detected: {metric}")
                break
        
        if metric_found:
            entities['metric'] = metric_found
            extraction_debug.append(f"Final metric set to: {metric_found}")
        else:
            extraction_debug.append("No specific metric found in query")
        
        # Extract chart type for visualization requests
        if any(word in query_lower for word in ['chart', 'plot', 'visualize', 'graph']):
            # Determine what to chart based on metrics mentioned
            if 'revenue' in query_lower:
                entities['chart_type'] = 'revenue'
            elif 'presales' in query_lower or 'presale' in query_lower:
                entities['chart_type'] = 'presales'
            elif 'npatmi' in query_lower or 'net profit' in query_lower or 'pat' in query_lower:
                entities['chart_type'] = 'npatmi'
            elif 'pnl' in query_lower or 'p&l' in query_lower:
                entities['chart_type'] = 'pnl'
            else:
                entities['chart_type'] = 'combined'  # Default to showing all metrics
            extraction_debug.append(f"Chart type detected: {entities['chart_type']}")
        
        extraction_debug.append(f"Final entities extracted: {entities}")
        
        return entities, extraction_debug
    
    def execute_action(self, intent: str, entities: Dict[str, Any], query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action based on intent with intelligent routing"""
        
        routing_debug = []
        routing_debug.append("\n🚦 **ROUTING DECISION**")
        routing_debug.append(f"Claude AI Intent: {intent}")
        
        # Special handling for PROJECT_DETAILS - it should handle all metric-specific queries
        if intent == 'PROJECT_DETAILS':
            # This handles revenue, profit, margins, ASP, presales, etc.
            routing_debug.append("→ PROJECT_DETAILS: Handling financial metrics query")
            result = self.handle_project_details(entities, context)
        
        elif intent == 'LIST_PROJECTS':
            routing_debug.append("→ LIST_PROJECTS: Showing project list")
            result = self.handle_list_projects(entities, context)
        
        elif intent == 'RANK_PROJECTS':
            routing_debug.append("→ RANK_PROJECTS: Ranking projects by metric")
            result = self.handle_rank_projects(entities, context)
        
        elif intent == 'COMPARE_PROJECTS':
            routing_debug.append("→ COMPARE_PROJECTS: Comparing specific projects")
            result = self.handle_compare_projects(entities, context)
        
        elif intent == 'CALCULATE_METRICS':
            routing_debug.append("→ CALCULATE_METRICS: Calculating aggregate metrics")
            result = self.handle_calculate_metrics(entities, context)
        
        elif intent == 'ANALYZE_GROWTH':
            routing_debug.append("→ ANALYZE_GROWTH: Analyzing growth trends")
            result = self.handle_growth_analysis(entities, context)
        
        elif intent == 'CREATE_CHART':
            routing_debug.append("→ CREATE_CHART: Creating financial charts")
            result = self.handle_create_chart(entities, context)
        
        elif intent == 'SUGGEST_PARAMETERS':
            routing_debug.append("→ SUGGEST_PARAMETERS: Getting AI suggestions")
            result = self.handle_suggest_parameters(entities, query, context)
        
        elif intent == 'RESEARCH_INSIGHTS':
            routing_debug.append("→ RESEARCH_INSIGHTS: Fetching market insights")
            result = self.handle_research_insights(entities, query, context)
        
        elif intent == 'UPDATE_PROJECT':
            routing_debug.append("→ UPDATE_PROJECT: Updating project data")
            result = self.handle_update_project(entities, query, context)
        
        elif intent == 'GENERAL_QUERY':
            # Check if there's a metric that needs to be extracted
            metric = entities.get('metric')
            if metric:
                routing_debug.append(f"→ GENERAL_QUERY with metric '{metric}' → PROJECT_DETAILS")
                result = self.handle_project_details(entities, context)
            else:
                routing_debug.append("→ GENERAL_QUERY: Using general handler")
                result = self.handle_general_query(query, context)
        
        else:
            # Fallback
            routing_debug.append(f"→ Unknown intent '{intent}' → Using general handler")
            result = self.handle_general_query(query, context)
        
        # Prepend routing debug to result
        if result.get('message'):
            result['message'] = '\n'.join(routing_debug) + '\n' + result['message']
        
        return result
    
    def handle_list_projects(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle project listing request - now supports querying any ticker"""
        debug_msg = []
        debug_msg.append("\n📊 **LIST PROJECTS HANDLER**")
        
        tickers = entities.get('tickers', [])
        debug_msg.append(f"Tickers from entities: {tickers}")
        
        # If no tickers extracted from query, fall back to selected company
        if not tickers:
            company = context.get('selected_company')
            debug_msg.append(f"No tickers in entities, checking context...")
            debug_msg.append(f"Selected company from context: {company}")
            if company:
                tickers = [company]
                debug_msg.append(f"Using selected company as ticker: {tickers}")
        
        # Load all projects from MongoDB
        debug_msg.append("Loading all projects from MongoDB...")
        from .mongodb_utils import load_projects_data
        all_projects_df = load_projects_data()
        
        debug_msg.append(f"Total projects loaded from MongoDB: {len(all_projects_df)}")
        
        if all_projects_df.empty:
            return {
                'type': 'info',
                'message': '\n'.join(debug_msg) + '\n\n❌ No projects found in database',
                'data': None
            }
        
        # Show available tickers in database
        available_tickers = sorted(all_projects_df['company_ticker'].unique())
        debug_msg.append(f"Available tickers in database: {available_tickers}")
        
        # Filter by tickers if specified
        if tickers:
            debug_msg.append(f"Filtering projects for tickers: {tickers}")
            projects_df = all_projects_df[all_projects_df['company_ticker'].isin(tickers)]
            company_names = ', '.join(tickers)
            debug_msg.append(f"Projects after filtering: {len(projects_df)}")
        else:
            projects_df = all_projects_df
            company_names = 'all companies'
            debug_msg.append(f"No ticker filter applied, showing all {len(projects_df)} projects")
        
        if projects_df.empty:
            return {
                'type': 'info',
                'message': '\n'.join(debug_msg) + f'\n\n❌ No projects found for {company_names}',
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
        
        debug_msg.append(f"✅ Successfully prepared {len(display_df)} projects for display")
        
        return {
            'type': 'project_list',
            'message': '\n'.join(debug_msg) + f"\n\n✅ Found {len(display_df)} projects for {company_names}",
            'summary': f"Showing {len(display_df)} projects",
            'data': display_df
        }
    
    def handle_rank_projects(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle project ranking request - now searches all projects in MongoDB"""
        debug_msg = []
        debug_msg.append("\n🏆 **RANK PROJECTS HANDLER**")
        
        tickers = entities.get('tickers', [])
        metric = entities.get('metric', None)
        
        debug_msg.append(f"Entities received: {entities}")
        debug_msg.append(f"Tickers: {tickers}")
        debug_msg.append(f"Metric from entities: {metric}")
        
        # If no metric was extracted, default to rnav
        if not metric:
            metric = 'rnav'
            debug_msg.append("⚠️ No metric found in entities, defaulting to RNAV")
        else:
            debug_msg.append(f"✅ Using metric: {metric}")
        
        # Load all projects from MongoDB
        from .mongodb_utils import load_projects_data
        all_projects_df = load_projects_data()
        
        if all_projects_df.empty:
            return {
                'type': 'error',
                'message': '\n'.join(debug_msg) + '\n\n❌ No projects found in database',
                'data': None
            }
        
        # Filter by tickers if specified
        if tickers:
            projects_df = all_projects_df[all_projects_df['company_ticker'].isin(tickers)]
            debug_msg.append(f"Filtered to {len(projects_df)} projects for tickers: {tickers}")
        else:
            projects_df = all_projects_df
            debug_msg.append(f"Using all {len(projects_df)} projects")
        
        if projects_df.empty:
            return {
                'type': 'error',
                'message': '\n'.join(debug_msg) + '\n\n❌ No projects found for specified criteria',
                'data': None
            }
        
        # Calculate gross margin if needed
        metric_lower = str(metric).lower() if metric else ''
        if 'gross margin' in metric_lower or ('margin' in metric_lower and 'net' not in metric_lower and 'profit' not in metric_lower):
            debug_msg.append("📊 Calculating gross margins for ranking...")
            # Calculate gross margin for each project
            projects_df = projects_df.copy()
            gross_margins = []
            for _, project in projects_df.iterrows():
                gross_margin = self._calculate_gross_margin(project.to_dict())
                # Extract numeric value from percentage string
                if gross_margin != 'N/A':
                    margin_value = float(gross_margin.replace('%', ''))
                else:
                    margin_value = 0
                gross_margins.append(margin_value)
            projects_df['gross_margin_value'] = gross_margins
            sorted_df = projects_df.sort_values('gross_margin_value', ascending=False, na_position='last')
            metric_display = 'Gross Margin'
            if len(sorted_df) > 0 and 'gross_margin_value' in sorted_df.columns:
                debug_msg.append(f"✅ Sorted by gross margin (highest: {sorted_df.iloc[0]['gross_margin_value']:.1f}%)")
            else:
                debug_msg.append("⚠️ No valid gross margin values found")
        
        # Handle net margin / profit margin
        elif 'net margin' in metric_lower or 'profit margin' in metric_lower:
            debug_msg.append("📊 Calculating net margins for ranking...")
            projects_df = projects_df.copy()
            net_margins = []
            for _, project in projects_df.iterrows():
                total_revenue = project.get('total_revenue', 0)
                if total_revenue == 0:
                    # Calculate from NSA and ASP
                    nsa = project.get('net_sellable_area', 0)
                    asp = project.get('average_selling_price', 0)
                    total_revenue = (nsa * asp) / 1e9
                
                total_pat = project.get('total_pat', 0)
                net_margin = (total_pat / total_revenue * 100) if total_revenue > 0 else 0
                net_margins.append(net_margin)
            
            projects_df['net_margin_value'] = net_margins
            sorted_df = projects_df.sort_values('net_margin_value', ascending=False, na_position='last')
            metric_display = 'Net Margin'
            if len(sorted_df) > 0:
                debug_msg.append(f"✅ Sorted by net margin (highest: {sorted_df.iloc[0]['net_margin_value']:.1f}%)")
        
        # Handle other metrics
        elif any(word in str(metric).lower() for word in ['revenue', 'sales']):
            if 'total_revenue' in projects_df.columns:
                sorted_df = projects_df.sort_values('total_revenue', ascending=False, na_position='last')
                metric_display = 'Total Revenue'
            else:
                # Calculate from NSA and ASP
                projects_df = projects_df.copy()
                projects_df['calculated_revenue'] = (projects_df['net_sellable_area'] * projects_df['average_selling_price']) / 1e9
                sorted_df = projects_df.sort_values('calculated_revenue', ascending=False, na_position='last')
                metric_display = 'Total Revenue (Calculated)'
            debug_msg.append(f"Sorted by {metric_display}")
        
        elif any(word in str(metric).lower() for word in ['profit', 'pat', 'net profit', 'net income']):
            if 'total_pat' in projects_df.columns:
                sorted_df = projects_df.sort_values('total_pat', ascending=False, na_position='last')
                metric_display = 'Net Profit (PAT)'
            else:
                sorted_df = projects_df
                metric_display = 'Net Profit (N/A)'
            debug_msg.append(f"Sorted by {metric_display}")
        
        elif any(word in str(metric).lower() for word in ['nsa', 'net sellable area', 'area']):
            sorted_df = projects_df.sort_values('net_sellable_area', ascending=False, na_position='last')
            metric_display = 'Net Sellable Area'
            debug_msg.append(f"Sorted by {metric_display}")
        
        elif any(word in str(metric).lower() for word in ['asp', 'average selling price', 'price']):
            sorted_df = projects_df.sort_values('average_selling_price', ascending=False, na_position='last')
            metric_display = 'Average Selling Price'
            debug_msg.append(f"Sorted by {metric_display}")
        
        elif 'rnav' in str(metric).lower():
            if 'rnav_value' in projects_df.columns:
                sorted_df = projects_df.sort_values('rnav_value', ascending=False, na_position='last')
                metric_display = 'RNAV Value'
            else:
                sorted_df = projects_df
                metric_display = 'RNAV (Not Calculated)'
            debug_msg.append(f"Sorted by {metric_display}")
        
        else:
            # Default to RNAV
            if 'rnav_value' in projects_df.columns:
                sorted_df = projects_df.sort_values('rnav_value', ascending=False, na_position='last')
                metric_display = 'RNAV Value (Default)'
            else:
                sorted_df = projects_df
                metric_display = 'Default Order'
            debug_msg.append(f"No specific metric found, defaulting to {metric_display}")
        
        # Get top 10
        top_projects = sorted_df.head(10)
        debug_msg.append(f"Selected top {len(top_projects)} projects")
        
        # Prepare display columns based on metric type
        if 'margin' in metric_display.lower():
            # For margin ranking, show margin-related columns
            display_columns = ['company_ticker', 'project_name', 'location']
            # Add gross margin column
            if 'gross_margin_value' in top_projects.columns:
                display_columns.append('gross_margin_value')
            # Add revenue and cost columns for context
            if 'total_revenue' in top_projects.columns:
                display_columns.append('total_revenue')
            elif 'calculated_revenue' in top_projects.columns:
                display_columns.append('calculated_revenue')
            display_columns.extend(['net_sellable_area', 'average_selling_price'])
        elif 'revenue' in metric_display.lower():
            display_columns = ['company_ticker', 'project_name', 'location', 'total_revenue', 'net_sellable_area', 'average_selling_price']
        elif 'profit' in metric_display.lower():
            display_columns = ['company_ticker', 'project_name', 'location', 'total_pat', 'total_revenue', 'net_sellable_area']
        else:
            # Default columns
            display_columns = ['company_ticker', 'project_name', 'location', 'rnav_value', 'net_sellable_area', 'average_selling_price']
        
        available_columns = [col for col in display_columns if col in top_projects.columns]
        display_df = top_projects[available_columns].copy()
        
        # Add ranking
        display_df.insert(0, 'Rank', range(1, len(display_df) + 1))
        
        # Format numbers and add special columns
        if 'gross_margin_value' in display_df.columns:
            display_df['Gross Margin'] = display_df['gross_margin_value'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) and x > 0 else "N/A")
            display_df = display_df.drop('gross_margin_value', axis=1)
        
        if 'net_sellable_area' in display_df.columns:
            display_df['NSA (sqm)'] = display_df['net_sellable_area'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
            display_df = display_df.drop('net_sellable_area', axis=1)
            
        if 'average_selling_price' in display_df.columns:
            display_df['ASP (VND/sqm)'] = display_df['average_selling_price'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
            display_df = display_df.drop('average_selling_price', axis=1)
            
        if 'rnav_value' in display_df.columns:
            display_df['RNAV (B VND)'] = display_df['rnav_value'].apply(lambda x: f"{x:,.1f}" if pd.notna(x) else "N/A")
            display_df = display_df.drop('rnav_value', axis=1)
            
        if 'total_revenue' in display_df.columns:
            display_df['Revenue (B VND)'] = display_df['total_revenue'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) and x > 0 else "N/A")
            display_df = display_df.drop('total_revenue', axis=1)
            
        if 'calculated_revenue' in display_df.columns:
            display_df['Revenue (B VND)'] = display_df['calculated_revenue'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) and x > 0 else "N/A")
            display_df = display_df.drop('calculated_revenue', axis=1)
            
        if 'total_pat' in display_df.columns:
            display_df['PAT (B VND)'] = display_df['total_pat'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
            display_df = display_df.drop('total_pat', axis=1)
        
        # Rename columns for display
        display_df = display_df.rename(columns={
            'company_ticker': 'Ticker',
            'project_name': 'Project Name',
            'location': 'Location'
        })
        
        return {
            'type': 'ranked_projects',
            'message': '\n'.join(debug_msg) + f"\n\n✅ Top {len(display_df)} projects ranked by {metric_display}",
            'summary': f"Ranked {len(display_df)} projects by {metric_display}",
            'data': display_df,
            'metric': metric_display
        }
    
    def handle_compare_projects(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle comparison between specific projects"""
        debug_msg = []
        debug_msg.append("\n📊 **COMPARE PROJECTS HANDLER**")
        
        # Load all projects from MongoDB
        from .mongodb_utils import load_projects_data
        all_projects_df = load_projects_data()
        
        if all_projects_df.empty:
            return {
                'type': 'error',
                'message': '❌ No projects found in database',
                'data': None
            }
        
        # Get project names from entities
        project_names = entities.get('project_names', [])
        if not project_names:
            # Try to extract from context or use default
            project_name = entities.get('project_name')
            if project_name:
                project_names = [project_name]
            else:
                # Default to comparing top projects
                project_names = all_projects_df.head(3)['project_name'].tolist()
                debug_msg.append(f"No specific projects mentioned, comparing top 3 projects")
        
        debug_msg.append(f"Comparing projects: {', '.join(project_names)}")
        
        # Filter projects for comparison
        compare_df = all_projects_df[all_projects_df['project_name'].isin(project_names)]
        
        if compare_df.empty:
            return {
                'type': 'error', 
                'message': f'❌ Projects not found: {", ".join(project_names)}',
                'data': None
            }
        
        # Create comprehensive comparison data
        comparison_data = []
        for _, project in compare_df.iterrows():
            project_dict = project.to_dict()
            
            # Calculate key metrics
            total_revenue = project_dict.get('total_revenue', 0)
            if total_revenue == 0:
                nsa = project_dict.get('net_sellable_area', 0)
                asp = project_dict.get('average_selling_price', 0)
                if nsa > 0 and asp > 0:
                    total_revenue = (nsa * asp) / 1e9
            
            total_construction_cost = project_dict.get('total_construction_cost', 0)
            total_land_cost = project_dict.get('total_land_cost', 0)
            
            if total_construction_cost == 0 or total_land_cost == 0:
                gfa = project_dict.get('gross_floor_area', 0)
                land_area = project_dict.get('land_area', 0)
                
                if total_construction_cost == 0 and gfa > 0:
                    construction_cost_per_sqm = project_dict.get('construction_cost_per_sqm', 0)
                    total_construction_cost = (construction_cost_per_sqm * gfa) / 1e9
                
                if total_land_cost == 0 and land_area > 0:
                    land_cost_per_sqm = project_dict.get('land_cost_per_sqm', 0)
                    total_land_cost = (land_cost_per_sqm * land_area) / 1e9
            
            # Calculate gross margin
            gross_margin = 0
            if total_revenue > 0:
                total_cogs = total_construction_cost + total_land_cost
                gross_profit = total_revenue - total_cogs
                gross_margin = (gross_profit / total_revenue) * 100
            
            # Calculate net margin
            total_pat = project_dict.get('total_pat', 0)
            net_margin = (total_pat / total_revenue * 100) if total_revenue > 0 else 0
            
            comparison_data.append({
                'Project': project['project_name'],
                'Company': project['company_ticker'],
                'Location': project.get('location', 'N/A'),
                'Total Units': f"{project.get('total_units', 0):,.0f}",
                'NSA (sqm)': f"{project.get('net_sellable_area', 0):,.0f}",
                'ASP (VND/sqm)': f"{project.get('average_selling_price', 0):,.0f}",
                'Total Revenue (B VND)': f"{total_revenue:,.0f}",
                'Construction Cost (B VND)': f"{total_construction_cost:,.0f}",
                'Land Cost (B VND)': f"{total_land_cost:,.0f}",
                'Gross Margin (%)': f"{gross_margin:.1f}",
                'Net Margin (%)': f"{net_margin:.1f}",
                'RNAV (B VND)': f"{project.get('rnav_value', 0):,.0f}",
                'Sale Start': project.get('sale_start_year', 'N/A'),
                'Completion': project.get('project_completion_year', 'N/A')
            })
        
        comparison_df = pd.DataFrame(comparison_data)
        
        # Transpose for side-by-side comparison if 2-3 projects
        if len(comparison_df) <= 3:
            comparison_df = comparison_df.set_index('Project').T
            message = f"📊 **Side-by-side Comparison**\n\nComparing {len(compare_df)} projects across key metrics"
        else:
            message = f"📊 **Project Comparison**\n\nComparing {len(compare_df)} projects"
        
        return {
            'type': 'comparison',
            'message': '\n'.join(debug_msg) + f"\n\n{message}",
            'summary': f"Compared {len(compare_df)} projects",
            'data': comparison_df
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
        debug_msg = []
        debug_msg.append("\n📋 **PROJECT DETAILS HANDLER**")
        
        project_name = entities.get('project_name')
        tickers = entities.get('tickers', [])
        metric = entities.get('metric', None)
        
        debug_msg.append(f"Project name: {project_name}")
        debug_msg.append(f"Tickers: {tickers}")
        debug_msg.append(f"Metric requested: {metric}")
        
        # Load all projects from MongoDB with FULL details
        debug_msg.append("Loading all projects from MongoDB...")
        from .mongodb_utils import load_projects_data
        all_projects_df = load_projects_data()
        
        debug_msg.append(f"Total projects loaded: {len(all_projects_df)}")
        
        if all_projects_df.empty:
            return {
                'type': 'error',
                'message': '\n'.join(debug_msg) + '\n\n❌ No projects found in database',
                'data': None
            }
        
        # Filter by ticker if specified
        if tickers:
            debug_msg.append(f"Filtering by tickers: {tickers}")
            projects_df = all_projects_df[all_projects_df['company_ticker'].isin(tickers)]
            debug_msg.append(f"Projects after ticker filter: {len(projects_df)}")
        else:
            projects_df = all_projects_df
            debug_msg.append(f"No ticker filter, using all {len(projects_df)} projects")
        
        # Filter by project name if specified
        if project_name:
            debug_msg.append(f"Filtering by project name: {project_name}")
            projects_df = projects_df[projects_df['project_name'] == project_name]
            debug_msg.append(f"Projects after name filter: {len(projects_df)}")
        
        if projects_df.empty:
            return {
                'type': 'error',
                'message': '\n'.join(debug_msg) + '\n\n❌ No projects found for specified criteria',
                'data': None
            }
        
        # If specific metric requested, extract that
        if metric:
            debug_msg.append(f"Extracting metric: {metric}")
            result = self._extract_project_metrics(projects_df, metric)
            # Prepend debug info to result
            if result.get('message'):
                result['message'] = '\n'.join(debug_msg) + '\n\n' + result['message']
            return result
        
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
        """Calculate gross margin for a project using total values"""
        try:
            # Get total revenue
            total_revenue = project_data.get('total_revenue', 0)
            
            # If total_revenue is not stored, calculate it from NSA * ASP
            if total_revenue == 0:
                nsa = project_data.get('net_sellable_area', 0)
                asp = project_data.get('average_selling_price', 0)
                if nsa > 0 and asp > 0:
                    total_revenue = (nsa * asp) / 1e9  # Convert to billions VND
            
            # Get total costs
            total_construction_cost = project_data.get('total_construction_cost', 0)
            total_land_cost = project_data.get('total_land_cost', 0)
            
            # If total costs are not stored, calculate from per-sqm values
            if total_construction_cost == 0 or total_land_cost == 0:
                gfa = project_data.get('gross_floor_area', 0)
                land_area = project_data.get('land_area', 0)
                
                if total_construction_cost == 0 and gfa > 0:
                    construction_cost_per_sqm = project_data.get('construction_cost_per_sqm', 0)
                    total_construction_cost = (construction_cost_per_sqm * gfa) / 1e9  # Convert to billions
                
                if total_land_cost == 0 and land_area > 0:
                    land_cost_per_sqm = project_data.get('land_cost_per_sqm', 0)
                    total_land_cost = (land_cost_per_sqm * land_area) / 1e9  # Convert to billions
            
            # Calculate gross margin
            if total_revenue > 0:
                total_cogs = total_construction_cost + total_land_cost
                gross_profit = total_revenue - total_cogs
                gross_margin = (gross_profit / total_revenue) * 100
                return f"{gross_margin:.1f}%"
            
            return "N/A"
        except Exception as e:
            return "N/A"
    
    def _create_trends_chart(self, chart_df: pd.DataFrame) -> go.Figure:
        """Create a visualization chart for presales and revenue booking trends"""
        fig = go.Figure()
        
        # Group by project for multiple project comparison
        projects = chart_df['Project'].unique()
        
        if len(projects) == 1:
            # Single project - show detailed trend
            project_data = chart_df[chart_df['Project'] == projects[0]]
            
            # Add presales percentage line
            fig.add_trace(go.Scatter(
                x=project_data['Year'],
                y=project_data['Presales %'],
                mode='lines+markers',
                name='Presales %',
                line=dict(color='blue', width=2),
                marker=dict(size=8)
            ))
            
            # Add revenue booking percentage line
            fig.add_trace(go.Scatter(
                x=project_data['Year'],
                y=project_data['Revenue %'],
                mode='lines+markers',
                name='Revenue Booking %',
                line=dict(color='green', width=2),
                marker=dict(size=8)
            ))
            
            # Add actual revenue bars
            fig.add_trace(go.Bar(
                x=project_data['Year'],
                y=project_data['Revenue (B VND)'],
                name='Actual Revenue (B VND)',
                marker_color='lightgreen',
                yaxis='y2'
            ))
            
            fig.update_layout(
                title=f'Presales & Revenue Trends - {projects[0]}',
                xaxis_title='Year',
                yaxis=dict(title='Percentage (%)', side='left'),
                yaxis2=dict(title='Revenue (Billion VND)', overlaying='y', side='right'),
                hovermode='x unified',
                height=400
            )
        else:
            # Multiple projects - show comparison
            for project in projects[:5]:  # Limit to 5 projects for clarity
                project_data = chart_df[chart_df['Project'] == project]
                
                # Add revenue percentage line for each project
                fig.add_trace(go.Scatter(
                    x=project_data['Year'],
                    y=project_data['Revenue %'],
                    mode='lines+markers',
                    name=f'{project}',
                    marker=dict(size=6)
                ))
            
            fig.update_layout(
                title='Revenue Booking Trends Comparison',
                xaxis_title='Year',
                yaxis_title='Revenue Booking %',
                hovermode='x unified',
                height=400
            )
        
        return fig
    
    def _create_revenue_schedule_chart(self, projects_df: pd.DataFrame) -> go.Figure:
        """Create revenue schedule chart for one or more projects"""
        fig = go.Figure()
        
        # Collect all years and aggregate data
        years_set = set()
        project_revenues = {}
        has_data = False
        
        for _, project in projects_df.iterrows():
            project_name = f"{project['company_ticker']} - {project['project_name']}"
            pnl_schedule = project.get('pnl_schedule', {})
            
            # Also try to get revenue from revenue_distribution if pnl_schedule is empty
            revenue_dist = project.get('revenue_distribution', {})
            total_revenue = project.get('total_revenue', 0)
            
            if isinstance(pnl_schedule, dict) and pnl_schedule:
                project_revenues[project_name] = {}
                for year_str, pnl_data in pnl_schedule.items():
                    try:
                        year = int(year_str)
                        years_set.add(year)
                        revenue = pnl_data.get('revenue', 0) / 1e9 if isinstance(pnl_data, dict) else 0
                        project_revenues[project_name][year] = revenue
                        if revenue > 0:
                            has_data = True
                    except (ValueError, TypeError):
                        continue
            elif isinstance(revenue_dist, dict) and revenue_dist and total_revenue > 0:
                # Fallback to revenue distribution if no P&L schedule
                project_revenues[project_name] = {}
                for year_str, percentage in revenue_dist.items():
                    try:
                        year = int(year_str)
                        years_set.add(year)
                        revenue = (total_revenue * float(percentage) / 100)  # total_revenue already in billions
                        project_revenues[project_name][year] = revenue
                        if revenue > 0:
                            has_data = True
                    except (ValueError, TypeError):
                        continue
        
        # If no data found, create empty chart with message
        if not has_data or not years_set:
            fig.add_annotation(
                text="No revenue schedule data available for selected project(s).<br>Please ensure P&L schedule is calculated.",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=14)
            )
            fig.update_layout(
                title='Revenue Schedule by Year',
                xaxis_title='Year',
                yaxis_title='Revenue (Billion VND)',
                height=500
            )
            return fig
        
        # Sort years
        years = sorted(years_set)
        
        # If multiple projects, show stacked or grouped bars
        if len(projects_df) > 1:
            # Create stacked bar chart for aggregated view
            total_revenues = {year: 0 for year in years}
            for project_name, revenues in project_revenues.items():
                year_revenues = [revenues.get(year, 0) for year in years]
                fig.add_trace(go.Bar(
                    x=years,
                    y=year_revenues,
                    name=project_name[:30],  # Truncate long names
                    text=[f'{v:.0f}B' if v > 0 else '' for v in year_revenues],
                    textposition='inside'
                ))
                for year in years:
                    total_revenues[year] += revenues.get(year, 0)
            
            # Add total line
            fig.add_trace(go.Scatter(
                x=years,
                y=[total_revenues[year] for year in years],
                mode='lines+markers',
                name='Total',
                line=dict(color='red', width=2),
                marker=dict(size=8)
            ))
            
            fig.update_layout(barmode='stack')
        else:
            # Single project - simple bar chart
            for project_name, revenues in project_revenues.items():
                year_revenues = [revenues.get(year, 0) for year in years]
                fig.add_trace(go.Bar(
                    x=years,
                    y=year_revenues,
                    name='Revenue',
                    marker_color='green',
                    text=[f'{v:.0f}B' for v in year_revenues],
                    textposition='outside'
                ))
        
        fig.update_layout(
            title='Revenue Schedule by Year',
            xaxis_title='Year',
            yaxis_title='Revenue (Billion VND)',
            hovermode='x unified',
            showlegend=True,
            height=500
        )
        
        return fig
    
    def _create_presales_chart(self, projects_df: pd.DataFrame) -> go.Figure:
        """Create presales distribution chart"""
        fig = go.Figure()
        
        for _, project in projects_df.iterrows():
            project_name = f"{project['company_ticker']} - {project['project_name']}"
            presales_dist = project.get('presales_distribution', {})
            
            if presales_dist and isinstance(presales_dist, dict):
                years = sorted([int(y) for y in presales_dist.keys() if y.isdigit()])
                percentages = [float(presales_dist.get(str(y), 0)) for y in years]
                
                fig.add_trace(go.Scatter(
                    x=years,
                    y=percentages,
                    mode='lines+markers',
                    name=project_name[:30],
                    marker=dict(size=8)
                ))
        
        fig.update_layout(
            title='Presales Distribution Over Time',
            xaxis_title='Year',
            yaxis_title='Presales %',
            hovermode='x unified',
            showlegend=True,
            height=500
        )
        
        return fig
    
    def _create_npatmi_chart(self, projects_df: pd.DataFrame) -> go.Figure:
        """Create NPATMI (Net Profit After Tax) chart"""
        fig = go.Figure()
        
        # Collect all years and aggregate data
        years_set = set()
        project_profits = {}
        has_data = False
        
        for _, project in projects_df.iterrows():
            project_name = f"{project['company_ticker']} - {project['project_name']}"
            pnl_schedule = project.get('pnl_schedule', {})
            
            # Try P&L schedule first
            if isinstance(pnl_schedule, dict) and pnl_schedule:
                project_profits[project_name] = {}
                for year_str, pnl_data in pnl_schedule.items():
                    try:
                        year = int(year_str)
                        years_set.add(year)
                        # Use PAT (Profit After Tax) from P&L schedule
                        pat = pnl_data.get('pat', 0) / 1e9 if isinstance(pnl_data, dict) else 0
                        project_profits[project_name][year] = pat
                        if pat != 0:
                            has_data = True
                    except (ValueError, TypeError):
                        continue
            # Fallback to total_pat if available
            elif project.get('total_pat', 0) > 0:
                # If we only have total PAT, show it as a single point
                current_year = 2025  # Default year
                project_profits[project_name] = {current_year: project.get('total_pat', 0)}
                years_set.add(current_year)
                has_data = True
        
        # If no data found, show message
        if not has_data or not years_set:
            fig.add_annotation(
                text="No profit data available for selected project(s).<br>Please ensure P&L schedule is calculated.",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=14)
            )
            fig.update_layout(
                title='Net Profit After Tax (NPATMI) by Year',
                xaxis_title='Year',
                yaxis_title='NPATMI (Billion VND)',
                height=500
            )
            return fig
        
        # Sort years
        years = sorted(years_set)
        
        # Create chart
        if len(projects_df) > 1:
            # Multiple projects - show as lines for easier comparison
            total_profits = {year: 0 for year in years}
            for project_name, profits in project_profits.items():
                year_profits = [profits.get(year, 0) for year in years]
                fig.add_trace(go.Scatter(
                    x=years,
                    y=year_profits,
                    mode='lines+markers',
                    name=project_name[:30],
                    marker=dict(size=6)
                ))
                for year in years:
                    total_profits[year] += profits.get(year, 0)
            
            # Add total line
            fig.add_trace(go.Scatter(
                x=years,
                y=[total_profits[year] for year in years],
                mode='lines+markers',
                name='Total NPATMI',
                line=dict(color='red', width=3, dash='dash'),
                marker=dict(size=8)
            ))
        else:
            # Single project
            for project_name, profits in project_profits.items():
                year_profits = [profits.get(year, 0) for year in years]
                fig.add_trace(go.Bar(
                    x=years,
                    y=year_profits,
                    name='NPATMI',
                    marker_color='blue',
                    text=[f'{v:.0f}B' for v in year_profits],
                    textposition='outside'
                ))
        
        fig.update_layout(
            title='Net Profit After Tax (NPATMI) by Year',
            xaxis_title='Year',
            yaxis_title='NPATMI (Billion VND)',
            hovermode='x unified',
            showlegend=True,
            height=500
        )
        
        return fig
    
    def _create_pnl_chart(self, projects_df: pd.DataFrame) -> go.Figure:
        """Create comprehensive P&L chart"""
        fig = go.Figure()
        
        # For P&L, we'll show revenue, costs, and profit for better understanding
        years_set = set()
        aggregated_pnl = {}
        
        for _, project in projects_df.iterrows():
            pnl_schedule = project.get('pnl_schedule', {})
            
            if isinstance(pnl_schedule, dict):
                for year_str, pnl_data in pnl_schedule.items():
                    try:
                        year = int(year_str)
                        years_set.add(year)
                        
                        if year not in aggregated_pnl:
                            aggregated_pnl[year] = {
                                'revenue': 0,
                                'construction': 0,
                                'land': 0,
                                'sga': 0,
                                'pat': 0
                            }
                        
                        if isinstance(pnl_data, dict):
                            aggregated_pnl[year]['revenue'] += pnl_data.get('revenue', 0) / 1e9
                            aggregated_pnl[year]['construction'] += abs(pnl_data.get('construction_cost', 0)) / 1e9
                            aggregated_pnl[year]['land'] += abs(pnl_data.get('land_cost', 0)) / 1e9
                            aggregated_pnl[year]['sga'] += abs(pnl_data.get('sga', 0)) / 1e9
                            aggregated_pnl[year]['pat'] += pnl_data.get('pat', 0) / 1e9
                    except (ValueError, TypeError):
                        continue
        
        # Sort years
        years = sorted(years_set)
        
        # Create stacked bar chart for costs and revenue
        fig.add_trace(go.Bar(
            x=years,
            y=[aggregated_pnl[y]['revenue'] for y in years],
            name='Revenue',
            marker_color='green'
        ))
        
        fig.add_trace(go.Bar(
            x=years,
            y=[-aggregated_pnl[y]['construction'] for y in years],
            name='Construction Cost',
            marker_color='orange'
        ))
        
        fig.add_trace(go.Bar(
            x=years,
            y=[-aggregated_pnl[y]['land'] for y in years],
            name='Land Cost',
            marker_color='brown'
        ))
        
        fig.add_trace(go.Bar(
            x=years,
            y=[-aggregated_pnl[y]['sga'] for y in years],
            name='SG&A',
            marker_color='gray'
        ))
        
        # Add PAT as a line
        fig.add_trace(go.Scatter(
            x=years,
            y=[aggregated_pnl[y]['pat'] for y in years],
            mode='lines+markers',
            name='Net Profit (PAT)',
            line=dict(color='blue', width=2),
            marker=dict(size=8),
            yaxis='y2'
        ))
        
        fig.update_layout(
            title='P&L Schedule Overview',
            xaxis_title='Year',
            yaxis_title='Amount (Billion VND)',
            yaxis2=dict(
                title='Net Profit (Billion VND)',
                overlaying='y',
                side='right'
            ),
            barmode='relative',
            hovermode='x unified',
            showlegend=True,
            height=600
        )
        
        return fig
    
    def _create_combined_financial_chart(self, projects_df: pd.DataFrame) -> go.Figure:
        """Create combined chart showing revenue, costs, and profit"""
        # Create subplots
        from plotly.subplots import make_subplots
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Revenue Schedule', 'Net Profit (NPATMI)', 
                          'Cost Breakdown', 'Profit Margin %'),
            specs=[[{'type': 'bar'}, {'type': 'scatter'}],
                   [{'type': 'bar'}, {'type': 'scatter'}]]
        )
        
        # Aggregate data
        years_set = set()
        aggregated_data = {}
        
        for _, project in projects_df.iterrows():
            pnl_schedule = project.get('pnl_schedule', {})
            
            if isinstance(pnl_schedule, dict):
                for year_str, pnl_data in pnl_schedule.items():
                    try:
                        year = int(year_str)
                        years_set.add(year)
                        
                        if year not in aggregated_data:
                            aggregated_data[year] = {
                                'revenue': 0,
                                'construction': 0,
                                'land': 0,
                                'sga': 0,
                                'pat': 0
                            }
                        
                        if isinstance(pnl_data, dict):
                            aggregated_data[year]['revenue'] += pnl_data.get('revenue', 0) / 1e9
                            aggregated_data[year]['construction'] += abs(pnl_data.get('construction_cost', 0)) / 1e9
                            aggregated_data[year]['land'] += abs(pnl_data.get('land_cost', 0)) / 1e9
                            aggregated_data[year]['sga'] += abs(pnl_data.get('sga', 0)) / 1e9
                            aggregated_data[year]['pat'] += pnl_data.get('pat', 0) / 1e9
                    except (ValueError, TypeError):
                        continue
        
        years = sorted(years_set)
        
        # Revenue chart (top left)
        fig.add_trace(
            go.Bar(x=years, y=[aggregated_data[y]['revenue'] for y in years], 
                  name='Revenue', marker_color='green'),
            row=1, col=1
        )
        
        # Net Profit chart (top right)
        fig.add_trace(
            go.Scatter(x=years, y=[aggregated_data[y]['pat'] for y in years],
                      mode='lines+markers', name='NPATMI', line=dict(color='blue')),
            row=1, col=2
        )
        
        # Cost breakdown (bottom left)
        fig.add_trace(
            go.Bar(x=years, y=[aggregated_data[y]['construction'] for y in years],
                  name='Construction', marker_color='orange'),
            row=2, col=1
        )
        fig.add_trace(
            go.Bar(x=years, y=[aggregated_data[y]['land'] for y in years],
                  name='Land', marker_color='brown'),
            row=2, col=1
        )
        fig.add_trace(
            go.Bar(x=years, y=[aggregated_data[y]['sga'] for y in years],
                  name='SG&A', marker_color='gray'),
            row=2, col=1
        )
        
        # Profit margin % (bottom right)
        margins = []
        for year in years:
            revenue = aggregated_data[year]['revenue']
            pat = aggregated_data[year]['pat']
            margin = (pat / revenue * 100) if revenue > 0 else 0
            margins.append(margin)
        
        fig.add_trace(
            go.Scatter(x=years, y=margins,
                      mode='lines+markers', name='Net Margin %', 
                      line=dict(color='purple')),
            row=2, col=2
        )
        
        fig.update_layout(
            title_text='Combined Financial Analysis',
            showlegend=True,
            height=800
        )
        
        # Update axes labels
        fig.update_xaxes(title_text="Year", row=2, col=1)
        fig.update_xaxes(title_text="Year", row=2, col=2)
        fig.update_yaxes(title_text="Billion VND", row=1, col=1)
        fig.update_yaxes(title_text="Billion VND", row=1, col=2)
        fig.update_yaxes(title_text="Billion VND", row=2, col=1)
        fig.update_yaxes(title_text="Margin %", row=2, col=2)
        
        return fig
    
    def _extract_project_metrics(self, projects_df: pd.DataFrame, metric: str) -> Dict[str, Any]:
        """Extract specific metrics from projects with comprehensive financial data"""
        metric_lower = metric.lower()
        
        # Total Revenue
        if any(word in metric_lower for word in ['revenue', 'total revenue', 'sales']):
            revenue_data = []
            for _, project in projects_df.iterrows():
                total_revenue = project.get('total_revenue', 0)
                if total_revenue == 0:
                    # Try to calculate from NSA and ASP
                    nsa = project.get('net_sellable_area', 0)
                    asp = project.get('average_selling_price', 0)
                    total_revenue = (nsa * asp) / 1e9  # Convert to billions
                
                revenue_data.append({
                    'Company': project['company_ticker'],
                    'Project': project['project_name'],
                    'Total Revenue': f"{total_revenue:,.0f}B VND" if total_revenue > 0 else "N/A",
                    'NSA': f"{project.get('net_sellable_area', 0):,.0f} sqm",
                    'ASP': f"{project.get('average_selling_price', 0):,.0f} VND/sqm"
                })
            
            if revenue_data:
                revenue_df = pd.DataFrame(revenue_data)
                message = f"💰 **Revenue Analysis**\nShowing total revenue for {len(revenue_df)} projects"
                
                return {
                    'type': 'metric_revenue',
                    'message': message,
                    'summary': f"Revenue analysis for {len(revenue_df)} projects",
                    'data': revenue_df
                }
        
        # Net Profit (PAT)
        elif any(word in metric_lower for word in ['profit', 'pat', 'net profit', 'net income']):
            profit_data = []
            for _, project in projects_df.iterrows():
                total_pat = project.get('total_pat', 0)
                total_revenue = project.get('total_revenue', 0)
                
                if total_revenue == 0:
                    # Calculate from NSA and ASP
                    nsa = project.get('net_sellable_area', 0)
                    asp = project.get('average_selling_price', 0)
                    total_revenue = (nsa * asp) / 1e9
                
                # Calculate profit margin
                profit_margin = (total_pat / total_revenue * 100) if total_revenue > 0 else 0
                
                profit_data.append({
                    'Company': project['company_ticker'],
                    'Project': project['project_name'],
                    'Total PAT': f"{total_pat:,.0f}B VND" if total_pat > 0 else "N/A",
                    'Total Revenue': f"{total_revenue:,.0f}B VND" if total_revenue > 0 else "N/A",
                    'Net Margin': f"{profit_margin:.1f}%" if profit_margin > 0 else "N/A"
                })
            
            if profit_data:
                profit_df = pd.DataFrame(profit_data)
                message = f"📊 **Profit Analysis**\nShowing net profit for {len(profit_df)} projects"
                
                return {
                    'type': 'metric_profit',
                    'message': message,
                    'summary': f"Profit analysis for {len(profit_df)} projects",
                    'data': profit_df
                }
        
        # Presales and Revenue Booking Trends
        elif any(word in metric_lower for word in ['presales', 'presale', 'booking', 'revenue booking']):
            trends_data = []
            chart_data = []
            
            for _, project in projects_df.iterrows():
                # Get presales and revenue distributions
                presales_dist = project.get('presales_distribution', {})
                revenue_dist = project.get('revenue_distribution', {})
                pnl_schedule = project.get('pnl_schedule', {})
                
                if presales_dist or revenue_dist or pnl_schedule:
                    # Create trend visualization data
                    years = sorted(set(list(presales_dist.keys()) + list(revenue_dist.keys()) + list(pnl_schedule.keys())))
                    
                    trend_info = {
                        'Company': project['company_ticker'],
                        'Project': project['project_name'],
                        'Years': ', '.join(years),
                        'Presales Years': ', '.join(presales_dist.keys()) if presales_dist else 'N/A',
                        'Revenue Years': ', '.join(revenue_dist.keys()) if revenue_dist else 'N/A'
                    }
                    
                    # Add yearly breakdown
                    for year in years:
                        trend_info[f'Presales {year}'] = f"{presales_dist.get(year, 0)}%"
                        trend_info[f'Revenue {year}'] = f"{revenue_dist.get(year, 0)}%"
                        
                        # Add actual revenue from P&L schedule
                        if year in pnl_schedule:
                            revenue_value = pnl_schedule[year].get('revenue', 0) / 1e9
                            trend_info[f'Revenue {year} (B)'] = f"{revenue_value:,.0f}"
                    
                    trends_data.append(trend_info)
                    
                    # Prepare chart data
                    for year in years:
                        chart_data.append({
                            'Year': year,
                            'Project': project['project_name'],
                            'Presales %': float(presales_dist.get(year, 0)),
                            'Revenue %': float(revenue_dist.get(year, 0)),
                            'Revenue (B VND)': pnl_schedule.get(year, {}).get('revenue', 0) / 1e9 if year in pnl_schedule else 0
                        })
            
            if trends_data:
                trends_df = pd.DataFrame(trends_data)
                chart_df = pd.DataFrame(chart_data) if chart_data else None
                
                # Create visualization if we have chart data
                fig = None
                if chart_df is not None and not chart_df.empty:
                    fig = self._create_trends_chart(chart_df)
                
                message = f"📈 **Presales & Revenue Booking Trends**\nShowing trends for {len(trends_df)} projects"
                
                result = {
                    'type': 'metric_trends',
                    'message': message,
                    'summary': f"Trends analysis for {len(trends_df)} projects",
                    'data': trends_df
                }
                
                if fig:
                    result['chart'] = fig
                
                return result
        
        # Financial Summary (all key metrics)
        elif any(word in metric_lower for word in ['financial', 'summary', 'all metrics', 'overview']):
            summary_data = []
            for _, project in projects_df.iterrows():
                # Calculate all key metrics
                nsa = project.get('net_sellable_area', 0)
                asp = project.get('average_selling_price', 0)
                total_revenue = project.get('total_revenue', 0)
                if total_revenue == 0:
                    total_revenue = (nsa * asp) / 1e9
                
                # Get costs
                construction_cost = project.get('total_construction_cost', 0)
                land_cost = project.get('total_land_cost', 0)
                sga_cost = project.get('total_sga_cost', 0)
                
                # Calculate margins
                gross_margin = self._calculate_gross_margin(project.to_dict())
                total_pat = project.get('total_pat', 0)
                net_margin = (total_pat / total_revenue * 100) if total_revenue > 0 else 0
                
                summary_data.append({
                    'Company': project['company_ticker'],
                    'Project': project['project_name'],
                    'Total Revenue': f"{total_revenue:,.0f}B",
                    'Total PAT': f"{total_pat:,.0f}B",
                    'RNAV': f"{project.get('rnav_value', 0):,.0f}B",
                    'Gross Margin': gross_margin,
                    'Net Margin': f"{net_margin:.1f}%",
                    'Construction Cost': f"{construction_cost:,.0f}B",
                    'Land Cost': f"{land_cost:,.0f}B"
                })
            
            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                message = f"📊 **Financial Summary**\nComplete financial overview for {len(summary_df)} projects"
                
                return {
                    'type': 'metric_financial_summary',
                    'message': message,
                    'summary': f"Financial summary for {len(summary_df)} projects",
                    'data': summary_df
                }
        
        elif 'rnav' in metric_lower:
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
                project_dict = project.to_dict()
                margin = self._calculate_gross_margin(project_dict)
                if margin != "N/A":
                    # Get total values (same logic as in _calculate_gross_margin)
                    total_revenue = project_dict.get('total_revenue', 0)
                    if total_revenue == 0:
                        nsa = project_dict.get('net_sellable_area', 0)
                        asp = project_dict.get('average_selling_price', 0)
                        if nsa > 0 and asp > 0:
                            total_revenue = (nsa * asp) / 1e9
                    
                    total_construction_cost = project_dict.get('total_construction_cost', 0)
                    total_land_cost = project_dict.get('total_land_cost', 0)
                    
                    if total_construction_cost == 0 or total_land_cost == 0:
                        gfa = project_dict.get('gross_floor_area', 0)
                        land_area = project_dict.get('land_area', 0)
                        
                        if total_construction_cost == 0 and gfa > 0:
                            construction_cost_per_sqm = project_dict.get('construction_cost_per_sqm', 0)
                            total_construction_cost = (construction_cost_per_sqm * gfa) / 1e9
                        
                        if total_land_cost == 0 and land_area > 0:
                            land_cost_per_sqm = project_dict.get('land_cost_per_sqm', 0)
                            total_land_cost = (land_cost_per_sqm * land_area) / 1e9
                    
                    margins_data.append({
                        'Company': project['company_ticker'],
                        'Project': project['project_name'],
                        'Total Revenue': f"{total_revenue:,.0f}B",
                        'Total Construction Cost': f"{total_construction_cost:,.0f}B",
                        'Total Land Cost': f"{total_land_cost:,.0f}B",
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
    
    def handle_create_chart(self, entities: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chart creation requests for project financials"""
        debug_msg = []
        debug_msg.append("\n📊 **CREATE CHART HANDLER**")
        
        project_name = entities.get('project_name')
        tickers = entities.get('tickers', [])
        chart_type = entities.get('chart_type', 'combined')
        
        debug_msg.append(f"Project name: {project_name}")
        debug_msg.append(f"Tickers: {tickers}")
        debug_msg.append(f"Chart type: {chart_type}")
        
        # Load all projects from MongoDB
        from .mongodb_utils import load_projects_data
        all_projects_df = load_projects_data()
        
        if all_projects_df.empty:
            return {
                'type': 'error',
                'message': '\n'.join(debug_msg) + '\n\n❌ No projects found in database',
                'data': None
            }
        
        # Filter projects
        if project_name:
            # Specific project by name
            projects_df = all_projects_df[all_projects_df['project_name'] == project_name]
            debug_msg.append(f"Filtered by project name: {len(projects_df)} projects")
        elif tickers:
            # Projects for specific tickers
            projects_df = all_projects_df[all_projects_df['company_ticker'].isin(tickers)]
            debug_msg.append(f"Filtered by tickers: {len(projects_df)} projects")
        else:
            # All projects
            projects_df = all_projects_df
            debug_msg.append(f"Using all {len(projects_df)} projects")
        
        if projects_df.empty:
            return {
                'type': 'error',
                'message': '\n'.join(debug_msg) + '\n\n❌ No projects found for specified criteria',
                'data': None
            }
        
        # Check what data is available for charting
        for _, project in projects_df.iterrows():
            project_name = project.get('project_name', 'Unknown')
            debug_msg.append(f"\nChecking data for {project_name}:")
            
            # Check P&L schedule
            pnl_schedule = project.get('pnl_schedule', {})
            if pnl_schedule:
                debug_msg.append(f"  - P&L Schedule: {len(pnl_schedule)} years")
                if isinstance(pnl_schedule, dict):
                    years = list(pnl_schedule.keys())[:3]  # Show first 3 years
                    debug_msg.append(f"    Years: {', '.join(years)}...")
            else:
                debug_msg.append("  - P&L Schedule: NOT FOUND")
            
            # Check revenue distribution
            revenue_dist = project.get('revenue_distribution', {})
            if revenue_dist:
                debug_msg.append(f"  - Revenue Distribution: {len(revenue_dist)} years")
            else:
                debug_msg.append("  - Revenue Distribution: NOT FOUND")
            
            # Check total values
            total_revenue = project.get('total_revenue', 0)
            total_pat = project.get('total_pat', 0)
            debug_msg.append(f"  - Total Revenue: {total_revenue:.0f}B VND" if total_revenue else "  - Total Revenue: NOT SET")
            debug_msg.append(f"  - Total PAT: {total_pat:.0f}B VND" if total_pat else "  - Total PAT: NOT SET")
        
        # Create appropriate chart based on type
        try:
            if chart_type == 'revenue':
                fig = self._create_revenue_schedule_chart(projects_df)
                chart_title = "Revenue Schedule"
            elif chart_type == 'presales':
                fig = self._create_presales_chart(projects_df)
                chart_title = "Presales Distribution"
            elif chart_type == 'npatmi':
                fig = self._create_npatmi_chart(projects_df)
                chart_title = "NPATMI (Net Profit After Tax)"
            elif chart_type == 'pnl':
                fig = self._create_pnl_chart(projects_df)
                chart_title = "P&L Schedule"
            else:  # combined
                fig = self._create_combined_financial_chart(projects_df)
                chart_title = "Combined Financial Metrics"
            
            debug_msg.append(f"\n✅ Successfully created {chart_title} chart")
            
            # Prepare summary data
            summary_data = []
            for _, project in projects_df.iterrows():
                summary_data.append({
                    'Company': project['company_ticker'],
                    'Project': project['project_name'],
                    'Total Revenue': f"{project.get('total_revenue', 0):,.0f}B VND" if project.get('total_revenue') else 'N/A',
                    'Total PAT': f"{project.get('total_pat', 0):,.0f}B VND" if project.get('total_pat') else 'N/A'
                })
            
            return {
                'type': 'chart',
                'message': '\n'.join(debug_msg) + f'\n\n✅ {chart_title} for {len(projects_df)} project(s)',
                'summary': f"Showing {chart_title}",
                'chart': fig,
                'data': pd.DataFrame(summary_data) if summary_data else None
            }
            
        except Exception as e:
            return {
                'type': 'error',
                'message': '\n'.join(debug_msg) + f'\n\n❌ Error creating chart: {str(e)}',
                'data': None
            }
    
    def handle_general_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle general queries - check if it's about projects first"""
        
        # Extract entities to check if user is asking about specific tickers
        entities = self.extract_entities(query, context)
        
        # If tickers are mentioned, try to handle it as a project query
        if entities.get('tickers'):
            # Determine what to do based on keywords
            query_lower = query.lower()
            if any(word in query_lower for word in ['project', 'list', 'show', 'display']):
                return self.handle_list_projects(entities, context)
            elif any(word in query_lower for word in ['rank', 'top', 'largest', 'biggest']):
                return self.handle_rank_projects(entities, context)
            elif any(word in query_lower for word in ['detail', 'information', 'about']):
                return self.handle_project_details(entities, context)
            else:
                # Default to listing projects for the ticker
                return self.handle_list_projects(entities, context)
        
        # Original general query handling
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
• List projects for any ticker (e.g., "Show KDH projects")
• Compare multiple tickers (e.g., "List projects for KDH and NLG")
• Rank projects by RNAV
• Analyze growth trends
• Calculate portfolio metrics

Try asking: "Show KDH projects" or "What's the largest RNAV for VHM?" """
        
        return {
            'type': 'info',
            'message': help_message,
            'summary': 'Help message',
            'data': None
        }