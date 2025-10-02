"""
Quarterly Earnings Tab - Analyzes quarterly earnings documents and generates comprehensive reports
"""

import streamlit as st
import pandas as pd
import os
from datetime import datetime
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from utils.quarterly_earnings_manager import QuarterlyEarningsManager
from utils.mongodb_utils import load_real_estate_companies_from_mongo_db


class QuarterlyEarningsTab:
    """Tab for quarterly earnings analysis"""
    
    def __init__(self, parent=None):
        """Initialize the quarterly earnings tab"""
        self.parent = parent
        self.manager = self._get_manager()
        self._initialize_session_state()
    
    @staticmethod
    @st.cache_resource
    def _get_manager():
        """Initialize earnings manager (cached)"""
        return QuarterlyEarningsManager(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            base_data_path="data"
        )
    
    def _initialize_session_state(self):
        """Initialize session state for this tab"""
        if 'qe_processed_data' not in st.session_state:
            st.session_state.qe_processed_data = None
        if 'qe_current_doc_id' not in st.session_state:
            st.session_state.qe_current_doc_id = None
        if 'qe_upload_ticker' not in st.session_state:
            st.session_state.qe_upload_ticker = None
        if 'qe_upload_company' not in st.session_state:
            st.session_state.qe_upload_company = None
        if 'qe_upload_quarter' not in st.session_state:
            st.session_state.qe_upload_quarter = None
        if 'qe_upload_year' not in st.session_state:
            st.session_state.qe_upload_year = None
        if 'qe_upload_quarter_num' not in st.session_state:
            st.session_state.qe_upload_quarter_num = None
    
    def render(self):
        """Render the quarterly earnings analysis interface"""
        
        # Header
        st.markdown("""
        Upload quarterly earnings documents (presentations, analyst reports, or commentary) 
        and generate comprehensive AI-powered analysis reports.
        """)
        
        # Create tabs
        tab_upload, tab_documents, tab_analysis, tab_summary = st.tabs([
            "📤 Upload Documents",
            "📁 Document Management",
            "🤖 AI Analysis",
            "📋 Summary Reports"
        ])
        
        with tab_upload:
            self._render_upload_tab()
        
        with tab_documents:
            self._render_documents_tab()
        
        with tab_analysis:
            self._render_analysis_tab()
        
        with tab_summary:
            self._render_summary_tab()
    
    def _render_upload_tab(self):
        """Render the upload documents tab"""
        st.header("Upload Quarterly Earnings Document")
        
        # Get company from sidebar selection
        # Check both 'selected_company' (used by sidebar) and 'selected_ticker' (legacy)
        ticker_only = st.session_state.get('selected_company') or st.session_state.get('selected_ticker')
        
        if not ticker_only:
            st.warning("⚠️ Please select a company from the sidebar first.")
            st.info("👈 Use the sidebar to select a company before uploading quarterly earnings documents.")
            return
        
        company_name = st.session_state.get('selected_company_name', ticker_only)
        
        # Display selected company
        st.info(f"📊 **Selected Company:** {company_name} ({ticker_only})")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Quarter selection
            current_year = datetime.now().year
            years = list(range(current_year - 2, current_year + 2))
            
            col_q, col_y = st.columns(2)
            with col_q:
                quarter_num = st.selectbox("Quarter", options=[1, 2, 3, 4], key="qe_upload_quarter_num_widget")
            with col_y:
                year = st.selectbox("Year", options=years, index=years.index(current_year), key="qe_upload_year_widget")
            
            quarter = f"{quarter_num}Q{str(year)[2:]}"  # e.g., "2Q25"
        
        with col2:
            # Document type selection
            document_type = st.selectbox(
                "Document Type",
                options=[
                    "earnings_presentation",
                    "sellside_report",
                    "buyside_commentary",
                    "financial_data"
                ],
                format_func=lambda x: {
                    "earnings_presentation": "📊 Company Earnings Presentation",
                    "sellside_report": "📈 Sell-Side Research Report",
                    "buyside_commentary": "💼 Buy-Side Commentary",
                    "financial_data": "🔢 Financial Data (Automated)"
                }.get(x, x),
                help="Select the type of document you're uploading or data to process",
                key="qe_upload_doc_type"
            )
            
            # Analyst firm (for sell-side reports)
            analyst_firm = None
            if document_type == "sellside_report":
                analyst_firm = st.text_input(
                    "Analyst Firm Name",
                    placeholder="e.g., VCBS, SSI, Viet Capital",
                    help="Name of the research firm",
                    key="qe_upload_analyst_firm"
                )
        
        # Financial data: Automated extraction (no upload)
        if document_type == "financial_data":
            st.markdown("---")
            st.subheader("🔢 Automated Financial Data Extraction")
            st.info("""
            📊 **Automatic extraction from internal database (FA_processed.parquet)**
            
            This will extract:
            - Complete financial statements for **{quarter}** (current quarter)
            - Comparison data for **QoQ** and **YoY** analysis
            - All 43 financial metrics (Income Statement, Balance Sheet, Cash Flow)
            - Pre-calculated percentage changes
            
            ⚠️ **Note:** If the selected quarter is not available in the database, 
            you will see a warning and the process will not continue.
            """.format(quarter=quarter))
            uploaded_file = None
            buyside_text = None
            
        else:
            # File upload OR text paste for all document types (earnings, sell-side, buy-side)
            st.markdown("---")
            
            # Input method selection
            input_method = st.radio(
                "Input Method",
                options=["Upload File", "Paste Text"],
                horizontal=True,
                key="qe_input_method",
                help="Choose to upload a file or paste the document text directly"
            )
            
            if input_method == "Upload File":
                uploaded_file = st.file_uploader(
                    "Upload Document",
                    type=['pdf', 'xlsx', 'xls', 'docx', 'txt', 'md'],
                    help="Supported formats: PDF, Excel, Word, Text",
                    key="qe_upload_file"
                )
                buyside_text = None
            else:  # Paste Text
                doc_type_labels = {
                    'earnings_presentation': 'Earnings Presentation',
                    'sellside_report': 'Sell-Side Report',
                    'buyside_commentary': 'Buy-Side Commentary'
                }
                doc_type_label = doc_type_labels.get(document_type, 'Document')
                st.subheader(f"📋 Paste {doc_type_label} Text")
                
                # Customize instructions based on document type
                if document_type == "buyside_commentary":
                    st.markdown("""
                    Enter your buy-side analysis, investment thesis, or key observations.  
                    Include any valuation analysis, catalysts, risks, or key takeaways.
                    """)
                    placeholder_text = """Example:
• Valuation: RNAV at VND 45,000/share implies 35% discount to current price
• Key catalyst: Expected VHM02 presales acceleration in Q3-Q4
• Risk: Potential margin pressure from increased land costs
• Investment view: Accumulate on dips below VND 30,000

Add your bullet points, valuation analysis, and key observations here..."""
                    text_height = 400
                elif document_type == "earnings_presentation":
                    st.markdown("""
                    Paste the full text content from the earnings presentation. You can copy from:
                    - PDF (using your PDF reader's copy function)
                    - PowerPoint/Keynote presentations
                    - Word documents
                    - Web pages or investor relations sites
                    """)
                    placeholder_text = "Paste the full earnings presentation text here...\n\nInclude all slides, financial data, commentary, guidance, and Q&A sections."
                    text_height = 500
                else:  # sellside_report
                    st.markdown("""
                    Paste the full text content from the sell-side research report. You can copy from:
                    - PDF research reports
                    - Bloomberg/FactSet reports
                    - Email reports
                    - Web-based research platforms
                    """)
                    placeholder_text = "Paste the full sell-side report text here...\n\nInclude analyst views, forecasts, financial models, ratings, target prices, and recommendations."
                    text_height = 500
                
                buyside_text = st.text_area(
                    "Document Text",
                    height=text_height,
                    placeholder=placeholder_text,
                    help="Paste the complete document text here",
                    key="qe_document_text_input"
                )
                uploaded_file = None
        
        # Upload and process button
        # Show button if: file is uploaded OR text is entered (any document type) OR financial_data selected
        has_input = (uploaded_file or 
                     (buyside_text and buyside_text.strip()) or
                     document_type == "financial_data")
        
        if has_input:
            if uploaded_file:
                st.info(f"📄 File selected: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")
            elif buyside_text:
                word_count = len(buyside_text.strip().split())
                if document_type == "buyside_commentary":
                    st.info(f"💼 Buy-side commentary: **{word_count} words** entered")
                elif document_type == "earnings_presentation":
                    st.info(f"📊 Earnings presentation text: **{word_count} words** entered")
                elif document_type == "sellside_report":
                    st.info(f"📈 Sell-side report text: **{word_count} words** entered")
            elif document_type == "financial_data":
                st.info(f"🔢 Ready to extract financial data for **{ticker_only} {quarter}**")
            
            # Button label based on document type
            if document_type == "financial_data":
                button_label = "🔢 Process Financial Data"
            elif document_type == "buyside_commentary":
                button_label = "🚀 Process Buy-Side Commentary"
            else:
                button_label = "🚀 Upload and Analyze Document"
            
            if st.button(button_label, type="primary", use_container_width=True, key="qe_upload_analyze_btn"):
                # Store metadata in session state
                st.session_state.qe_upload_ticker = ticker_only
                st.session_state.qe_upload_company = company_name
                st.session_state.qe_upload_quarter = quarter
                st.session_state.qe_upload_year = year
                st.session_state.qe_upload_quarter_num = quarter_num
                
                # Process based on document type
                if document_type == "financial_data":
                    # Special handling for automated financial data extraction
                    result = self.manager._process_financial_data(
                        ticker=ticker_only,
                        company_name=company_name,
                        quarter=quarter,
                        year=year,
                        quarter_num=quarter_num
                    )
                else:
                    # Process document upload or text input (buy-side, earnings, sell-side)
                    result = self.manager.process_document(
                        uploaded_file=uploaded_file,
                        ticker=ticker_only,
                        company_name=company_name,
                        quarter=quarter,
                        year=year,
                        quarter_num=quarter_num,
                        document_type=document_type,
                        analyst_firm=analyst_firm,
                        buyside_text=buyside_text  # Pass text input for all document types
                    )
                
                if result.get('success'):
                    success_msg = {
                        'financial_data': 'Financial data extracted successfully!',
                        'buyside_commentary': 'Buy-side commentary processed successfully!',
                        'earnings_presentation': 'Management presentation processed successfully!',
                        'sellside_report': 'Sell-side report processed successfully!'
                    }.get(document_type, 'Document processed successfully!')
                    
                    st.success(f"✅ {success_msg}")
                    
                    # Store in session state for review
                    st.session_state.qe_processed_data = result['extracted_data']
                    st.session_state.qe_current_doc_id = result['document_id']
                    
                    st.info("👉 Please review the extracted data in the **AI Analysis** tab")
                    st.rerun()
                else:
                    st.error(f"❌ Processing failed: {result.get('error', 'Unknown error')}")
    
    def _render_documents_tab(self):
        """Render the document management tab"""
        st.header("Document Management")
        
        # Get company from sidebar selection
        # Check both 'selected_company' (used by sidebar) and 'selected_ticker' (legacy)
        selected_ticker = st.session_state.get('selected_company') or st.session_state.get('selected_ticker')
        
        if not selected_ticker:
            st.warning("⚠️ Please select a company from the sidebar first.")
            st.info("👈 Use the sidebar to select a company before viewing documents.")
            return
        
        company_name = st.session_state.get('selected_company_name', selected_ticker)
        
        # Display selected company
        st.info(f"📊 **Selected Company:** {company_name} ({selected_ticker})")
        
        # Quarter selector
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # Get available quarters for this company
            available_quarters = self.manager.get_company_quarters(selected_ticker)
            if available_quarters:
                selected_quarter = st.selectbox(
                    "Quarter",
                    options=available_quarters,
                    key="qe_doc_mgmt_quarter"
                )
            else:
                st.info("No quarters available")
                selected_quarter = None
        
        with col2:
            if st.button("🔄 Refresh", use_container_width=True, key="qe_doc_mgmt_refresh"):
                st.rerun()
        
        # Display documents
        if selected_ticker and selected_quarter:
            documents = self.manager.get_quarter_documents(selected_ticker, selected_quarter)
            
            if documents:
                st.success(f"Found **{len(documents)}** document(s) for {selected_ticker} - {selected_quarter}")
                
                # Create DataFrame
                doc_data = []
                for doc in documents:
                    doc_data.append({
                        "File Name": doc.get('file_name', 'N/A'),
                        "Type": doc.get('document_type', 'N/A').replace('_', ' ').title(),
                        "Upload Date": doc.get('upload_date', datetime.now()).strftime('%Y-%m-%d %H:%M'),
                        "Status": doc.get('processing_status', 'Unknown'),
                        "Size (MB)": doc.get('file_size_mb', 0),
                        "Source": doc.get('source', 'N/A').title(),
                        "Analyst Firm": doc.get('analyst_firm', '-') if doc.get('analyst_firm') else '-',
                        "Document ID": doc.get('_id')
                    })
                
                df_docs = pd.DataFrame(doc_data)
                
                # Display table
                st.dataframe(
                    df_docs.drop(columns=['Document ID']),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Document actions
                st.markdown("### Document Actions")
                selected_doc_idx = st.selectbox(
                    "Select document for actions",
                    options=range(len(documents)),
                    format_func=lambda i: doc_data[i]['File Name'],
                    key="qe_doc_action_selector"
                )
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("🔍 View Details", use_container_width=True, key="qe_doc_view_btn"):
                        selected_doc = documents[selected_doc_idx]
                        st.json(selected_doc)
                
                with col2:
                    if st.button("🔄 Re-analyze", use_container_width=True, key="qe_doc_reanalyze_btn"):
                        st.info("Re-analysis feature coming soon")
                
                with col3:
                    if st.button("🗑️ Delete", use_container_width=True, type="secondary", key="qe_doc_delete_btn"):
                        doc_id = doc_data[selected_doc_idx]['Document ID']
                        if self.manager.delete_document(doc_id):
                            st.rerun()
            else:
                st.info(f"No documents found for {selected_ticker} - {selected_quarter}")
        else:
            st.info("Select a company and quarter to view documents")
    
    def _render_analysis_tab(self):
        """Render the AI analysis review tab"""
        st.header("AI-Extracted Data Review")
        
        if st.session_state.qe_processed_data:
            extracted_data = st.session_state.qe_processed_data
            doc_id = st.session_state.qe_current_doc_id
            
            st.success("✅ Data extracted successfully! Please review below:")
            
            # Display extracted sections in expandable format
            for section_name, section_data in extracted_data.items():
                if section_name == 'extraction_metadata':
                    continue
                
                with st.expander(f"📊 {section_name.replace('_', ' ').title()}", expanded=True):
                    if isinstance(section_data, dict):
                        st.json(section_data)
                    elif isinstance(section_data, list):
                        if section_data:
                            for idx, item in enumerate(section_data):
                                st.markdown(f"**Item {idx + 1}:**")
                                st.json(item)
                        else:
                            st.info("No data in this section")
                    else:
                        st.write(section_data)
            
            # Edit option (simplified - JSON editor)
            st.markdown("---")
            st.markdown("### Edit Extracted Data (Optional)")
            
            with st.expander("🔧 Advanced: Edit JSON"):
                edited_json = st.text_area(
                    "Edit the extracted data as JSON",
                    value=str(extracted_data),
                    height=300,
                    key="qe_analysis_json_editor"
                )
            
            # Save to MongoDB
            st.markdown("---")
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.info("💡 Review the data above. If it looks good, click Save to store in MongoDB.")
            
            with col2:
                if st.button("💾 Save to MongoDB", type="primary", use_container_width=True, key="qe_analysis_save_btn"):
                    # Get metadata from session state
                    ticker = st.session_state.qe_upload_ticker
                    company_name = st.session_state.qe_upload_company
                    quarter = st.session_state.qe_upload_quarter
                    year = st.session_state.qe_upload_year
                    quarter_num = st.session_state.qe_upload_quarter_num
                    
                    success = self.manager.save_extracted_data_to_mongodb(
                        extracted_data=extracted_data,
                        document_id=doc_id,
                        ticker=ticker,
                        company_name=company_name,
                        quarter=quarter,
                        year=year,
                        quarter_num=quarter_num
                    )
                    
                    if success:
                        st.session_state.qe_processed_data = None
                        st.session_state.qe_current_doc_id = None
                        st.rerun()
        else:
            st.info("👈 Upload and analyze a document first to see extracted data here")
    
    def _render_summary_tab(self):
        """Render the summary report generation tab"""
        st.header("Generate Quarterly Summary Report")
        
        # Get company from sidebar selection
        # Check both 'selected_company' (used by sidebar) and 'selected_ticker' (legacy)
        summary_ticker = st.session_state.get('selected_company') or st.session_state.get('selected_ticker')
        
        if not summary_ticker:
            st.warning("⚠️ Please select a company from the sidebar first.")
            st.info("👈 Use the sidebar to select a company before generating reports.")
            return
        
        summary_company_name = st.session_state.get('selected_company_name', summary_ticker)
        
        # Display selected company
        st.info(f"📊 **Selected Company:** {summary_company_name} ({summary_ticker})")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # Quarter selection
            available_quarters = self.manager.get_company_quarters(summary_ticker)
            if available_quarters:
                summary_quarter = st.selectbox(
                    "Quarter",
                    options=available_quarters,
                    key="qe_summary_quarter"
                )
                # Extract year from quarter (e.g., "2Q25" -> 2025)
                quarter_year = 2000 + int(summary_quarter[-2:])
            else:
                st.warning("No data available for this company")
                summary_quarter = None
                quarter_year = datetime.now().year
        
        # Generate button
        col1, col2 = st.columns(2)
        with col1:
            generate_btn = st.button(
                "📝 Generate Summary Report",
                type="primary",
                use_container_width=True,
                disabled=not summary_quarter,
                key="qe_summary_generate_btn"
            )
        
        with col2:
            force_regenerate = st.checkbox(
                "Force regenerate (ignore cache)",
                help="Check this to regenerate even if a cached report exists",
                key="qe_summary_force_regen"
            )
        
        # Generate summary
        if generate_btn and summary_quarter:
            summary = self.manager.generate_quarterly_summary(
                ticker=summary_ticker,
                company_name=summary_company_name,
                quarter=summary_quarter,
                year=quarter_year,
                force_regenerate=force_regenerate
            )
            
            if "error" not in summary:
                st.success("✅ Summary report generated successfully!")
                
                # Display summary
                st.markdown("---")
                st.markdown("## 📋 Quarterly Earnings Summary")
                
                st.markdown(summary.get('summary_text', 'No summary text available'))
                
                # Download buttons
                st.markdown("---")
                st.markdown("### Download Report")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Download as TXT
                    if 'file_paths' in summary and 'txt' in summary['file_paths']:
                        file_path = summary['file_paths']['txt']
                        if os.path.exists(file_path):
                            with open(file_path, 'r', encoding='utf-8') as f:
                                txt_content = f.read()
                            
                            st.download_button(
                                label="📄 Download as TXT",
                                data=txt_content,
                                file_name=f"earnings_summary_{summary_ticker}_{summary_quarter}.txt",
                                mime="text/plain",
                                use_container_width=True,
                                key="qe_summary_download_txt"
                            )
                
                with col2:
                    # Download as markdown
                    st.download_button(
                        label="📝 Download as Markdown",
                        data=summary.get('summary_text', ''),
                        file_name=f"earnings_summary_{summary_ticker}_{summary_quarter}.md",
                        mime="text/markdown",
                        use_container_width=True,
                        key="qe_summary_download_md"
                    )
            else:
                st.error(f"Failed to generate summary: {summary.get('error')}")
