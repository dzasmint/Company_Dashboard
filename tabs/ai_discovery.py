#%%
import streamlit as st
import pandas as pd
import numpy as np
import PyPDF2
import anthropic
import os
import json
import re
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
    
    def save_edited_projects_to_database(self, edited_df):
        """Save edited projects from the dataframe to MongoDB database"""
        from utils.mongodb_utils import save_project_to_mongodb
        
        if edited_df is None or edited_df.empty:
            st.error("No projects to save")
            return
        
        success_count = 0
        error_count = 0
        error_messages = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, row in edited_df.iterrows():
            progress = (i + 1) / len(edited_df)
            progress_bar.progress(progress)
            status_text.text(f"Saving project {i+1}/{len(edited_df)}: {row.get('project_name', 'Unknown')}")
            
            try:
                # Parse values from edited dataframe - NO DEFAULTS, use actual column names
                project_data = {
                    'company_ticker': row.get('company_ticker', st.session_state.get('selected_company', '')),
                    'company_name': st.session_state.get('selected_company_name', ''),
                    'location': row.get('location', ''),
                    'project_ownership': self._parse_number(row.get('project_ownership', 0)),
                    'total_units': self._parse_number(row.get('total_units', 0)),
                    'net_sellable_area': self._parse_number(row.get('net_sellable_area', 0)),
                    'average_unit_size': self._parse_number(row.get('average_unit_size', 0)),
                    'average_selling_price': self._parse_number(row.get('average_selling_price', 0)),
                    'price_increment_factor': self._parse_number(row.get('price_increment_factor', 0)),
                    'gross_floor_area': self._parse_number(row.get('gross_floor_area', 0)),
                    'land_area': self._parse_number(row.get('land_area', 0)),
                    'construction_cost_per_sqm': self._parse_number(row.get('construction_cost_per_sqm', 0)),
                    'land_cost_per_sqm': self._parse_number(row.get('land_cost_per_sqm', 0)),
                    'construction_start_year': self._parse_year(row.get('construction_start_year', '')),
                    'sale_start_year': self._parse_year(row.get('sale_start_year', '')),
                    'land_payment_year': self._parse_year(row.get('sale_start_year', '')),  # Default to sale start
                    'construction_years': self._parse_number(row.get('construction_years', 0)),
                    'sales_years': self._parse_number(row.get('sales_years', 0)),
                    'revenue_booking_start_year': self._parse_year(row.get('revenue_booking_start_year', '')),
                    'project_completion_year': self._parse_year(row.get('project_completion_year', '')),
                    'sga_percentage': 0,  # Not in table
                    'wacc_rate': 0,  # Not in table
                    'cost_of_debt': 0,  # Not in table
                    # Financial metrics - not in edited table
                    'total_revenue': 0,
                    'total_construction_cost': 0,
                    'total_land_cost': 0,
                    'total_sga_cost': 0,
                    'total_pat': 0,
                    'total_pbt': 0,
                    # Additional fields - not in the new column structure
                    'development_status': '',
                    'sales_status': '',
                    'remaining_units': 0,
                    # Empty distribution fields
                    'revenue_distribution': {},
                    'presales_distribution': {},
                    'pnl_schedule': {},
                    # RNAV value if provided
                    'rnav_value': self._parse_number(row.get('rnav_value', 0)) if row.get('rnav_value', 'N/A') != 'N/A' else None
                }
                
                # Recalculate average unit size if needed
                if project_data['average_unit_size'] == 0 and project_data['net_sellable_area'] > 0 and project_data['total_units'] > 0:
                    project_data['average_unit_size'] = project_data['net_sellable_area'] / project_data['total_units']
                
                # Save to MongoDB
                result = save_project_to_mongodb(
                    project_data,
                    row.get('project_name', f"Project_{i+1}")
                )
                
                if result.get('success', False):
                    success_count += 1
                else:
                    error_count += 1
                    error_messages.append(f"{row.get('project_name', 'Unknown')}: {result.get('message', 'Unknown error')}")
                    
            except Exception as e:
                error_count += 1
                error_messages.append(f"{row.get('project_name', 'Unknown')}: {str(e)}")
        
        progress_bar.empty()
        status_text.empty()
        
        # Display results
        if success_count > 0:
            st.success(f"✅ Successfully saved {success_count} project(s) to database")
        
        if error_count > 0:
            st.error(f"❌ Failed to save {error_count} project(s)")
            with st.expander("View error details"):
                for error_msg in error_messages:
                    st.write(f"• {error_msg}")
        
        # Clear selected projects after saving
        if success_count > 0:
            st.session_state.selected_projects_for_db = []
            st.rerun()
    
    def save_projects_to_database(self, projects: List[Dict]):
        """Save selected projects to MongoDB database"""
        from utils.mongodb_utils import save_project_to_mongodb
        
        if not projects:
            st.error("No projects to save")
            return
        
        success_count = 0
        error_count = 0
        error_messages = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, project in enumerate(projects):
            progress = (i + 1) / len(projects)
            progress_bar.progress(progress)
            status_text.text(f"Saving project {i+1}/{len(projects)}: {project.get('project_name', 'Unknown')}")
            
            try:
                # Parse key numeric values - no defaults
                total_units = self._parse_number(project.get('total_units', 0))
                land_area = self._parse_number(project.get('land_area_sqm', 0))
                gfa = self._parse_number(project.get('gfa_sqm', 0))
                nsa = self._parse_number(project.get('nsa_sqm', 0))
                avg_price = self._parse_number(project.get('avg_selling_price', 0))
                
                # Calculate average unit size only if we have data
                avg_unit_size = 0
                if nsa > 0 and total_units > 0:
                    avg_unit_size = nsa / total_units
                
                # Calculate net sellable area only if we have data
                net_sellable_area = 0
                if nsa > 0:
                    net_sellable_area = nsa
                elif total_units > 0 and avg_unit_size > 0:
                    net_sellable_area = total_units * avg_unit_size
                
                # Parse financial values
                total_revenue_bn = self._parse_number(project.get('total_revenue_bn_vnd', 0))
                construction_cost_bn = self._parse_number(project.get('construction_cost_bn_vnd', 0))
                land_cost_bn = self._parse_number(project.get('land_cost_bn_vnd', 0))
                
                # Calculate land cost per sqm only if data available
                land_cost_per_sqm = 0
                if land_cost_bn > 0 and land_area > 0:
                    land_cost_per_sqm = (land_cost_bn * 1000) / land_area  # Convert bn to million then to per sqm
                
                # Parse years - use 0 if not available
                construction_start = self._parse_year(project.get('construction_start', ''))
                launch_date = self._parse_year(project.get('launch_date', ''))
                handover_date = self._parse_year(project.get('handover_date', ''))
                
                # Prepare project data - NO DEFAULTS, only map what exists
                project_data = {
                    'company_ticker': st.session_state.get('selected_company', ''),
                    'company_name': st.session_state.get('selected_company_name', ''),
                    'location': project.get('location', ''),
                    'project_ownership': 0,  # No default ownership
                    'total_units': total_units,
                    'net_sellable_area': net_sellable_area,
                    'average_unit_size': avg_unit_size,
                    'average_selling_price': avg_price,
                    'price_increment_factor': 0,
                    'gross_floor_area': gfa,
                    'land_area': land_area,
                    'construction_cost_per_sqm': 0,  # No default
                    'land_cost_per_sqm': land_cost_per_sqm,
                    'construction_start_year': construction_start,
                    'sale_start_year': launch_date,
                    'land_payment_year': launch_date,
                    'construction_years': 0,  # No default
                    'sales_years': 0,  # No default
                    'revenue_booking_start_year': launch_date,
                    'project_completion_year': handover_date,
                    'sga_percentage': 0,  # No default
                    'wacc_rate': 0,  # No default
                    'cost_of_debt': 0,  # No default
                    # Financial metrics
                    'total_revenue': total_revenue_bn * 1000 if total_revenue_bn > 0 else 0,
                    'total_construction_cost': construction_cost_bn * 1000 if construction_cost_bn > 0 else 0,
                    'total_land_cost': land_cost_bn * 1000 if land_cost_bn > 0 else 0,
                    'total_sga_cost': 0,
                    'total_pat': 0,
                    'total_pbt': 0,
                    # Additional fields
                    'development_status': project.get('development_status', ''),
                    'sales_status': project.get('sales_status', ''),
                    'remaining_units': self._parse_number(project.get('remaining_units', 0)),
                    # Empty distribution fields
                    'revenue_distribution': {},
                    'presales_distribution': {},
                    'pnl_schedule': {}
                }
                
                # Save to MongoDB
                result = save_project_to_mongodb(
                    project_data,
                    project.get('project_name', f"Project_{i+1}")
                )
                
                if result.get('success', False):
                    success_count += 1
                else:
                    error_count += 1
                    error_messages.append(f"{project.get('project_name', 'Unknown')}: {result.get('message', 'Unknown error')}")
                    
            except Exception as e:
                error_count += 1
                error_messages.append(f"{project.get('project_name', 'Unknown')}: {str(e)}")
        
        progress_bar.empty()
        status_text.empty()
        
        # Display results
        if success_count > 0:
            st.success(f"✅ Successfully saved {success_count} project(s) to database")
        
        if error_count > 0:
            st.error(f"❌ Failed to save {error_count} project(s)")
            with st.expander("View error details"):
                for error_msg in error_messages:
                    st.write(f"• {error_msg}")
        
        # Clear selected projects after saving
        if success_count > 0:
            st.session_state.selected_projects_for_db = []
            st.rerun()
    
    def _parse_number(self, value):
        """Parse number from various formats"""
        if value == 'N/A' or value is None or value == '':
            return 0
        if isinstance(value, (int, float)):
            return float(value)
        # Handle string numbers with commas
        if isinstance(value, str):
            # Remove commas and convert
            try:
                return float(str(value).replace(',', '').strip())
            except:
                return 0
        return 0
    
    def _parse_year(self, value):
        """Parse year from various formats"""
        if value == 'N/A' or value is None or value == '':
            return 0  # Return 0 for no data
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            # Try to extract year from string (e.g., "Q1/2025" -> 2025)
            import re
            year_match = re.search(r'20\d{2}', str(value))
            if year_match:
                return int(year_match.group())
            # Try direct conversion
            try:
                year = int(value)
                if 2000 <= year <= 2050:
                    return year
            except:
                pass
        return 0  # Return 0 for no valid year found
    
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
        """Display extracted real estate projects with selection options"""
        
        # Real Estate Projects Table
        if st.session_state.real_estate_projects:
            st.subheader("🏢 Extracted Real Estate Projects")
            
            projects = st.session_state.real_estate_projects
            
            # Load existing projects from MongoDB for duplicate detection
            try:
                from utils.mongodb_utils import load_projects_data
                existing_projects_df = load_projects_data()
                existing_project_names = []
                if not existing_projects_df.empty:
                    existing_project_names = existing_projects_df['project_name'].str.lower().tolist() if 'project_name' in existing_projects_df.columns else []
            except:
                existing_project_names = []
            
            # Create comprehensive display dataframe with selection options
            display_data = []
            for proj in projects:
                # Check if project is duplicate
                proj_name = proj.get('project_name', 'N/A')
                is_duplicate = proj_name.lower() in existing_project_names if proj_name != 'N/A' else False
                
                # Determine completion status
                dev_status = str(proj.get('development_status', '')).lower()
                progress = str(proj.get('construction_progress', '')).replace('%', '').strip()
                
                is_completed = (
                    'completed' in dev_status or 
                    'complete' in dev_status or
                    progress == '100' or
                    '100%' in str(proj.get('construction_progress', '')) or
                    'handover' in dev_status
                )
                
                display_data.append({
                    'Add to DB': False,  # Checkbox column
                    'Duplicate Warning': '⚠️ Duplicate' if is_duplicate else '',
                    'Status': '✅ Completed' if is_completed else '🔄 In Progress',
                    'Project Name': proj_name,
                    'Location': proj.get('location', 'N/A'),
                    'Type': proj.get('project_type', 'N/A'),
                    'Land Area (sqm)': proj.get('land_area_sqm', 'N/A'),
                    'Total Units': proj.get('total_units', 'N/A'),
                    'Sales Status': proj.get('sales_status', proj.get('selling_status', 'N/A')),
                    'Dev Status': proj.get('development_status', 'N/A'),
                    'Progress': proj.get('construction_progress', 'N/A'),
                    'Launch': proj.get('launch_date', proj.get('launch_year', 'N/A')),
                    'Handover': proj.get('handover_date', 'N/A'),
                    '_original_data': proj  # Store original data for later use
                })
            
            df = pd.DataFrame(display_data)
            
            # Sort by status - completed projects first
            df = df.sort_values('Status', ascending=False).reset_index(drop=True)
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Projects", len(df))
            with col2:
                completed_count = (df['Status'] == '✅ Completed').sum()
                st.metric("Completed Projects", completed_count)
            with col3:
                duplicate_count = (df['Duplicate Warning'] != '').sum()
                st.metric("Duplicate Projects", duplicate_count)
            with col4:
                st.metric("Documents Analyzed", len(st.session_state.uploaded_documents))
            
            # Create editable dataframe with checkboxes
            edited_df = st.data_editor(
                df.drop(columns=['_original_data']),
                column_config={
                    "Add to DB": st.column_config.CheckboxColumn(
                        "Add to DB",
                        help="Select projects to add to database",
                        default=False,
                    ),
                    "Duplicate Warning": st.column_config.TextColumn(
                        "Duplicate",
                        help="⚠️ indicates project may already exist in database",
                        disabled=True,
                    ),
                    "Status": st.column_config.TextColumn(
                        "Status",
                        help="Project completion status",
                        disabled=True,
                    )
                },
                disabled=[col for col in df.columns if col not in ['Add to DB']],
                hide_index=True,
                use_container_width=True,
                height=400,
                key="project_selector"
            )
            
            # Button to process selected projects
            if st.button("📊 Select Projects to Add to Database", type="primary"):
                # Get selected projects
                selected_mask = edited_df['Add to DB'] == True
                selected_projects = []
                
                for idx in df[selected_mask].index:
                    selected_projects.append(df.loc[idx, '_original_data'])
                
                if selected_projects:
                    st.session_state.selected_projects_for_db = selected_projects
                    st.success(f"✅ Selected {len(selected_projects)} projects for database addition")
                else:
                    st.warning("⚠️ No projects selected. Please check the 'Add to DB' boxes for projects you want to add.")
            
            # Display selected projects in pipeline format
            if 'selected_projects_for_db' in st.session_state and st.session_state.selected_projects_for_db:
                st.markdown("---")
                st.subheader("📋 Projects to be Added to Database")
                
                # Load existing projects from MongoDB for comparison - ONLY for selected ticker
                existing_pipeline_data = []
                selected_ticker = st.session_state.get('selected_company', '')
                try:
                    from utils.mongodb_utils import load_projects_data
                    existing_projects_df = load_projects_data()
                    if not existing_projects_df.empty and selected_ticker:
                        # Filter by selected company ticker
                        filtered_df = existing_projects_df[existing_projects_df['company_ticker'] == selected_ticker]
                        
                        # Convert existing projects to pipeline format - ONLY specified columns
                        for _, row in filtered_df.iterrows():
                            existing_pipeline_data.append({
                                'Source': '📂 Existing in DB',
                                'project_name': row.get('project_name', 'N/A'),
                                'company_ticker': row.get('company_ticker', 'N/A'),
                                'location': row.get('location', 'N/A'),
                                'project_ownership': row.get('project_ownership', 'N/A'),
                                'total_units': row.get('total_units', 'N/A'),
                                'net_sellable_area': row.get('net_sellable_area', 'N/A'),
                                'average_unit_size': row.get('average_unit_size', 'N/A'),
                                'average_selling_price': row.get('average_selling_price', 'N/A'),
                                'price_increment_factor': row.get('price_increment_factor', 'N/A'),
                                'gross_floor_area': row.get('gross_floor_area', 'N/A'),
                                'land_area': row.get('land_area', 'N/A'),
                                'construction_cost_per_sqm': row.get('construction_cost_per_sqm', 'N/A'),
                                'land_cost_per_sqm': row.get('land_cost_per_sqm', 'N/A'),
                                'construction_start_year': row.get('construction_start_year', 'N/A'),
                                'construction_years': row.get('construction_years', 'N/A'),
                                'sale_start_year': row.get('sale_start_year', 'N/A'),
                                'sales_years': row.get('sales_years', 'N/A'),
                                'revenue_booking_start_year': row.get('revenue_booking_start_year', 'N/A'),
                                'project_completion_year': row.get('project_completion_year', 'N/A'),
                                'rnav_value': row.get('rnav_value', 'N/A')
                            })
                except:
                    pass
                
                # Create pipeline-compatible table for NEW projects - matching existing columns
                new_pipeline_data = []
                for proj in st.session_state.selected_projects_for_db:
                    # Parse NSA and calculate average unit size
                    nsa = self._parse_number(proj.get('nsa_sqm', 0))
                    total_units = self._parse_number(proj.get('total_units', 0))
                    avg_unit_size = nsa / total_units if total_units > 0 and nsa > 0 else 'N/A'
                    
                    new_pipeline_data.append({
                        'Source': '✨ New Project',
                        'project_name': proj.get('project_name', 'N/A'),
                        'company_ticker': st.session_state.get('selected_company', 'N/A'),
                        'location': proj.get('location', 'N/A'),
                        'project_ownership': 'N/A',  # Will be set by user
                        'total_units': proj.get('total_units', 'N/A'),
                        'net_sellable_area': proj.get('nsa_sqm', 'N/A'),
                        'average_unit_size': avg_unit_size if avg_unit_size != 'N/A' else 'N/A',
                        'average_selling_price': proj.get('avg_selling_price', 'N/A'),
                        'price_increment_factor': 'N/A',  # Will be set by user
                        'gross_floor_area': proj.get('gfa_sqm', 'N/A'),
                        'land_area': proj.get('land_area_sqm', 'N/A'),
                        'construction_cost_per_sqm': 'N/A',  # Will be set by user
                        'land_cost_per_sqm': 'N/A',  # Will be calculated or set
                        'construction_start_year': proj.get('construction_start', 'N/A'),
                        'construction_years': 'N/A',  # Will be set by user
                        'sale_start_year': proj.get('launch_date', 'N/A'),
                        'sales_years': 'N/A',  # Will be set by user
                        'revenue_booking_start_year': proj.get('launch_date', 'N/A'),
                        'project_completion_year': proj.get('handover_date', 'N/A'),
                        'rnav_value': 'N/A'  # Will be calculated
                    })
                
                # Combine existing and new projects
                all_pipeline_data = existing_pipeline_data + new_pipeline_data
                
                if all_pipeline_data:
                    pipeline_df = pd.DataFrame(all_pipeline_data)
                    
                    # Display metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Existing Projects in DB", len(existing_pipeline_data))
                    with col2:
                        st.metric("New Projects to Add", len(new_pipeline_data))
                    with col3:
                        # Check for potential duplicates
                        if existing_pipeline_data and new_pipeline_data:
                            existing_names = [p['project_name'].lower() for p in existing_pipeline_data if p['project_name'] != 'N/A']
                            new_names = [p['project_name'].lower() for p in new_pipeline_data if p['project_name'] != 'N/A']
                            duplicates = len([n for n in new_names if n in existing_names])
                            st.metric("Potential Duplicates", duplicates)
                        else:
                            st.metric("Potential Duplicates", 0)
                    
                    # Split dataframe for display
                    existing_df = pipeline_df[pipeline_df['Source'] == '📂 Existing in DB']
                    new_df = pipeline_df[pipeline_df['Source'] == '✨ New Project']
                    
                    # Display existing projects (non-editable)
                    if not existing_df.empty:
                        st.markdown("**📂 Existing Projects in Database (Reference Only)**")
                        st.dataframe(
                            existing_df.style.applymap(
                                lambda x: 'background-color: #f0f0f0; color: #666;',
                                subset=['Source']
                            ),
                            use_container_width=True,
                            height=min(200, len(existing_df) * 40 + 40)
                        )
                    
                    # Display new projects (editable)
                    if not new_df.empty:
                        st.markdown("**✨ New Projects to Add (Editable)**")
                        
                        # Make new projects editable
                        edited_new_df = st.data_editor(
                            new_df,
                            use_container_width=True,
                            height=min(300, len(new_df) * 40 + 40),
                            column_config={
                                "Source": st.column_config.TextColumn(
                                    "Source",
                                    help="✨ = New project to add",
                                    disabled=True,
                                    width="small"
                                )
                            },
                            disabled=['Source'],  # Only Source column is disabled
                            hide_index=True,
                            key="editable_new_projects"
                        )
                        
                    
                    if new_pipeline_data:
                        st.success(f"✅ {len(new_pipeline_data)} new project(s) ready for database addition")
                        if duplicates > 0:
                            st.warning(f"⚠️ {duplicates} project name(s) match existing database entries. Please review before saving.")
                        
                        # Save button
                        col1, col2, col3 = st.columns([1, 2, 1])
                        with col2:
                            if st.button("💾 Save New Projects to Database", type="primary", use_container_width=True):
                                # Always use the edited dataframe values
                                if edited_new_df is not None and not edited_new_df.empty:
                                    # Filter to only new projects (not existing ones)
                                    new_projects_only = edited_new_df[edited_new_df['Source'] == '✨ New Project']
                                    if not new_projects_only.empty:
                                        self.save_edited_projects_to_database(new_projects_only)
                                    else:
                                        st.warning("No new projects to save")
                                else:
                                    st.warning("No projects available to save")
                    
                    st.info("🔍 Review the projects above. Existing database projects (gray rows) are shown for duplicate checking.")
                else:
                    st.info("No projects to display")