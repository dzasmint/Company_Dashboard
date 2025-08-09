"""
Claude AI integration for extracting real estate projects from financial statements
"""

import anthropic
import json
import os
import streamlit as st
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
import PyPDF2
import pandas as pd
from io import BytesIO
from datetime import datetime
import numpy as np

# Load environment variables
load_dotenv()

class ClaudeProjectExtractor:
    """Extract real estate project information from financial statements using Claude AI"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Claude client with API key"""
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found. Please set it in .env file or pass it directly.")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
    
    def _convert_none_to_zero(self, obj):
        """Recursively convert None values to 0 in nested dictionaries/lists"""
        if isinstance(obj, dict):
            return {k: self._convert_none_to_zero(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_none_to_zero(item) for item in obj]
        elif obj is None:
            return 0
        else:
            return obj
        
    def extract_text_from_pdf(self, pdf_file) -> str:
        """Extract text from uploaded PDF file using multiple methods"""
        text = ""
        extraction_successful = False
        
        # Show extraction status
        extraction_container = st.container()
        with extraction_container:
            with st.spinner("Attempting to extract text from PDF..."):
                
                # Method 1: Try pdfplumber first (better for complex PDFs)
                try:
                    import pdfplumber
                    
                    if isinstance(pdf_file, str):
                        # File path
                        with pdfplumber.open(pdf_file) as pdf:
                            for page in pdf.pages:
                                page_text = page.extract_text()
                                if page_text:
                                    text += page_text + "\n"
                    else:
                        # Streamlit uploaded file - need to save temporarily
                        import tempfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                            tmp_file.write(pdf_file.read())
                            tmp_file_path = tmp_file.name
                        
                        # Reset file pointer for potential reuse
                        pdf_file.seek(0)
                        
                        with pdfplumber.open(tmp_file_path) as pdf:
                            for page in pdf.pages:
                                page_text = page.extract_text()
                                if page_text:
                                    text += page_text + "\n"
                        
                        # Clean up temp file
                        os.unlink(tmp_file_path)
                    
                    if text.strip():
                        extraction_successful = True
                        st.success(f"✅ Extracted {len(text):,} characters from PDF")
                        return text
                        
                except Exception as e:
                    pass  # Try next method
        
                # Method 2: Fallback to PyPDF2
                if not extraction_successful:
                    try:
                        # Reset file pointer if needed
                        if hasattr(pdf_file, 'seek'):
                            pdf_file.seek(0)
                        
                        if isinstance(pdf_file, str):
                            with open(pdf_file, 'rb') as file:
                                pdf_reader = PyPDF2.PdfReader(file)
                                for page in pdf_reader.pages:
                                    page_text = page.extract_text()
                                    if page_text:
                                        text += page_text + "\n"
                        else:
                            pdf_reader = PyPDF2.PdfReader(pdf_file)
                            for page in pdf_reader.pages:
                                page_text = page.extract_text()
                                if page_text:
                                    text += page_text + "\n"
                        
                        if text.strip():
                            extraction_successful = True
                            st.success(f"✅ Extracted {len(text):,} characters from PDF")
                            return text
                            
                    except Exception as e:
                        pass  # Try next method
        
                # Method 3: Try PyMuPDF if available
                if not extraction_successful:
                    try:
                        import fitz  # PyMuPDF
                        
                        # Reset file pointer if needed
                        if hasattr(pdf_file, 'seek'):
                            pdf_file.seek(0)
                        
                        if isinstance(pdf_file, str):
                            doc = fitz.open(pdf_file)
                        else:
                            # For uploaded file, read bytes
                            pdf_bytes = pdf_file.read()
                            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        
                        for page in doc:
                            page_text = page.get_text()
                            if page_text:
                                text += page_text + "\n"
                        
                        doc.close()
                        
                        if text.strip():
                            extraction_successful = True
                            st.success(f"✅ Extracted {len(text):,} characters from PDF")
                            return text
                            
                    except ImportError:
                        pass  # PyMuPDF not installed
                    except Exception as e:
                        pass  # Continue to manual input
        
        # If all methods fail, provide manual input option
        if not extraction_successful:
            st.warning("""
            ⚠️ **Unable to extract text from PDF automatically**
            
            This PDF appears to be scanned or image-based. This is common with Vietnamese financial statements.
            
            **Please use one of these options:**
            """)
            
            # Create tabs for different input methods
            tab1, tab2, tab3 = st.tabs(["📝 Manual Input", "🔧 OCR Tools", "💡 Tips"])
            
            with tab1:
                st.info("Paste the relevant sections from your financial statement below:")
                
                manual_text = st.text_area(
                    "Financial Statement Text (focus on Inventory/Hàng tồn kho section):",
                    height=500,
                    placeholder="""Paste your financial statement text here. Example format:

HÀNG TỒN KHO / INVENTORY
Đơn vị: Triệu VNĐ

Bất động sản đang phát triển (Properties under development):
- Dự án Gem Riverside: 2,500,000
  Địa điểm: Quận 2, TP.HCM
  Diện tích: 6.7 ha
  Tổng số căn: 3,175 căn
  
- Dự án Opal Boulevard: 1,500,000
  Địa điểm: Dĩ An, Bình Dương
  Tổng số căn: 2,156 căn
  
- Dự án Gem Sky World: 3,200,000
  Địa điểm: Long Thành, Đồng Nai
  Quy mô: 92 ha
  Tổng số căn: 4,500 căn

Bất động sản hoàn thành (Completed properties):
- Lux Star: 450,000
- St. Moritz: 680,000

Tổng cộng: 11,050,000""",
                    key="manual_pdf_text_input"
                )
                
                if manual_text and manual_text.strip():
                    st.success(f"✓ Using manually provided text ({len(manual_text):,} characters)")
                    return manual_text
            
            with tab2:
                st.markdown("""
                ### Free OCR Tools to Convert Your PDF:
                
                **1. Google Drive (Recommended)**
                - Upload PDF to Google Drive
                - Right-click → Open with → Google Docs
                - Google will OCR the PDF automatically
                - Copy the text and paste in Manual Input tab
                
                **2. Online OCR Services**
                - [SmallPDF](https://smallpdf.com/pdf-to-word) - 2 free files per day
                - [ILovePDF](https://www.ilovepdf.com/pdf_to_word) - Free with limits
                - [PDF.io](https://pdf.io/pdf2txt/) - Simple text extraction
                
                **3. Adobe Acrobat Online**
                - [Adobe PDF to Word](https://www.adobe.com/acrobat/online/pdf-to-word.html)
                - Free trial available
                """)
            
            with tab3:
                st.markdown("""
                ### Tips for Better Results:
                
                **What Claude Opus is looking for:**
                - **Inventory section** (Hàng tồn kho)
                - **Project names** and their **book values**
                - **Location information** (city, district)
                - **Project scale** (number of units, area)
                - **Development status** (under construction, completed)
                
                **Key Vietnamese terms:**
                - Bất động sản đang phát triển = Properties under development
                - Bất động sản hoàn thành = Completed properties
                - Dự án = Project
                - Địa điểm = Location
                - Tổng số căn = Total units
                - Diện tích = Area
                - Giá trị sổ sách = Book value
                
                **Format your text clearly:**
                - Include project names
                - Include values in VND (millions or billions)
                - Include location details
                - Separate projects clearly
                """)
            
            return ""
        
        return text
    
    def extract_text_from_excel(self, excel_file) -> str:
        """Extract text from uploaded Excel file"""
        try:
            # Reset file pointer if needed
            if hasattr(excel_file, 'seek'):
                excel_file.seek(0)
            
            # Read all sheets
            excel_data = pd.read_excel(excel_file, sheet_name=None)
            text = ""
            
            # Process each sheet
            for sheet_name, df in excel_data.items():
                text += f"\n\n=== Sheet: {sheet_name} ===\n"
                
                # Convert DataFrame to string, handling various data types
                try:
                    # Replace NaN with empty string for better readability
                    df = df.fillna('')
                    
                    # Convert to string with better formatting
                    sheet_text = df.to_string(max_rows=None, max_cols=None)
                    text += sheet_text
                    
                    # Also add a CSV-like version for better parsing
                    text += "\n\n--- CSV Format ---\n"
                    text += df.to_csv(index=False)
                    
                except Exception as e:
                    st.warning(f"Issue formatting sheet {sheet_name}: {str(e)}")
                    # Try simpler conversion
                    text += str(df)
            
            if not text.strip():
                st.error("Excel file appears to be empty")
                return ""
            
            # Show extraction success
            st.success(f"✓ Extracted {len(text):,} characters from Excel file")
            
            return text
            
        except Exception as e:
            st.error(f"""
            ❌ **Error extracting text from Excel: {str(e)}**
            
            **Try:**
            - Ensuring the file is a valid Excel file (.xlsx or .xls)
            - Checking if the file is not corrupted
            - Making sure the file is not password-protected
            """)
            return ""
    
    def detect_document_type(self, document_text: str) -> str:
        """
        Detect whether the document is a financial statement, analyst report, or company presentation
        
        Args:
            document_text: The extracted text from the document
            
        Returns:
            'financial_statement', 'analyst_report', or 'company_presentation'
        """
        # Keywords that indicate analyst reports
        analyst_keywords = [
            'buy recommendation', 'sell recommendation', 'hold recommendation',
            'target price', 'investment thesis', 'valuation', 'earnings preview',
            'earnings review', 'initiation of coverage', 'equity research',
            'analyst note', 'research note', 'investment summary',
            'rating', 'overweight', 'underweight', 'neutral',
            'dcf model', 'rnav', 'sotp', 'p/e ratio', 'ev/ebitda'
        ]
        
        # Keywords that indicate financial statements
        financial_keywords = [
            'balance sheet', 'income statement', 'cash flow statement',
            'bảng cân đối kế toán', 'báo cáo kết quả kinh doanh',
            'báo cáo lưu chuyển tiền tệ', 'thuyết minh báo cáo tài chính',
            'notes to financial statements', 'auditor', 'kiểm toán'
        ]
        
        # Keywords that indicate company presentations
        presentation_keywords = [
            'investor presentation', 'company presentation', 'roadshow',
            'investor deck', 'corporate presentation', 'management presentation',
            'agm presentation', 'annual general meeting', 'investor day',
            'project pipeline', 'development pipeline', 'land bank',
            'strategic plan', 'growth strategy', 'business strategy',
            'market overview', 'company overview', 'investment highlights'
        ]
        
        text_lower = document_text.lower()
        
        # Count keyword matches
        analyst_count = sum(1 for keyword in analyst_keywords if keyword in text_lower)
        financial_count = sum(1 for keyword in financial_keywords if keyword in text_lower)
        presentation_count = sum(1 for keyword in presentation_keywords if keyword in text_lower)
        
        # Determine document type based on keyword density
        max_count = max(analyst_count, financial_count, presentation_count)
        
        if max_count == presentation_count and presentation_count > 0:
            return 'company_presentation'
        elif max_count == analyst_count and analyst_count > 0:
            return 'analyst_report'
        else:
            return 'financial_statement'
    
    def extract_projects_from_analyst_report(self, 
                                            document_text: str, 
                                            company_name: str,
                                            company_ticker: str) -> Dict:
        """
        Extract real estate projects from sell-side analyst reports using Claude AI
        
        Args:
            document_text: The extracted text from the analyst report
            company_name: Name of the company
            company_ticker: Stock ticker of the company
            
        Returns:
            Dictionary containing extracted projects and metadata
        """
        
        prompt = f"""
        Analyze this sell-side analyst report for {company_name} ({company_ticker}) and extract ALL real estate projects mentioned.
        
        IMPORTANT: Analyst reports discuss projects differently than financial statements. Look for projects in:
        
        1. PROJECT PIPELINE DISCUSSIONS
           - Current projects under development
           - Upcoming launches
           - Projects in presales
           - Completed projects with remaining inventory
        
        2. RNAV (REVALUED NET ASSET VALUE) CALCULATIONS
           - Project-by-project breakdown
           - NAV calculations per project
           - Development timeline assumptions
           - Sales assumptions
        
        3. EARNINGS FORECASTS & ASSUMPTIONS
           - Revenue recognition schedules
           - Project handover timelines
           - Presales targets and achievements
           - Construction progress updates
        
        4. KEY INVESTMENT HIGHLIGHTS
           - New project acquisitions
           - Land bank discussions
           - Joint venture projects
           - Strategic developments
        
        5. TABLES AND EXHIBITS
           - Project pipeline tables
           - Sales status tables
           - Development schedule charts
           - RNAV breakdown tables
        
        For each project found, extract:
        - Project name (as mentioned in the report)
        - Estimated NAV or project value (if provided)
        - Development stage (planning/presales/construction/handover)
        - Location (city and district)
        - Total units or GFA
        - Sales status (% sold if mentioned)
        - Expected launch/completion dates
        - ASP (average selling price) assumptions
        - Any specific analyst comments or concerns
        
        Also capture:
        - Analyst's total RNAV estimate
        - Target price if mentioned
        - Key assumptions about the projects
        - Risk factors related to specific projects
        
        Return ONLY a valid JSON object in this exact format:
        {{
            "projects_in_pipeline": [
                {{
                    "project_name": "Project name from report",
                    "nav_value_vnd": 1500000000000,
                    "stage": "presales",
                    "location": "District 2, Ho Chi Minh City",
                    "total_units": 500,
                    "gfa_sqm": 50000,
                    "sales_status_pct": 65,
                    "launch_date": "Q2 2024",
                    "completion_date": "2026",
                    "asp_per_sqm": 45000000,
                    "analyst_notes": "Key project contributing 30% of NAV",
                    "source_section": "RNAV breakdown table"
                }}
            ],
            "future_projects": [
                {{
                    "project_name": "Future project mentioned",
                    "location": "Location if specified",
                    "expected_launch": "2025",
                    "analyst_view": "Potential upside not included in base case"
                }}
            ],
            "analyst_metrics": {{
                "total_rnav": 35000000000000,
                "rnav_per_share": 25000,
                "target_price": 27000,
                "implied_discount_to_rnav": 0.15,
                "key_assumptions": "Assumes 20% presales price growth"
            }},
            "extraction_summary": {{
                "total_projects_found": 12,
                "projects_in_rnav": 10,
                "confidence_score": 0.85,
                "report_date": "Date if found",
                "analyst_firm": "Firm name if identified"
            }}
        }}
        
        Focus on extracting actionable project information that analysts use for valuation.
        
        Analyst Report Text:
        {document_text[:80000]}  # Limit to ~80k characters for optimal performance
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0,
                system="""You are a financial analyst expert specialized in reading sell-side equity research reports 
                on Vietnamese real estate companies. You understand how analysts discuss and value real estate projects,
                including RNAV methodology, project pipeline analysis, and development assumptions.
                Always return valid JSON only, with no additional text.""",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse the response
            response_text = response.content[0].text
            
            # Clean up response if needed
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            # Parse JSON
            result = json.loads(response_text)
            
            # Clean up None values in numeric fields
            if 'projects_in_pipeline' in result:
                for project in result.get('projects_in_pipeline', []):
                    # Ensure numeric fields are not None
                    if project.get('nav_value_vnd') is None:
                        project['nav_value_vnd'] = 0
                    if project.get('sales_status_pct') is None:
                        project['sales_status_pct'] = 0
                    if project.get('asp_per_sqm') is None:
                        project['asp_per_sqm'] = 0
                    if project.get('total_units') is None:
                        project['total_units'] = 0
                    if project.get('gfa_sqm') is None:
                        project['gfa_sqm'] = 0
            
            # Clean up analyst metrics
            if 'analyst_metrics' in result:
                metrics = result['analyst_metrics']
                if metrics.get('total_rnav') is None:
                    metrics['total_rnav'] = 0
                if metrics.get('rnav_per_share') is None:
                    metrics['rnav_per_share'] = 0
                if metrics.get('target_price') is None:
                    metrics['target_price'] = 0
                if metrics.get('implied_discount_to_rnav') is None:
                    metrics['implied_discount_to_rnav'] = 0
            
            # Add metadata
            result['metadata'] = {
                'company_name': company_name,
                'company_ticker': company_ticker,
                'extraction_date': pd.Timestamp.now().isoformat(),
                'document_type': 'analyst_report',
                'model_used': 'claude-3-5-sonnet-20241022'
            }
            
            return result
            
        except json.JSONDecodeError as e:
            st.error(f"Error parsing Claude response as JSON: {str(e)}")
            return {
                "error": "Failed to parse response",
                "projects_in_pipeline": [],
                "future_projects": [],
                "analyst_metrics": {}
            }
        except Exception as e:
            st.error(f"Error calling Claude API: {str(e)}")
            return {
                "error": str(e),
                "projects_in_pipeline": [],
                "future_projects": [],
                "analyst_metrics": {}
            }
    
    def extract_projects_from_presentation(self, 
                                          document_text: str, 
                                          company_name: str,
                                          company_ticker: str) -> Dict:
        """
        Extract real estate projects from company presentations using Claude AI
        
        Args:
            document_text: The extracted text from the presentation
            company_name: Name of the company
            company_ticker: Stock ticker of the company
            
        Returns:
            Dictionary containing extracted projects and metadata
        """
        
        prompt = f"""
        Analyze this company presentation for {company_name} ({company_ticker}) and extract ALL real estate projects mentioned.
        
        IMPORTANT: Company presentations often discuss projects in various sections. Look for:
        
        1. PROJECT PIPELINE / DEVELOPMENT PIPELINE
           - Current projects in different stages
           - Upcoming launches and timeline
           - Land bank and future developments
           - Geographic distribution of projects
        
        2. PROJECT HIGHLIGHTS / KEY PROJECTS
           - Featured projects with details
           - Sales performance and progress
           - Construction status updates
           - Project specifications (GFA, units, etc.)
        
        3. FINANCIAL HIGHLIGHTS BY PROJECT
           - Revenue contribution by project
           - Presales achievements
           - Backlog and future revenue
           - Project profitability metrics
        
        4. STRATEGIC INITIATIVES
           - New land acquisitions
           - Joint venture projects
           - Township developments
           - Mixed-use projects
        
        5. APPENDIX / PROJECT FACT SHEETS
           - Detailed project information
           - Location maps
           - Product mix details
           - Development schedules
        
        For each project found, extract:
        - Project name (exact as mentioned)
        - Location (city, district, province)
        - Project type (residential/commercial/mixed-use)
        - Total units or GFA
        - Development stage (land bank/planning/construction/selling/completed)
        - Launch timeline (if mentioned)
        - Sales status (units sold, % sold)
        - Key highlights or unique features
        - Any financial metrics (revenue, presales value)
        
        Return ONLY a valid JSON object in this exact format:
        {{
            "active_projects": [
                {{
                    "project_name": "Project name from presentation",
                    "location": "District, City",
                    "project_type": "residential",
                    "total_units": 1500,
                    "gfa_sqm": 150000,
                    "stage": "construction",
                    "launch_date": "Q2 2024",
                    "sales_status_pct": 70,
                    "presales_value_vnd": 3500000000000,
                    "key_features": "Waterfront, near metro line",
                    "source_slide": "Slide 15"
                }}
            ],
            "pipeline_projects": [
                {{
                    "project_name": "Future project",
                    "location": "Location",
                    "land_area_sqm": 50000,
                    "planned_units": 2000,
                    "expected_launch": "2025",
                    "development_stage": "planning"
                }}
            ],
            "land_bank": [
                {{
                    "location": "Province/City",
                    "land_area_ha": 25,
                    "intended_use": "residential township",
                    "acquisition_year": "2023"
                }}
            ],
            "presentation_metrics": {{
                "total_projects": 15,
                "total_units_in_pipeline": 25000,
                "total_gfa_sqm": 2500000,
                "geographic_presence": ["HCMC", "Hanoi", "Da Nang"],
                "presentation_date": "Date if found"
            }},
            "extraction_summary": {{
                "total_projects_found": 15,
                "active_projects": 10,
                "pipeline_projects": 5,
                "confidence_score": 0.9,
                "document_quality": "Good - detailed project information"
            }}
        }}
        
        Focus on concrete project information rather than general statements.
        
        Presentation Text:
        {document_text[:80000]}  # Limit to ~80k characters for optimal performance
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0,
                system="""You are a financial analyst expert specialized in analyzing real estate company presentations.
                You understand how companies present their project pipelines, development strategies, and project details.
                You can extract structured project information from presentations, investor decks, and management slides.
                Always return valid JSON only, with no additional text.""",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse the response
            response_text = response.content[0].text
            
            # Clean up response if needed
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            # Parse JSON
            result = json.loads(response_text)
            
            # Clean up None values in numeric fields
            for project_list_key in ['active_projects', 'pipeline_projects']:
                if project_list_key in result:
                    for project in result.get(project_list_key, []):
                        # Ensure numeric fields are not None
                        numeric_fields = ['total_units', 'gfa_sqm', 'sales_status_pct', 
                                        'presales_value_vnd', 'land_area_sqm', 'planned_units']
                        for field in numeric_fields:
                            if field in project and project[field] is None:
                                project[field] = 0
            
            # Add metadata
            result['metadata'] = {
                'company_name': company_name,
                'company_ticker': company_ticker,
                'extraction_date': pd.Timestamp.now().isoformat(),
                'document_type': 'company_presentation',
                'model_used': 'claude-3-5-sonnet-20241022'
            }
            
            return result
            
        except json.JSONDecodeError as e:
            st.error(f"Error parsing Claude response as JSON: {str(e)}")
            return {
                "error": "Failed to parse response",
                "active_projects": [],
                "pipeline_projects": [],
                "land_bank": []
            }
        except Exception as e:
            st.error(f"Error calling Claude API: {str(e)}")
            return {
                "error": str(e),
                "active_projects": [],
                "pipeline_projects": [],
                "land_bank": []
            }
    
    def extract_revenue_and_projects(self,
                                     document_text: str,
                                     company_name: str,
                                     company_ticker: str) -> Dict:
        """
        Extract ALL revenue streams AND real estate projects from financial statements
        
        Args:
            document_text: Text from financial document
            company_name: Company name
            company_ticker: Stock ticker
            
        Returns:
            Dictionary with revenue streams and projects
        """
        
        prompt = f"""
        Analyze the financial statements of {company_name} ({company_ticker}) to extract comprehensive revenue information.
        
        DOCUMENT TEXT:
        {document_text[:12000]}
        
        Extract the following information:
        
        1. ALL REVENUE STREAMS/BUSINESS SEGMENTS:
        Look for revenue breakdown by business segment. Common segments include:
        - Real Estate Development / Property Development (Bất động sản)
        - Construction Services (Dịch vụ xây dựng)
        - Property Management (Quản lý bất động sản)
        - Leasing/Rental Income (Cho thuê)
        - Brokerage/Agency Services (Môi giới)
        - Hotels/Resorts (Khách sạn)
        - Other Services
        
        For each revenue stream found, extract:
        - Revenue amount for latest year (2023 or 2024)
        - Revenue amount for prior year (2022 or 2023)
        - Percentage of total revenue
        - Gross profit and margin if available
        - Year-over-year growth rate
        
        2. REAL ESTATE PROJECTS (if mentioned):
        Extract any real estate projects mentioned in inventory or notes
        
        IMPORTANT: Return ONLY valid JSON in the following format. Do not include any text before or after the JSON:
        {{
            "revenue_analysis": {{
                "total_revenue": {{
                    "2023": 15000000000000,
                    "2022": 12000000000000
                }},
                "revenue_streams": [
                    {{
                        "segment_name": "Real Estate Development",
                        "revenue_2023": 10000000000000,
                        "revenue_2022": 8000000000000,
                        "percentage_of_total": 67,
                        "gross_profit_2023": 3000000000000,
                        "gross_margin": 0.30,
                        "growth_rate": 0.25,
                        "description": "Property development and sales"
                    }},
                    {{
                        "segment_name": "Construction Services",
                        "revenue_2023": 3000000000000,
                        "revenue_2022": 2500000000000,
                        "percentage_of_total": 20,
                        "gross_margin": 0.15,
                        "growth_rate": 0.20,
                        "description": "External construction contracts"
                    }}
                ]
            }},
            "real_estate_projects": [
                {{
                    "project_name": "Project name",
                    "location": "City, District",
                    "book_value_vnd": 1000000000000,
                    "total_units": 500,
                    "stage": "construction"
                }}
            ],
            "extraction_confidence": 0.85,
            "data_quality": "high"
        }}
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0,
                system="""You are a financial analyst expert in extracting revenue segments and project data
                from Vietnamese financial statements. You understand both revenue analysis and real estate
                project extraction. 
                
                CRITICAL: You must ONLY return valid JSON without any additional text, explanation, or markdown formatting.
                Start your response with { and end with }. Do not use markdown code blocks.""",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse response
            response_text = response.content[0].text
            
            # Clean the response text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            # Remove any leading/trailing whitespace
            response_text = response_text.strip()
            
            # Try to find JSON content if it's embedded in text
            if response_text and not response_text.startswith('{'):
                # Look for JSON structure
                json_start = response_text.find('{')
                if json_start != -1:
                    response_text = response_text[json_start:]
            
            if not response_text:
                raise ValueError("Empty response from Claude")
            
            # Parse JSON
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as je:
                # Log the problematic response for debugging
                st.error(f"Failed to parse JSON response. First 500 chars: {response_text[:500]}")
                raise je
            
            # Ensure all numeric values are proper Python types
            result = self._convert_none_to_zero(result)
            
            return result
            
        except json.JSONDecodeError as je:
            st.error(f"JSON parsing error: {str(je)}")
            st.error(f"Response text preview: {response_text[:200] if 'response_text' in locals() else 'No response text'}")
            return {
                "error": f"JSON parsing failed: {str(je)}",
                "revenue_analysis": {
                    "total_revenue": {},
                    "revenue_streams": []
                },
                "real_estate_projects": []
            }
        except Exception as e:
            st.error(f"Error extracting revenue and projects: {str(e)}")
            return {
                "error": str(e),
                "revenue_analysis": {
                    "total_revenue": {},
                    "revenue_streams": []
                },
                "real_estate_projects": []
            }
    
    def extract_projects_from_document(self, 
                                      document_text: str, 
                                      company_name: str,
                                      company_ticker: str,
                                      document_type: Optional[str] = None) -> Dict:
        """
        Extract real estate projects from any document using Claude AI
        Automatically detects document type if not specified
        
        Args:
            document_text: The extracted text from the document
            company_name: Name of the company
            company_ticker: Stock ticker of the company
            document_type: Optional - 'financial_statement' or 'analyst_report'
            
        Returns:
            Dictionary containing extracted projects and metadata
        """
        
        # Auto-detect document type if not specified
        if document_type is None:
            document_type = self.detect_document_type(document_text)
            st.info(f"📄 Detected document type: {document_type.replace('_', ' ').title()}")
        
        # Route to appropriate extraction method
        if document_type == 'analyst_report':
            return self.extract_projects_from_analyst_report(
                document_text, company_name, company_ticker
            )
        elif document_type == 'company_presentation':
            return self.extract_projects_from_presentation(
                document_text, company_name, company_ticker
            )
        else:
            return self.extract_projects_from_financial_statement(
                document_text, company_name, company_ticker
            )
    
    def extract_projects_from_financial_statement(self, 
                                                  document_text: str, 
                                                  company_name: str,
                                                  company_ticker: str) -> Dict:
        """
        Extract real estate projects from financial statements using Claude AI
        
        Args:
            document_text: The extracted text from the financial statement
            company_name: Name of the company
            company_ticker: Stock ticker of the company
            
        Returns:
            Dictionary containing extracted projects and metadata
        """
        
        prompt = f"""
        Analyze this financial statement for {company_name} ({company_ticker}) and extract ALL real estate projects.
        
        IMPORTANT: Look for projects in these specific sections:
        
        1. INVENTORY BREAKDOWN / HÀNG TỒN KHO
           - Development properties (Bất động sản đang phát triển)
           - Properties under construction (Bất động sản đang xây dựng)
           - Completed properties for sale (Bất động sản hoàn thành chờ bán)
           - Land use rights (Quyền sử dụng đất)
        
        2. NOTES TO FINANCIAL STATEMENTS / THUYẾT MINH BÁO CÁO TÀI CHÍNH
           - Detailed inventory notes
           - Segment reporting
           - Investment properties
           - Joint ventures and associates
        
        3. MANAGEMENT DISCUSSION & ANALYSIS
           - Project pipeline discussions
           - Development timeline
           - Sales status updates
        
        For each project found, extract:
        - Project name (exact name as written)
        - Book value in VND (from inventory breakdown)
        - Development stage: planning/under_construction/completed/selling
        - Location (city/province and district if mentioned)
        - Total units (if mentioned)
        - Land area in m2 (if mentioned)
        - Ownership percentage (100% if not specified)
        - Any notes about timeline or status
        
        Also identify:
        - Projects mentioned but not yet in inventory (future pipeline)
        - Joint venture projects with ownership percentage
        - Total inventory value
        
        Return ONLY a valid JSON object in this exact format:
        {{
            "projects_in_inventory": [
                {{
                    "project_name": "Exact project name from document",
                    "book_value_vnd": 1500000000000,
                    "stage": "under_construction",
                    "location": "District 2, Ho Chi Minh City",
                    "total_units": 500,
                    "land_area_sqm": 10000,
                    "ownership_pct": 100,
                    "notes": "Any relevant notes",
                    "source_section": "Inventory Note 8.1"
                }}
            ],
            "future_projects": [
                {{
                    "project_name": "Future Project Name",
                    "location": "Location if mentioned",
                    "planned_launch": "2025",
                    "notes": "Planning stage"
                }}
            ],
            "joint_ventures": [
                {{
                    "project_name": "JV Project Name",
                    "ownership_pct": 51,
                    "partner": "Partner name",
                    "book_value_vnd": 800000000000
                }}
            ],
            "total_inventory_value": 25000000000000,
            "extraction_summary": {{
                "total_projects_found": 15,
                "projects_with_values": 12,
                "confidence_score": 0.95,
                "data_quality_notes": "Clear inventory breakdown found in Note 8"
            }}
        }}
        
        Be precise with numbers and names. If a value is not found, use null instead of 0.
        
        Financial Statement Text:
        {document_text[:80000]}  # Limit to ~80k characters for optimal performance
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",  # Using Claude 3.5 Sonnet - most advanced model
                max_tokens=4000,
                temperature=0,  # Use 0 for more consistent extraction
                system="""You are a financial analyst expert specialized in Vietnamese real estate companies. 
                You understand both English and Vietnamese financial terminology. 
                You are meticulous about extracting accurate data from financial statements.
                Always return valid JSON only, with no additional text.""",
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse the response
            response_text = response.content[0].text
            
            # Clean up response if needed (remove any markdown formatting)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            # Parse JSON
            result = json.loads(response_text)
            
            # Clean up None values in numeric fields for financial statements
            if 'projects_in_inventory' in result:
                for project in result.get('projects_in_inventory', []):
                    # Ensure numeric fields are not None
                    if project.get('book_value_vnd') is None:
                        project['book_value_vnd'] = 0
                    if project.get('total_units') is None:
                        project['total_units'] = 0
                    if project.get('land_area_sqm') is None:
                        project['land_area_sqm'] = 0
                    if project.get('ownership_pct') is None:
                        project['ownership_pct'] = 100
            
            # Clean up joint ventures
            if 'joint_ventures' in result:
                for jv in result.get('joint_ventures', []):
                    if jv.get('book_value_vnd') is None:
                        jv['book_value_vnd'] = 0
                    if jv.get('ownership_pct') is None:
                        jv['ownership_pct'] = 50
            
            # Ensure total inventory value is not None
            if result.get('total_inventory_value') is None:
                result['total_inventory_value'] = 0
            
            # Add metadata
            result['metadata'] = {
                'company_name': company_name,
                'company_ticker': company_ticker,
                'extraction_date': pd.Timestamp.now().isoformat(),
                'model_used': 'claude-3-5-sonnet-20241022'
            }
            
            return result
            
        except json.JSONDecodeError as e:
            st.error(f"Error parsing Claude response as JSON: {str(e)}")
            return {
                "error": "Failed to parse response",
                "projects_in_inventory": [],
                "future_projects": [],
                "joint_ventures": []
            }
        except Exception as e:
            st.error(f"Error calling Claude API: {str(e)}")
            return {
                "error": str(e),
                "projects_in_inventory": [],
                "future_projects": [],
                "joint_ventures": []
            }
    
    def analyze_project_changes(self, 
                               new_projects: List[Dict],
                               existing_projects: List[Dict]) -> Dict:
        """
        Compare newly extracted projects with existing ones to identify changes
        
        Args:
            new_projects: Projects extracted from latest financial statement
            existing_projects: Projects currently in database
            
        Returns:
            Dictionary containing new, updated, and removed projects
        """
        
        comparison = {
            'new_projects': [],
            'updated_projects': [],
            'removed_projects': [],
            'unchanged_projects': []
        }
        
        # Create lookup dictionaries
        new_by_name = {p['project_name']: p for p in new_projects}
        existing_by_name = {p['project_name']: p for p in existing_projects}
        
        # Find new and updated projects
        for name, project in new_by_name.items():
            if name not in existing_by_name:
                comparison['new_projects'].append(project)
            else:
                # Check for updates
                existing = existing_by_name[name]
                changes = self._detect_changes(existing, project)
                
                if changes:
                    comparison['updated_projects'].append({
                        'project_name': name,
                        'new_data': project,
                        'old_data': existing,
                        'changes': changes
                    })
                else:
                    comparison['unchanged_projects'].append(project)
        
        # Find removed projects (in database but not in new statement)
        for name, project in existing_by_name.items():
            if name not in new_by_name:
                comparison['removed_projects'].append(project)
        
        return comparison
    
    def _detect_changes(self, old_project: Dict, new_project: Dict) -> Dict:
        """Detect specific changes between old and new project data"""
        changes = {}
        
        # Fields to compare
        compare_fields = [
            'book_value_vnd', 'stage', 'location', 'total_units',
            'land_area_sqm', 'ownership_pct'
        ]
        
        for field in compare_fields:
            old_val = old_project.get(field)
            new_val = new_project.get(field)
            
            if old_val != new_val and new_val is not None:
                changes[field] = {
                    'old': old_val,
                    'new': new_val
                }
        
        return changes
    
    def process_multiple_documents(self,
                                  pdf_files: List,
                                  company_name: str,
                                  company_ticker: str) -> Dict:
        """
        Process multiple PDF documents and combine results
        
        Args:
            pdf_files: List of uploaded PDF files
            company_name: Company name
            company_ticker: Stock ticker
            
        Returns:
            Combined extraction results from all documents
        """
        
        results = {
            'successful_extractions': [],
            'failed_extractions': [],
            'all_projects': [],
            'combined_metrics': {},
            'document_summaries': []
        }
        
        # Process each document
        for idx, pdf_file in enumerate(pdf_files):
            file_name = pdf_file.name if hasattr(pdf_file, 'name') else f"Document_{idx+1}"
            
            try:
                # Extract text from PDF
                with st.spinner(f"📄 Processing {file_name}..."):
                    document_text = self.extract_text_from_pdf(pdf_file)
                    
                    if not document_text:
                        results['failed_extractions'].append({
                            'file_name': file_name,
                            'error': 'Failed to extract text from PDF',
                            'suggestion': 'PDF might be scanned. Try OCR or manual input.'
                        })
                        continue
                    
                    # Detect document type
                    doc_type = self.detect_document_type(document_text)
                    
                    # Extract projects
                    extraction_result = self.extract_projects_from_document(
                        document_text=document_text,
                        company_name=company_name,
                        company_ticker=company_ticker,
                        document_type=doc_type
                    )
                    
                    if "error" in extraction_result:
                        results['failed_extractions'].append({
                            'file_name': file_name,
                            'error': extraction_result.get('error'),
                            'document_type': doc_type
                        })
                    else:
                        # Successful extraction
                        extraction_result['source_file'] = file_name
                        extraction_result['document_type'] = doc_type
                        results['successful_extractions'].append(extraction_result)
                        
                        # Add document summary
                        results['document_summaries'].append({
                            'file_name': file_name,
                            'document_type': doc_type,
                            'projects_found': self._count_projects_in_result(extraction_result),
                            'extraction_quality': extraction_result.get('extraction_summary', {}).get('confidence_score', 0)
                        })
                        
            except Exception as e:
                results['failed_extractions'].append({
                    'file_name': file_name,
                    'error': str(e),
                    'error_type': type(e).__name__
                })
                continue
        
        # Combine all projects from successful extractions
        results['all_projects'] = self._combine_projects_from_extractions(results['successful_extractions'])
        
        # Generate combined metrics
        results['combined_metrics'] = self._generate_combined_metrics(results['successful_extractions'])
        
        # Add summary statistics
        results['summary'] = {
            'total_documents': len(pdf_files),
            'successful_extractions': len(results['successful_extractions']),
            'failed_extractions': len(results['failed_extractions']),
            'total_unique_projects': len(results['all_projects']),
            'document_types_processed': list(set(s['document_type'] for s in results['successful_extractions']))
        }
        
        return results
    
    def _count_projects_in_result(self, extraction_result: Dict) -> int:
        """Count total projects in an extraction result"""
        count = 0
        
        # Count based on document type
        if 'projects_in_inventory' in extraction_result:
            count += len(extraction_result.get('projects_in_inventory', []))
            count += len(extraction_result.get('future_projects', []))
            count += len(extraction_result.get('joint_ventures', []))
        elif 'projects_in_pipeline' in extraction_result:
            count += len(extraction_result.get('projects_in_pipeline', []))
            count += len(extraction_result.get('future_projects', []))
        elif 'active_projects' in extraction_result:
            count += len(extraction_result.get('active_projects', []))
            count += len(extraction_result.get('pipeline_projects', []))
        
        return count
    
    def _combine_projects_from_extractions(self, extractions: List[Dict]) -> List[Dict]:
        """Combine and deduplicate projects from multiple extractions"""
        all_projects = []
        seen_projects = set()
        
        for extraction in extractions:
            doc_type = extraction.get('document_type', '')
            source_file = extraction.get('source_file', '')
            
            # Extract projects based on document type
            projects_to_add = []
            
            if doc_type == 'financial_statement':
                projects_to_add.extend(extraction.get('projects_in_inventory', []))
                projects_to_add.extend(extraction.get('future_projects', []))
                projects_to_add.extend(extraction.get('joint_ventures', []))
            elif doc_type == 'analyst_report':
                projects_to_add.extend(extraction.get('projects_in_pipeline', []))
                projects_to_add.extend(extraction.get('future_projects', []))
            elif doc_type == 'company_presentation':
                projects_to_add.extend(extraction.get('active_projects', []))
                projects_to_add.extend(extraction.get('pipeline_projects', []))
            
            # Add source information and check for duplicates
            for project in projects_to_add:
                project_name = project.get('project_name', '').lower().strip()
                
                # Simple deduplication by name
                if project_name and project_name not in seen_projects:
                    project['source_document'] = source_file
                    project['source_type'] = doc_type
                    all_projects.append(project)
                    seen_projects.add(project_name)
                elif project_name:
                    # Project already seen - update with additional info if available
                    for existing in all_projects:
                        if existing.get('project_name', '').lower().strip() == project_name:
                            # Merge additional information
                            self._merge_project_info(existing, project, source_file)
                            break
        
        return all_projects
    
    def _merge_project_info(self, existing_project: Dict, new_project: Dict, source_file: str):
        """Merge additional information from new_project into existing_project"""
        # Add source documents list
        if 'source_documents' not in existing_project:
            existing_project['source_documents'] = [existing_project.get('source_document', '')]
        if source_file not in existing_project['source_documents']:
            existing_project['source_documents'].append(source_file)
        
        # Update with non-None values
        for key, value in new_project.items():
            if value is not None and (existing_project.get(key) is None or existing_project.get(key) == 0):
                existing_project[key] = value
    
    def _generate_combined_metrics(self, extractions: List[Dict]) -> Dict:
        """Generate combined metrics from all successful extractions"""
        metrics = {
            'total_inventory_value': 0,
            'total_rnav': 0,
            'total_projects_count': 0,
            'document_types': {},
            'confidence_scores': []
        }
        
        for extraction in extractions:
            doc_type = extraction.get('document_type', '')
            
            # Count by document type
            metrics['document_types'][doc_type] = metrics['document_types'].get(doc_type, 0) + 1
            
            # Add values based on document type
            if doc_type == 'financial_statement':
                metrics['total_inventory_value'] += extraction.get('total_inventory_value', 0)
            elif doc_type == 'analyst_report':
                analyst_metrics = extraction.get('analyst_metrics', {})
                metrics['total_rnav'] += analyst_metrics.get('total_rnav', 0)
            
            # Collect confidence scores
            confidence = extraction.get('extraction_summary', {}).get('confidence_score', 0)
            if confidence:
                metrics['confidence_scores'].append(confidence)
            
            # Count projects
            metrics['total_projects_count'] += self._count_projects_in_result(extraction)
        
        # Calculate average confidence
        if metrics['confidence_scores']:
            metrics['average_confidence'] = sum(metrics['confidence_scores']) / len(metrics['confidence_scores'])
        else:
            metrics['average_confidence'] = 0
        
        return metrics
    
    def merge_claude_perplexity_results(self,
                                       claude_projects: List[Dict],
                                       perplexity_projects: List[Dict],
                                       company_name: str,
                                       company_ticker: str) -> Dict:
        """
        Use Claude AI to intelligently merge projects from Claude and Perplexity sources
        
        Args:
            claude_projects: Projects extracted from documents by Claude
            perplexity_projects: Projects discovered from web by Perplexity
            company_name: Company name
            company_ticker: Stock ticker
            
        Returns:
            Merged and deduplicated project list with confidence scores
        """
        
        # Clean datetime objects from projects before JSON serialization
        def clean_for_json(obj):
            """Convert datetime and other non-serializable objects to strings"""
            if isinstance(obj, dict):
                return {k: clean_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_for_json(item) for item in obj]
            elif isinstance(obj, (pd.Timestamp, datetime)):
                return obj.isoformat() if hasattr(obj, 'isoformat') else str(obj)
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif pd.isna(obj):
                return None
            else:
                return obj
        
        # Clean the projects for JSON serialization
        claude_projects_clean = clean_for_json(claude_projects[:50])
        perplexity_projects_clean = clean_for_json(perplexity_projects[:50])
        
        # Prepare data for Claude to analyze
        merge_prompt = f"""
        You are tasked with merging and deduplicating real estate project information for {company_name} ({company_ticker}) from two sources:
        
        1. CLAUDE EXTRACTED PROJECTS (from financial documents):
        {json.dumps(claude_projects_clean, indent=2)}  # Limit to first 50 for token management
        
        2. PERPLEXITY WEB RESEARCH PROJECTS:
        {json.dumps(perplexity_projects_clean, indent=2)}  # Limit to first 50 for token management
        
        MERGING RULES:
        1. Identify duplicate projects based on:
           - Similar project names (consider variations, abbreviations)
           - Same location
           - Similar specifications (units, GFA)
        
        2. When merging duplicates:
           - Prefer financial document data (Claude) for book values
           - Prefer web research (Perplexity) for market data (ASP, sales status)
           - Combine all available information
           - Track both sources
        
        3. Confidence scoring:
           - High confidence (0.9-1.0): Project appears in both sources with matching details
           - Medium confidence (0.6-0.8): Project in one source with complete information
           - Low confidence (0.3-0.5): Project with limited information
        
        Return a JSON object with:
        {{
            "merged_projects": [
                {{
                    "project_name": "Standardized project name",
                    "location": "Full location",
                    "total_units": number,
                    "book_value_vnd": number (from Claude if available),
                    "market_value_vnd": number (from Perplexity if available),
                    "stage": "development stage",
                    "data_sources": ["claude", "perplexity"] or one of them,
                    "confidence_score": 0.0-1.0,
                    "merge_notes": "Any important notes about the merge"
                }}
            ],
            "merge_summary": {{
                "total_unique_projects": number,
                "high_confidence_projects": number,
                "medium_confidence_projects": number,
                "low_confidence_projects": number,
                "projects_only_in_claude": number,
                "projects_only_in_perplexity": number,
                "projects_in_both": number
            }}
        }}
        
        Be intelligent about name matching - "Gem Riverside" and "Dự án Gem Riverside Q2" are the same project.
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0,
                system="""You are an expert at merging and deduplicating real estate project data from multiple sources.
                You understand project naming variations, Vietnamese and English names, and can identify duplicate projects
                even when they have slightly different names or specifications. Always return valid JSON only.""",
                messages=[{"role": "user", "content": merge_prompt}]
            )
            
            # Parse response
            response_text = response.content[0].text
            
            # Clean up response if needed
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            # Parse JSON
            result = json.loads(response_text)
            
            # Add metadata
            result['metadata'] = {
                'company_name': company_name,
                'company_ticker': company_ticker,
                'merge_date': pd.Timestamp.now().isoformat(),
                'claude_projects_count': len(claude_projects),
                'perplexity_projects_count': len(perplexity_projects)
            }
            
            return result
            
        except Exception as e:
            st.error(f"Error in AI-powered merge: {str(e)}")
            # Fallback to simple merge
            return self._simple_merge_fallback(claude_projects, perplexity_projects)
    
    def _simple_merge_fallback(self, claude_projects: List[Dict], perplexity_projects: List[Dict]) -> Dict:
        """Simple fallback merge if AI merge fails"""
        all_projects = []
        seen_names = set()
        
        # Add Claude projects first (higher priority)
        for project in claude_projects:
            name = project.get('project_name', '').lower().strip()
            if name:
                project['data_sources'] = ['claude']
                project['confidence_score'] = 0.8
                all_projects.append(project)
                seen_names.add(name)
        
        # Add Perplexity projects if not duplicates
        for project in perplexity_projects:
            name = project.get('project_name', '').lower().strip()
            if name and name not in seen_names:
                project['data_sources'] = ['perplexity']
                project['confidence_score'] = 0.6
                all_projects.append(project)
        
        return {
            'merged_projects': all_projects,
            'merge_summary': {
                'total_unique_projects': len(all_projects),
                'projects_only_in_claude': len(claude_projects),
                'projects_only_in_perplexity': len([p for p in all_projects if 'perplexity' in p.get('data_sources', [])])
            }
        }
    
    def compare_with_database_projects(self,
                                      merged_projects: List[Dict],
                                      existing_projects: List[Dict]) -> Dict:
        """
        Compare merged results with existing database projects to identify new discoveries
        
        Args:
            merged_projects: Merged projects from Claude and Perplexity
            existing_projects: Projects currently in database
            
        Returns:
            Comparison results showing new, updated, and unchanged projects
        """
        
        # Clean datetime objects before JSON serialization
        def clean_for_json(obj):
            """Convert datetime and other non-serializable objects to strings"""
            if isinstance(obj, dict):
                return {k: clean_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_for_json(item) for item in obj]
            elif isinstance(obj, (pd.Timestamp, datetime)):
                return obj.isoformat() if hasattr(obj, 'isoformat') else str(obj)
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif pd.isna(obj):
                return None
            else:
                return obj
        
        merged_projects_clean = clean_for_json(merged_projects[:50])
        existing_projects_clean = clean_for_json(existing_projects[:50])
        
        comparison_prompt = f"""
        Compare the newly discovered projects with existing database projects to identify:
        1. NEW projects (not in database)
        2. UPDATED projects (exist but with new information)
        3. UNCHANGED projects (no new information)
        
        NEWLY DISCOVERED PROJECTS (from Claude + Perplexity):
        {json.dumps(merged_projects_clean, indent=2)}
        
        EXISTING DATABASE PROJECTS:
        {json.dumps(existing_projects_clean, indent=2)}
        
        COMPARISON RULES:
        - Projects are the same if they have similar names and same location
        - Mark as NEW if project doesn't exist in database
        - Mark as UPDATED if project exists but has new/different information
        - Mark as UNCHANGED if all information matches
        
        Return JSON:
        {{
            "new_projects": [
                {{
                    "project_name": "name",
                    "location": "location",
                    "key_details": "what makes this significant",
                    "confidence": 0.0-1.0
                }}
            ],
            "updated_projects": [
                {{
                    "project_name": "name",
                    "updates": ["list of what's new/changed"],
                    "old_value": "previous data",
                    "new_value": "updated data"
                }}
            ],
            "unchanged_projects": ["list of project names"],
            "comparison_summary": {{
                "total_compared": number,
                "new_discoveries": number,
                "updates_found": number,
                "unchanged": number,
                "significance_notes": "Key findings from comparison"
            }}
        }}
        """
        
        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                temperature=0,
                system="""You are an expert at comparing real estate project databases to identify new discoveries
                and updates. You can match projects even with name variations. Always return valid JSON only.""",
                messages=[{"role": "user", "content": comparison_prompt}]
            )
            
            # Parse response
            response_text = response.content[0].text
            
            # Clean up response if needed
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            # Parse JSON
            result = json.loads(response_text)
            
            # Add timestamp
            result['comparison_date'] = pd.Timestamp.now().isoformat()
            
            return result
            
        except Exception as e:
            st.error(f"Error in database comparison: {str(e)}")
            # Simple fallback comparison
            return self._simple_comparison_fallback(merged_projects, existing_projects)
    
    def _simple_comparison_fallback(self, merged_projects: List[Dict], existing_projects: List[Dict]) -> Dict:
        """Simple fallback comparison if AI comparison fails"""
        existing_names = set(p.get('project_name', '').lower().strip() for p in existing_projects)
        
        new_projects = []
        for project in merged_projects:
            name = project.get('project_name', '').lower().strip()
            if name and name not in existing_names:
                new_projects.append({
                    'project_name': project.get('project_name'),
                    'location': project.get('location'),
                    'confidence': 0.7
                })
        
        return {
            'new_projects': new_projects,
            'updated_projects': [],
            'unchanged_projects': [],
            'comparison_summary': {
                'total_compared': len(merged_projects),
                'new_discoveries': len(new_projects),
                'updates_found': 0,
                'unchanged': len(merged_projects) - len(new_projects)
            }
        }
    
    def generate_extraction_summary(self, extraction_result: Dict) -> str:
        """Generate a human-readable summary of the extraction results"""
        
        # Check document type based on result structure
        is_analyst_report = 'projects_in_pipeline' in extraction_result
        
        if is_analyst_report:
            # Handle analyst report format
            projects = extraction_result.get('projects_in_pipeline', [])
            future = extraction_result.get('future_projects', [])
            metrics = extraction_result.get('analyst_metrics', {})
            
            summary = f"""
            📊 **Analyst Report Extraction Summary**
            
            **Projects Found:**
            - In Pipeline: {len(projects)} projects
            - Future Projects: {len(future)} projects
            
            **Analyst Metrics:**
            - Total RNAV: {(metrics.get('total_rnav') or 0) / 1e12:.1f}T VND
            - RNAV per share: {metrics.get('rnav_per_share', 0):,.0f} VND
            - Target Price: {metrics.get('target_price', 0):,.0f} VND
            - Discount to RNAV: {metrics.get('implied_discount_to_rnav', 0):.0%}
            
            **Report Details:**
            - Report Date: {extraction_result.get('extraction_summary', {}).get('report_date', 'Not specified')}
            - Analyst Firm: {extraction_result.get('extraction_summary', {}).get('analyst_firm', 'Not identified')}
            - Confidence Score: {extraction_result.get('extraction_summary', {}).get('confidence_score', 0):.0%}
            
            **Top Projects by NAV:**
            """
            
            # Sort projects by NAV value
            valued_projects = [p for p in projects if p.get('nav_value_vnd')]
            valued_projects.sort(key=lambda x: x['nav_value_vnd'], reverse=True)
            
            for i, project in enumerate(valued_projects[:5]):
                value_t = (project.get('nav_value_vnd') or 0) / 1e12
                sales_pct = project.get('sales_status_pct', 0)
                summary += f"\n{i+1}. {project['project_name']}: {value_t:.1f}T VND (Sales: {sales_pct}%)"
        
        else:
            # Handle financial statement format
            projects = extraction_result.get('projects_in_inventory', [])
            future = extraction_result.get('future_projects', [])
            jvs = extraction_result.get('joint_ventures', [])
            
            summary = f"""
            📊 **Financial Statement Extraction Summary**
            
            **Projects Found:**
            - In Inventory: {len(projects)} projects
            - Future Pipeline: {len(future)} projects
            - Joint Ventures: {len(jvs)} projects
            
            **Total Inventory Value:** {(extraction_result.get('total_inventory_value') or 0) / 1e12:.1f}T VND
            
            **Data Quality:**
            - Confidence Score: {extraction_result.get('extraction_summary', {}).get('confidence_score', 0):.0%}
            - Projects with Values: {extraction_result.get('extraction_summary', {}).get('projects_with_values', 0)}
            
            **Top Projects by Value:**
            """
            
            # Sort projects by value
            valued_projects = [p for p in projects if p.get('book_value_vnd')]
            valued_projects.sort(key=lambda x: x['book_value_vnd'], reverse=True)
            
            for i, project in enumerate(valued_projects[:5]):
                value_t = (project.get('book_value_vnd') or 0) / 1e12
                summary += f"\n{i+1}. {project['project_name']}: {value_t:.1f}T VND"
        
        return summary