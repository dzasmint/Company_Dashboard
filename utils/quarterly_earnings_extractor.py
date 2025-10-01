"""
Quarterly Earnings Extractor - Uses ChatGPT to extract structured data from documents
"""

import openai
import json
from typing import Dict, List, Any, Optional
import os
from datetime import datetime
import streamlit as st


class QuarterlyEarningsExtractor:
    """Extracts structured financial data from quarterly earnings documents using ChatGPT"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with OpenAI API key"""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            openai.api_key = self.api_key
    
    def extract_from_earnings_presentation(self, 
                                          document_text: str,
                                          company_name: str,
                                          ticker: str,
                                          quarter: str) -> Dict[str, Any]:
        """
        Extract structured data from company earnings presentation
        
        Args:
            document_text: Full text from the document
            company_name: Company name
            ticker: Stock ticker
            quarter: Quarter (e.g., "2Q25")
            
        Returns:
            Dictionary with extracted financial and operational data
        """
        
        prompt = f"""
You are a financial analyst extracting data from a quarterly earnings presentation for {company_name} ({ticker}) - {quarter}.

Extract the following information from the document text and return it in strict JSON format:

{{
  "financial_metrics": {{
    "revenue": {{"value": <number in VND>, "yoy_growth": <percentage>, "qoq_growth": <percentage>}},
    "net_profit": {{"value": <number in VND>, "yoy_growth": <percentage>, "qoq_growth": <percentage>, "margin": <percentage>}},
    "gross_profit": {{"value": <number in VND>, "margin": <percentage>}},
    "ebitda": {{"value": <number in VND>, "margin": <percentage>}},
    "eps": <number in VND>,
    "book_value_per_share": <number in VND>
  }},
  "operational_metrics": {{
    "units_sold": {{"total": <number>, "yoy_growth": <percentage>, "qoq_growth": <percentage>}},
    "units_handed_over": <number>,
    "avg_selling_price": {{"value": <number in VND/m2>, "yoy_change": <percentage>}},
    "contracted_sales": <number in VND>,
    "inventory": {{"completed_units": <number>, "under_construction": <number>}}
  }},
  "project_highlights": [
    {{
      "project_name": "<name>",
      "status": "<status>",
      "units_launched": <number>,
      "units_sold": <number>,
      "sales_rate": <percentage>,
      "revenue_contribution": <number in VND>,
      "notes": "<key notes>"
    }}
  ],
  "new_launches": [
    {{
      "project_name": "<name>",
      "location": "<location>",
      "launch_date": "<date>",
      "total_units": <number>,
      "gfa_sqm": <number>,
      "target_asp": <number>
    }}
  ],
  "landbank_changes": {{
    "new_acquisitions": [
      {{
        "location": "<location>",
        "area_hectares": <number>,
        "cost": <number>,
        "acquisition_date": "<date>",
        "planned_project_type": "<type>"
      }}
    ],
    "total_landbank_hectares": <number>
  }},
  "management_outlook": {{
    "guidance": {{
      "full_year_revenue": <number>,
      "full_year_net_profit": <number>,
      "units_to_sell": <number>,
      "units_to_handover": <number>
    }},
    "key_strategies": ["<strategy1>", "<strategy2>"],
    "risks_mentioned": ["<risk1>", "<risk2>"],
    "opportunities": ["<opportunity1>", "<opportunity2>"]
  }},
  "balance_sheet": {{
    "total_assets": <number>,
    "total_equity": <number>,
    "total_debt": <number>,
    "net_debt": <number>,
    "debt_to_equity": <ratio>,
    "cash_and_equivalents": <number>,
    "inventory_real_estate": <number>
  }}
}}

Important:
- Use null for any missing data
- All financial values should be in VND (convert if needed)
- Growth rates and margins as percentages (e.g., 25.5 for 25.5%)
- Return ONLY valid JSON, no additional text
- If a section has no data, use empty object {{}} or empty array []

Document text:
{document_text[:50000]}  
"""

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a financial data extraction expert. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Add metadata
            result['extraction_metadata'] = {
                'source_type': 'earnings_presentation',
                'extraction_date': datetime.now().isoformat(),
                'model': 'gpt-4o',
                'confidence': 'high'
            }
            
            return result
            
        except Exception as e:
            st.error(f"Error extracting from earnings presentation: {str(e)}")
            return {"error": str(e)}
    
    def extract_from_sellside_report(self,
                                     document_text: str,
                                     company_name: str,
                                     ticker: str,
                                     quarter: str) -> Dict[str, Any]:
        """
        Extract analyst insights from sell-side research report
        
        Args:
            document_text: Full text from the document
            company_name: Company name
            ticker: Stock ticker
            quarter: Quarter (e.g., "2Q25")
            
        Returns:
            Dictionary with analyst insights
        """
        
        prompt = f"""
You are analyzing a sell-side research report for {company_name} ({ticker}) - {quarter}.

Extract analyst opinions, recommendations, and key insights in strict JSON format:

{{
  "analyst_insights": {{
    "target_price": <number in VND>,
    "recommendation": "<BUY|HOLD|SELL>",
    "analyst_firm": "<firm name>",
    "analyst_name": "<name>",
    "report_date": "<YYYY-MM-DD>",
    "key_points": [
      "<positive point 1>",
      "<positive point 2>"
    ],
    "concerns": [
      "<concern 1>",
      "<concern 2>"
    ],
    "catalysts": [
      "<catalyst 1>",
      "<catalyst 2>"
    ],
    "valuation_metrics": {{
      "pe_ratio": <number>,
      "pb_ratio": <number>,
      "ev_ebitda": <number>,
      "dividend_yield": <percentage>
    }}
  }},
  "financial_forecasts": {{
    "revenue_forecast": {{"fy2025": <number>, "fy2026": <number>}},
    "net_profit_forecast": {{"fy2025": <number>, "fy2026": <number>}},
    "eps_forecast": {{"fy2025": <number>, "fy2026": <number>}}
  }},
  "key_takeaways": [
    "<takeaway 1>",
    "<takeaway 2>",
    "<takeaway 3>"
  ]
}}

Important:
- Use null for missing data
- Return ONLY valid JSON
- Extract specific numbers and metrics

Document text:
{document_text[:50000]}
"""

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a financial analyst expert. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Add metadata
            result['extraction_metadata'] = {
                'source_type': 'sellside_report',
                'extraction_date': datetime.now().isoformat(),
                'model': 'gpt-4o',
                'confidence': 'high'
            }
            
            return result
            
        except Exception as e:
            st.error(f"Error extracting from sell-side report: {str(e)}")
            return {"error": str(e)}
    
    def extract_from_user_commentary(self,
                                     document_text: str,
                                     company_name: str,
                                     ticker: str,
                                     quarter: str) -> Dict[str, Any]:
        """
        Extract structured insights from user commentary/notes
        
        Args:
            document_text: User's notes or commentary
            company_name: Company name
            ticker: Stock ticker
            quarter: Quarter (e.g., "2Q25")
            
        Returns:
            Dictionary with categorized user insights
        """
        
        prompt = f"""
You are analyzing user commentary and notes about {company_name} ({ticker}) - {quarter}.

Extract and categorize the key insights in strict JSON format:

{{
  "user_notes": [
    {{
      "note": "<actual note text>",
      "category": "<management_tone|strategic_insight|market_observation|risk_factor|opportunity>",
      "importance": "<high|medium|low>",
      "sentiment": "<positive|neutral|negative>",
      "topic": "<specific topic>"
    }}
  ],
  "key_observations": [
    "<observation 1>",
    "<observation 2>"
  ],
  "important_quotes": [
    "<quote 1>",
    "<quote 2>"
  ],
  "action_items": [
    "<action or follow-up 1>",
    "<action or follow-up 2>"
  ]
}}

Important:
- Preserve the original meaning and tone
- Categorize each note appropriately
- Identify the most important insights
- Return ONLY valid JSON

User commentary:
{document_text}
"""

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing qualitative commentary. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Add metadata
            result['extraction_metadata'] = {
                'source_type': 'user_commentary',
                'extraction_date': datetime.now().isoformat(),
                'model': 'gpt-4o',
                'confidence': 'medium'
            }
            
            return result
            
        except Exception as e:
            st.error(f"Error extracting from user commentary: {str(e)}")
            return {"error": str(e)}
    
    def extract_by_document_type(self,
                                 document_text: str,
                                 document_type: str,
                                 company_name: str,
                                 ticker: str,
                                 quarter: str) -> Dict[str, Any]:
        """
        Route to appropriate extraction method based on document type
        
        Args:
            document_text: Full document text
            document_type: Type of document
            company_name: Company name
            ticker: Stock ticker
            quarter: Quarter
            
        Returns:
            Extracted data dictionary
        """
        
        if document_type == "earnings_presentation":
            return self.extract_from_earnings_presentation(
                document_text, company_name, ticker, quarter
            )
        elif document_type == "sellside_report":
            return self.extract_from_sellside_report(
                document_text, company_name, ticker, quarter
            )
        elif document_type == "user_commentary":
            return self.extract_from_user_commentary(
                document_text, company_name, ticker, quarter
            )
        else:
            return {"error": f"Unknown document type: {document_type}"}
