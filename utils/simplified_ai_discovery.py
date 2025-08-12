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
import time
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
            combined_text += f"\n\n=== DOC: {doc['name']} ===\n"
            combined_text += doc['text'][:20000]  # Further reduced limit per doc
            if len(combined_text) > 40000:  # Further reduced total limit
                break
        
        prompt = """Analyze financial documents (Vietnamese/English) and merge business segment data.
        
        KEY TERMS:
        VN: Doanh thu, Giá vốn, Lợi nhuận gộp, Bất động sản, Xây dựng, Dịch vụ
        EN: Revenue, COGS, Gross Profit, Real Estate, Construction, Services
        
        MERGE RULES:
        - Combine ALL segments from ALL documents
        - Combine ALL periods (2022, 2023, 2024, Q1/2024, etc.)
        - For conflicts: use most recent/complete data
        
        Return JSON:
        {
            "segments": ["Segment1", "Segment2"],
            "periods": ["2023", "2024"],
            "data": {
                "revenue": {"Segment1": {"2023": 1234.5}, "Total": {"2023": 5678.9}},
                "cogs": {"Segment1": {"2023": 900.0}, "Total": {"2023": 1500.0}},
                "gross_profit": {"Segment1": {"2023": 334.5}, "Total": {"2023": 624.6}},
                "gross_margin": {"Segment1": {"2023": 27.1}, "Blended": {"2023": 29.4}}
            }
        }
        
        Amounts in VND billions. Start with { end with }
        
        Docs: """ + ", ".join(doc_list) + "\n\n" + combined_text[:40000]
        
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
            combined_text += f"\n\n=== DOC: {doc['name']} ===\n"
            combined_text += doc['text'][:30000]  # Moderate limit per doc
            if len(combined_text) > 60000:  # Moderate total limit
                break
        
        prompt = """Extract ALL real estate projects from these documents. Look for project names with variations (e.g., Hoang Huy Commerce, HH Commerce, Hoàng Huy Commerce are the same).

        IMPORTANT PROJECT NAMES TO FIND:
        1. Hoang Huy Commerce (H1, H2, or phases/toà/tower)
        2. Hoang Huy New City (Phase 1, II, or zones like Prince Park, Queen Park)
        3. Hoang Huy Green River
        4. Hoàng Huy Sở Dầu / Hoang Huy Grand Tower
        5. Hoang Huy Riverside
        6. Any other projects mentioned
        
        KEY TERMS (Vietnamese/English):
        - Dự án/Project
        - Diện tích/Area: ha (hectare), m2/sqm
        - Căn hộ/Units/Apartments
        - Townhouse/Nhà phố/Shophouse
        - Villa/Biệt thự
        - Tòa/Tower/Block (H1, H2, etc.)
        - Giai đoạn/Phase (1, 2, I, II)
        - Giá bán/Selling price (triệu/million, tỷ/billion VND)
        - Doanh thu/Revenue
        - Tiến độ/Progress/Status
        
        EXTRACTION RULES:
        1. Convert all areas to sqm (1 ha = 10,000 sqm)
        2. Look for numbers near project names
        3. Extract phases/towers as separate entries if they have different data
        4. Check tables, bullet points, and narrative text
        5. Look for launch dates, handover dates, construction status
        
        For EACH project/phase, extract:
        {
            "project_name": "Full name with phase/tower",
            "land_area_sqm": numeric or "N/A",
            "total_units": numeric or "N/A",
            "unit_types": "apartments/townhouse/villa/mixed",
            "avg_selling_price": "price per sqm in million VND",
            "total_revenue_bn_vnd": numeric or "N/A",
            "construction_status": "planning/under construction/completed/%",
            "launch_year": "2024/2025/etc",
            "handover_year": "2025/2026/etc",
            "ownership_pct": "TCH ownership %",
            "location": "district/city",
            "phases": "list of phases if mentioned",
            "notes": "any other important info"
        }
        
        Return JSON array. Include ALL projects found, even with partial data.
        Start [ end ]
        
        Docs: """ + ", ".join(doc_list) + "\n\n" + combined_text[:60000]
        
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
        
        prompt = f"""Merge duplicate real estate projects.
        
        Projects:
        {json.dumps(projects[:20], indent=1)}  # Limit to first 20 projects
        
        RULES:
        - Same project = similar names (Manor = Manor Central Park)
        - Keep most complete data
        - Prefer non-"N/A" values
        - Add "merged_from" field if merged
        
        Return JSON array. Start [ end ]
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