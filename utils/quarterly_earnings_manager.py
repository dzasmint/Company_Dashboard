"""
Quarterly Earnings Manager - Main orchestrator for quarterly earnings analysis workflow
"""

import os
import json
import shutil
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import streamlit as st
import pandas as pd

from .quarterly_earnings_extractor import QuarterlyEarningsExtractor
from .quarterly_report_generator import QuarterlyReportGenerator
from .mongodb_utils import MongoDBHelper
from .chatGPT_project_extractor import ChatGPTProjectExtractor
from .financial_data_extractor import FinancialDataExtractor
from .supplementary_data_parser import SupplementaryDataParser
from .forecast_data_extractor import ForecastDataExtractor


class QuarterlyEarningsManager:
    """Manages the complete workflow for quarterly earnings analysis"""
    
    def __init__(self, 
                 openai_api_key: Optional[str] = None,
                 base_data_path: str = "data"):
        """
        Initialize the quarterly earnings manager
        
        Args:
            openai_api_key: OpenAI API key
            base_data_path: Base path for data storage
        """
        self.extractor = QuarterlyEarningsExtractor(api_key=openai_api_key)
        self.report_generator = QuarterlyReportGenerator(api_key=openai_api_key)
        self.mongo_helper = MongoDBHelper()
        self.pdf_extractor = ChatGPTProjectExtractor(api_key=openai_api_key)
        self.financial_extractor = FinancialDataExtractor()
        self.supplementary_parser = SupplementaryDataParser()
        self.forecast_extractor = ForecastDataExtractor()
        self.base_data_path = base_data_path
    
    def save_uploaded_file(self,
                          uploaded_file,
                          ticker: str,
                          quarter: str,
                          document_type: str) -> str:
        """
        Save uploaded file to organized folder structure
        
        Args:
            uploaded_file: Streamlit uploaded file object
            ticker: Stock ticker
            quarter: Quarter (e.g., "2Q25")
            document_type: Type of document
            
        Returns:
            File path where document was saved
        """
        
        # Create directory structure: data/{TICKER}/{QUARTER}/RawReports/
        folder_path = os.path.join(
            self.base_data_path,
            ticker.upper(),
            quarter.upper(),
            "RawReports"
        )
        
        Path(folder_path).mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp to avoid duplicates
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = uploaded_file.name.split('.')[-1]
        filename = f"{document_type}_{ticker}_{quarter}_{timestamp}.{file_extension}"
        
        file_path = os.path.join(folder_path, filename)
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        return file_path
    
    def extract_text_from_file(self, 
                               file_path: str,
                               file_type: str) -> str:
        """
        Extract text from uploaded file
        
        Args:
            file_path: Path to the file
            file_type: File extension (pdf, xlsx, docx, txt)
            
        Returns:
            Extracted text
        """
        
        try:
            if file_type.lower() == 'pdf':
                # Use existing PDF extractor
                with open(file_path, 'rb') as f:
                    text = self.pdf_extractor.extract_text_from_pdf(f)
                return text
            
            elif file_type.lower() in ['xlsx', 'xls']:
                # Use existing Excel extractor
                with open(file_path, 'rb') as f:
                    text = self.pdf_extractor.extract_text_from_excel(f)
                return text
            
            elif file_type.lower() in ['txt', 'md']:
                # Plain text files
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            
            elif file_type.lower() in ['docx', 'doc']:
                # Word documents
                try:
                    import docx
                    doc = docx.Document(file_path)
                    text = '\n'.join([para.text for para in doc.paragraphs])
                    return text
                except ImportError:
                    st.error("python-docx library not installed. Please run: pip install python-docx")
                    return None
            
            else:
                st.warning(f"Unsupported file type: {file_type}. Attempting as text file.")
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
        
        except Exception as e:
            st.error(f"Error extracting text from file: {str(e)}")
            return None
    
    def process_document(self,
                        uploaded_file,
                        ticker: str,
                        company_name: str,
                        quarter: str,
                        year: int,
                        quarter_num: int,
                        document_type: str,
                        analyst_firm: Optional[str] = None,
                        buyside_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Complete workflow: save file, extract text, analyze with AI, save to MongoDB
        
        Args:
            uploaded_file: Streamlit uploaded file (None for text-based input)
            ticker: Stock ticker
            company_name: Company name
            quarter: Quarter (e.g., "2Q25")
            year: Year
            quarter_num: Quarter number (1-4)
            document_type: Type of document
            analyst_firm: Analyst firm name (optional, for sell-side)
            buyside_text: Text input for buy-side commentary, earnings presentation, or sell-side report (optional)
            
        Returns:
            Dictionary with processing results
        """
        
        # Handle text input (no file upload) - for buy-side, earnings presentations, or sell-side reports
        if buyside_text and not uploaded_file:
            if document_type == "buyside_commentary":
                return self._process_buyside_commentary(
                    buyside_text=buyside_text,
                    ticker=ticker,
                    company_name=company_name,
                    quarter=quarter,
                    year=year,
                    quarter_num=quarter_num
                )
            elif document_type == "earnings_presentation":
                return self._process_text_earnings_presentation(
                    document_text=buyside_text,
                    ticker=ticker,
                    company_name=company_name,
                    quarter=quarter,
                    year=year,
                    quarter_num=quarter_num
                )
            elif document_type == "sellside_report":
                return self._process_text_sellside_report(
                    document_text=buyside_text,
                    ticker=ticker,
                    company_name=company_name,
                    quarter=quarter,
                    year=year,
                    quarter_num=quarter_num,
                    analyst_firm=analyst_firm
                )
        
        # Validate that we have a file for file-based processing
        if not uploaded_file:
            return {
                "error": "No file uploaded and no text provided. Please upload a file or paste text.",
                "document_id": None,
                "file_path": None
            }
        
        # Handle supplementary data (Excel/CSV file - different processing)
        if document_type == "supplementary_data":
            # Save file first
            with st.spinner("💾 Saving file..."):
                file_path = self.save_uploaded_file(
                    uploaded_file, ticker, quarter, document_type
                )
                st.success(f"✅ File saved to: {file_path}")
            
            # Process supplementary data
            return self._process_supplementary_data(
                ticker=ticker,
                company_name=company_name,
                quarter=quarter,
                year=year,
                quarter_num=quarter_num,
                file_path=file_path
            )
        
        # Step 1: Save file (for other document types)
        with st.spinner("💾 Saving file..."):
            file_path = self.save_uploaded_file(
                uploaded_file, ticker, quarter, document_type
            )
            st.success(f"✅ File saved to: {file_path}")
        
        # Step 2: Create document metadata in MongoDB
        file_size_mb = uploaded_file.size / (1024 * 1024)
        file_extension = uploaded_file.name.split('.')[-1].lower()
        
        document_metadata = {
            "ticker": ticker.upper(),
            "company_name": company_name,
            "quarter": quarter.upper(),
            "year": year,
            "quarter_num": quarter_num,
            "document_type": document_type,
            "file_name": uploaded_file.name,
            "file_path": file_path,
            "file_size_mb": round(file_size_mb, 2),
            "upload_date": datetime.now(),
            "processing_status": "pending",
            "source": "analyst" if document_type == "sellside_report" else "management" if document_type == "earnings_presentation" else "buyside",
            "analyst_firm": analyst_firm,
            "report_date": datetime.now(),
            "metadata": {
                "file_extension": file_extension,
                "has_tables": None,
                "has_charts": None,
                "language": "en"
            }
        }
        
        doc_id = self.mongo_helper.save_quarterly_document(document_metadata)
        
        # Step 3: Extract text
        with st.spinner("📄 Extracting text from document..."):
            document_text = self.extract_text_from_file(file_path, file_extension)
            
            if not document_text:
                # Update status to error
                self.mongo_helper.update_quarterly_document_status(
                    doc_id, "error", error_message="Failed to extract text"
                )
                return {
                    "error": "Text extraction failed",
                    "document_id": doc_id,
                    "file_path": file_path
                }
        
        # Step 4: Extract data with ChatGPT
        with st.spinner("🤖 Analyzing document with ChatGPT..."):
            self.mongo_helper.update_quarterly_document_status(doc_id, "processing")
            
            extracted_data = self.extractor.extract_by_document_type(
                document_text=document_text,
                document_type=document_type,
                company_name=company_name,
                ticker=ticker,
                quarter=quarter,
                analyst_firm=analyst_firm
            )
            
            if "error" in extracted_data:
                self.mongo_helper.update_quarterly_document_status(
                    doc_id, "error", error_message=extracted_data["error"]
                )
                return {
                    "error": extracted_data["error"],
                    "document_id": doc_id,
                    "file_path": file_path
                }
        
        # Return for user review
        return {
            "success": True,
            "document_id": doc_id,
            "file_path": file_path,
            "extracted_data": extracted_data,
            "document_metadata": document_metadata
        }
    
    def _process_buyside_commentary(self,
                                    buyside_text: str,
                                    ticker: str,
                                    company_name: str,
                                    quarter: str,
                                    year: int,
                                    quarter_num: int) -> Dict[str, Any]:
        """
        Process buy-side commentary text input
        
        Args:
            buyside_text: Free-form buy-side commentary text
            ticker: Stock ticker
            company_name: Company name
            quarter: Quarter
            year: Year
            quarter_num: Quarter number
            
        Returns:
            Processing result dictionary
        """
        try:
            # Step 1: Create document metadata in MongoDB
            document_metadata = {
                "file_name": f"buyside_commentary_{ticker}_{quarter}.txt",
                "ticker": ticker.upper(),
                "company_name": company_name,
                "quarter": quarter.upper(),
                "year": year,
                "quarter_num": quarter_num,
                "document_type": "buyside_commentary",
                "upload_date": datetime.now(),
                "processing_status": "pending",
                "source": "buyside",
                "analyst_firm": None,
                "report_date": datetime.now(),
                "metadata": {
                    "file_extension": "txt",
                    "word_count": len(buyside_text.strip().split())
                }
            }
            
            doc_id = self.mongo_helper.save_quarterly_document(document_metadata)
            
            # Step 2: Extract data with ChatGPT
            with st.spinner("🤖 Analyzing buy-side commentary with ChatGPT..."):
                self.mongo_helper.update_quarterly_document_status(doc_id, "processing")
                
                extracted_data = self.extractor.extract_from_buyside_commentary(
                    commentary_text=buyside_text,
                    company_name=company_name,
                    ticker=ticker,
                    quarter=quarter
                )
                
                if "error" in extracted_data:
                    self.mongo_helper.update_quarterly_document_status(
                        doc_id, "error", error_message=extracted_data["error"]
                    )
                    return {
                        "error": extracted_data["error"],
                        "document_id": doc_id,
                        "file_path": None
                    }
            
            # Return for user review
            return {
                "success": True,
                "document_id": doc_id,
                "file_path": None,
                "extracted_data": extracted_data,
                "document_metadata": document_metadata
            }
            
        except Exception as e:
            st.error(f"Error processing buy-side commentary: {str(e)}")
            return {"error": str(e)}
    
    def _process_text_earnings_presentation(self,
                                           document_text: str,
                                           ticker: str,
                                           company_name: str,
                                           quarter: str,
                                           year: int,
                                           quarter_num: int) -> Dict[str, Any]:
        """
        Process earnings presentation from pasted text
        
        Args:
            document_text: Pasted earnings presentation text
            ticker: Stock ticker
            company_name: Company name
            quarter: Quarter
            year: Year
            quarter_num: Quarter number
            
        Returns:
            Processing result dictionary
        """
        try:
            # Step 1: Create document metadata in MongoDB
            document_metadata = {
                "file_name": f"earnings_presentation_{ticker}_{quarter}_pasted.txt",
                "ticker": ticker.upper(),
                "company_name": company_name,
                "quarter": quarter.upper(),
                "year": year,
                "quarter_num": quarter_num,
                "document_type": "earnings_presentation",
                "upload_date": datetime.now(),
                "processing_status": "pending",
                "source": "management",
                "analyst_firm": None,
                "report_date": datetime.now(),
                "metadata": {
                    "file_extension": "txt",
                    "word_count": len(document_text.strip().split()),
                    "input_method": "text_paste"
                }
            }
            
            doc_id = self.mongo_helper.save_quarterly_document(document_metadata)
            
            # Step 2: Extract data with ChatGPT
            with st.spinner("🤖 Analyzing earnings presentation with ChatGPT..."):
                self.mongo_helper.update_quarterly_document_status(doc_id, "processing")
                
                extracted_data = self.extractor.extract_from_earnings_presentation(
                    document_text=document_text,
                    company_name=company_name,
                    ticker=ticker,
                    quarter=quarter
                )
                
                if "error" in extracted_data:
                    self.mongo_helper.update_quarterly_document_status(
                        doc_id, "error", error_message=extracted_data["error"]
                    )
                    return {
                        "error": extracted_data["error"],
                        "document_id": doc_id,
                        "file_path": None
                    }
            
            # Return for user review
            return {
                "success": True,
                "document_id": doc_id,
                "file_path": None,
                "extracted_data": extracted_data,
                "document_metadata": document_metadata
            }
            
        except Exception as e:
            st.error(f"Error processing earnings presentation text: {str(e)}")
            return {"error": str(e)}
    
    def _process_text_sellside_report(self,
                                      document_text: str,
                                      ticker: str,
                                      company_name: str,
                                      quarter: str,
                                      year: int,
                                      quarter_num: int,
                                      analyst_firm: Optional[str] = None) -> Dict[str, Any]:
        """
        Process sell-side report from pasted text
        
        Args:
            document_text: Pasted sell-side report text
            ticker: Stock ticker
            company_name: Company name
            quarter: Quarter
            year: Year
            quarter_num: Quarter number
            analyst_firm: Analyst firm name (optional)
            
        Returns:
            Processing result dictionary
        """
        try:
            # Step 1: Create document metadata in MongoDB
            document_metadata = {
                "file_name": f"sellside_report_{ticker}_{quarter}_pasted.txt",
                "ticker": ticker.upper(),
                "company_name": company_name,
                "quarter": quarter.upper(),
                "year": year,
                "quarter_num": quarter_num,
                "document_type": "sellside_report",
                "upload_date": datetime.now(),
                "processing_status": "pending",
                "source": "analyst",
                "analyst_firm": analyst_firm,
                "report_date": datetime.now(),
                "metadata": {
                    "file_extension": "txt",
                    "word_count": len(document_text.strip().split()),
                    "input_method": "text_paste"
                }
            }
            
            doc_id = self.mongo_helper.save_quarterly_document(document_metadata)
            
            # Step 2: Extract data with ChatGPT
            with st.spinner("🤖 Analyzing sell-side report with ChatGPT..."):
                self.mongo_helper.update_quarterly_document_status(doc_id, "processing")
                
                extracted_data = self.extractor.extract_from_sellside_report(
                    document_text=document_text,
                    company_name=company_name,
                    ticker=ticker,
                    quarter=quarter,
                    analyst_firm=analyst_firm
                )
                
                if "error" in extracted_data:
                    self.mongo_helper.update_quarterly_document_status(
                        doc_id, "error", error_message=extracted_data["error"]
                    )
                    return {
                        "error": extracted_data["error"],
                        "document_id": doc_id,
                        "file_path": None
                    }
            
            # Return for user review
            return {
                "success": True,
                "document_id": doc_id,
                "file_path": None,
                "extracted_data": extracted_data,
                "document_metadata": document_metadata
            }
            
        except Exception as e:
            st.error(f"Error processing sell-side report text: {str(e)}")
            return {"error": str(e)}
    
    def _process_financial_data(self,
                               ticker: str,
                               company_name: str,
                               quarter: str,
                               year: int,
                               quarter_num: int) -> Dict[str, Any]:
        """
        Process automated financial data extraction from FA_processed.parquet
        
        Args:
            ticker: Stock ticker
            company_name: Company name
            quarter: Quarter (e.g., "2Q25")
            year: Year
            quarter_num: Quarter number
            
        Returns:
            Processing result dictionary
        """
        try:
            # Step 1: Validate data availability
            with st.spinner(f"🔍 Validating data availability for {ticker} {quarter}..."):
                validation = self.financial_extractor.validate_data_availability(ticker, quarter)
                
                if not validation["valid"]:
                    st.error(f"❌ Data not available: {validation['message']}")
                    return {
                        "error": validation["message"],
                        "validation": validation
                    }
                
                st.success(f"✅ Data available for {quarter} and comparison quarters")
            
            # Step 2: Create document metadata in MongoDB
            document_metadata = {
                "file_name": f"financial_data_{ticker}_{quarter}.json",
                "ticker": ticker.upper(),
                "company_name": company_name,
                "quarter": quarter.upper(),
                "year": year,
                "quarter_num": quarter_num,
                "document_type": "financial_data",
                "upload_date": datetime.now(),
                "processing_status": "pending",
                "source": "internal_database",
                "analyst_firm": None,
                "report_date": datetime.now(),
                "metadata": {
                    "file_extension": "json",
                    "data_source": "FA_processed.parquet",
                    "extraction_method": "automated"
                }
            }
            
            doc_id = self.mongo_helper.save_quarterly_document(document_metadata)
            
            # Step 3: Extract financial data
            with st.spinner("📊 Extracting financial data from database..."):
                self.mongo_helper.update_quarterly_document_status(doc_id, "processing")
                
                # Extract data in unified schema format
                extracted_data = self.financial_extractor.extract_quarterly_data(
                    ticker, quarter, company_name
                )
                
                if "error" in extracted_data:
                    self.mongo_helper.update_quarterly_document_status(
                        doc_id, "error", error_message=extracted_data["error"]
                    )
                    return {
                        "error": extracted_data["error"],
                        "document_id": doc_id,
                        "file_path": None
                    }
                
                # Get comparison quarters from the financial_data section
                qoq_q = extracted_data.get('financial_data', {}).get('qoq_comparison', {}).get('quarter', 'N/A')
                yoy_q = extracted_data.get('financial_data', {}).get('yoy_comparison', {}).get('quarter', 'N/A')
                
                st.success(f"✅ Extracted data for {quarter}, {qoq_q} (QoQ), and {yoy_q} (YoY)")
            
            # Return for user review (extracted_data is now in unified schema format)
            return {
                "success": True,
                "document_id": doc_id,
                "file_path": None,  # No file saved for automated extraction
                "extracted_data": extracted_data,  # Already in unified schema format
                "document_metadata": document_metadata
            }
            
        except Exception as e:
            st.error(f"Error processing financial data: {str(e)}")
            return {"error": str(e)}
    
    def _process_supplementary_data(self,
                                    ticker: str,
                                    company_name: str,
                                    quarter: str,
                                    year: int,
                                    quarter_num: int,
                                    file_path: str) -> Dict[str, Any]:
        """
        Process supplementary data from uploaded Excel/CSV file
        
        Args:
            ticker: Stock ticker
            company_name: Company name
            quarter: Quarter
            year: Year
            quarter_num: Quarter number
            file_path: Path to uploaded file
            
        Returns:
            Processing result dictionary
        """
        try:
            # Step 1: Create document metadata
            document_metadata = {
                "file_name": file_path.split('/')[-1],
                "ticker": ticker.upper(),
                "company_name": company_name,
                "quarter": quarter.upper(),
                "year": year,
                "quarter_num": quarter_num,
                "document_type": "supplementary_data",
                "upload_date": datetime.now(),
                "processing_status": "pending",
                "source": "user",
                "analyst_firm": None,
                "report_date": datetime.now(),
                "metadata": {
                    "file_extension": file_path.split('.')[-1],
                    "data_type": "time_series"
                }
            }
            
            doc_id = self.mongo_helper.save_quarterly_document(document_metadata)
            
            # Step 2: Parse supplementary data
            with st.spinner("📊 Parsing supplementary data..."):
                self.mongo_helper.update_quarterly_document_status(doc_id, "processing")
                
                supplementary_data = self.supplementary_parser.parse_file(file_path, quarter)
                
                if "error" in supplementary_data:
                    self.mongo_helper.update_quarterly_document_status(
                        doc_id, "error", error_message=supplementary_data["error"]
                    )
                    return {
                        "error": supplementary_data["error"],
                        "document_id": doc_id,
                        "file_path": file_path
                    }
            
            # Step 3: Structure in unified schema format
            extracted_data = {
                "company": company_name,
                "ticker": ticker.upper(),
                "period": {
                    "quarter": quarter.upper(),
                    "comparison_quarters": [],
                    "fiscal_year_half": "1H" if quarter_num <= 2 else "2H",
                    "as_of_date": None
                },
                "source": {
                    "file_name": file_path.split('/')[-1],
                    "file_type": "supplementary_data",
                    "publisher": "User Upload",
                    "publish_date": datetime.now().isoformat(),
                    "pages_covered": None,
                    "version_note": "User-provided supplementary time series data"
                },
                "currency": "VND",
                "units": "bn",
                "accounting_basis": None,
                
                # Supplementary data section
                "supplementary_data": supplementary_data,
                
                # Empty sections
                "headline": {},
                "recognition_drivers": {},
                "presales": {},
                "balance_sheet": {},
                "one_offs_and_events": [],
                "outlook_and_guidance": {},
                "management_commentary": {},
                "sell_side_commentary": {},
                "buy_side_commentary": {},
                "financial_data": {},
                "methodology": {
                    "parsing_notes": "Parsed from user-uploaded Excel/CSV file",
                    "assumptions": None,
                    "omissions": None,
                    "confidence_pct": 100
                }
            }
            
            # Return for user review
            return {
                "success": True,
                "document_id": doc_id,
                "file_path": file_path,
                "extracted_data": extracted_data,
                "document_metadata": document_metadata
            }
            
        except Exception as e:
            st.error(f"Error processing supplementary data: {str(e)}")
            return {"error": str(e)}
    
    def save_extracted_data_to_mongodb(self,
                                      extracted_data: Dict[str, Any],
                                      document_id: str,
                                      ticker: str,
                                      company_name: str,
                                      quarter: str,
                                      year: int,
                                      quarter_num: int) -> bool:
        """
        Save validated extracted data to MongoDB
        
        Args:
            extracted_data: Extracted and validated data
            document_id: Document ID in MongoDB
            ticker: Stock ticker
            company_name: Company name
            quarter: Quarter
            year: Year
            quarter_num: Quarter number
            
        Returns:
            Success status
        """
        
        try:
            # Get source type
            source_type = extracted_data.get('source', {}).get('file_type', 'unknown')
            
            # Prepare new earnings data document (each upload is separate)
            earnings_data = {
                "document_id": document_id,  # Link to source document
                "ticker": ticker.upper(),
                "company_name": company_name,
                "quarter": quarter.upper(),
                "year": year,
                "quarter_num": quarter_num,
                "upload_date": datetime.now(),
                "last_updated": datetime.now()
            }
            
            # Copy all extracted data
            for key, value in extracted_data.items():
                if key != 'extraction_metadata' and key != 'error':
                    earnings_data[key] = value
            
            # Add extraction metadata
            earnings_data['extraction_metadata'] = extracted_data.get('extraction_metadata', {})
            
            # Save to MongoDB (insert new document - each source is separate)
            data_id = self.mongo_helper.save_quarterly_earnings_data(earnings_data)
            
            st.info(f"🆕 Created separate data document for {ticker} - {quarter} ({source_type})")
            
            # Update document status
            self.mongo_helper.update_quarterly_document_status(
                document_id, "completed", extraction_id=data_id
            )
            
            # Invalidate cached summary for this quarter
            self.mongo_helper.invalidate_quarterly_summary(ticker, quarter)
            
            st.success("✅ Data saved to MongoDB successfully!")
            return True
            
        except Exception as e:
            st.error(f"Error saving data to MongoDB: {str(e)}")
            return False
    
    def generate_quarterly_summary(self,
                                   ticker: str,
                                   company_name: str,
                                   quarter: str,
                                   year: int,
                                   force_regenerate: bool = False) -> Dict[str, Any]:
        """
        Generate comprehensive quarterly summary report
        
        Args:
            ticker: Stock ticker
            company_name: Company name
            quarter: Quarter
            year: Year
            force_regenerate: Force regeneration even if cache exists
            
        Returns:
            Summary report dictionary
        """
        
        # Check for cached summary
        if not force_regenerate:
            cached_summary = self.mongo_helper.get_quarterly_summary(ticker, quarter)
            if cached_summary and cached_summary.get('cache_valid', False):
                st.info("📋 Using cached summary report")
                return cached_summary
        
        # Get all earnings data for this quarter
        with st.spinner("📊 Retrieving earnings data..."):
            all_earnings_data = self.mongo_helper.get_quarterly_earnings_data(ticker, quarter)
            
            if not all_earnings_data:
                st.warning("⚠️ No earnings data found for this quarter. Please upload and analyze documents first.")
                return {"error": "No data available"}
        
        # Auto-load forecast data from MongoDB (if available)
        with st.spinner("🎯 Loading forecast and valuation data..."):
            try:
                forecast_data_doc = self.forecast_extractor.structure_for_unified_schema(
                    ticker=ticker,
                    quarter=quarter,
                    company_name=company_name,
                    quarterly_data=all_earnings_data
                )
                
                if forecast_data_doc and "error" not in forecast_data_doc:
                    # Add forecast data to the earnings data list
                    all_earnings_data.append(forecast_data_doc)
                    st.success(f"✅ Loaded forecast for FY{forecast_data_doc.get('forecast_data', {}).get('fy_forecast', {}).get('year', '')}")
                else:
                    st.info("ℹ️ No forecast data available (optional - will generate report without it)")
            except Exception as e:
                st.warning(f"⚠️ Could not load forecast data: {str(e)} (optional - continuing without it)")
        
        # Generate summary report
        with st.spinner("🤖 Generating comprehensive summary report..."):
            summary_report = self.report_generator.generate_summary_report(
                earnings_data=all_earnings_data,
                company_name=company_name,
                ticker=ticker,
                quarter=quarter,
                year=year
            )
            
            if "error" in summary_report:
                return summary_report
        
        # Save summary to file
        summary_folder = os.path.join(
            self.base_data_path,
            ticker.upper(),
            quarter.upper(),
            "Summaries"
        )
        Path(summary_folder).mkdir(parents=True, exist_ok=True)
        
        summary_file_path = os.path.join(
            summary_folder,
            f"earnings_summary_{quarter}.txt"
        )
        
        with open(summary_file_path, 'w', encoding='utf-8') as f:
            f.write(summary_report['summary_text'])
        
        # Save to MongoDB for caching
        summary_report['file_paths'] = {
            'txt': summary_file_path
        }
        summary_report['cache_valid'] = True
        summary_report['ticker'] = ticker.upper()
        summary_report['quarter'] = quarter.upper()
        
        self.mongo_helper.save_quarterly_summary(summary_report)
        
        st.success(f"✅ Summary report generated and saved to: {summary_file_path}")
        
        return summary_report
    
    def get_company_quarters(self, ticker: str) -> List[str]:
        """
        Get list of quarters with data for a company
        
        Args:
            ticker: Stock ticker
            
        Returns:
            List of quarters
        """
        return self.mongo_helper.get_company_quarters(ticker)
    
    def get_quarter_documents(self, ticker: str, quarter: str) -> List[Dict[str, Any]]:
        """
        Get all documents for a specific quarter
        
        Args:
            ticker: Stock ticker
            quarter: Quarter
            
        Returns:
            List of document metadata
        """
        return self.mongo_helper.get_quarterly_documents(ticker, quarter)
    
    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document and its associated data
        
        Args:
            document_id: Document ID
            
        Returns:
            Success status
        """
        try:
            # Get document metadata
            doc = self.mongo_helper.get_quarterly_document_by_id(document_id)
            
            if doc:
                # Delete physical file
                file_path = doc.get('file_path')
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                
                # Delete from MongoDB
                self.mongo_helper.delete_quarterly_document(document_id)
                
                # Invalidate cache
                self.mongo_helper.invalidate_quarterly_summary(
                    doc.get('ticker'), doc.get('quarter')
                )
                
                st.success("✅ Document deleted successfully")
                return True
            
            return False
            
        except Exception as e:
            st.error(f"Error deleting document: {str(e)}")
            return False
