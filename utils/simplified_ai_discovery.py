"""
Simplified AI Discovery Module for Document Analysis
"""

import streamlit as st
import pandas as pd
import PyPDF2
import anthropic
import os
import json
import re
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class SimplifiedAIDiscovery:
    """Simplified AI discovery for business segments and real estate projects"""
    
    def __init__(self):
        """Initialize with Claude AI client"""
        self.client = None
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            self.client = anthropic.Anthropic(api_key=api_key)
    
    def extract_text_from_pdf(self, pdf_file) -> str:
        """Extract text content from PDF file"""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            total_pages = len(pdf_reader.pages)
            
            # Read all pages
            for page_num in range(total_pages):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                text += page_text + "\n"
            
            return text
        except Exception as e:
            st.error(f"Error reading PDF {pdf_file.name}: {str(e)}")
            return ""
    
    def analyze_business_segments(self, documents: List[Dict[str, str]]) -> pd.DataFrame:
        """Analyze business segments using Claude AI with intelligent merging"""
        if not self.client:
            st.error("Claude AI not initialized")
            return pd.DataFrame()
        
        # Combine document texts with clear separation
        combined_text = ""
        doc_list = []
        for doc in documents:
            doc_list.append(doc['name'])
            combined_text += f"\n\n=== DOCUMENT: {doc['name']} ===\n"
            combined_text += doc['text'][:60000]  # Increased limit per doc
            if len(combined_text) > 120000:  # Increased total limit
                break
        
        prompt = """You are analyzing financial documents that may be in Vietnamese or English. 
        Extract and intelligently merge business segment information from ALL documents.
        
        IMPORTANT INSTRUCTIONS:
        1. Documents may be in Vietnamese or English - understand both languages
        2. Merge information from multiple documents to create the MOST COMPLETE picture
        3. If the same segment appears in multiple documents with different data, use the most recent or complete data
        4. Common Vietnamese business segments to look for:
           - Bất động sản (Real Estate)
           - Phát triển dự án (Project Development)
           - Xây dựng (Construction)
           - Cho thuê (Leasing/Rental)
           - Dịch vụ (Services)
           - Thương mại (Trading/Commerce)
           - Sản xuất (Manufacturing)
           - Du lịch/Khách sạn (Tourism/Hospitality)
        5. Common English segments: Real Estate Development, Property Investment, Construction, Hospitality, Retail, Services
        6. Extract data for ALL periods mentioned (yearly: 2022, 2023, 2024 and quarterly: Q1/2023, Q2/2023, etc.)
        
        Look for these metrics (in Vietnamese or English):
        - Doanh thu/Revenue
        - Giá vốn hàng bán/COGS/Cost of Goods Sold
        - Lợi nhuận gộp/Gross Profit
        - Biên lợi nhuận gộp/Gross Margin
        
        MERGE STRATEGY:
        - If Document 1 has 2023 data and Document 2 has 2024 data, include BOTH
        - If Document 1 has segments A,B and Document 2 has segments B,C, include ALL (A,B,C)
        - If both documents have same period/segment but different values, use the one from the most recent document or annual report over quarterly
        
        Return ONLY a valid JSON object with this exact structure:
        {
            "segments": ["Actual Segment Name 1", "Actual Segment Name 2"],
            "periods": ["2022", "2023", "2024", "Q1/2024", "Q2/2024"],
            "data": {
                "revenue": {
                    "Segment1": {"2023": 1234.5, "2024": 1456.7},
                    "Segment2": {"2023": 890.1, "2024": 950.3},
                    "Total": {"2023": 2124.6, "2024": 2407.0}
                },
                "cogs": {
                    "Segment1": {"2023": 900.0, "2024": 1000.0},
                    "Segment2": {"2023": 600.0, "2024": 650.0},
                    "Total": {"2023": 1500.0, "2024": 1650.0}
                },
                "gross_profit": {
                    "Segment1": {"2023": 334.5, "2024": 456.7},
                    "Segment2": {"2023": 290.1, "2024": 300.3},
                    "Total": {"2023": 624.6, "2024": 757.0}
                },
                "gross_margin": {
                    "Segment1": {"2023": 27.1, "2024": 31.4},
                    "Segment2": {"2023": 32.6, "2024": 31.6},
                    "Blended": {"2023": 29.4, "2024": 31.5}
                }
            },
            "data_sources": ["doc1.pdf", "doc2.pdf"],
            "merge_notes": "Merged Q1 and Q2 data from quarterly report with annual data from 2023 report"
        }
        
        All amounts in VND billions (tỷ VND).
        Margins as percentages (e.g., 25.5 for 25.5%).
        Use "N/A" only for truly missing values.
        Start with { and end with }
        
        Documents being analyzed:
        """ + "\n".join(doc_list) + "\n\nDocument contents:\n" + combined_text[:120000]
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            try:
                result = json.loads(response_text)
                return self.format_segments_dataframe(result)
            except json.JSONDecodeError:
                # Try to extract JSON
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return self.format_segments_dataframe(result)
            
        except Exception as e:
            st.error(f"Error analyzing segments: {str(e)}")
        
        return pd.DataFrame()
    
    def format_segments_dataframe(self, result: Dict) -> pd.DataFrame:
        """Format segments data into DataFrame with merge information"""
        if not result:
            return pd.DataFrame()
        
        df_data = []
        segments = result.get('segments', [])
        periods = result.get('periods', [])
        data = result.get('data', {})
        
        if not segments or not periods:
            return pd.DataFrame()
        
        # Store merge notes if available
        if 'merge_notes' in result and result['merge_notes']:
            st.info(f"📝 Merge Notes: {result['merge_notes']}")
        
        # Store data sources if available
        if 'data_sources' in result and result['data_sources']:
            st.success(f"📄 Data merged from: {', '.join(result['data_sources'])}")
        
        # Sort periods to ensure chronological order
        def sort_period(period):
            # Handle both yearly (2023) and quarterly (Q1/2023) formats
            if 'Q' in str(period):
                quarter, year = period.split('/')
                quarter_num = int(quarter[1])  # Extract quarter number
                return (int(year), quarter_num)
            else:
                return (int(period), 0)
        
        try:
            periods = sorted(periods, key=sort_period)
        except:
            pass  # Keep original order if sorting fails
        
        # Revenue rows
        for segment in segments:
            row = {'Metric': f'{segment} Revenue'}
            for period in periods:
                value = data.get('revenue', {}).get(segment, {}).get(period, 'N/A')
                if isinstance(value, (int, float)) and value != 'N/A':
                    row[period] = f"{value:,.1f}"
                else:
                    row[period] = value
            df_data.append(row)
        
        # Total revenue
        row = {'Metric': 'Total Revenue'}
        for period in periods:
            value = data.get('revenue', {}).get('Total', {}).get(period, 'N/A')
            if isinstance(value, (int, float)) and value != 'N/A':
                row[period] = f"{value:,.1f}"
            else:
                row[period] = value
        df_data.append(row)
        
        # COGS rows
        for segment in segments:
            row = {'Metric': f'{segment} COGS'}
            for period in periods:
                value = data.get('cogs', {}).get(segment, {}).get(period, 'N/A')
                if isinstance(value, (int, float)) and value != 'N/A':
                    row[period] = f"{value:,.1f}"
                else:
                    row[period] = value
            df_data.append(row)
        
        # Total COGS
        row = {'Metric': 'Total COGS'}
        for period in periods:
            value = data.get('cogs', {}).get('Total', {}).get(period, 'N/A')
            if isinstance(value, (int, float)) and value != 'N/A':
                row[period] = f"{value:,.1f}"
            else:
                row[period] = value
        df_data.append(row)
        
        # Gross profit rows
        for segment in segments:
            row = {'Metric': f'{segment} Gross Profit'}
            for period in periods:
                value = data.get('gross_profit', {}).get(segment, {}).get(period, 'N/A')
                if isinstance(value, (int, float)) and value != 'N/A':
                    row[period] = f"{value:,.1f}"
                else:
                    row[period] = value
            df_data.append(row)
        
        # Total gross profit
        row = {'Metric': 'Total Gross Profit'}
        for period in periods:
            value = data.get('gross_profit', {}).get('Total', {}).get(period, 'N/A')
            if isinstance(value, (int, float)) and value != 'N/A':
                row[period] = f"{value:,.1f}"
            else:
                row[period] = value
        df_data.append(row)
        
        # Margin rows
        for segment in segments:
            row = {'Metric': f'{segment} Gross Margin %'}
            for period in periods:
                value = data.get('gross_margin', {}).get(segment, {}).get(period, 'N/A')
                if isinstance(value, (int, float)) and value != 'N/A':
                    row[period] = f"{value:.1f}%"
                else:
                    row[period] = value
            df_data.append(row)
        
        # Blended margin
        row = {'Metric': 'Blended Gross Margin %'}
        for period in periods:
            value = data.get('gross_margin', {}).get('Blended', {}).get(period, 'N/A')
            if isinstance(value, (int, float)) and value != 'N/A':
                row[period] = f"{value:.1f}%"
            else:
                row[period] = value
        df_data.append(row)
        
        return pd.DataFrame(df_data)
    
    def extract_real_estate_projects(self, documents: List[Dict[str, str]]) -> List[Dict]:
        """Extract real estate projects using Claude AI with Vietnamese/English support"""
        if not self.client:
            st.error("Claude AI not initialized")
            return []
        
        # Combine document texts with clear separation
        combined_text = ""
        doc_list = []
        for doc in documents:
            doc_list.append(doc['name'])
            combined_text += f"\n\n=== DOCUMENT: {doc['name']} ===\n"
            combined_text += doc['text'][:60000]
            if len(combined_text) > 120000:
                break
        
        prompt = """Extract ALL real estate projects from these documents (Vietnamese or English).
        
        IMPORTANT: Documents may be in Vietnamese or English. Understand both languages.
        
        Vietnamese terms to look for:
        - Dự án/Project
        - Diện tích đất/Land area
        - Tổng diện tích sàn/GFA (Gross Floor Area)
        - Diện tích bán/NSA (Net Sellable Area)
        - Số căn/Total units
        - Giá bán trung bình/Average selling price
        - Chi phí xây dựng/Construction cost
        - Chi phí đất/Land cost
        - Tình trạng pháp lý/Legal status
        - Tình trạng bán hàng/Selling status
        - Số căn còn lại/Remaining units
        
        For each project, extract:
        - project_name: Project name (keep original name)
        - land_area_sqm: Land area in sqm (diện tích đất)
        - gfa_sqm: Gross Floor Area in sqm (tổng diện tích sàn)
        - nsa_sqm: Net Sellable Area in sqm (diện tích bán)
        - total_units: Total units (tổng số căn)
        - avg_selling_price: Average selling price (giá bán trung bình)
        - construction_cost_bn_vnd: Construction cost in billion VND (chi phí xây dựng)
        - land_cost_bn_vnd: Land cost in billion VND (chi phí đất)
        - legal_status: Legal status (e.g., "Có sổ đỏ", "Has LURC", "Pending approval")
        - selling_status: Selling status (e.g., "Đã bán 70%", "70% sold", "Pre-sales started")
        - remaining_units: Remaining units to be sold (số căn còn lại)
        - source_document: Which document this came from
        
        MERGING STRATEGY:
        - If the same project appears in multiple documents, include ALL instances
        - We will merge them later
        - Projects may have slightly different names (e.g., "The Manor" vs "Manor Central Park")
        - Include ALL projects, even if only partial information is available
        
        Use "N/A" for unavailable information.
        Return ONLY a valid JSON array. Start with [ and end with ]
        
        Example format:
        [
            {
                "project_name": "Vinhomes Grand Park",
                "land_area_sqm": 271000,
                "gfa_sqm": 850000,
                "nsa_sqm": 680000,
                "total_units": 10000,
                "avg_selling_price": "65 triệu/m2",
                "construction_cost_bn_vnd": 15000,
                "land_cost_bn_vnd": 8000,
                "legal_status": "Có sổ đỏ",
                "selling_status": "Đã bán 85%",
                "remaining_units": 1500,
                "source_document": "BCTN_2023.pdf"
            }
        ]
        
        Documents being analyzed:
        """ + "\n".join(doc_list) + "\n\nDocument contents:\n" + combined_text[:120000]
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            try:
                result = json.loads(response_text)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                # Try to extract JSON array
                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            
        except Exception as e:
            st.error(f"Error extracting projects: {str(e)}")
        
        return []
    
    def merge_duplicate_projects(self, projects: List[Dict]) -> List[Dict]:
        """Merge duplicate projects intelligently using Claude AI"""
        if not self.client or not projects or len(projects) <= 1:
            return projects
        
        prompt = f"""Review these real estate projects extracted from multiple documents and merge duplicates intelligently.
        
        Projects to merge:
        {json.dumps(projects, indent=2)}
        
        MERGING RULES:
        1. Identify same projects even with slightly different names:
           - "The Manor" = "Manor Central Park" = "Dự án Manor"
           - "Vinhomes Grand Park" = "VH Grand Park" = "Grand Park"
           - Look for common keywords and locations
        
        2. When merging, create the MOST COMPLETE record:
           - Keep the most descriptive project name
           - For numeric values: prefer non-"N/A" values
           - If both have values, prefer the larger/more recent one
           - For status fields: prefer more detailed descriptions
        
        3. Track data sources:
           - Add "merged_from" field listing all source_documents
           - Add "merge_confidence" field: "high", "medium", or "low"
           - Add "merge_notes" explaining any conflicts resolved
        
        4. Vietnamese/English handling:
           - If project has both Vietnamese and English names, keep both
           - Legal status can be in either language
           - Selling status can be mixed (e.g., "Đã bán 70%" or "70% sold")
        
        Return ONLY a valid JSON array of merged projects.
        Each project should have all original fields plus:
        - "merged_from": ["doc1.pdf", "doc2.pdf"] (if merged)
        - "merge_confidence": "high/medium/low"
        - "merge_notes": "Any important notes about the merge"
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            try:
                result = json.loads(response_text)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            
        except Exception as e:
            st.warning(f"Could not merge projects: {str(e)}")
        
        return projects