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
        """Analyze business segments using Claude AI"""
        if not self.client:
            st.error("Claude AI not initialized")
            return pd.DataFrame()
        
        # Combine document texts
        combined_text = ""
        for doc in documents:
            combined_text += f"\n\n--- Document: {doc['name']} ---\n"
            combined_text += doc['text'][:50000]
            if len(combined_text) > 100000:
                break
        
        prompt = """Analyze these financial documents and extract business segment information.
        
        Look for business segments like: Real Estate Development, Property Investment, Construction, Hospitality, Retail, etc.
        
        Create a table with:
        - Columns: Time periods (e.g., 2023, 2024, Q1/2024)
        - Rows: [Segment] Revenue, Total Revenue, [Segment] COGS, Total COGS, [Segment] Gross Profit, Total Gross Profit, [Segment] Margin %, Blended Margin %
        
        Return ONLY a valid JSON object:
        {
            "segments": ["Segment1", "Segment2"],
            "periods": ["2023", "2024"],
            "data": {
                "revenue": {"Segment1": {"2023": 1234.5}, "Total": {"2023": 5678.9}},
                "cogs": {},
                "gross_profit": {},
                "gross_margin": {}
            }
        }
        
        All amounts in VND billions. Start with { and end with }
        
        Documents:
        """ + combined_text[:100000]
        
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
        """Format segments data into DataFrame"""
        if not result:
            return pd.DataFrame()
        
        df_data = []
        segments = result.get('segments', [])
        periods = result.get('periods', [])
        data = result.get('data', {})
        
        if not segments or not periods:
            return pd.DataFrame()
        
        # Revenue rows
        for segment in segments:
            row = {'Metric': f'{segment} Revenue'}
            for period in periods:
                value = data.get('revenue', {}).get(segment, {}).get(period, 'N/A')
                row[period] = f"{value:,.0f}" if isinstance(value, (int, float)) else value
            df_data.append(row)
        
        # Total revenue
        row = {'Metric': 'Total Revenue'}
        for period in periods:
            value = data.get('revenue', {}).get('Total', {}).get(period, 'N/A')
            row[period] = f"{value:,.0f}" if isinstance(value, (int, float)) else value
        df_data.append(row)
        
        # COGS rows
        for segment in segments:
            row = {'Metric': f'{segment} COGS'}
            for period in periods:
                value = data.get('cogs', {}).get(segment, {}).get(period, 'N/A')
                row[period] = f"{value:,.0f}" if isinstance(value, (int, float)) else value
            df_data.append(row)
        
        # Total COGS
        row = {'Metric': 'Total COGS'}
        for period in periods:
            value = data.get('cogs', {}).get('Total', {}).get(period, 'N/A')
            row[period] = f"{value:,.0f}" if isinstance(value, (int, float)) else value
        df_data.append(row)
        
        # Gross profit rows
        for segment in segments:
            row = {'Metric': f'{segment} Gross Profit'}
            for period in periods:
                value = data.get('gross_profit', {}).get(segment, {}).get(period, 'N/A')
                row[period] = f"{value:,.0f}" if isinstance(value, (int, float)) else value
            df_data.append(row)
        
        # Total gross profit
        row = {'Metric': 'Total Gross Profit'}
        for period in periods:
            value = data.get('gross_profit', {}).get('Total', {}).get(period, 'N/A')
            row[period] = f"{value:,.0f}" if isinstance(value, (int, float)) else value
        df_data.append(row)
        
        # Margin rows
        for segment in segments:
            row = {'Metric': f'{segment} Gross Margin %'}
            for period in periods:
                value = data.get('gross_margin', {}).get(segment, {}).get(period, 'N/A')
                row[period] = f"{value:.1f}%" if isinstance(value, (int, float)) else value
            df_data.append(row)
        
        # Blended margin
        row = {'Metric': 'Blended Gross Margin %'}
        for period in periods:
            value = data.get('gross_margin', {}).get('Blended', {}).get(period, 'N/A')
            row[period] = f"{value:.1f}%" if isinstance(value, (int, float)) else value
        df_data.append(row)
        
        return pd.DataFrame(df_data)
    
    def extract_real_estate_projects(self, documents: List[Dict[str, str]]) -> List[Dict]:
        """Extract real estate projects using Claude AI"""
        if not self.client:
            st.error("Claude AI not initialized")
            return []
        
        # Combine document texts
        combined_text = ""
        for doc in documents:
            combined_text += f"\n\n--- Document: {doc['name']} ---\n"
            combined_text += doc['text'][:50000]
            if len(combined_text) > 100000:
                break
        
        prompt = """Extract ALL real estate projects from these documents.
        
        For each project, extract:
        - project_name: Project name
        - land_area_sqm: Land area in sqm
        - gfa_sqm: Gross Floor Area in sqm
        - nsa_sqm: Net Sellable Area in sqm
        - total_units: Total units
        - avg_selling_price: Average selling price
        - construction_cost_bn_vnd: Construction cost in billion VND
        - land_cost_bn_vnd: Land cost in billion VND
        - legal_status: Legal status
        - selling_status: Selling status (% sold, etc.)
        - remaining_units: Remaining units to be sold
        
        Use "N/A" for unavailable information.
        Return ONLY a valid JSON array. Start with [ and end with ]
        
        Documents:
        """ + combined_text[:100000]
        
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
        
        prompt = f"""Review these real estate projects and merge duplicates intelligently.
        
        Projects:
        {json.dumps(projects, indent=2)}
        
        Rules:
        1. Identify same projects with slightly different names
        2. Keep most complete/recent information when merging
        3. Prefer non-"N/A" values
        
        Return ONLY a valid JSON array.
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