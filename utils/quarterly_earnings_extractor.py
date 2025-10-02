"""
Quarterly Earnings Extractor - Uses ChatGPT to extract structured data from documents
"""

import openai
import json
from typing import Dict, List, Any, Optional
import os
from datetime import datetime
from pathlib import Path
import streamlit as st


class QuarterlyEarningsExtractor:
    """Extracts structured financial data from quarterly earnings documents using ChatGPT"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with OpenAI API key"""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            openai.api_key = self.api_key
        
        # Load the JSON schema
        self.schema = self._load_schema()
    
    def _load_schema(self) -> Dict[str, Any]:
        """Load the quarterly analysis JSON schema"""
        try:
            schema_path = Path(__file__).parent / "quarterly_analysis.json"
            with open(schema_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            st.warning(f"Could not load schema file: {e}. Using default schema.")
            # Return a basic schema as fallback
            return {}
    
    def _load_management_prompt(self) -> str:
        """Load the management earnings presentation prompt template"""
        try:
            prompt_path = Path(__file__).parent / "quarterly_earnings_management_presentation_prompt.txt"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            st.warning(f"Could not load management prompt file: {e}. Using default prompt.")
            return None
    
    def _load_sellside_prompt(self) -> str:
        """Load the sell-side report prompt template"""
        try:
            prompt_path = Path(__file__).parent / "quarterly_earnings_sell_side_report_prompt.txt"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            st.warning(f"Could not load sell-side prompt file: {e}. Using default prompt.")
            return None
    
    def extract_from_earnings_presentation(self, 
                                          document_text: str,
                                          company_name: str,
                                          ticker: str,
                                          quarter: str) -> Dict[str, Any]:
        """
        Extract structured data from company earnings presentation using custom prompt template
        
        Args:
            document_text: Full text from the document
            company_name: Company name
            ticker: Stock ticker
            quarter: Quarter (e.g., "2Q25")
            
        Returns:
            Dictionary with extracted financial and operational data following the schema
        """
        
        # Load the custom prompt template
        prompt_template = self._load_management_prompt()
        
        # Parse quarter to extract components (e.g., "2Q25" -> quarter_num=2, year=2025)
        quarter_num = int(quarter[0])  # First character is quarter number (1-4)
        year_short = quarter[-2:]  # Last 2 characters are year (e.g., "25")
        year_full = 2000 + int(year_short)
        
        # Calculate comparison quarters (QoQ and YoY)
        # QoQ: Previous quarter
        if quarter_num > 1:
            qoq_quarter = f"{quarter_num-1}Q{year_short}"
        else:
            # Q1 -> previous Q4 of last year
            qoq_quarter = f"4Q{str(year_full-1)[2:]}"
        
        # YoY: Same quarter last year
        yoy_quarter = f"{quarter_num}Q{str(year_full-1)[2:]}"
        
        comparison_quarters = [qoq_quarter, yoy_quarter]
        
        # Calculate fiscal half (1H or 2H)
        # Q1 and Q2 -> 1H, Q3 and Q4 -> 2H
        fiscal_half = f"{(quarter_num+1)//2}H{year_short}"
        
        # Format the schema for the prompt
        schema_str = json.dumps(self.schema, indent=2)
        
        # If custom prompt loaded, use it; otherwise use default
        if prompt_template:
            # Replace all template variables with actual values
            prompt = prompt_template.replace("{{COMPANY_NAME}}", company_name)
            prompt = prompt.replace("{{TICKER}}", ticker)
            prompt = prompt.replace("{{QUARTER}}", quarter)
            prompt = prompt.replace("{{COMPARISON_QUARTERS_JSON}}", json.dumps(comparison_quarters))
            prompt = prompt.replace("{{FISCAL_HALF}}", fiscal_half)
            prompt = prompt.replace("{{TARGET_CCY}}", "VND")
            prompt = prompt.replace("{{TARGET_UNITS}}", "bn")
            prompt = prompt.replace("{{ACCOUNTING_BASIS}}", "VAS")  # Default for Vietnam, but can detect IFRS/USGAAP
            
            # Add schema and document text at the end
            full_prompt = f"{prompt}\n\nJSON SCHEMA:\n{schema_str}\n\nDOCUMENT TEXT:\n{document_text[:50000]}"
        else:
            # Fallback to inline prompt if file not found
            full_prompt = f"""
You are a meticulous financial data extractor for Vietnamese real estate companies.

Company: {company_name} ({ticker})
Quarter: {quarter}

Extract data from the management earnings presentation and output ONE JSON object conforming EXACTLY to the schema.

JSON SCHEMA:
{schema_str}

CRITICAL RULES:
- Zero hallucination: if a metric is not explicitly stated, leave it null
- Distinguish reported vs adjusted metrics (adjusted includes BCC, bulk sales)
- Distinguish presales vs recognized revenue
- Capture project-level contributors with exact names
- Normalize all amounts to VND billions
- Set currency to "VND", units to "bn"
- Set accounting_basis to "VAS" unless deck indicates IFRS or USGAAP
- Return ONLY valid JSON

Document text:
{document_text[:50000]}
"""

        try:
            response = openai.chat.completions.create(
                model="gpt-5",
                messages=[
                    {"role": "system", "content": "You are a meticulous financial data extractor specializing in Vietnamese real estate earnings. Zero hallucination tolerance. Extract only what is explicitly present in the document."},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=1.0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Add extraction metadata
            if 'methodology' not in result:
                result['methodology'] = {}
            
            result['methodology']['extraction_metadata'] = {
                'extraction_tool': 'quarterly_earnings_extractor',
                'extraction_date': datetime.now().isoformat(),
                'model': 'gpt-5',
                'document_type': 'earnings_presentation'
            }
            
            return result
            
        except Exception as e:
            st.error(f"Error extracting from earnings presentation: {str(e)}")
            return {"error": str(e)}
    
    def extract_from_sellside_report(self,
                                     document_text: str,
                                     company_name: str,
                                     ticker: str,
                                     quarter: str,
                                     analyst_firm: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract data from sell-side research report using custom prompt template
        
        Args:
            document_text: Full text from the document
            company_name: Company name
            ticker: Stock ticker
            quarter: Quarter (e.g., "2Q25")
            analyst_firm: Analyst firm name (e.g., "VCBS", "SSI")
            
        Returns:
            Dictionary with analyst insights following the schema
        """
        
        # Load the custom prompt template
        prompt_template = self._load_sellside_prompt()
        
        # Parse quarter to extract components (same logic as management)
        quarter_num = int(quarter[0])
        year_short = quarter[-2:]
        year_full = 2000 + int(year_short)
        
        # Calculate comparison quarters (QoQ and YoY)
        if quarter_num > 1:
            qoq_quarter = f"{quarter_num-1}Q{year_short}"
        else:
            qoq_quarter = f"4Q{str(year_full-1)[2:]}"
        
        yoy_quarter = f"{quarter_num}Q{str(year_full-1)[2:]}"
        comparison_quarters = [qoq_quarter, yoy_quarter]
        
        # Calculate fiscal half
        fiscal_half = f"{(quarter_num+1)//2}H{year_short}"
        
        # Format the schema for the prompt
        schema_str = json.dumps(self.schema, indent=2)
        
        # If custom prompt loaded, use it; otherwise use default
        if prompt_template:
            # Replace all template variables with actual values
            prompt = prompt_template.replace("{{COMPANY_NAME}}", company_name)
            prompt = prompt.replace("{{TICKER}}", ticker)
            prompt = prompt.replace("{{QUARTER}}", quarter)
            prompt = prompt.replace("{{COMPARISON_QUARTERS_JSON}}", json.dumps(comparison_quarters))
            prompt = prompt.replace("{{FISCAL_HALF}}", fiscal_half)
            prompt = prompt.replace("{{SELL_SIDE_FIRM}}", analyst_firm or "Unknown")
            prompt = prompt.replace("{{TARGET_CCY}}", "VND")
            prompt = prompt.replace("{{TARGET_UNITS}}", "bn")
            prompt = prompt.replace("{{ACCOUNTING_BASIS}}", "VAS")  # Default for Vietnam, but can detect IFRS/USGAAP
            
            # Add schema and document text at the end
            full_prompt = f"{prompt}\n\nJSON SCHEMA:\n{schema_str}\n\nDOCUMENT TEXT:\n{document_text[:50000]}"
        else:
            # Fallback to inline prompt if file not found
            full_prompt = f"""
You are a meticulous financial data extractor for Vietnamese sell-side reports.

Company: {company_name} ({ticker})
Quarter: {quarter}
Analyst Firm: {analyst_firm or "Unknown"}

Extract data from the sell-side report and output ONE JSON object conforming EXACTLY to the schema.

JSON SCHEMA:
{schema_str}

CRITICAL RULES:
- Zero hallucination: only record what the note states
- Distinguish reported vs adjusted metrics
- Do NOT infer bases for % changes
- Capture analyst estimates separately from actuals
- Normalize all amounts to VND billions
- Set currency to "VND", units to "bn"
- Set source.file_type to "sell_side"
- Set source.publisher to analyst firm
- Return ONLY valid JSON

Document text:
{document_text[:50000]}
"""

        try:
            response = openai.chat.completions.create(
                model="gpt-5",
                messages=[
                    {"role": "system", "content": "You are a meticulous financial data extractor specializing in Vietnamese sell-side research reports. Zero hallucination tolerance. Only extract what is explicitly present. Distinguish actuals from estimates."},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=1.0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Add extraction metadata
            if 'methodology' not in result:
                result['methodology'] = {}
            
            result['methodology']['extraction_metadata'] = {
                'extraction_tool': 'quarterly_earnings_extractor',
                'extraction_date': datetime.now().isoformat(),
                'model': 'gpt-5',
                'document_type': 'sellside_report'
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
        Extract structured insights from user commentary/notes using the unified schema
        
        Args:
            document_text: User's notes or commentary
            company_name: Company name
            ticker: Stock ticker
            quarter: Quarter (e.g., "2Q25")
            
        Returns:
            Dictionary with categorized user insights following the schema
        """
        
        # Format the schema for the prompt
        schema_str = json.dumps(self.schema, indent=2)
        
        prompt = f"""
You are analyzing user commentary and notes about {company_name} ({ticker}) - {quarter}.

This is a Vietnamese real estate company. The user has provided qualitative observations, opinions, and notes about the company's quarterly performance.
Extract and structure this information according to the JSON schema below.

JSON SCHEMA TO FOLLOW:
{schema_str}

IMPORTANT INSTRUCTIONS:
1. Return ONLY valid JSON matching the schema structure exactly
2. For the "company" and "ticker" fields:
   - Set "company" to "{company_name}"
   - Set "ticker" to "{ticker}"
3. For the "source" section:
   - Set "file_type" to "management" (or "sell_side" if commentary references analyst views)
   - Set "publisher" to "User Commentary"
4. For "currency" and "business_model":
   - Set "currency" to "VND"
   - Infer business model from user's description of the Vietnamese company
5. Extract any quantitative data mentioned by the user (revenue, units, etc.) into appropriate sections
6. For qualitative insights:
   - Use "one_offs_and_events" for notable observations about specific events
   - Use "outlook_and_guidance.management_quotes" for user's key observations
   - Use "methodology.parsing_notes" to capture the qualitative nature of the source
7. Preserve the user's tone and opinions
8. If user mentions specific projects, add them to "presales.new_launches" or "recognition_drivers.projects_contributing"
9. If user discusses balance sheet concerns, extract to "balance_sheet.notable_movements"
10. Set "methodology.confidence_pct" lower (30-60%) to reflect qualitative source
11. Use notes fields liberally to capture context and user opinions

SPECIAL HANDLING FOR USER COMMENTARY:
- Much of the data will be qualitative observations rather than hard numbers
- Use null for most quantitative fields unless user explicitly mentions numbers
- Focus on capturing:
  * User's sentiment and tone
  * Key observations and opinions
  * Concerns or opportunities noted
  * Strategic insights
  * Management tone observations
  * Market positioning views

User commentary:
{document_text}
"""

        try:
            response = openai.chat.completions.create(
                model="gpt-5",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing qualitative financial commentary and structuring insights. You preserve the original meaning while organizing information systematically."},
                    {"role": "user", "content": prompt}
                ],
                temperature=1.0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Add extraction metadata
            if 'methodology' not in result:
                result['methodology'] = {}
            
            result['methodology']['extraction_metadata'] = {
                'extraction_tool': 'quarterly_earnings_extractor',
                'extraction_date': datetime.now().isoformat(),
                'model': 'gpt-5',
                'document_type': 'user_commentary'
            }
            
            return result
            
        except Exception as e:
            st.error(f"Error extracting from user commentary: {str(e)}")
            return {"error": str(e)}
    
    def extract_from_buyside_commentary(self, 
                                       commentary_text: str,
                                       company_name: str,
                                       ticker: str,
                                       quarter: str) -> Dict[str, Any]:
        """
        Extract data from buy-side commentary using custom prompt template
        
        Args:
            commentary_text: Buy-side analyst commentary text
            company_name: Company name
            ticker: Stock ticker
            quarter: Quarter (e.g., "2Q25")
            
        Returns:
            Dictionary with buy-side insights following the schema
        """
        
        # Load the custom prompt template
        buyside_prompt = self._load_buyside_prompt()
        
        # Format the schema for the prompt
        schema_str = json.dumps(self.schema, indent=2)
        
        # If custom prompt loaded, use it; otherwise use default
        if buyside_prompt:
            # Replace template variables with actual values
            prompt = buyside_prompt.replace("{{COMPANY_NAME}}", company_name)
            prompt = prompt.replace("{{TICKER}}", ticker)
            prompt = prompt.replace("{{QUARTER}}", quarter)
            prompt = prompt.replace("{{YOUR_NAME_OR_TEAM}}", "Internal Buy-Side Team")
            
            # Add schema and commentary text at the end
            full_prompt = f"{prompt}\n\nJSON SCHEMA:\n{schema_str}\n\nBUY-SIDE COMMENTARY TEXT:\n{commentary_text}"
        else:
            # Fallback to inline prompt if file not found
            full_prompt = f"""
You are a meticulous note organizer processing buy-side analyst commentary.

Company: {company_name} ({ticker})
Quarter: {quarter}

Extract and organize the buy-side commentary according to the schema.

JSON SCHEMA:
{schema_str}

CRITICAL RULES:
- Capture each bullet exactly as written in raw_bullets
- Classify each point by category (earnings, presales, balance_sheet, etc.)
- Extract valuation analysis if present (RNAV, target price, upside/downside)
- Determine sentiment: positive/neutral/negative/mixed/not_stated
- Do not invent metrics or sentiment
- Return ONLY valid JSON

Buy-side commentary:
{commentary_text}
"""

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a meticulous note organizer specializing in buy-side investment analysis. Extract and structure commentary without losing nuance or inventing details."},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=1.0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Add extraction metadata
            if 'methodology' not in result:
                result['methodology'] = {}
            
            result['methodology'].update({
                "extraction_metadata": {
                    "source_type": "buyside_commentary",
                    "document_type": "buyside_commentary",
                    "extraction_timestamp": datetime.now().isoformat(),
                    "word_count": len(commentary_text.split())
                }
            })
            
            return result
            
        except Exception as e:
            st.error(f"Error extracting from buy-side commentary: {str(e)}")
            return {"error": str(e)}
    
    def _load_buyside_prompt(self) -> str:
        """Load the buy-side commentary prompt template"""
        try:
            prompt_path = Path(__file__).parent / "quarterly_earnings_buy_side_commentary_prompt.txt"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            st.warning(f"Could not load buy-side prompt file: {e}. Using default prompt.")
            return None
    
    def extract_by_document_type(self,
                                 document_text: str,
                                 document_type: str,
                                 company_name: str,
                                 ticker: str,
                                 quarter: str,
                                 analyst_firm: Optional[str] = None) -> Dict[str, Any]:
        """
        Route to appropriate extraction method based on document type
        
        Args:
            document_text: Full document text
            document_type: Type of document
            company_name: Company name
            ticker: Stock ticker
            quarter: Quarter
            analyst_firm: Analyst firm name (optional, for sell-side reports)
            
        Returns:
            Extracted data dictionary
        """
        
        if document_type == "earnings_presentation":
            return self.extract_from_earnings_presentation(
                document_text, company_name, ticker, quarter
            )
        elif document_type == "sellside_report":
            return self.extract_from_sellside_report(
                document_text, company_name, ticker, quarter, analyst_firm
            )
        elif document_type == "buyside_commentary":
            return self.extract_from_buyside_commentary(
                document_text, company_name, ticker, quarter
            )
        else:
            return {"error": f"Unknown document type: {document_type}"}
