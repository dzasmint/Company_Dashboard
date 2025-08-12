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
        """Render AI discovery interface focused on project extraction"""
        st.header("🤖 AI-Powered Real Estate Project Extraction")
        
        st.markdown("""
        Upload multiple PDF files (annual reports, earnings reports, analyst reports, or company presentations) for comprehensive project extraction.
        
        **Claude AI will extract ALL real estate projects with:**
        - Complete project details (name, location, area, units)
        - Financial metrics (prices, costs, revenues)
        - Development timeline (launch, construction, handover)
        - Sales status and legal information
        - Any other available project data
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
        
        # Extract real estate projects from EACH document separately
        all_projects = []
        for i, doc in enumerate(documents):
            progress = 0.3 + (i + 1) / len(documents) * 0.5  # Progress from 30% to 80%
            progress_bar.progress(progress)
            status_text.text(f"Extracting projects from {doc['name']}...")
            
            # Process single document
            doc_projects = self.extract_real_estate_projects_single(doc)
            if doc_projects:
                # Add source document info to each project
                for project in doc_projects:
                    project['source_document'] = doc['name']
                all_projects.extend(doc_projects)
                st.info(f"📄 Found {len(doc_projects)} projects in {doc['name']}")
        
        # Merge all projects from all documents
        if all_projects:
            progress_bar.progress(0.9)
            status_text.text(f"Merging {len(all_projects)} total projects from all documents...")
            merged_projects = self.merge_projects_from_multiple_docs(all_projects)
            st.session_state.real_estate_projects = merged_projects
        else:
            merged_projects = []
            st.session_state.real_estate_projects = []
        
        progress_bar.progress(1.0)
        status_text.text("✅ Analysis complete!")
        progress_bar.empty()
        status_text.empty()
        
        # Show success message
        st.success(f"✅ Successfully analyzed {len(documents)} document(s)")
        if all_projects:
            st.info(f"🏢 Found {len(merged_projects)} unique real estate projects from {len(all_projects)} total extractions")
        else:
            st.warning("⚠️ No projects found. Please check if the documents contain real estate project information.")
    
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
    
    def extract_real_estate_projects_single(self, document: Dict[str, str]) -> List[Dict]:
        """Extract real estate projects from a SINGLE document"""
        
        # Reduce document text to save tokens
        doc_text = document['text'][:40000]  # Reduced from 100,000
        doc_name = document['name']
        
        prompt = """Extract ALL real estate projects from this document.

Look for: project names, phases/towers (H1, H2), zones, Vietnamese terms (dự án, khu đô thị, chung cư).

For each project extract:
- project_name (include phase/tower)
- location
- land_area_sqm (convert ha to sqm: 1ha=10,000sqm) 
- total_units
- project_type (apartment/townhouse/villa/shophouse/mixed)
- avg_selling_price (million VND/sqm)
- total_revenue_bn_vnd
- development_status
- sales_status (% sold)
- launch_date
- handover_date
- construction_progress
- remaining_units

Include ALL projects even with partial data. Use "N/A" for missing info.
Return JSON array. Start [ end ]

Doc: """ + doc_name + "\n\n" + doc_text
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=3000,  # Reduced to save costs
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            
            # Extract JSON array
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            
        except Exception as e:
            st.error(f"Error extracting projects from {doc_name}: {str(e)}")
        
        return []
    
    def extract_real_estate_projects(self, documents: List[Dict[str, str]]) -> List[Dict]:
        """Extract ALL real estate projects using Claude AI with comprehensive details"""
        
        # Combine document texts with more context
        combined_text = ""
        doc_names = []
        for doc in documents:
            doc_names.append(doc['name'])
            combined_text += f"\n\n=== DOCUMENT: {doc['name']} ===\n"
            combined_text += doc['text'][:50000]  # Increased limit for more context
            if len(combined_text) > 120000:  # Increased total limit
                break
        
        prompt = """You are analyzing real estate documents. Extract ABSOLUTELY EVERY real estate project mentioned, no matter how briefly.
        
        CRITICAL: Look for ALL project names including:
        - Projects with phases/towers (e.g., Hoang Huy Commerce H1, H2)
        - Projects with zones (e.g., Prince Park, Queen Park)
        - Projects mentioned in tables, lists, or narrative text
        - Projects in development pipeline
        - Completed projects still being sold
        - Future/planned projects
        
        For EACH project found, extract AS MUCH information as possible:
        
        BASIC INFORMATION:
        - project_name: Full project name (include phase/tower if mentioned)
        - location: District, city, address
        - developer: Developer name
        - project_type: apartment/townhouse/villa/shophouse/mixed-use/commercial
        
        AREA & SIZE:
        - land_area_sqm: Land area (convert ha to sqm: 1ha = 10,000sqm)
        - gfa_sqm: Gross Floor Area
        - nsa_sqm: Net Sellable Area
        - site_area: Site/plot area
        - construction_area: Construction area
        
        UNITS & COMPOSITION:
        - total_units: Total number of units
        - apartments: Number of apartments
        - townhouses: Number of townhouses
        - villas: Number of villas
        - shophouses: Number of shophouses
        - commercial_units: Commercial units
        - unit_mix: Description of unit types and sizes
        
        FINANCIAL:
        - avg_selling_price: Average price per sqm (million VND)
        - price_range: Price range if mentioned
        - total_revenue_bn_vnd: Total revenue (billion VND)
        - construction_cost_bn_vnd: Construction cost
        - land_cost_bn_vnd: Land acquisition cost
        - total_investment: Total investment amount
        - revenue_recognition: Revenue recognition schedule
        
        TIMELINE:
        - launch_date: Launch date/quarter/year
        - construction_start: Construction start date
        - construction_end: Construction completion date
        - handover_date: Handover/delivery date
        - sales_start: Sales launch date
        - presales_date: Presales date
        
        STATUS:
        - development_status: planning/approved/under construction/completed
        - construction_progress: Construction progress %
        - sales_status: Sales progress (e.g., "70% sold", "500 units sold")
        - units_sold: Number of units sold
        - remaining_units: Remaining units
        - inventory_value: Value of remaining inventory
        
        LEGAL & PERMITS:
        - legal_status: Legal status/permits obtained
        - ownership_structure: Ownership type (freehold/leasehold)
        - ownership_duration: Ownership duration (e.g., 50 years)
        - permits: List of permits obtained
        
        OTHER:
        - floors: Number of floors
        - blocks: Number of blocks/towers
        - facilities: Amenities and facilities
        - contractor: Main contractor
        - architect: Architect/designer
        - notes: Any other important information
        - data_source: Which document this info came from
        
        IMPORTANT INSTRUCTIONS:
        1. Extract EVERY project, even if only the name is mentioned
        2. Include ALL phases/towers as separate entries
        3. Use "N/A" for missing information
        4. Include projects at ANY stage (planning to completed)
        5. If numbers appear near project names, associate them
        6. Check tables, footnotes, and management discussion sections
        7. Look for Vietnamese terms: dự án, khu đô thị, chung cư, căn hộ
        
        Return a JSON array with ALL projects found. Start with [ and end with ]
        
        Documents being analyzed: """ + ", ".join(doc_names) + "\n\n" + combined_text[:120000]
        
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
    
    def merge_projects_from_multiple_docs(self, all_projects: List[Dict]) -> List[Dict]:
        """Intelligently merge projects from multiple documents using Claude AI"""
        
        if not all_projects:
            return []
        
        if len(all_projects) <= 1:
            return all_projects
        
        # If too many projects, batch process
        if len(all_projects) > 50:
            # Process in batches of 40 to avoid token limits
            merged = []
            for i in range(0, len(all_projects), 40):
                batch = all_projects[i:i+40]
                batch_merged = self._merge_project_batch(batch)
                merged.extend(batch_merged)
            
            # Merge the batches together
            if len(merged) > 1:
                return self._merge_project_batch(merged)
            return merged
        else:
            return self._merge_project_batch(all_projects)
    
    def _merge_project_batch(self, projects: List[Dict]) -> List[Dict]:
        """Merge a batch of projects"""
        
        # Simplify project data to reduce tokens
        simplified_projects = []
        for p in projects:
            simplified = {k: v for k, v in p.items() if v and v != 'N/A'}
            simplified_projects.append(simplified)
        
        prompt = f"""Merge duplicate real estate projects from different documents.

Projects:
{json.dumps(simplified_projects, indent=1)}

MERGE RULES:
- Same project = similar name + location (ignore H1/H2 differences)
- Keep most complete data, prefer non-N/A values
- Don't merge different phases (H1 vs H2, Phase 1 vs 2)
- Add "sources" field with document names

Return JSON array with merged projects. Start [ end ]
"""
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,  # Reduced from 8000
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                merged = json.loads(json_match.group())
                
                # Add merge statistics
                st.success(f"✅ Merged {len(projects)} project entries into {len(merged)} unique projects")
                
                return merged
            
        except Exception as e:
            st.warning(f"Could not merge projects: {str(e)}")
            st.info("Returning unmerged projects")
        
        return projects
    
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
        """Display extracted real estate projects"""
        
        # Real Estate Projects Table
        if st.session_state.real_estate_projects:
            st.subheader("🏢 Extracted Real Estate Projects")
            
            projects = st.session_state.real_estate_projects
            
            # Create comprehensive display dataframe
            display_data = []
            for proj in projects:
                display_data.append({
                    'Project Name': proj.get('project_name', 'N/A'),
                    'Location': proj.get('location', 'N/A'),
                    'Type': proj.get('project_type', 'N/A'),
                    'Land Area (sqm)': proj.get('land_area_sqm', 'N/A'),
                    'Total Units': proj.get('total_units', 'N/A'),
                    'Units Sold': proj.get('units_sold', 'N/A'),
                    'Sales Status': proj.get('sales_status', proj.get('selling_status', 'N/A')),
                    'Avg Price/sqm': proj.get('avg_selling_price', 'N/A'),
                    'Revenue (Bn VND)': proj.get('total_revenue_bn_vnd', 'N/A'),
                    'Launch': proj.get('launch_date', proj.get('launch_year', 'N/A')),
                    'Handover': proj.get('handover_date', 'N/A'),
                    'Dev Status': proj.get('development_status', 'N/A'),
                    'Progress': proj.get('construction_progress', 'N/A'),
                    'Source': proj.get('data_source', 'N/A')
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
            
            # Download buttons
            col1, col2 = st.columns(2)
            
            with col1:
                # Download summary CSV
                csv = df.to_csv(index=False)
                st.download_button(
                    "📥 Download Summary (CSV)",
                    data=csv,
                    file_name=f"projects_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                # Download full data with all fields
                full_df = pd.DataFrame(projects)
                full_csv = full_df.to_csv(index=False)
                st.download_button(
                    "📥 Download Full Data (All Fields)",
                    data=full_csv,
                    file_name=f"projects_full_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
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
            
            # Show full project details
            with st.expander("🔍 View Complete Project Details"):
                for i, proj in enumerate(projects):
                    st.markdown(f"### 📍 Project {i+1}: **{proj.get('project_name', 'Unknown Project')}**")
                    
                    # Organize fields by category
                    categories = {
                        "Basic Info": ['location', 'developer', 'project_type', 'data_source'],
                        "Area & Size": ['land_area_sqm', 'gfa_sqm', 'nsa_sqm', 'site_area', 'construction_area'],
                        "Units": ['total_units', 'apartments', 'townhouses', 'villas', 'shophouses', 'commercial_units', 'unit_mix'],
                        "Financial": ['avg_selling_price', 'price_range', 'total_revenue_bn_vnd', 'construction_cost_bn_vnd', 'land_cost_bn_vnd', 'total_investment', 'revenue_recognition', 'inventory_value'],
                        "Timeline": ['launch_date', 'construction_start', 'construction_end', 'handover_date', 'sales_start', 'presales_date'],
                        "Status": ['development_status', 'construction_progress', 'sales_status', 'units_sold', 'remaining_units'],
                        "Legal": ['legal_status', 'ownership_structure', 'ownership_duration', 'permits'],
                        "Other": ['floors', 'blocks', 'facilities', 'contractor', 'architect', 'notes']
                    }
                    
                    # Display by category
                    cols = st.columns(2)
                    col_idx = 0
                    
                    for category, fields in categories.items():
                        has_data = any(proj.get(field) and proj.get(field) != 'N/A' for field in fields)
                        if has_data:
                            with cols[col_idx % 2]:
                                st.markdown(f"**{category}:**")
                                for field in fields:
                                    value = proj.get(field)
                                    if value and value != 'N/A':
                                        field_name = field.replace('_', ' ').title()
                                        st.write(f"• {field_name}: {value}")
                            col_idx += 1
                    
                    st.markdown("---")