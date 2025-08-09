"""
Revenue Stream Analyzer and Financial Model Updater
Uses AI to identify revenue streams and update financial assumptions dynamically
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import json
import anthropic
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

class RevenueStreamAnalyzer:
    """Analyzes revenue streams and updates financial assumptions based on project discovery"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Claude API key"""
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
        
        # Default revenue stream categories for real estate
        self.revenue_categories = {
            'development_sales': {
                'name': 'Property Development Sales',
                'recognition': 'handover',
                'typical_margin': 0.25
            },
            'rental_income': {
                'name': 'Rental Income',
                'recognition': 'monthly',
                'typical_margin': 0.70
            },
            'management_fees': {
                'name': 'Property Management Fees',
                'recognition': 'monthly',
                'typical_margin': 0.40
            },
            'brokerage': {
                'name': 'Brokerage Commissions',
                'recognition': 'transaction',
                'typical_margin': 0.60
            },
            'construction': {
                'name': 'Construction Services',
                'recognition': 'percentage_completion',
                'typical_margin': 0.15
            }
        }
    
    def analyze_revenue_streams(self, 
                               projects: List[Dict],
                               financial_data: Optional[Dict] = None,
                               company_name: str = "",
                               company_ticker: str = "") -> Dict:
        """
        Analyze projects and financial data to identify revenue streams
        
        Args:
            projects: List of discovered projects
            financial_data: Historical financial data if available
            company_name: Company name
            company_ticker: Stock ticker
            
        Returns:
            Dictionary with identified revenue streams and characteristics
        """
        
        # Prepare data for Claude
        projects_summary = self._summarize_projects(projects)
        
        prompt = f"""
        Analyze the real estate projects and business model of {company_name} ({company_ticker}) to identify all revenue streams.
        
        PROJECT PORTFOLIO:
        {json.dumps(projects_summary, indent=2)}
        
        {f"HISTORICAL FINANCIALS: {json.dumps(financial_data, indent=2)}" if financial_data else ""}
        
        Identify and analyze:
        
        1. REVENUE STREAMS:
           - Property development sales (presales, handover)
           - Recurring revenue (rental, management fees)
           - Service revenue (brokerage, construction)
           - Other income sources
        
        2. REVENUE RECOGNITION PATTERNS:
           - Presales to handover timeline
           - Revenue recognition method (handover vs percentage completion)
           - Seasonality patterns
           - Geographic concentration
        
        3. KEY METRICS FOR EACH STREAM:
           - Contribution to total revenue (%)
           - Gross margin
           - Growth rate
           - Risk factors
        
        4. PROJECT-BASED REVENUE FORECAST:
           - Revenue timing by project
           - Presales velocity assumptions
           - Price appreciation assumptions
           - Handover schedule
        
        Return JSON:
        {{
            "revenue_streams": [
                {{
                    "stream_name": "Property Development Sales",
                    "type": "development_sales",
                    "current_contribution_pct": 85,
                    "gross_margin": 0.28,
                    "growth_rate": 0.15,
                    "recognition_method": "handover",
                    "key_drivers": ["number of projects", "ASP", "sales velocity"],
                    "risk_level": "medium"
                }}
            ],
            "revenue_recognition": {{
                "primary_method": "handover",
                "presales_to_handover_months": 24,
                "handover_concentration": "Q4 heavy",
                "geographic_split": {{"HCMC": 60, "Hanoi": 30, "Others": 10}}
            }},
            "project_revenue_forecast": [
                {{
                    "project_name": "Project X",
                    "total_revenue_potential": 5000000000000,
                    "revenue_schedule": {{
                        "2024": 1000000000000,
                        "2025": 3000000000000,
                        "2026": 1000000000000
                    }},
                    "confidence": 0.8
                }}
            ],
            "assumptions": {{
                "avg_presales_velocity_pct_per_month": 5,
                "price_appreciation_per_year": 0.08,
                "handover_success_rate": 0.95,
                "collection_rate": 0.98
            }},
            "insights": {{
                "key_findings": ["Main revenue from development", "Increasing recurring revenue"],
                "opportunities": ["Expand rental portfolio", "Higher margin products"],
                "risks": ["Concentration in HCMC", "Dependent on few large projects"]
            }}
        }}
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0,
                system="""You are a financial analyst expert specialized in real estate revenue modeling.
                You understand project-based revenue recognition, presales mechanisms, and can forecast
                revenue based on project pipelines. Always return valid JSON only.""",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse response
            response_text = response.content[0].text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            result = json.loads(response_text)
            result['analysis_date'] = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            st.error(f"Error analyzing revenue streams: {str(e)}")
            return self._default_revenue_analysis(projects)
    
    def _summarize_projects(self, projects: List[Dict]) -> Dict:
        """Summarize project portfolio for analysis"""
        summary = {
            'total_projects': len(projects),
            'total_units': sum(p.get('total_units', 0) for p in projects),
            'total_gfa': sum(p.get('gfa_sqm', 0) or p.get('net_sellable_area', 0) for p in projects),
            'stages': {},
            'locations': {},
            'project_list': []
        }
        
        for project in projects[:20]:  # Limit to first 20 for token management
            stage = project.get('stage', 'unknown')
            location = project.get('location', 'unknown')
            
            summary['stages'][stage] = summary['stages'].get(stage, 0) + 1
            summary['locations'][location] = summary['locations'].get(location, 0) + 1
            
            summary['project_list'].append({
                'name': project.get('project_name'),
                'units': project.get('total_units'),
                'stage': stage,
                'location': location,
                'value': project.get('book_value_vnd') or project.get('nav_value_vnd')
            })
        
        return summary
    
    def _default_revenue_analysis(self, projects: List[Dict]) -> Dict:
        """Fallback revenue analysis if AI fails"""
        return {
            'revenue_streams': [
                {
                    'stream_name': 'Property Development Sales',
                    'type': 'development_sales',
                    'current_contribution_pct': 90,
                    'gross_margin': 0.25
                }
            ],
            'assumptions': {
                'avg_presales_velocity_pct_per_month': 5,
                'price_appreciation_per_year': 0.05
            }
        }
    
    def generate_financial_assumptions(self,
                                      revenue_analysis: Dict,
                                      projects: List[Dict],
                                      current_year: int = None) -> Dict:
        """
        Generate dynamic financial assumptions based on revenue analysis
        
        Args:
            revenue_analysis: Output from analyze_revenue_streams
            projects: List of projects
            current_year: Current year for forecasting
            
        Returns:
            Dictionary of financial assumptions
        """
        
        if current_year is None:
            current_year = datetime.now().year
        
        assumptions = {
            'revenue': {},
            'costs': {},
            'working_capital': {},
            'timeline': {},
            'risk_adjustments': {}
        }
        
        # Revenue assumptions from analysis
        revenue_data = revenue_analysis.get('assumptions', {})
        assumptions['revenue'] = {
            'presales_velocity': revenue_data.get('avg_presales_velocity_pct_per_month', 5),
            'price_growth': revenue_data.get('price_appreciation_per_year', 0.05),
            'handover_rate': revenue_data.get('handover_success_rate', 0.95),
            'collection_rate': revenue_data.get('collection_rate', 0.98)
        }
        
        # Cost assumptions based on margins
        for stream in revenue_analysis.get('revenue_streams', []):
            margin = stream.get('gross_margin', 0.25)
            assumptions['costs'][stream.get('type', 'default')] = {
                'gross_margin': margin,
                'cogs_ratio': 1 - margin,
                'opex_ratio': 0.10  # Default operating expense ratio
            }
        
        # Working capital assumptions
        assumptions['working_capital'] = {
            'receivables_days': 30,
            'inventory_days': 365,  # Long for real estate
            'payables_days': 60,
            'cash_conversion_cycle': 335
        }
        
        # Timeline assumptions
        recognition = revenue_analysis.get('revenue_recognition', {})
        assumptions['timeline'] = {
            'presales_to_construction': 6,  # months
            'construction_period': recognition.get('presales_to_handover_months', 24),
            'handover_period': 6,  # months for handover after completion
            'payment_schedule': {
                'deposit': 0.20,
                'during_construction': 0.30,
                'on_handover': 0.50
            }
        }
        
        # Risk adjustments
        assumptions['risk_adjustments'] = {
            'market_risk': 0.10,  # 10% discount for market risk
            'execution_risk': 0.05,  # 5% discount for execution risk
            'regulatory_risk': 0.05  # 5% for regulatory changes
        }
        
        return assumptions
    
    def create_revenue_forecast(self,
                               projects: List[Dict],
                               assumptions: Dict,
                               revenue_analysis: Dict,
                               forecast_years: int = 5) -> pd.DataFrame:
        """
        Create detailed revenue forecast based on projects and assumptions
        
        Args:
            projects: List of projects with details
            assumptions: Financial assumptions
            revenue_analysis: Revenue stream analysis
            forecast_years: Number of years to forecast
            
        Returns:
            DataFrame with revenue forecast by project and year
        """
        
        current_year = datetime.now().year
        years = list(range(current_year, current_year + forecast_years))
        
        # Initialize forecast structure
        forecast_data = []
        
        # Get project revenue schedules from analysis
        project_forecasts = revenue_analysis.get('project_revenue_forecast', [])
        project_forecast_dict = {pf['project_name']: pf for pf in project_forecasts}
        
        for project in projects:
            project_name = project.get('project_name', 'Unknown')
            
            # Check if we have AI-generated forecast for this project
            if project_name in project_forecast_dict:
                ai_forecast = project_forecast_dict[project_name]
                revenue_schedule = ai_forecast.get('revenue_schedule', {})
                
                for year in years:
                    year_str = str(year)
                    if year_str in revenue_schedule:
                        forecast_data.append({
                            'Project': project_name,
                            'Year': year,
                            'Revenue Type': 'Development Sales',
                            'Revenue': revenue_schedule[year_str],
                            'Confidence': ai_forecast.get('confidence', 0.7),
                            'Stage': project.get('stage', 'unknown')
                        })
            else:
                # Generate forecast based on project details and assumptions
                forecast = self._generate_project_forecast(
                    project, assumptions, current_year, forecast_years
                )
                forecast_data.extend(forecast)
        
        # Create DataFrame
        df = pd.DataFrame(forecast_data)
        
        if df.empty:
            # Return empty forecast structure
            return pd.DataFrame(columns=['Project', 'Year', 'Revenue Type', 'Revenue', 'Confidence'])
        
        # Add summary rows
        summary = df.groupby(['Year', 'Revenue Type'])['Revenue'].sum().reset_index()
        summary['Project'] = 'TOTAL'
        
        # Combine with project details
        result = pd.concat([df, summary], ignore_index=True)
        
        return result.sort_values(['Year', 'Project'])
    
    def _generate_project_forecast(self, 
                                  project: Dict,
                                  assumptions: Dict,
                                  current_year: int,
                                  forecast_years: int) -> List[Dict]:
        """Generate forecast for a single project based on assumptions"""
        
        forecast = []
        project_name = project.get('project_name', 'Unknown')
        stage = project.get('stage', 'planning')
        total_units = project.get('total_units', 0)
        asp = project.get('average_selling_price', 50000000)  # Default 50M VND/sqm
        nsa = project.get('net_sellable_area', 0) or project.get('gfa_sqm', 0) * 0.75
        
        if total_units == 0 or nsa == 0:
            return forecast
        
        # Calculate total revenue potential
        total_revenue = nsa * asp
        
        # Determine revenue timing based on stage
        revenue_timing = self._determine_revenue_timing(
            stage, current_year, assumptions
        )
        
        # Distribute revenue across years
        for year, percentage in revenue_timing.items():
            if year < current_year + forecast_years:
                forecast.append({
                    'Project': project_name,
                    'Year': year,
                    'Revenue Type': 'Development Sales',
                    'Revenue': total_revenue * percentage,
                    'Confidence': 0.6 if stage == 'planning' else 0.8,
                    'Stage': stage
                })
        
        return forecast
    
    def _determine_revenue_timing(self,
                                 stage: str,
                                 current_year: int,
                                 assumptions: Dict) -> Dict[int, float]:
        """Determine when revenue will be recognized based on project stage"""
        
        timing = {}
        construction_period = assumptions['timeline']['construction_period'] // 12  # Convert to years
        
        if stage in ['completed', 'selling']:
            # Immediate revenue recognition
            timing[current_year] = 0.6
            timing[current_year + 1] = 0.4
        
        elif stage in ['construction', 'under_construction']:
            # Revenue in 1-2 years
            timing[current_year + 1] = 0.3
            timing[current_year + 2] = 0.5
            timing[current_year + 3] = 0.2
        
        elif stage in ['presales', 'launching']:
            # Revenue in 2-3 years
            timing[current_year + 2] = 0.4
            timing[current_year + 3] = 0.4
            timing[current_year + 4] = 0.2
        
        else:  # planning, land_bank
            # Revenue in 3+ years
            timing[current_year + 3] = 0.3
            timing[current_year + 4] = 0.4
            timing[current_year + 5] = 0.3
        
        return timing
    
    def update_financial_model(self,
                              existing_model: Dict,
                              revenue_forecast: pd.DataFrame,
                              assumptions: Dict) -> Dict:
        """
        Update existing financial model with new assumptions and forecasts
        
        Args:
            existing_model: Current financial model/assumptions
            revenue_forecast: Generated revenue forecast
            assumptions: New assumptions from analysis
            
        Returns:
            Updated financial model
        """
        
        updated_model = existing_model.copy() if existing_model else {}
        
        # Update revenue projections
        revenue_by_year = revenue_forecast[revenue_forecast['Project'] == 'TOTAL'].groupby('Year')['Revenue'].sum()
        updated_model['revenue_forecast'] = revenue_by_year.to_dict()
        
        # Update assumptions
        updated_model['assumptions'] = assumptions
        
        # Calculate derived metrics
        updated_model['metrics'] = self._calculate_financial_metrics(
            revenue_forecast, assumptions
        )
        
        # Add timestamp
        updated_model['last_updated'] = datetime.now().isoformat()
        updated_model['update_source'] = 'AI Project Discovery'
        
        return updated_model
    
    def _calculate_financial_metrics(self,
                                    revenue_forecast: pd.DataFrame,
                                    assumptions: Dict) -> Dict:
        """Calculate key financial metrics from forecast"""
        
        metrics = {}
        
        # Revenue metrics
        total_revenue = revenue_forecast[revenue_forecast['Project'] == 'TOTAL']['Revenue'].sum()
        metrics['total_revenue_forecast'] = total_revenue
        
        # Growth metrics
        yearly_revenue = revenue_forecast[revenue_forecast['Project'] == 'TOTAL'].groupby('Year')['Revenue'].sum()
        if len(yearly_revenue) > 1:
            revenues = yearly_revenue.values
            growth_rates = [(revenues[i+1] - revenues[i]) / revenues[i] 
                           for i in range(len(revenues)-1) if revenues[i] > 0]
            metrics['avg_growth_rate'] = np.mean(growth_rates) if growth_rates else 0
        
        # Margin metrics
        avg_margin = np.mean([stream['cogs_ratio'] 
                             for stream in assumptions.get('costs', {}).values()])
        metrics['avg_gross_margin'] = 1 - avg_margin if avg_margin else 0.25
        
        # Risk-adjusted metrics
        risk_discount = sum(assumptions.get('risk_adjustments', {}).values())
        metrics['risk_adjusted_revenue'] = total_revenue * (1 - risk_discount)
        
        return metrics