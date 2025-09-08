"""
Project Pipeline Manager - Coordinates AI agents to discover and manage real estate projects
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json
from .chatGPT_project_extractor import ChatGPTProjectExtractor
from .perplexity_utils import PerplexityProjectResearcher
from .mongodb_utils import MongoDBHelper
import numpy as np


class ProjectPipelineManager:
    """Manages the discovery, enrichment, and storage of real estate projects"""
    
    def __init__(self, claude_api_key: Optional[str] = None, perplexity_api_key: Optional[str] = None):
        """Initialize with AI agent API keys"""
        self.claude_extractor = ChatGPTProjectExtractor(api_key=claude_api_key)
        self.perplexity_researcher = PerplexityProjectResearcher(api_key=perplexity_api_key)
        self.mongo_helper = MongoDBHelper()
    
    def discover_projects_from_document(self, 
                                       document_file,
                                       company_name: str,
                                       company_ticker: str,
                                       document_type: str = "pdf",
                                       specified_doc_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Discover projects from uploaded financial statement or analyst report
        
        Args:
            document_file: Uploaded file object (PDF or Excel)
            company_name: Company name
            company_ticker: Stock ticker
            document_type: "pdf" or "excel"
            specified_doc_type: Optional - "financial_statement" or "analyst_report" or None for auto-detect
            
        Returns:
            Dictionary containing discovered projects and metadata
        """
        
        with st.spinner("📄 Extracting text from document..."):
            # Extract text based on document type
            try:
                if document_type.lower() == "pdf":
                    document_text = self.claude_extractor.extract_text_from_pdf(document_file)
                else:
                    document_text = self.claude_extractor.extract_text_from_excel(document_file)
                
                if not document_text:
                    # More specific error message
                    if document_type.lower() == "pdf":
                        st.error("""
                        ❌ **Failed to extract text from PDF**
                        
                        This PDF appears to be scanned or image-based. Please try:
                        1. **Use the Excel version instead** (strongly recommended)
                        2. **Use the manual text input** below the error message
                        3. **Convert PDF with OCR** using Google Drive or online tools
                        """)
                        
                        # The extract_text_from_pdf already shows manual input option
                        # Just return the error
                    else:
                        st.error("""
                        ❌ **Failed to extract text from Excel file**
                        
                        Please ensure:
                        - The file is a valid Excel file (.xlsx or .xls)
                        - The file is not corrupted or password-protected
                        - The file contains data (not empty)
                        """)
                    
                    return {"error": "Text extraction failed", "document_type": document_type}
                    
            except Exception as e:
                st.error(f"Error reading document: {str(e)}")
                return {"error": f"Document reading error: {str(e)}"}
        
        with st.spinner("🤖 Analyzing document with Claude AI..."):
            # Use Claude to extract projects - with optional document type specification
            extraction_result = self.claude_extractor.extract_projects_from_document(
                document_text=document_text,
                company_name=company_name,
                company_ticker=company_ticker,
                document_type=specified_doc_type  # Pass the specified doc type if provided
            )
            
            if "error" in extraction_result:
                st.error(f"Claude extraction failed: {extraction_result['error']}")
                return extraction_result
        
        # Display extraction summary
        summary = self.claude_extractor.generate_extraction_summary(extraction_result)
        st.info(summary)
        
        return extraction_result
    
    def enrich_projects_with_research(self, 
                                     projects: List[Dict], 
                                     company_name: str,
                                     progress_callback=None) -> List[Dict]:
        """
        Enrich project data using Perplexity research
        
        Args:
            projects: List of projects to enrich
            company_name: Developer company name
            progress_callback: Optional callback for progress updates
            
        Returns:
            List of enriched projects
        """
        
        enriched_projects = []
        total_projects = len(projects)
        
        for idx, project in enumerate(projects):
            project_name = project.get('project_name', '')
            location = project.get('location', '')
            
            if progress_callback:
                progress_callback(idx + 1, total_projects, project_name)
            
            with st.spinner(f"🔍 Researching {project_name}..."):
                # Research project details with Perplexity
                research_data = self.perplexity_researcher.research_project_details(
                    project_name=project_name,
                    company_name=company_name,
                    location_hint=location
                )
                
                # Merge research data with existing project data
                enriched_project = self._merge_project_data(project, research_data)
                enriched_projects.append(enriched_project)
        
        return enriched_projects
    
    def _merge_project_data(self, 
                          claude_data: Dict, 
                          perplexity_data: Dict) -> Dict:
        """
        Intelligently merge data from Claude and Perplexity
        
        Priority: Specific values > Estimates > Nulls
        Claude data (from financial statements) takes precedence for book values
        Perplexity data (from research) fills in missing details
        """
        
        merged = claude_data.copy()
        
        # Map Perplexity fields to project fields
        field_mapping = {
            'specifications.land_area_sqm': 'land_area_sqm',
            'specifications.total_units': 'total_units',
            'specifications.nsa_sqm': 'net_sellable_area',
            'specifications.gfa_sqm': 'gross_floor_area',
            'pricing.avg_price_per_sqm': 'average_selling_price',
            'timeline.construction_start': 'construction_start_date',
            'timeline.expected_completion': 'completion_date',
            'sales.units_sold': 'units_sold',
            'pricing.construction_cost_per_sqm': 'construction_cost_per_sqm',
            'pricing.land_cost_per_sqm': 'land_cost_per_sqm'
        }
        
        # Extract nested values from Perplexity data
        for perplexity_path, project_field in field_mapping.items():
            value = self._get_nested_value(perplexity_data, perplexity_path)
            
            # Only update if current value is None/empty and new value exists
            if value is not None and (merged.get(project_field) is None or merged.get(project_field) == 0):
                merged[project_field] = value
        
        # Add location details if more specific
        if 'location' in perplexity_data and isinstance(perplexity_data['location'], dict):
            location_details = perplexity_data['location']
            if location_details.get('district'):
                merged['location'] = f"{location_details.get('district', '')}, {location_details.get('city', '')}".strip(', ')
        
        # Add metadata about data sources
        merged['data_sources'] = {
            'financial_statement': True,
            'perplexity_research': 'error' not in perplexity_data,
            'confidence_score': perplexity_data.get('confidence_score', 0),
            'last_updated': datetime.now().isoformat()
        }
        
        # Calculate additional fields if we have the data
        if merged.get('net_sellable_area') and merged.get('average_selling_price'):
            merged['total_revenue_potential'] = merged['net_sellable_area'] * merged['average_selling_price']
        
        return merged
    
    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """Get value from nested dictionary using dot notation path"""
        keys = path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value
    
    def discover_all_projects_from_web(self, 
                                      company_name: str,
                                      company_ticker: str) -> List[Dict]:
        """
        Discover all projects from web research (not just additional ones)
        
        Args:
            company_name: Company name
            company_ticker: Stock ticker
            
        Returns:
            List of all projects discovered from web
        """
        
        with st.spinner("🌐 Researching all company projects on the web..."):
            # Use empty list for known_projects to get all projects
            all_projects = self.perplexity_researcher.discover_additional_projects(
                company_name=company_name,
                company_ticker=company_ticker,
                known_projects=[]  # Empty list means get all projects
            )
            
            if all_projects:
                st.success(f"Found {len(all_projects)} projects from web research")
            else:
                st.info("No projects found from web research. Try being more specific with the company name.")
            
            return all_projects
    
    def discover_additional_projects(self, 
                                    company_name: str,
                                    company_ticker: str,
                                    known_projects: List[str]) -> List[Dict]:
        """
        Discover additional projects not in financial statements
        
        Args:
            company_name: Company name
            company_ticker: Stock ticker
            known_projects: List of already known project names
            
        Returns:
            List of additional projects discovered
        """
        
        with st.spinner("🔎 Searching for additional projects..."):
            additional = self.perplexity_researcher.discover_additional_projects(
                company_name=company_name,
                company_ticker=company_ticker,
                known_projects=known_projects
            )
            
            if additional:
                st.success(f"Found {len(additional)} additional projects not in financial statements")
            
            return additional
    
    def compare_with_existing_projects(self, 
                                      new_projects: List[Dict],
                                      ticker: str) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Compare newly discovered projects with existing ones in MongoDB
        
        Args:
            new_projects: Newly discovered projects
            ticker: Company ticker
            
        Returns:
            Tuple of (new_projects, updated_projects, unchanged_projects)
        """
        
        # Get existing projects from MongoDB
        existing_projects = self.mongo_helper.get_real_estate_projects(ticker)
        
        if not existing_projects:
            # All projects are new
            return new_projects, [], []
        
        # Create lookup by project name
        existing_by_name = {p['project_name']: p for p in existing_projects}
        
        new = []
        updated = []
        unchanged = []
        
        for project in new_projects:
            name = project.get('project_name')
            
            if name not in existing_by_name:
                new.append(project)
            else:
                # Check if there are meaningful updates
                existing = existing_by_name[name]
                if self._has_meaningful_changes(existing, project):
                    updated.append(project)
                else:
                    unchanged.append(project)
        
        return new, updated, unchanged
    
    def _has_meaningful_changes(self, old_project: Dict, new_project: Dict) -> bool:
        """Check if there are meaningful changes between projects"""
        
        # Key fields to check for changes
        key_fields = [
            'book_value_vnd', 'total_units', 'net_sellable_area',
            'average_selling_price', 'stage', 'units_sold'
        ]
        
        for field in key_fields:
            old_val = old_project.get(field)
            new_val = new_project.get(field)
            
            # Check if value has been added or changed
            if old_val != new_val:
                # Ignore if both are None/0
                if not (not old_val and not new_val):
                    return True
        
        return False
    
    def save_projects_to_mongodb(self, 
                                projects: List[Dict],
                                ticker: str,
                                mode: str = "merge") -> bool:
        """
        Save projects to MongoDB
        
        Args:
            projects: List of projects to save
            ticker: Company ticker
            mode: "merge" (update existing), "replace" (replace all), "append" (add only)
            
        Returns:
            Success status
        """
        
        try:
            if mode == "replace":
                # Clear existing projects first
                self.mongo_helper.delete_real_estate_projects(ticker)
            
            success_count = 0
            for project in projects:
                # Ensure ticker is set
                project['ticker'] = ticker
                
                # Convert numpy types to Python types
                project = self._convert_numpy_types(project)
                
                if mode == "merge":
                    # Update if exists, insert if not
                    result = self.mongo_helper.upsert_real_estate_project(project)
                else:
                    # Just insert
                    result = self.mongo_helper.save_real_estate_project(project)
                
                if result:
                    success_count += 1
            
            st.success(f"✅ Saved {success_count}/{len(projects)} projects to database")
            return success_count == len(projects)
            
        except Exception as e:
            st.error(f"Failed to save projects: {str(e)}")
            return False
    
    def _convert_numpy_types(self, obj):
        """Convert numpy types to Python types for MongoDB"""
        if isinstance(obj, dict):
            return {k: self._convert_numpy_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj
    
    def generate_project_summary_table(self, projects: List[Dict]) -> pd.DataFrame:
        """Generate a summary table of projects for display"""
        
        if not projects:
            return pd.DataFrame()
        
        # Check if this is analyst report format (has nav_value_vnd) or financial statement format
        is_analyst_format = any('nav_value_vnd' in p for p in projects)
        
        # Extract key fields for summary
        summary_data = []
        for project in projects:
            if is_analyst_format:
                # Analyst report format
                summary_data.append({
                    'Project Name': project.get('project_name', 'Unknown'),
                    'Location': project.get('location', 'N/A'),
                    'Stage': project.get('stage', 'N/A'),
                    'Total Units': project.get('total_units', 0),
                    'GFA (m²)': project.get('gfa_sqm', 0),
                    'Sales %': project.get('sales_status_pct', 0),
                    'ASP (VND/m²)': project.get('asp_per_sqm', 0),
                    'NAV (B VND)': project.get('nav_value_vnd', 0) / 1e9 if project.get('nav_value_vnd') else 0,
                    'Launch': project.get('launch_date', 'N/A'),
                    'Completion': project.get('completion_date', 'N/A')
                })
            else:
                # Financial statement format
                summary_data.append({
                    'Project Name': project.get('project_name', 'Unknown'),
                    'Location': project.get('location', 'N/A'),
                    'Stage': project.get('stage', 'N/A'),
                    'Total Units': project.get('total_units', 0),
                    'NSA (m²)': project.get('net_sellable_area', 0),
                    'ASP (VND/m²)': project.get('average_selling_price', 0),
                    'Book Value (B VND)': project.get('book_value_vnd', 0) / 1e9 if project.get('book_value_vnd') else 0,
                    'Data Source': 'FS + Research' if project.get('data_sources', {}).get('perplexity_research') else 'FS Only'
                })
        
        df = pd.DataFrame(summary_data)
        
        # Format numeric columns
        if not df.empty:
            df['Total Units'] = df['Total Units'].apply(lambda x: f"{int(x):,}" if x else "N/A")
            
            if is_analyst_format:
                # Format analyst report columns
                if 'GFA (m²)' in df.columns:
                    df['GFA (m²)'] = df['GFA (m²)'].apply(lambda x: f"{int(x):,}" if x else "N/A")
                if 'Sales %' in df.columns:
                    df['Sales %'] = df['Sales %'].apply(lambda x: f"{x:.0f}%" if x else "N/A")
                if 'ASP (VND/m²)' in df.columns:
                    df['ASP (VND/m²)'] = df['ASP (VND/m²)'].apply(lambda x: f"{x/1e6:.1f}M" if x else "N/A")
                if 'NAV (B VND)' in df.columns:
                    df['NAV (B VND)'] = df['NAV (B VND)'].apply(lambda x: f"{x:.1f}" if x else "N/A")
            else:
                # Format financial statement columns
                if 'NSA (m²)' in df.columns:
                    df['NSA (m²)'] = df['NSA (m²)'].apply(lambda x: f"{int(x):,}" if x else "N/A")
                if 'ASP (VND/m²)' in df.columns:
                    df['ASP (VND/m²)'] = df['ASP (VND/m²)'].apply(lambda x: f"{x/1e6:.1f}M" if x else "N/A")
                if 'Book Value (B VND)' in df.columns:
                    df['Book Value (B VND)'] = df['Book Value (B VND)'].apply(lambda x: f"{x:.1f}" if x else "N/A")
        
        return df
    
    def export_projects_to_excel(self, projects: List[Dict], filename: str = "projects_export.xlsx"):
        """Export projects to Excel file"""
        
        # Create DataFrame with all fields
        df = pd.DataFrame(projects)
        
        # Save to Excel
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Projects', index=False)
            
            # Add a summary sheet
            summary_df = self.generate_project_summary_table(projects)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        return filename