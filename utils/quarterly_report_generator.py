"""
Quarterly Report Generator - Creates comprehensive summary reports using ChatGPT
"""

import openai
from openai import OpenAI
import json
from typing import Dict, List, Any, Optional
import os
from datetime import datetime
from pathlib import Path
import streamlit as st


class QuarterlyReportGenerator:
    """Generates comprehensive quarterly earnings summary reports"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with OpenAI API key"""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            openai.api_key = self.api_key
        # Initialize modern OpenAI client when possible
        try:
            self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        except Exception:
            self.client = None
    
    def _load_report_prompt(self) -> str:
        """Load the report generation prompt template"""
        try:
            prompt_path = Path(__file__).parent / "quarterly_earnings_generate_report_prompt.txt"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            st.warning(f"Could not load report prompt file: {e}. Using default prompt.")
            return None
    
    def generate_summary_report(self,
                               earnings_data: List[Dict[str, Any]],
                               company_name: str,
                               ticker: str,
                               quarter: str,
                               year: int) -> Dict[str, Any]:
        """
        Generate comprehensive quarterly summary report from extracted data using custom prompt template
        
        Args:
            earnings_data: List of extracted data dictionaries from all sources
            company_name: Company name
            ticker: Stock ticker
            quarter: Quarter (e.g., "2Q25")
            year: Year
            
        Returns:
            Dictionary with summary report sections
        """
        
        # Prepare data summary for ChatGPT
        data_summary = self._prepare_data_for_summary(earnings_data)
        
        # Load the custom prompt template
        prompt_template = self._load_report_prompt()
        
        # Calculate next half/period for template
        quarter_num = int(quarter[0])
        year_short = quarter[-2:]
        
        # Determine next reporting period
        if quarter_num <= 2:
            next_period = f"2H{year_short}"
        else:
            next_year_short = str(int(year_short) + 1).zfill(2)
            next_period = f"1H{next_year_short}"
        
        # Calculate comparison quarters for the new prompt
        if quarter_num > 1:
            qoq_quarter = f"{quarter_num-1}Q{year_short}"
        else:
            qoq_quarter = f"4Q{str(int(year_short)-1).zfill(2)}"
        
        yoy_quarter = f"{quarter_num}Q{str(int(year_short)-1).zfill(2)}"
        comparison_quarters_str = f"{qoq_quarter} and {yoy_quarter}"
        
        # Extract publisher info from sell-side sources
        sell_side_publisher = "Consensus"
        for data in earnings_data:
            if data.get("source", {}).get("file_type") == "sell_side":
                sell_side_publisher = data.get("source", {}).get("publisher", "Unknown Analyst")
                break
        
        # If custom prompt loaded, use it; otherwise use default
        if prompt_template:
            # Replace all template variables with actual values
            prompt = prompt_template.replace("{{COMPANY_NAME}}", company_name)
            prompt = prompt.replace("{{TICKER}}", ticker)
            prompt = prompt.replace("{{QUARTER}}", quarter)
            prompt = prompt.replace("{{COMPARISON_QUARTERS}}", comparison_quarters_str)
            prompt = prompt.replace("{{TARGET_CCY}}", "VND")
            prompt = prompt.replace("{{TARGET_UNITS}}", "bn")
            prompt = prompt.replace("{{publisher}}", sell_side_publisher)
            
            # Add the JSON data at the end
            full_prompt = f"{prompt}\n\nINPUT DATA:\n{json.dumps(data_summary, indent=2)}"
        else:
            # Fallback to inline prompt if file not found (updated for buy-side focus)
            full_prompt = f"""
You are a senior buy-side analyst writing a professional quarterly report for {company_name} ({ticker}) - {quarter}.

PRIORITY OF SOURCES:
1) Buy-side commentary (our primary view)
2) Management (factual numbers and guidance)  
3) Sell-side (market consensus and expectations)

Generate a buy-side focused report with these sections:
1) Headline Summary
2) Earnings Review ({quarter} vs {comparison_quarters_str})
3) Presales & Sales Pipeline
4) Balance Sheet & Leverage
5) Guidance & Outlook
6) Valuation & Recommendation
7) Catalysts & Risks

CRITICAL RULES:
- Buy-side commentary drives the narrative
- Attribute management and sell-side sources explicitly [Management] / [Sell-side]
- Highlight where our view differs from sell-side consensus
- Professional buy-side tone and language
- Currency: VND billions

INPUT DATA:
{json.dumps(data_summary, indent=2)}

Return ONLY the final Markdown report.
"""

        try:
            messages = [
                {"role": "system", "content": "You are a senior buy-side equity analyst specializing in Vietnamese real estate companies. Write professional investment reports that prioritize internal buy-side analysis while incorporating management and sell-side perspectives with proper attribution."},
                {"role": "user", "content": full_prompt}
            ]

            model_used = "gpt-5"

            # Prefer OpenAI client with max_completion_tokens for GPT-5
            if self.client is not None:
                response = self.client.chat.completions.create(
                    model=model_used,
                    messages=messages,
                    max_completion_tokens=3500
                )
            else:
                # Legacy fallback
                response = openai.chat.completions.create(
                    model=model_used,
                    messages=messages
                )

            full_report = response.choices[0].message.content if response and response.choices else None

            # Debug: Log response details
            if response:
                st.info(f"GPT-5 Response - Choices: {len(response.choices) if response.choices else 0}")
                if response.choices and len(response.choices) > 0:
                    st.info(f"GPT-5 Message content length: {len(response.choices[0].message.content) if response.choices[0].message.content else 0}")
                    st.info(f"GPT-5 Finish reason: {response.choices[0].finish_reason if hasattr(response.choices[0], 'finish_reason') else 'N/A'}")
            
            # If GPT-5 returns empty content, surface an explicit error (no model fallback)
            if not full_report or not full_report.strip():
                error_msg = f"Empty response from gpt-5. Response object: {response is not None}, Choices: {len(response.choices) if response and response.choices else 0}"
                if response and response.choices and len(response.choices) > 0:
                    error_msg += f", Finish reason: {response.choices[0].finish_reason if hasattr(response.choices[0], 'finish_reason') else 'N/A'}"
                st.error(error_msg)
                raise ValueError(error_msg)
            
            # Parse report into sections based on your custom format
            sections = self._parse_custom_report_sections(full_report)
            
            result = {
                "summary_text": full_report,
                "summary_sections": sections,
                "generated_date": datetime.now().isoformat(),
                "generation_model": model_used,
                "source_document_count": len(earnings_data),
                "company_name": company_name,
                "ticker": ticker,
                "quarter": quarter,
                "year": year,
                "next_period": next_period
            }
            
            return result
            
        except Exception as e:
            st.error(f"Error generating summary report: {str(e)}")
            return {"error": str(e)}
    
    def _prepare_data_for_summary(self, earnings_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate and prepare data from multiple sources for summary generation
        Now handles the unified quarterly_analysis.json schema
        
        Args:
            earnings_data: List of extracted data from different sources (each following the schema)
            
        Returns:
            Aggregated data dictionary combining all sources
        """
        
        # Initialize with the schema structure
        aggregated = {
            "sources": [],
            "headline": {},
            "recognition_drivers": {},
            "presales": {},
            "balance_sheet": {},
            "one_offs_and_events": [],
            "outlook_and_guidance": {},
            "management_commentary": [],  # Collect all management commentary
            "sell_side_commentary": [],  # Collect all sell-side commentary
            "buy_side_commentary": [],   # Collect all buy-side commentary
            "financial_data": None,      # Financial data from internal database
            "methodology_notes": []
        }
        
        for idx, data in enumerate(earnings_data):
            # Track data sources
            source_info = {
                "index": idx + 1,
                "file_type": data.get("source", {}).get("file_type", "unknown"),
                "publisher": data.get("source", {}).get("publisher", "unknown"),
                "extraction_type": data.get("methodology", {}).get("extraction_metadata", {}).get("document_type", "unknown")
            }
            aggregated["sources"].append(source_info)
            
            # Merge headline financials (prefer management/actual data over estimates)
            if "headline" in data and data["headline"]:
                if not aggregated["headline"] or self._count_non_null(data["headline"]) > self._count_non_null(aggregated["headline"]):
                    aggregated["headline"] = data["headline"]
                    aggregated["headline"]["_source"] = source_info
            
            # Merge presales (prefer more complete data)
            if "presales" in data and data["presales"]:
                if not aggregated["presales"] or self._count_non_null(data["presales"]) > self._count_non_null(aggregated["presales"]):
                    aggregated["presales"] = data["presales"]
                    aggregated["presales"]["_source"] = source_info
            
            # Merge balance sheet (prefer more complete data)
            if "balance_sheet" in data and data["balance_sheet"]:
                if not aggregated["balance_sheet"] or self._count_non_null(data["balance_sheet"]) > self._count_non_null(aggregated["balance_sheet"]):
                    aggregated["balance_sheet"] = data["balance_sheet"]
                    aggregated["balance_sheet"]["_source"] = source_info
            
            # Merge recognition drivers
            if "recognition_drivers" in data and data["recognition_drivers"]:
                if not aggregated["recognition_drivers"]:
                    aggregated["recognition_drivers"] = data["recognition_drivers"]
                else:
                    # Combine project lists
                    if "projects_contributing" in data["recognition_drivers"]:
                        if "projects_contributing" not in aggregated["recognition_drivers"]:
                            aggregated["recognition_drivers"]["projects_contributing"] = []
                        aggregated["recognition_drivers"]["projects_contributing"].extend(
                            data["recognition_drivers"]["projects_contributing"]
                        )
            
            # Combine one-offs and events from all sources
            if "one_offs_and_events" in data and data["one_offs_and_events"]:
                for event in data["one_offs_and_events"]:
                    event["_source"] = source_info["file_type"]
                    aggregated["one_offs_and_events"].append(event)
            
            # Collect management commentary from management presentations
            if "management_commentary" in data and data["management_commentary"] and source_info["file_type"] == "management":
                commentary_with_source = data["management_commentary"].copy()
                commentary_with_source["_source"] = source_info
                aggregated["management_commentary"].append(commentary_with_source)
            
            # Collect sell-side commentary from sell-side reports
            if "sell_side_commentary" in data and data["sell_side_commentary"] and source_info["file_type"] == "sell_side":
                commentary_with_source = data["sell_side_commentary"].copy()
                commentary_with_source["_source"] = source_info
                aggregated["sell_side_commentary"].append(commentary_with_source)
            
            # Collect buy-side commentary from buy-side analyses
            if "buy_side_commentary" in data and data["buy_side_commentary"] and source_info["file_type"] == "buy_side":
                commentary_with_source = data["buy_side_commentary"].copy()
                commentary_with_source["_source"] = source_info
                aggregated["buy_side_commentary"].append(commentary_with_source)
            
            # Collect financial data from internal database (priority: use this as ground truth)
            if "financial_data" in data and data["financial_data"] and source_info["file_type"] == "financial_data":
                # Financial data takes precedence as ground truth
                aggregated["financial_data"] = data["financial_data"].copy()
                aggregated["financial_data"]["_source"] = source_info
            
            # Merge outlook (combine guidance from all sources)
            if "outlook_and_guidance" in data and data["outlook_and_guidance"]:
                if not aggregated["outlook_and_guidance"]:
                    aggregated["outlook_and_guidance"] = data["outlook_and_guidance"]
                else:
                    # Merge project highlights
                    if "project_pipeline_highlights" in data["outlook_and_guidance"]:
                        if "project_pipeline_highlights" not in aggregated["outlook_and_guidance"]:
                            aggregated["outlook_and_guidance"]["project_pipeline_highlights"] = []
                        aggregated["outlook_and_guidance"]["project_pipeline_highlights"].extend(
                            data["outlook_and_guidance"]["project_pipeline_highlights"]
                        )
                    # Append management quotes
                    if "management_quotes" in data["outlook_and_guidance"] and data["outlook_and_guidance"]["management_quotes"]:
                        if "management_quotes" not in aggregated["outlook_and_guidance"]:
                            aggregated["outlook_and_guidance"]["management_quotes"] = ""
                        aggregated["outlook_and_guidance"]["management_quotes"] += "\n\n" + data["outlook_and_guidance"]["management_quotes"]
            
            # Collect methodology notes
            if "methodology" in data and data["methodology"]:
                if "parsing_notes" in data["methodology"] and data["methodology"]["parsing_notes"]:
                    aggregated["methodology_notes"].append({
                        "source": source_info["file_type"],
                        "notes": data["methodology"]["parsing_notes"],
                        "confidence": data["methodology"].get("confidence_pct", 0)
                    })
        
        return aggregated
    
    def _count_non_null(self, obj: Any) -> int:
        """Count non-null values in nested dictionary"""
        if isinstance(obj, dict):
            return sum(1 for v in obj.values() if v is not None and v != {} and v != [])
        return 0
    
    def _parse_custom_report_sections(self, full_report: str) -> Dict[str, str]:
        """
        Parse the full report into named sections based on buy-side format
        
        Args:
            full_report: Full report text from custom prompt template
            
        Returns:
            Dictionary with section names and content
        """
        
        sections = {}
        
        # Define section markers based on your buy-side prompt template
        section_markers = [
            "Headline Summary",           # Section 1
            "Earnings Review",            # Section 2 
            "Presales & Sales Pipeline",  # Section 3
            "Balance Sheet & Leverage",   # Section 4
            "Guidance & Outlook",         # Section 5
            "Valuation & Recommendation", # Section 6
            "Catalysts & Risks"           # Section 7
        ]
        
        # Try to split by sections
        current_section = "full_report"
        current_content = []
        
        for line in full_report.split('\n'):
            # Check if this line is a section header
            is_header = False
            for marker in section_markers:
                # Look for section headers (allowing for variations in formatting)
                if (marker.lower() in line.lower() and 
                    (line.startswith("#") or line.endswith(")") or ":" in line or line.startswith("**")) and 
                    len(line.strip()) < 150):
                    # Save previous section
                    if current_content:
                        sections[current_section] = '\n'.join(current_content).strip()
                    # Start new section
                    current_section = marker.lower().replace(' ', '_').replace('&', 'and')
                    current_content = []
                    is_header = True
                    break
            
            if not is_header:
                current_content.append(line)
        
        # Save last section
        if current_content:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
    
    def generate_comparison_report(self,
                                  quarters_data: Dict[str, Dict],
                                  company_name: str,
                                  ticker: str) -> str:
        """
        Generate a comparison report across multiple quarters
        
        Args:
            quarters_data: Dictionary with quarter keys and their summary data
            company_name: Company name
            ticker: Stock ticker
            
        Returns:
            Comparison report text
        """
        
        quarters_list = sorted(quarters_data.keys())
        
        prompt = f"""
You are analyzing quarterly trends for {company_name} ({ticker}).

Generate a comparative analysis across these quarters: {', '.join(quarters_list)}

Data for each quarter:
{json.dumps(quarters_data, indent=2)}

Create a report with:
1. TREND SUMMARY - Key trends across quarters
2. FINANCIAL TREND ANALYSIS - Revenue, profit, margins over time
3. OPERATIONAL TRENDS - Units sold, ASP, sales performance
4. STRATEGIC EVOLUTION - Changes in strategy and focus
5. PERFORMANCE TRAJECTORY - Improving, stable, or declining?

Be specific with numbers and highlight significant changes.
"""

        try:
            messages = [
                {"role": "system", "content": "You are a senior analyst analyzing quarterly trends."},
                {"role": "user", "content": prompt}
            ]

            if self.client is not None:
                response = self.client.chat.completions.create(
                    model="gpt-5",
                    messages=messages,
                    max_completion_tokens=3000
                )
            else:
                response = openai.chat.completions.create(
                    model="gpt-5",
                    messages=messages
                )

            content = response.choices[0].message.content if response and response.choices else None
            if not content or not content.strip():
                raise ValueError("Empty response from gpt-5 during comparison generation")

            return content
            
        except Exception as e:
            st.error(f"Error generating comparison report: {str(e)}")
            return f"Error: {str(e)}"
