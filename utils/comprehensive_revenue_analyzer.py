"""
Comprehensive Revenue Stream Analyzer
Identifies ALL revenue streams of a company (real estate + other business segments)
Uses AI to extract revenue information from financial statements and web research
"""

import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json
import anthropic
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

class ComprehensiveRevenueAnalyzer:
    """Analyzes all revenue streams of a company, not just real estate"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Claude API key"""
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
    
    def extract_revenue_streams_from_pdf(self, 
                                        document_text: str,
                                        company_name: str,
                                        company_ticker: str) -> Dict:
        """
        Extract ALL revenue streams from financial statements
        
        Args:
            document_text: Extracted text from PDF
            company_name: Company name
            company_ticker: Stock ticker
            
        Returns:
            Dictionary with all identified revenue streams
        """
        
        prompt = f"""
        Analyze the financial statements of {company_name} ({company_ticker}) to identify ALL revenue streams and business segments.
        
        DOCUMENT TEXT:
        {document_text[:15000]}  # Limit for token management
        
        Extract and analyze:
        
        1. BUSINESS SEGMENTS:
           Identify all business segments and their revenue contribution
           - Real Estate Development (project sales, land sales)
           - Construction Services (external construction contracts)
           - Property Management (fees from managing properties)
           - Leasing/Rental Income (from investment properties)
           - Brokerage/Agency Services (commission income)
           - Hospitality (hotels, resorts)
           - Other Services (design, consulting, etc.)
        
        2. REVENUE BREAKDOWN:
           For each segment, extract:
           - Revenue amount (latest year)
           - % of total revenue
           - Growth rate (YoY)
           - Gross margin
           - Key drivers
        
        3. REAL ESTATE PROJECTS:
           If real estate development exists:
           - List of projects mentioned
           - Revenue recognition method
           - Presales/backlog information
           - Project pipeline value
        
        4. RECURRING vs NON-RECURRING:
           Classify revenue streams as:
           - One-time (project sales, land sales)
           - Recurring (rental, management fees)
           - Semi-recurring (construction contracts)
        
        5. GEOGRAPHIC BREAKDOWN:
           Revenue by region/city if available
        
        6. SEGMENT TRENDS:
           - Which segments are growing/declining
           - New business areas being developed
           - Segments being phased out
        
        Return comprehensive JSON:
        {{
            "revenue_streams": [
                {{
                    "segment_name": "Real Estate Development",
                    "revenue_2023": 10000000000000,
                    "revenue_2022": 8000000000000,
                    "revenue_percentage": 65,
                    "growth_rate": 0.25,
                    "gross_margin": 0.30,
                    "type": "non_recurring",
                    "sub_segments": [
                        "Residential sales",
                        "Commercial sales",
                        "Land sales"
                    ],
                    "key_metrics": {{
                        "presales_value": 5000000000000,
                        "units_sold": 2000,
                        "avg_price_per_sqm": 50000000
                    }}
                }},
                {{
                    "segment_name": "Construction Services",
                    "revenue_2023": 3000000000000,
                    "revenue_2022": 2500000000000,
                    "revenue_percentage": 20,
                    "growth_rate": 0.20,
                    "gross_margin": 0.15,
                    "type": "semi_recurring",
                    "key_metrics": {{
                        "backlog": 4000000000000,
                        "new_contracts": 3500000000000
                    }}
                }},
                {{
                    "segment_name": "Property Management",
                    "revenue_2023": 1000000000000,
                    "revenue_2022": 900000000000,
                    "revenue_percentage": 7,
                    "growth_rate": 0.11,
                    "gross_margin": 0.45,
                    "type": "recurring",
                    "key_metrics": {{
                        "properties_under_management": 50,
                        "total_gfa_managed": 2000000
                    }}
                }},
                {{
                    "segment_name": "Rental Income",
                    "revenue_2023": 800000000000,
                    "revenue_2022": 750000000000,
                    "revenue_percentage": 5,
                    "growth_rate": 0.07,
                    "gross_margin": 0.70,
                    "type": "recurring",
                    "key_metrics": {{
                        "occupancy_rate": 0.95,
                        "average_rent_per_sqm": 500000
                    }}
                }}
            ],
            "total_revenue": {{
                "2023": 15300000000000,
                "2022": 12150000000000,
                "growth_rate": 0.26
            }},
            "revenue_mix": {{
                "recurring_percentage": 12,
                "non_recurring_percentage": 65,
                "semi_recurring_percentage": 23
            }},
            "geographic_breakdown": {{
                "HCMC": 60,
                "Hanoi": 25,
                "Other": 15
            }},
            "real_estate_projects": [
                {{
                    "project_name": "Vinhomes Grand Park",
                    "revenue_recognized_2023": 3000000000000,
                    "presales_value": 2000000000000,
                    "completion_percentage": 70
                }}
            ],
            "future_growth_areas": [
                "Industrial real estate",
                "Data centers",
                "Renewable energy"
            ],
            "key_insights": [
                "Real estate remains core business at 65% of revenue",
                "Construction segment growing due to external contracts",
                "Increasing recurring revenue from property management"
            ]
        }}
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0,
                system="""You are a financial analyst expert in identifying and analyzing revenue streams
                from financial statements. You understand segment reporting, revenue recognition, and
                can identify both real estate and non-real estate revenue sources. Always return valid JSON.""",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse response
            response_text = response.content[0].text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            result = json.loads(response_text)
            result['extraction_date'] = datetime.now().isoformat()
            result['source'] = 'financial_statements'
            
            return result
            
        except Exception as e:
            st.error(f"Error extracting revenue streams: {str(e)}")
            return self._get_default_revenue_structure()
    
    def research_revenue_streams_from_web(self,
                                         company_name: str,
                                         company_ticker: str,
                                         perplexity_client=None) -> Dict:
        """
        Research all revenue streams using web research (Perplexity)
        
        Args:
            company_name: Company name
            company_ticker: Stock ticker
            perplexity_client: PerplexityProjectResearcher instance
            
        Returns:
            Dictionary with revenue streams from web research
        """
        
        if not perplexity_client:
            st.warning("Perplexity client not provided, using Claude for web research simulation")
            return self._research_with_claude(company_name, company_ticker)
        
        # Use Perplexity to research business segments
        query = f"""
        Research all business segments and revenue streams for {company_name} ({company_ticker}).
        
        Find information about:
        1. All business divisions and their revenue contribution
        2. Real estate development projects and pipeline
        3. Construction services and backlog
        4. Property management portfolio
        5. Rental/leasing income sources
        6. Other business activities
        7. Geographic revenue distribution
        8. Recent acquisitions or new business ventures
        9. Revenue growth trends by segment
        
        Provide specific numbers and percentages where available.
        """
        
        try:
            # This would call Perplexity API
            # For now, return a structured response
            return {
                "revenue_streams": [],
                "source": "web_research",
                "research_date": datetime.now().isoformat()
            }
        except Exception as e:
            st.error(f"Error researching revenue streams: {str(e)}")
            return {}
    
    def _research_with_claude(self, company_name: str, company_ticker: str) -> Dict:
        """Fallback research using Claude when Perplexity is not available"""
        
        prompt = f"""
        Based on your knowledge of Vietnamese real estate companies, provide a typical revenue stream
        breakdown for a company like {company_name} ({company_ticker}).
        
        Include typical business segments for Vietnamese property developers:
        - Real estate development
        - Construction services
        - Property management
        - Leasing/rental
        - Other services
        
        Return a JSON structure similar to the financial statement extraction.
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                temperature=0,
                system="You are a financial analyst familiar with Vietnamese real estate companies. Return valid JSON.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            return json.loads(response_text)
            
        except Exception as e:
            return self._get_default_revenue_structure()
    
    def merge_revenue_streams(self,
                            pdf_streams: Dict,
                            web_streams: Dict,
                            project_data: List[Dict]) -> Dict:
        """
        Merge revenue streams from PDF extraction, web research, and project discovery
        
        Args:
            pdf_streams: Revenue streams from financial statements
            web_streams: Revenue streams from web research
            project_data: Discovered real estate projects
            
        Returns:
            Comprehensive revenue model
        """
        
        merged = {
            "revenue_streams": [],
            "total_revenue": {},
            "revenue_mix": {},
            "real_estate_details": {},
            "comprehensive_model": True
        }
        
        # Start with PDF data as base (most reliable)
        if pdf_streams and 'revenue_streams' in pdf_streams:
            # Normalize field names
            normalized_streams = []
            for stream in pdf_streams['revenue_streams']:
                normalized = stream.copy()
                # Ensure consistent field naming
                if 'percentage_of_total' in normalized and 'revenue_percentage' not in normalized:
                    normalized['revenue_percentage'] = normalized['percentage_of_total']
                elif 'revenue_percentage' not in normalized and 'percentage_of_total' not in normalized:
                    # Calculate percentage if we have revenue amounts
                    total_rev = sum(s.get('revenue_2023', 0) for s in pdf_streams['revenue_streams'])
                    if total_rev > 0:
                        normalized['revenue_percentage'] = (stream.get('revenue_2023', 0) / total_rev) * 100
                    else:
                        normalized['revenue_percentage'] = 0
                
                # Ensure key_metrics exists
                if 'key_metrics' not in normalized:
                    normalized['key_metrics'] = {}
                    
                normalized_streams.append(normalized)
            
            merged['revenue_streams'] = normalized_streams
            merged['total_revenue'] = pdf_streams.get('total_revenue', {})
        
        # Enhance with web research
        if web_streams and 'revenue_streams' in web_streams:
            # Merge or add missing segments
            existing_segments = {s['segment_name']: s for s in merged['revenue_streams']}
            for web_segment in web_streams['revenue_streams']:
                if web_segment['segment_name'] not in existing_segments:
                    merged['revenue_streams'].append(web_segment)
        
        # Add detailed project data to real estate segment
        if project_data:
            # Find real estate segment
            for segment in merged['revenue_streams']:
                if 'real estate' in segment['segment_name'].lower():
                    segment['detailed_projects'] = project_data
                    segment['project_count'] = len(project_data)
                    
                    # Calculate metrics from projects
                    total_book_value = sum(p.get('book_value_vnd', 0) for p in project_data)
                    total_units = sum(p.get('total_units', 0) for p in project_data)
                    
                    segment['key_metrics']['total_book_value'] = total_book_value
                    segment['key_metrics']['total_units'] = total_units
                    segment['key_metrics']['project_count'] = len(project_data)
        
        # Calculate/recalculate revenue mix to ensure consistency
        total_rev = sum(s.get('revenue_2023', 0) for s in merged['revenue_streams'])
        if total_rev > 0:
            for segment in merged['revenue_streams']:
                # Always recalculate to ensure accuracy
                segment['revenue_percentage'] = (segment.get('revenue_2023', 0) / total_rev) * 100
        else:
            # If no revenue data, use equal distribution as fallback
            num_segments = len(merged['revenue_streams'])
            if num_segments > 0:
                for segment in merged['revenue_streams']:
                    segment['revenue_percentage'] = 100 / num_segments
        
        # Classify revenue types
        recurring = sum(s.get('revenue_2023', 0) for s in merged['revenue_streams'] 
                       if s.get('type') == 'recurring')
        non_recurring = sum(s.get('revenue_2023', 0) for s in merged['revenue_streams'] 
                           if s.get('type') == 'non_recurring')
        semi_recurring = sum(s.get('revenue_2023', 0) for s in merged['revenue_streams'] 
                            if s.get('type') == 'semi_recurring')
        
        if total_rev > 0:
            merged['revenue_mix'] = {
                'recurring_percentage': (recurring / total_rev) * 100,
                'non_recurring_percentage': (non_recurring / total_rev) * 100,
                'semi_recurring_percentage': (semi_recurring / total_rev) * 100
            }
        
        merged['merge_date'] = datetime.now().isoformat()
        
        return merged
    
    def generate_comprehensive_assumptions(self,
                                          revenue_model: Dict,
                                          current_year: int = None) -> Dict:
        """
        Generate financial assumptions for ALL revenue streams
        
        Args:
            revenue_model: Comprehensive revenue model
            current_year: Base year for projections
            
        Returns:
            Dictionary of assumptions by segment
        """
        
        if current_year is None:
            current_year = datetime.now().year
        
        assumptions = {
            'by_segment': {},
            'consolidated': {},
            'base_year': current_year
        }
        
        # Generate assumptions for each revenue stream
        for segment in revenue_model.get('revenue_streams', []):
            segment_name = segment['segment_name']
            segment_type = segment.get('type', 'non_recurring')
            
            segment_assumptions = {
                'revenue_growth_rate': self._estimate_growth_rate(segment),
                'gross_margin': segment.get('gross_margin', 0.25),
                'operating_margin': segment.get('gross_margin', 0.25) * 0.6,  # Rough estimate
            }
            
            # Segment-specific assumptions
            if 'real estate' in segment_name.lower():
                segment_assumptions.update({
                    'presales_velocity': 5,  # % per month
                    'price_appreciation': 0.08,  # 8% per year
                    'handover_rate': 0.95,
                    'construction_period_months': 24,
                    'presales_to_handover_months': 30
                })
            
            elif 'construction' in segment_name.lower():
                segment_assumptions.update({
                    'backlog_conversion_rate': 0.70,  # 70% of backlog converts to revenue
                    'new_contract_growth': 0.15,  # 15% growth in new contracts
                    'project_margin': 0.12,
                    'average_project_duration_months': 18
                })
            
            elif 'management' in segment_name.lower() or 'property' in segment_name.lower():
                segment_assumptions.update({
                    'portfolio_growth_rate': 0.20,  # 20% growth in properties managed
                    'fee_escalation_rate': 0.05,  # 5% annual fee increase
                    'client_retention_rate': 0.90
                })
            
            elif 'rental' in segment_name.lower() or 'leasing' in segment_name.lower():
                segment_assumptions.update({
                    'occupancy_rate': 0.92,
                    'rental_escalation': 0.05,  # 5% annual rent increase
                    'tenant_retention': 0.80
                })
            
            assumptions['by_segment'][segment_name] = segment_assumptions
        
        # Consolidated assumptions
        assumptions['consolidated'] = {
            'tax_rate': 0.20,
            'working_capital_ratio': 0.15,
            'capex_to_revenue': 0.05,
            'dividend_payout_ratio': 0.30,
            'debt_to_equity_target': 0.5
        }
        
        return assumptions
    
    def create_comprehensive_forecast(self,
                                     revenue_model: Dict,
                                     assumptions: Dict,
                                     forecast_years: int = 5) -> pd.DataFrame:
        """
        Create revenue forecast for ALL business segments
        
        Args:
            revenue_model: Comprehensive revenue model
            assumptions: Assumptions by segment
            forecast_years: Number of years to forecast
            
        Returns:
            DataFrame with complete revenue forecast
        """
        
        current_year = assumptions.get('base_year', datetime.now().year)
        years = list(range(current_year + 1, current_year + forecast_years + 1))
        
        forecast_data = []
        
        for segment in revenue_model.get('revenue_streams', []):
            segment_name = segment['segment_name']
            base_revenue = segment.get('revenue_2023', 0) or segment.get('revenue_2022', 0)
            
            if base_revenue == 0:
                continue
            
            segment_assumptions = assumptions['by_segment'].get(segment_name, {})
            growth_rate = segment_assumptions.get('revenue_growth_rate', 0.10)
            
            # Generate forecast for this segment
            for i, year in enumerate(years):
                # Apply growth with some variation
                if segment.get('type') == 'recurring':
                    # Steady growth for recurring revenue
                    revenue = base_revenue * ((1 + growth_rate) ** (i + 1))
                
                elif segment.get('type') == 'non_recurring':
                    # More volatile for project-based revenue
                    if 'real estate' in segment_name.lower():
                        # Use project pipeline if available
                        if 'detailed_projects' in segment:
                            revenue = self._forecast_from_projects(
                                segment['detailed_projects'],
                                year,
                                segment_assumptions
                            )
                        else:
                            # Cyclical pattern
                            cycle_factor = 1 + 0.2 * np.sin(i * np.pi / 2)
                            revenue = base_revenue * ((1 + growth_rate) ** (i + 1)) * cycle_factor
                    else:
                        revenue = base_revenue * ((1 + growth_rate) ** (i + 1))
                
                else:  # semi_recurring
                    # Moderate growth with some variation
                    revenue = base_revenue * ((1 + growth_rate) ** (i + 1)) * (0.9 + 0.2 * np.random.random())
                
                forecast_data.append({
                    'Year': year,
                    'Segment': segment_name,
                    'Revenue': revenue,
                    'Type': segment.get('type', 'non_recurring'),
                    'Gross_Profit': revenue * segment_assumptions.get('gross_margin', 0.25),
                    'Operating_Profit': revenue * segment_assumptions.get('operating_margin', 0.15)
                })
        
        # Create DataFrame
        df = pd.DataFrame(forecast_data)
        
        # Add totals
        if not df.empty:
            totals = df.groupby('Year').agg({
                'Revenue': 'sum',
                'Gross_Profit': 'sum',
                'Operating_Profit': 'sum'
            }).reset_index()
            totals['Segment'] = 'TOTAL'
            totals['Type'] = 'consolidated'
            
            df = pd.concat([df, totals], ignore_index=True)
        
        return df
    
    def _estimate_growth_rate(self, segment: Dict) -> float:
        """Estimate growth rate based on historical data or industry norms"""
        
        # If we have historical growth rate, use it
        if 'growth_rate' in segment and segment['growth_rate']:
            return segment['growth_rate']
        
        # Otherwise, use segment type defaults
        segment_name = segment.get('segment_name', '').lower()
        
        if 'real estate' in segment_name:
            return 0.15  # 15% default for real estate
        elif 'construction' in segment_name:
            return 0.12  # 12% for construction
        elif 'rental' in segment_name or 'leasing' in segment_name:
            return 0.08  # 8% for rental (stable)
        elif 'management' in segment_name:
            return 0.20  # 20% for property management (growing)
        else:
            return 0.10  # 10% default
    
    def _forecast_from_projects(self, projects: List[Dict], year: int, assumptions: Dict) -> float:
        """Calculate revenue from specific projects for a given year"""
        
        total_revenue = 0
        current_year = datetime.now().year
        
        for project in projects:
            # Determine when revenue will be recognized
            stage = project.get('stage', 'planning')
            
            if stage == 'completed':
                # Immediate revenue if units remain
                if year == current_year + 1:
                    total_revenue += project.get('book_value_vnd', 0) * 0.3
            
            elif stage == 'construction':
                # Revenue in 1-2 years
                if year in [current_year + 1, current_year + 2]:
                    total_revenue += project.get('book_value_vnd', 0) * 0.4
            
            elif stage == 'presales':
                # Revenue in 2-3 years
                if year in [current_year + 2, current_year + 3]:
                    total_revenue += project.get('book_value_vnd', 0) * 0.35
            
            else:  # planning
                # Revenue in 3+ years
                if year >= current_year + 3:
                    total_revenue += project.get('book_value_vnd', 0) * 0.2
        
        return total_revenue if total_revenue > 0 else 1000000000000  # Default 1T VND
    
    def _get_default_revenue_structure(self) -> Dict:
        """Return default revenue structure for Vietnamese real estate companies"""
        
        return {
            "revenue_streams": [
                {
                    "segment_name": "Real Estate Development",
                    "revenue_2023": 10000000000000,
                    "revenue_percentage": 70,
                    "type": "non_recurring",
                    "gross_margin": 0.30
                },
                {
                    "segment_name": "Construction Services",
                    "revenue_2023": 2000000000000,
                    "revenue_percentage": 15,
                    "type": "semi_recurring",
                    "gross_margin": 0.15
                },
                {
                    "segment_name": "Property Management",
                    "revenue_2023": 1000000000000,
                    "revenue_percentage": 8,
                    "type": "recurring",
                    "gross_margin": 0.40
                },
                {
                    "segment_name": "Rental Income",
                    "revenue_2023": 1000000000000,
                    "revenue_percentage": 7,
                    "type": "recurring",
                    "gross_margin": 0.70
                }
            ],
            "total_revenue": {
                "2023": 14000000000000
            }
        }