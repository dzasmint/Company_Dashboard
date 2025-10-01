"""
Quarterly Report Generator - Creates comprehensive summary reports using ChatGPT
"""

import openai
import json
from typing import Dict, List, Any, Optional
import os
from datetime import datetime
import streamlit as st


class QuarterlyReportGenerator:
    """Generates comprehensive quarterly earnings summary reports"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with OpenAI API key"""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if self.api_key:
            openai.api_key = self.api_key
    
    def generate_summary_report(self,
                               earnings_data: List[Dict[str, Any]],
                               company_name: str,
                               ticker: str,
                               quarter: str,
                               year: int) -> Dict[str, Any]:
        """
        Generate comprehensive quarterly summary report from extracted data
        
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
        
        prompt = f"""
You are a senior equity research analyst writing a comprehensive quarterly earnings summary for {company_name} ({ticker}) - {quarter} {year}.

You have access to data from {len(earnings_data)} source documents including earnings presentations, analyst reports, and commentary.

Based on the following aggregated data, write a professional, detailed, and data-driven quarterly earnings summary.

DATA:
{json.dumps(data_summary, indent=2)}

Generate a comprehensive report with the following sections:

1. EXECUTIVE SUMMARY (3-4 sentences capturing the key story of the quarter)

2. FINANCIAL PERFORMANCE
   - Revenue analysis with YoY and QoQ comparisons
   - Profitability metrics (gross profit, EBITDA, net profit, margins)
   - EPS and book value per share
   - Key drivers of performance

3. OPERATIONAL HIGHLIGHTS
   - Units sold and handed over
   - Average selling prices and trends
   - Contracted sales vs recognized revenue
   - Inventory position

4. PROJECT UPDATES & HIGHLIGHTS
   - Performance of key projects
   - Sales rates and revenue contributions
   - Notable achievements or issues

5. NEW PROJECT LAUNCHES
   - New launches during the quarter
   - Pipeline and upcoming launches
   - Strategic rationale

6. LAND BANK & EXPANSION
   - New land acquisitions
   - Total land bank position
   - Future development potential

7. MANAGEMENT OUTLOOK & GUIDANCE
   - Full year guidance and targets
   - Strategic priorities and focus areas
   - Management commentary on market conditions
   - Risks and opportunities mentioned

8. ANALYST VIEWS & MARKET SENTIMENT
   - Sell-side recommendations and target prices
   - Key catalysts identified by analysts
   - Concerns and risks highlighted
   - Valuation metrics

9. KEY TAKEAWAYS (5-7 bullet points)
   - Most important insights from the quarter
   - What investors should focus on

Format guidelines:
- Be specific with numbers and percentages
- Provide context for all metrics (YoY, QoQ comparisons)
- Professional tone, suitable for investment reports
- Clear section headers
- Use bullet points for lists
- Highlight significant changes or trends
- If data is missing for a section, note it briefly and move on

Write the complete report now:
"""

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a senior equity research analyst writing professional quarterly earnings summaries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=4000
            )
            
            full_report = response.choices[0].message.content
            
            # Parse report into sections
            sections = self._parse_report_sections(full_report)
            
            result = {
                "summary_text": full_report,
                "summary_sections": sections,
                "generated_date": datetime.now().isoformat(),
                "generation_model": "gpt-4o",
                "source_document_count": len(earnings_data),
                "company_name": company_name,
                "ticker": ticker,
                "quarter": quarter,
                "year": year
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
    
    def _parse_report_sections(self, full_report: str) -> Dict[str, str]:
        """
        Parse the full report into named sections
        
        Args:
            full_report: Full report text
            
        Returns:
            Dictionary with section names and content
        """
        
        sections = {}
        
        # Define section markers
        section_markers = [
            "EXECUTIVE SUMMARY",
            "FINANCIAL PERFORMANCE",
            "OPERATIONAL HIGHLIGHTS",
            "PROJECT UPDATES",
            "NEW PROJECT LAUNCHES",
            "LAND BANK",
            "MANAGEMENT OUTLOOK",
            "ANALYST VIEWS",
            "KEY TAKEAWAYS"
        ]
        
        # Try to split by sections
        current_section = "full_report"
        current_content = []
        
        for line in full_report.split('\n'):
            # Check if this line is a section header
            is_header = False
            for marker in section_markers:
                if marker.upper() in line.upper() and len(line.strip()) < 100:
                    # Save previous section
                    if current_content:
                        sections[current_section] = '\n'.join(current_content).strip()
                    # Start new section
                    current_section = marker.lower().replace(' ', '_')
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
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a senior analyst analyzing quarterly trends."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=3000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            st.error(f"Error generating comparison report: {str(e)}")
            return f"Error: {str(e)}"
