#%%
import streamlit as st
import pandas as pd
import numpy as np
import PyPDF2
import anthropic
import os
import json
import re
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AIDiscoveryTab:
    """Simplified AI Discovery tab for business segments and real estate projects analysis"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.client = None
        
        # Initialize Claude AI client
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            self.client = anthropic.Anthropic(api_key=api_key)
        
        # Initialize session state
        if 'business_segments_data' not in st.session_state:
            st.session_state.business_segments_data = None
        if 'real_estate_projects' not in st.session_state:
            st.session_state.real_estate_projects = []
        if 'uploaded_documents' not in st.session_state:
            st.session_state.uploaded_documents = []
    
    def render(self):
        """Render simplified AI discovery interface"""
        st.header("🤖 AI Document Analysis")
        
        st.markdown("""
        Upload multiple PDF files (annual reports, earnings reports, or analyst reports) for AI-powered analysis.
        
        **Claude AI will extract:**
        1. **Business Segments** - Revenue, COGS, Gross Profit and Margins by segment
        2. **Real Estate Projects** - Comprehensive project details with intelligent merging
        """)
        
        # File uploader section
        st.subheader("📄 Document Upload")
        uploaded_files = st.file_uploader(
            "Choose PDF documents",
            type=['pdf'],
            accept_multiple_files=True,
            help="Upload annual reports, quarterly earnings, or sell-side analyst reports",
            key="pdf_uploads"
        )
        
        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} document(s) uploaded")
            
            # Process uploaded files
            if st.button("🚀 Process Documents", type="primary", use_container_width=True):
                self.process_documents(uploaded_files)
        
        # Display results if available
        self.display_results()
    
    def extract_text_from_pdf(self, pdf_file) -> str:
        """Extract text content from PDF file"""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page_num in range(min(len(pdf_reader.pages), 100)):  # Limit to first 100 pages
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            st.error(f"Error reading PDF {pdf_file.name}: {str(e)}")
            return ""
    
    def process_documents(self, uploaded_files):
        """Process all uploaded documents"""
        if not self.client:
            st.error("❌ Claude AI not initialized. Please set ANTHROPIC_API_KEY in your .env file")
            return
        
        # Extract text from all PDFs
        documents = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, file in enumerate(uploaded_files):
            progress = (i + 1) / len(uploaded_files) * 0.3  # 30% for reading
            progress_bar.progress(progress)
            status_text.text(f"Reading {file.name}...")
            
            text = self.extract_text_from_pdf(file)
            if text:
                documents.append({
                    'name': file.name,
                    'text': text
                })
        
        if not documents:
            st.error("❌ Could not read any documents")
            return
        
        st.session_state.uploaded_documents = documents
        
        # Analyze business segments
        progress_bar.progress(0.5)
        status_text.text("Analyzing business segments...")
        segments_df = self.analyze_business_segments(documents)
        if not segments_df.empty:
            st.session_state.business_segments_data = segments_df
        
        # Extract real estate projects
        progress_bar.progress(0.7)
        status_text.text("Extracting real estate projects...")
        projects = self.extract_real_estate_projects(documents)
        
        # Merge duplicate projects
        if projects:
            progress_bar.progress(0.9)
            status_text.text("Merging duplicate projects...")
            merged_projects = self.merge_duplicate_projects(projects)
            st.session_state.real_estate_projects = merged_projects
        
        progress_bar.progress(1.0)
        status_text.text("✅ Analysis complete!")
        progress_bar.empty()
        status_text.empty()
        
        # Show success message
        st.success(f"✅ Successfully analyzed {len(documents)} document(s)")
        if not segments_df.empty:
            st.info(f"📊 Found business segments data")
        if projects:
            st.info(f"🏢 Found {len(merged_projects)} unique real estate projects")
    
    def analyze_business_segments(self, documents: List[Dict[str, str]]) -> pd.DataFrame:
        """Analyze business segments using Claude AI"""
        
        # Combine document texts (limit to avoid token limits)
        combined_text = ""
        for doc in documents:
            combined_text += f"\n\n--- Document: {doc['name']} ---\n"
            combined_text += doc['text'][:30000]  # Limit each document
            if len(combined_text) > 80000:  # Overall limit
                break
        
        prompt = """Analyze these financial documents and extract business segment information.
        
        Create a table with:
        - Columns: Time periods (e.g., 2023, 2024, Q1/2024, Q2/2024)
        - Rows in exact order:
          1. [Segment1 Name] Revenue
          2. [Segment2 Name] Revenue
          3. ... (other segments revenue)
          4. Total Revenue
          5. [Segment1 Name] COGS
          6. [Segment2 Name] COGS
          7. ... (other segments COGS)
          8. Total COGS
          9. [Segment1 Name] Gross Profit
          10. [Segment2 Name] Gross Profit
          11. ... (other segments gross profit)
          12. Total Gross Profit
          13. [Segment1 Name] Gross Margin %
          14. [Segment2 Name] Gross Margin %
          15. ... (other segments margins)
          16. Blended Gross Margin %
        
        Return ONLY a JSON object with structure:
        {
            "segments": ["Actual Segment Name 1", "Actual Segment Name 2"],
            "periods": ["2023", "Q1/2024"],
            "data": {
                "revenue": {"Segment1": {"2023": 1234.5}, "Total": {"2023": 5678.9}},
                "cogs": {...},
                "gross_profit": {...},
                "gross_margin": {...}
            }
        }
        
        Use "N/A" for missing values. All amounts in VND billions.
        
        Documents:
        """ + combined_text[:90000]
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            
            # Extract JSON
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return self.format_segments_dataframe(result)
            
        except Exception as e:
            st.error(f"Error analyzing segments: {str(e)}")
        
        return pd.DataFrame()
    
    def format_segments_dataframe(self, result: Dict) -> pd.DataFrame:
        """Format segments data into DataFrame"""
        df_data = []
        segments = result.get('segments', [])
        periods = result.get('periods', [])
        data = result.get('data', {})
        
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
        
        # Combine document texts
        combined_text = ""
        for doc in documents:
            combined_text += f"\n\n--- Document: {doc['name']} ---\n"
            combined_text += doc['text'][:30000]
            if len(combined_text) > 80000:
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
        
        IMPORTANT:
        - Extract EVERY project mentioned
        - Use "N/A" for unavailable information
        - If same project appears multiple times, include all instances (will merge later)
        
        Return ONLY a JSON array of projects.
        
        Documents:
        """ + combined_text[:90000]
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            
            # Extract JSON array
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
        except Exception as e:
            st.error(f"Error extracting projects: {str(e)}")
        
        return []
    
    def merge_duplicate_projects(self, projects: List[Dict]) -> List[Dict]:
        """Merge duplicate projects intelligently using Claude AI"""
        
        if not projects or len(projects) <= 1:
            return projects
        
        prompt = f"""Review these real estate projects and merge duplicates intelligently.
        
        Projects:
        {json.dumps(projects, indent=2)}
        
        Rules:
        1. Identify same projects with slightly different names
        2. Keep most complete/recent information when merging
        3. Prefer non-"N/A" values
        4. Add a "data_sources" field listing which documents mentioned the project
        
        Return ONLY a JSON array of merged projects.
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
        except Exception as e:
            st.warning(f"Could not merge projects: {str(e)}")
        
        return projects
    
    def display_results(self):
        """Display analysis results"""
        
        # Business Segments Table
        if st.session_state.business_segments_data is not None:
            st.subheader("📊 1. Business Segments Analysis")
            
            df = st.session_state.business_segments_data
            
            # Style the dataframe
            def style_rows(row):
                if 'Total' in str(row['Metric']):
                    return ['background-color: #f0f0f0; font-weight: bold'] * len(row)
                elif 'Margin' in str(row['Metric']):
                    return ['background-color: #e8f4f8; font-style: italic'] * len(row)
                return [''] * len(row)
            
            styled_df = df.style.apply(style_rows, axis=1)
            st.dataframe(styled_df, use_container_width=True, height=600)
            
            # Download button
            csv = df.to_csv(index=False)
            st.download_button(
                "📥 Download Business Segments (CSV)",
                data=csv,
                file_name=f"business_segments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        # Real Estate Projects Table
        if st.session_state.real_estate_projects:
            st.subheader("🏢 2. Real Estate Projects Summary")
            
            projects = st.session_state.real_estate_projects
            
            # Create display dataframe
            display_data = []
            for proj in projects:
                display_data.append({
                    'Project Name': proj.get('project_name', 'N/A'),
                    'Land Area (sqm)': proj.get('land_area_sqm', 'N/A'),
                    'GFA (sqm)': proj.get('gfa_sqm', 'N/A'),
                    'NSA (sqm)': proj.get('nsa_sqm', 'N/A'),
                    'Total Units': proj.get('total_units', 'N/A'),
                    'Avg Selling Price': proj.get('avg_selling_price', 'N/A'),
                    'Construction Cost (Bn VND)': proj.get('construction_cost_bn_vnd', 'N/A'),
                    'Land Cost (Bn VND)': proj.get('land_cost_bn_vnd', 'N/A'),
                    'Legal Status': proj.get('legal_status', 'N/A'),
                    'Selling Status': proj.get('selling_status', 'N/A'),
                    'Remaining Units': proj.get('remaining_units', 'N/A')
                })
            
            df = pd.DataFrame(display_data)
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Projects", len(df))
            with col2:
                units_count = df['Total Units'].apply(
                    lambda x: int(x) if str(x).isdigit() else 0
                ).sum()
                st.metric("Total Units", f"{units_count:,}" if units_count > 0 else "N/A")
            with col3:
                na_count = (df == 'N/A').sum().sum()
                total_cells = df.size
                completeness = (1 - na_count/total_cells) * 100
                st.metric("Data Completeness", f"{completeness:.0f}%")
            with col4:
                st.metric("Documents Analyzed", len(st.session_state.uploaded_documents))
            
            # Display table
            st.dataframe(df, use_container_width=True, height=400)
            
            # Download button
            csv = df.to_csv(index=False)
            st.download_button(
                "📥 Download Projects (CSV)",
                data=csv,
                file_name=f"real_estate_projects_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
            # Show data quality info
            with st.expander("📊 Data Quality Information"):
                na_summary = pd.DataFrame({
                    'Field': df.columns,
                    'Available': [(df[col] != 'N/A').sum() for col in df.columns],
                    'Missing': [(df[col] == 'N/A').sum() for col in df.columns],
                    'Completeness %': [((df[col] != 'N/A').sum() / len(df) * 100) for col in df.columns]
                })
                na_summary['Completeness %'] = na_summary['Completeness %'].apply(lambda x: f"{x:.0f}%")
                st.dataframe(na_summary, use_container_width=True)