#%%
import pandas as pd
import streamlit as st
import numpy as np
from dotenv import load_dotenv
import os
import re
import datetime
import requests
import sys
from pymongo import MongoClient
import certifi

# Add the parent directory to sys.path to import from utils
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import utility functions
from utils.utils import (
    get_project_root,
    get_data_path,
    format_vnd_billions,
    format_number_with_commas
)

# Import Perplexity utilities
from utils.perplexity_utils import get_project_basic_info_perplexity, parse_perplexity_response

# Import MongoDB utilities
from utils.mongodb_utils import (
    init_mongodb_connection, 
    load_companies_data, 
    load_projects_data, 
    get_projects_for_company, 
    get_project_data,
    save_project_to_mongodb,  # Add this missing import
    get_companies_list,       # Add this missing import
    delete_project_from_mongodb  # Add delete function import
)

# Import RNAV utilities
from utils.RNAV_utils import (
    selling_progress_schedule,
    land_use_right_payment_schedule_single_year,
    construction_payment_schedule,
    sga_payment_schedule,
    generate_pnl_schedule,
    RNAV_Calculation  # Add this missing import
)

# Load environment variables
load_dotenv()

# Read API key from environment
perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")

if not perplexity_api_key:
    st.warning(
        "⚠️ PERPLEXITY_API_KEY environment variable is not set.\n\n"
        "**For local development:**\n"
        "1. Create a file named `.env` in your project root directory\n"
        "2. Add this line: `PERPLEXITY_API_KEY=your_perplexity_api_key_here`\n\n"
        "**For Streamlit Cloud deployment:**\n"
        "1. Go to your app settings in Streamlit Cloud\n"
        "2. Add PERPLEXITY_API_KEY as a secret in the 'Secrets' section\n\n"
        "⚡ You can still use the calculator without Perplexity integration!"
    )
    perplexity_api_key = None  # Allow app to continue without API key



# Page configuration
st.set_page_config(
    page_title="RNAV Calculator (MongoDB Direct)",
    page_icon="🧮",
    layout="wide"
)

def main():
    st.title("🧮 Real Estate RNAV Calculator - MongoDB Direct Edition")

    # MongoDB connection status
    with st.sidebar:
        st.header("🔗 Database Connection")
        client = init_mongodb_connection()
        if client:
            st.success("✅ Connected to MongoDB")
            st.info(f"📊 Database: `VietnamStocks`")
            st.info(f"📁 Collections: `Companies`, `RealEstateProjects`")
        else:
            st.error("❌ MongoDB connection failed")
            st.info("Using manual entry mode only - You cannot save projects to MongoDB without a connection.")

    # Get current calendar year automatically
    current_calendar_year = datetime.datetime.now().year

    # Check for pre-loaded project data from dashboard
    preload_data = st.session_state.get('preload_project_data', None)
    preload_name = st.session_state.get('preload_project_name', None)

    # Load projects database only if available
    if client:
        #st.write("🔍 DEBUG: Loading projects database...")
        df_projects = load_projects_data()
        #st.write(f"🔍 DEBUG: Projects database shape: {df_projects.shape}")
        
        # Test companies loading
        #st.write("🔍 DEBUG: Loading companies...")
        companies = get_companies_list()
        #st.write(f"🔍 DEBUG: Companies loaded: {len(companies)} companies")
        #st.write(f"🔍 DEBUG: Sample companies: {companies[:3] if companies else 'No companies found'}")
    else:
        df_projects = pd.DataFrame()
        companies = []
        #st.write("🔍 DEBUG: MongoDB not available, using empty DataFrame")
    
    # Project selection interface
    st.header("📋 Project Selection")
    
    if df_projects.empty:
        if client:
            st.warning("No projects found in MongoDB. You can still enter project details manually below.")
            #st.write("🔍 DEBUG: DataFrame is empty - check database connection and collection names")
        else:
            st.info("MongoDB not available. Enter project details manually below but you cannot save them.")
        project_name = st.text_input("Project Name", value="My Project")
        selected_project_data = None
        selected_company_ticker = 'MANUAL'
        selected_company_name = 'Manual Entry'
    else:
        # Check if we have preloaded data to set default selection
        default_company_index = 0
        default_project_index = 0
        
        if preload_data and 'company_ticker' in preload_data:
            preload_company = f"{preload_data['company_ticker']} - {preload_data['company_name']}"
            if preload_company in companies:
                default_company_index = companies.index(preload_company) + 1
        
        selected_company = st.selectbox(
            "Select Company:",
            options=["Select a company..."] + companies,
            index=default_company_index
        )
        
        if selected_company == "Select a company...":
            st.info("👆 Please select a company to see available projects or add a new project")
            project_name = st.text_input("Project Name:", value="My Project")
            selected_project_data = None
            selected_company_ticker = 'MANUAL'
            selected_company_name = 'Manual Entry'
        else:
            # Extract ticker from selection
            selected_company_ticker = selected_company.split(" - ")[0]
            selected_company_name = selected_company.split(" - ")[1]
            
            # Project selection
            projects = get_projects_for_company(selected_company_ticker)
            
            if not projects:
                st.info(f"No existing projects found for **{selected_company}**")
                st.markdown("**Create a new project for this company:**")
                project_name = st.text_input(
                    f"New Project Name for {selected_company_ticker}:", 
                    value="",
                    placeholder="Enter new project name..."
                )
                selected_project_data = None
                
                if project_name:
                    st.success(f"✅ Ready to create new project: **{project_name}** for **{selected_company}**")
                
            else:
                # Show existing projects with option to create new one
                st.markdown(f"**Existing projects for {selected_company}:**")
                
                # Check if we have preloaded project to set default
                if preload_name and preload_name in projects:
                    default_project_index = projects.index(preload_name) + 1
                
                project_options = ["Select a project...", "➕ Create New Project"] + projects
                selected_project = st.selectbox(
                    "Choose existing project or create new:",
                    options=project_options,
                    index=default_project_index if default_project_index > 1 else 0
                )
                
                if selected_project == "Select a project...":
                    st.info("👆 Please select an existing project or choose 'Create New Project'")
                    project_name = ""
                    selected_project_data = None
                    
                elif selected_project == "➕ Create New Project":
                    st.markdown("**Create a new project:**")
                    project_name = st.text_input(
                        f"New Project Name for {selected_company_ticker}:", 
                        value="",
                        placeholder="Enter new project name..."
                    )
                    selected_project_data = None
                    
                    if project_name:
                        st.success(f"✅ Ready to create new project: **{project_name}** for **{selected_company}**")
                    
                else:
                    # Loading existing project
                    project_name = selected_project
                    selected_project_data = get_project_data(selected_company_ticker, selected_project)
                    
                    if selected_project_data:
                        st.success(f"✅ Loaded project from MongoDB: {selected_project}")
                        
                        # Show project summary with Location
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Units", f"{int(selected_project_data['total_units']):,}")
                            st.metric("NSA", f"{int(selected_project_data['net_sellable_area']):,} m²")
                        with col2:
                            st.metric("ASP", f"{int(selected_project_data['average_selling_price']/1_000_000):,}M VND/m²")
                            st.metric("Project Ownership", f"{float(selected_project_data['project_ownership']) * 100:.1f} %")
                        with col3:
                            st.metric("Land Area", f"{int(selected_project_data['land_area']):,} m²")
                            st.metric("Completion", f"{int(selected_project_data['project_completion_year'])}")
                        with col4:
                            # Display Location information
                            location = selected_project_data.get('location', 'N/A')
                            st.metric("Location", location if location and location != 'N/A' else "Not specified")
                            # Show RNAV if available
                            if 'rnav_value' in selected_project_data and selected_project_data['rnav_value']:
                                rnav_formatted = format_vnd_billions(selected_project_data['rnav_value'])
                                st.metric("Stored RNAV", rnav_formatted)
                            else:
                                st.metric("RNAV Status", "Not calculated")
                        
                        # Override preload_data with database data
                        preload_data = selected_project_data
                    else:
                        st.error("Error loading project data from MongoDB")

    # Add button to get project info from Perplexity
    if "project_info" not in st.session_state:
        st.session_state["project_info"] = {}
    if "project_info_raw" not in st.session_state:
        st.session_state["project_info_raw"] = ""
    if "show_raw_response" not in st.session_state:
        st.session_state["show_raw_response"] = False
    
    # Only show Perplexity button if API key is available
    if perplexity_api_key:
        if st.button("🔍 Search Project Info (Perplexity AI)"):
            with st.spinner("Searching for project information using Perplexity..."):
                info = get_project_basic_info_perplexity(project_name, perplexity_api_key)
                
                # Parse the response if it's a string (successful response)
                if isinstance(info, str):
                    parsed_info = parse_perplexity_response(info)
                    st.session_state["project_info"] = parsed_info
                    st.session_state["project_info_raw"] = info
                    
                    st.success("✅ Perplexity search completed successfully!")
                    
                    # Display parsed information in structured table format
                    if parsed_info:
                        st.subheader("🤖 AI-Extracted Project Information")
                        
                        # Show basic project info if available
                        if parsed_info.get("basic_info"):
                            st.info(f"**Project Description:** {parsed_info['basic_info']}")
                        
                        # Create structured table for comparison
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.markdown("**📊 Project Scale**")
                            if parsed_info.get("total_units"):
                                st.metric("Total Units (AI)", f"{format_number_with_commas(parsed_info['total_units'])}")
                            else:
                                st.metric("Total Units (AI)", "Not found")
                                
                            if parsed_info.get("average_unit_size"):
                                st.metric("Avg Unit Size (AI)", f"{format_number_with_commas(parsed_info['average_unit_size'])} m²")
                            else:
                                st.metric("Avg Unit Size (AI)", "Not found")
                                
                            if parsed_info.get("gfa"):
                                st.metric("GFA (AI)", f"{format_number_with_commas(parsed_info['gfa'])} m²")
                            else:
                                st.metric("GFA (AI)", "Not found")
                        
                        with col2:
                            st.markdown("**💰 Pricing Information**")
                            if parsed_info.get("asp"):
                                asp_millions = float(parsed_info['asp']) / 1_000_000 if parsed_info['asp'] else 0
                                st.metric("ASP (AI)", f"{asp_millions:.0f}M VND/m²")
                            else:
                                st.metric("ASP (AI)", "Not found")
                                
                            if parsed_info.get("construction_cost_per_sqm"):
                                const_millions = float(parsed_info['construction_cost_per_sqm']) / 1_000_000 if parsed_info['construction_cost_per_sqm'] else 0
                                st.metric("Construction Cost (AI)", f"{const_millions:.0f}M VND/m²")
                            else:
                                st.metric("Construction Cost (AI)", "Not found")
                                
                            if parsed_info.get("land_cost_per_sqm"):
                                land_millions = float(parsed_info['land_cost_per_sqm']) / 1_000_000 if parsed_info['land_cost_per_sqm'] else 0
                                st.metric("Land Cost (AI)", f"{land_millions:.0f}M VND/m²")
                            else:
                                st.metric("Land Cost (AI)", "Not found")
                        
                        with col3:
                            st.markdown("**🏗️ Development Info**")
                            if parsed_info.get("land_area"):
                                st.metric("Land Area (AI)", f"{format_number_with_commas(parsed_info['land_area'])} m²")
                            else:
                                st.metric("Land Area (AI)", "Not found")
                                
                            if parsed_info.get("confidence"):
                                confidence_color = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(parsed_info['confidence'], "⚪")
                                st.metric("Confidence", f"{confidence_color} {parsed_info['confidence']}")
                            else:
                                st.metric("Confidence", "Not specified")
                        
                        # Show sources and analysis method
                        if parsed_info.get("sources") or parsed_info.get("analysis_method"):
                            with st.expander("📋 Analysis Details", expanded=False):
                                if parsed_info.get("sources"):
                                    st.markdown(f"**Sources:** {parsed_info['sources']}")
                                if parsed_info.get("analysis_method"):
                                    st.markdown(f"**Analysis Method:** {parsed_info['analysis_method']}")
                        
                        # Comparison with database data if available
                        if selected_project_data:
                            st.markdown("---")
                            st.subheader("📊 Database vs AI Comparison")
                            
                            # Create comparison table
                            comparison_data = []
                            
                            fields_to_compare = [
                                ("Total Units", "total_units", "total_units"),
                                ("Average Unit Size (m²)", "average_unit_size", "average_unit_size"),
                                ("ASP (VND/m²)", "average_selling_price", "asp"),
                                ("GFA (m²)", "gross_floor_area", "gfa"),
                                ("Construction Cost (VND/m²)", "construction_cost_per_sqm", "construction_cost_per_sqm"),
                                ("Land Area (m²)", "land_area", "land_area"),
                                ("Land Cost (VND/m²)", "land_cost_per_sqm", "land_cost_per_sqm")
                            ]
                            
                            for field_name, db_key, ai_key in fields_to_compare:
                                db_value = selected_project_data.get(db_key, "N/A")
                                ai_value = parsed_info.get(ai_key, "N/A")
                                
                                # Format values for display
                                if db_value != "N/A" and isinstance(db_value, (int, float)):
                                    db_display = format_number_with_commas(str(int(db_value)))
                                else:
                                    db_display = str(db_value)
                                    
                                if ai_value != "N/A" and ai_value:
                                    try:
                                        ai_display = format_number_with_commas(str(int(float(ai_value))))
                                    except (ValueError, TypeError):
                                        ai_display = str(ai_value)
                                else:
                                    ai_display = "Not found"
                                
                                # Calculate difference if both values are numeric
                                difference = "N/A"
                                if (db_value != "N/A" and ai_value != "N/A" and ai_value and 
                                    isinstance(db_value, (int, float))):
                                    try:
                                        ai_numeric = float(ai_value)
                                        diff_pct = ((ai_numeric - db_value) / db_value) * 100
                                        difference = f"{diff_pct:+.1f}%"
                                    except (ValueError, TypeError, ZeroDivisionError):
                                        difference = "N/A"
                                
                                comparison_data.append({
                                    "Field": field_name,
                                    "Database": db_display,
                                    "AI Extract": ai_display,
                                    "Difference": difference
                                })
                            
                            comparison_df = pd.DataFrame(comparison_data)
                            st.dataframe(comparison_df, use_container_width=True)
                    
                    # Force refresh to show AI suggestions in input fields
                    st.rerun()
                    
                elif isinstance(info, dict) and "error" in info:
                    st.session_state["project_info"] = {}
                    st.session_state["project_info_raw"] = str(info)
                    
                    st.error(f"❌ Error: {info['error']}")
                    
                    # Show detailed debugging information
                    with st.expander("🔍 Debug Information (Click to expand)"):
                        st.json(info)
                        
                    # Show specific guidance for 400 errors
                    if info.get("status_code") == 400:
                        st.warning("""
                        **400 Bad Request Error - Possible causes:**
                        - Invalid API key format
                        - Unsupported model name
                        - Request payload format issues
                        - Missing required parameters
                        
                        Check the debug information above for the exact request sent to Perplexity.
                        """)
        
        # Show current Perplexity status
        st.success("✅ Perplexity API is configured and ready to use!")
    else:
        st.info("💡 Set up your Perplexity API key to use AI-powered project information search.")

    project_info = st.session_state.get("project_info", {})
    project_info_raw = st.session_state.get("project_info_raw", "")

    # Ensure project_info is always a dict
    if not isinstance(project_info, dict):
        project_info = {}

    # Toggle button for raw AI response
    if project_info_raw or (isinstance(project_info, dict) and "raw_content" in project_info):
        if st.button("🔍 Show/Hide Raw Perplexity Response"):
            st.session_state["show_raw_response"] = not st.session_state["show_raw_response"]
        
        # Show raw response from Perplexity only if toggled on
        if st.session_state["show_raw_response"]:
            st.markdown("**Raw Perplexity Response:**")
            if project_info_raw:
                st.code(project_info_raw, language="markdown")
            elif isinstance(project_info, dict) and "raw_content" in project_info:
                st.code(project_info["raw_content"], language="markdown")

    # Show basic info if available
    if project_info.get("basic_info"):
        st.info(project_info["basic_info"])
    elif project_info.get("error"):
        st.error(project_info["error"])

    
    # Helper function for float parsing with preload and fallback
    def parse_float_with_preload(ai_suggest, preload_value, default):
        try:
            if preload_value is not None:
                return float(preload_value)
            elif ai_suggest and str(ai_suggest).strip():
                # Clean the AI suggestion value
                clean_value = str(ai_suggest).replace(",", "")
                return float(clean_value)
            else:
                return float(default)
        except Exception:
            return float(default)

    # Helper function for int parsing with preload and fallback
    def parse_int_with_preload(ai_suggest, preload_value, default):
        try:
            if preload_value is not None:
                return int(preload_value)
            elif ai_suggest and str(ai_suggest).strip():
                # Clean the AI suggestion value
                clean_value = str(ai_suggest).replace(",", "")
                return int(float(clean_value))
            else:
                return int(default)
        except Exception:
            return int(default)

    # Create two parallel columns for Project Parameters and Timeline
    param_col, timeline_col = st.columns(2)

    with param_col:
        st.header("Project Parameters")
        
        # Add Location input field at the top
        location = st.text_input(
            "Project Location",
            value=preload_data.get('location', '') if preload_data else '',
            placeholder="Enter project location (e.g., District 1, Ho Chi Minh City)",
            key="location"
        )
        if preload_data and 'location' in preload_data and preload_data['location']:
            st.caption(f"📊 From database: **{preload_data['location']}**")
        else:
            st.caption("💡 Enter project location for better documentation")

        # Add project ownership input field
        project_ownership = st.number_input(
            "Project Ownership (enter 1 for 100% ownership)", 
            min_value=0.0, 
            value=float(preload_data.get('project_ownership', 1.0)) if preload_data and 'project_ownership' in preload_data else 1.0, 
            step=0.01
        )
        if preload_data and 'project_ownership' in preload_data:
            st.caption(f"📊 From database: **{float(preload_data['project_ownership']) * 100:.1f} %** ownership")

        # Total Units
        ai_total_units = project_info.get('total_units') if project_info else None
        total_units = st.number_input(
            "Total Units", 
            value=int(parse_float_with_preload(
                ai_total_units,
                preload_data.get('total_units') if preload_data else None, 
                2500
            )), 
            step=1,
            key="total_units"
        )
        if preload_data and 'total_units' in preload_data:
            st.caption(f"📊 From database: **{format_number_with_commas(str(int(preload_data['total_units'])))}** units")
        else:
            st.caption("💡 Using default value")
        
        if ai_total_units:
            try:
                ai_value_formatted = format_number_with_commas(str(int(float(ai_total_units))))
                st.caption(f"🤖 AI suggestion: **{ai_value_formatted}** units")
            except:
                st.caption(f"🤖 AI suggestion: **{ai_total_units}** units")
        
        # Average Unit Size
        ai_unit_size = project_info.get('average_unit_size') if project_info else None
        average_unit_size = st.number_input(
            "Average Unit Size (m²)", 
            value=int(parse_float_with_preload(
                ai_unit_size,
                preload_data.get('average_unit_size') if preload_data else None, 
                80
            )),
            step=1,
            key="average_unit_size"
        )
        if preload_data and 'average_unit_size' in preload_data:
            st.caption(f"📊 From database: **{format_number_with_commas(str(int(preload_data['average_unit_size'])))}** m²")
        else:
            st.caption("💡 Using default value")
        
        if ai_unit_size:
            try:
                ai_value_formatted = format_number_with_commas(str(int(float(ai_unit_size))))
                st.caption(f"🤖 AI suggestion: **{ai_value_formatted}** m²")
            except:
                st.caption(f"🤖 AI suggestion: **{ai_unit_size}** m²")
        
        # Calculate NSA from units and unit size
        nsa = total_units * average_unit_size
        st.info(f"📊 **Calculated Net Sellable Area:** {format_number_with_commas(str(int(nsa)))} m²")
        
        # Average Selling Price
        ai_asp = project_info.get('asp') if project_info else None
        asp = st.number_input(
            "Average Selling Price (VND/m²)", 
            value=int(parse_float_with_preload(
                ai_asp,
                preload_data.get('average_selling_price') if preload_data else None, 
                100_000_000
            )),
            step=1000_000,
            format="%d",
            key="asp"
        )
        if preload_data and 'average_selling_price' in preload_data:
            st.caption(f"📊 From database: **{format_number_with_commas(str(int(preload_data['average_selling_price'])))}** VND/m²")
        else:
            st.caption("💡 Using default value")
        
        if ai_asp:
            try:
                ai_value_formatted = format_number_with_commas(str(int(float(ai_asp))))
                st.caption(f"🤖 AI suggestion: **{ai_value_formatted}** VND/m²")
            except:
                st.caption(f"🤖 AI suggestion: **{ai_asp}** VND/m²")
        
        
        
        # Gross Floor Area
        ai_gfa = project_info.get('gfa') if project_info else None
        gfa = st.number_input(
            "Gross Floor Area (m²)", 
            value=int(parse_float_with_preload(
                ai_gfa,
                preload_data.get('gross_floor_area') if preload_data else None, 
                300_000
            )),
            step=1,
            key="gfa"
        )
        if preload_data and 'gross_floor_area' in preload_data:
            st.caption(f"📊 From database: **{format_number_with_commas(str(int(preload_data['gross_floor_area'])))}** m²")
        else:
            st.caption("💡 Using default value")
        
        if ai_gfa:
            try:
                ai_value_formatted = format_number_with_commas(str(int(float(ai_gfa))))
                st.caption(f"🤖 AI suggestion: **{ai_value_formatted}** m²")
            except:
                st.caption(f"🤖 AI suggestion: **{ai_gfa}** m²")
        
        # Construction Cost per sqm
        ai_construction_cost = project_info.get('construction_cost_per_sqm') if project_info else None
        construction_cost_per_sqm = st.number_input(
            "Construction Cost per m² (VND)", 
            value=int(parse_float_with_preload(
                ai_construction_cost,
                preload_data.get('construction_cost_per_sqm') if preload_data else None, 
                20_000_000
            )),
            step=1_000_000,
            key="construction_cost_per_sqm"
        )
        if preload_data and 'construction_cost_per_sqm' in preload_data:
            st.caption(f"📊 From database: **{format_number_with_commas(str(int(preload_data['construction_cost_per_sqm'])))}** VND/m²")
        else:
            st.caption("💡 Using default value")
        
        if ai_construction_cost:
            try:
                ai_value_formatted = format_number_with_commas(str(int(float(ai_construction_cost))))
                st.caption(f"🤖 AI suggestion: **{ai_value_formatted}** VND/m²")
            except:
                st.caption(f"🤖 AI suggestion: **{ai_construction_cost}** VND/m²")
        
        # Land Area
        ai_land_area = project_info.get('land_area') if project_info else None
        land_area = st.number_input(
            "Land Area (m²)", 
            value=int(parse_float_with_preload(
                ai_land_area,
                preload_data.get('land_area') if preload_data else None, 
                50_000
            )),
            step=1,
            key="land_area"
        )
        if preload_data and 'land_area' in preload_data:
            st.caption(f"📊 From database: **{format_number_with_commas(str(int(preload_data['land_area'])))}** m²")
        else:
            st.caption("💡 Using default value")
        
        if ai_land_area:
            try:
                ai_value_formatted = format_number_with_commas(str(int(float(ai_land_area))))
                st.caption(f"🤖 AI suggestion: **{ai_value_formatted}** m²")
            except:
                st.caption(f"🤖 AI suggestion: **{ai_land_area}** m²")
        
        # Land Cost per sqm
        ai_land_cost = project_info.get('land_cost_per_sqm') if project_info else None
        land_cost_per_sqm = st.number_input(
            "Land Cost per m² (VND)", 
            value=int(parse_float_with_preload(
                ai_land_cost,
                preload_data.get('land_cost_per_sqm') if preload_data else None, 
                50_000_000
            )),
            step=1_000_000,
            key="land_cost_per_sqm"
        )
        if preload_data and 'land_cost_per_sqm' in preload_data:
            st.caption(f"📊 From database: **{format_number_with_commas(str(int(preload_data['land_cost_per_sqm'])))}** VND/m²")
        else:
            st.caption("💡 Using default value")
        
        if ai_land_cost:
            try:
                ai_value_formatted = format_number_with_commas(str(int(float(ai_land_cost))))
                st.caption(f"🤖 AI suggestion: **{ai_value_formatted}** VND/m²")
            except:
                st.caption(f"🤖 AI suggestion: **{ai_land_cost}** VND/m²")

    with timeline_col:
        st.header("Timeline")
        
        # Remove the current year input and use calendar year automatically
        current_year = current_calendar_year
        st.info(f"**Current Year:** {current_year}")
        
        # Separate Construction Start Year and Sales Start Year
        construction_start_year = st.number_input(
            "Construction Start Year", 
            value=parse_int_with_preload("", preload_data.get('construction_start_year') if preload_data else None, current_year),
        )
        
        # Show warning if either start year is in the past
        if construction_start_year < current_year:
            years_ago = current_year - construction_start_year
            st.warning(f"⚠️ Construction start year is {years_ago} year(s) in the past. Historical data will be shown but not included in RNAV calculation.")

        sales_start_year = st.number_input(
            "Sales Start Year", 
            value=parse_int_with_preload("", preload_data.get('sale_start_year') if preload_data else None, current_year),
            #min_value=construction_start_year,  # Allow up to 10 years in the past
        )
               
        if sales_start_year < current_year:
            years_ago = current_year - sales_start_year
            st.warning(f"⚠️ Sales start year is {years_ago} year(s) in the past. Historical data will be shown but not included in RNAV calculation.")
        
        if sales_start_year < construction_start_year:
            years_ago = construction_start_year - sales_start_year
            st.warning(f"⚠️ Sales start year is {years_ago} year(s) before construction start. This is illegal in Vietnamese law and could cause RNAV or PnL issues.")
        
        # Add land payment year input
        land_payment_year = st.number_input(
            "Land Payment Year", 
            value=parse_int_with_preload("", preload_data.get('land_payment_year') if preload_data else None, construction_start_year),
        )
        
        # Separate construction and sales duration
        construction_years = st.number_input(
            "Number of Years for Construction", 
            value=parse_int_with_preload("", preload_data.get('construction_years') if preload_data else None, 3), 
            min_value=1
        )
        sales_years = st.number_input(
            "Number of Years for Sales", 
            value=parse_int_with_preload("", preload_data.get('sales_years') if preload_data else None, 3), 
            min_value=1
        )
        
        start_booking_year = st.number_input(
            "Revenue Booking Start Year", 
            value=parse_int_with_preload("", preload_data.get('revenue_booking_start_year') if preload_data else None, max(current_year, sales_start_year + 1)),
        )

        if start_booking_year < sales_start_year:
            years_ago = sales_start_year - start_booking_year
            st.warning(f"⚠️ Start booking year is {years_ago} year(s) before sales start. This is illogical and could cause RNAV or PnL issues.")

        end_booking_year = st.number_input(
            "Revenue Booking End Year", 
            value=parse_int_with_preload("", preload_data.get('project_completion_year') if preload_data else None, max(construction_start_year, sales_start_year) + 5),
            min_value=start_booking_year
        )

        if end_booking_year < start_booking_year:
            years_ago = start_booking_year - end_booking_year
            st.warning(f"⚠️ Complete year is {years_ago} year(s) before start booking year. This is illogical and could cause RNAV or PnL issues.")

        st.markdown("---")
        
        price_increment_factor = st.number_input(
            "Price Increment Factor (e.g. 0.05 for 5% increase per year)",             
            value=float(preload_data.get('price_increment_factor', 0.00)) if preload_data and 'price_increment_factor' in preload_data else 0.00, 
            step=0.01,
        )
        
        cost_of_debt = st.number_input(
            "Interest Rate (Cost of Debt)", 
            min_value=0.0, 
            value=float(preload_data.get('cost_of_debt', 0.08)) if preload_data and 'cost_of_debt' in preload_data else 0.08, 
            step=0.01
        )
        sga_percent = st.number_input(
            "SG&A as % of Revenue", 
            min_value=0.0, 
            value=float(preload_data.get('sga_percentage', 0.08)) if preload_data and 'sga_percentage' in preload_data else 0.1, 
            step=0.01
        )
        wacc_rate = st.number_input(
            "WACC (Discount Rate, e.g. 0.12 for 12%)", 
            min_value=0.0, 
            value=float(preload_data.get('wacc_rate', 0.12)) if preload_data and 'wacc_rate' in preload_data else 0.12, 
            step=0.01
        )

    project_start_year = min(construction_start_year, sales_start_year, land_payment_year, current_year)

    # Add Save Project button only if MongoDB is available
    if client:
        st.sidebar.markdown("---")
        st.sidebar.subheader("💾 Save Project")
        
        # Show current project context
        if selected_company_ticker != 'MANUAL':
            st.sidebar.info(f"**Company:** {selected_company_ticker} - {selected_company_name}")
        else:
            st.sidebar.info("**Company:** Manual Entry")
            
        if project_name:
            st.sidebar.info(f"**Project:** {project_name}")
            
            # Show save action type
            if selected_project_data:
                st.sidebar.warning("⚠️ **Update existing project**")
                save_button_text = "🔄 Update Project in MongoDB"
            else:
                st.sidebar.success("✅ **Create new project**")
                save_button_text = "💾 Save New Project to MongoDB"
        else:
            st.sidebar.error("❌ Please enter a project name")
            save_button_text = "💾 Save to MongoDB (Need Project Name)"
        
        # Save button (disabled if no project name)
        save_disabled = not bool(project_name and project_name.strip())
        
        if st.sidebar.button(save_button_text, type="primary", disabled=save_disabled):
            if not project_name or not project_name.strip():
                st.sidebar.error("❌ Project name is required!")
            else:
                # Use the selected company info (not from existing project data)
                company_ticker = selected_company_ticker
                company_name = selected_company_name
                
                # Calculate total revenue and PAT for storage with price increment factor
                # Calculate weighted average selling price over the sales period
                total_weighted_revenue = 0
                for year_offset in range(sales_years):
                    year_price = asp * (1 + price_increment_factor) ** year_offset
                    year_revenue = (nsa / sales_years) * year_price  # Equal sales distribution
                    total_weighted_revenue += year_revenue
                
                calculated_total_revenue = total_weighted_revenue
                calculated_total_construction_cost = gfa * construction_cost_per_sqm  # Positive value for storage
                calculated_total_land_cost = land_area * land_cost_per_sqm  # Positive value for storage
                calculated_total_sga_cost = calculated_total_revenue * sga_percent
                calculated_total_PBT = calculated_total_revenue - calculated_total_land_cost - calculated_total_construction_cost - calculated_total_sga_cost
                calculated_total_PAT = calculated_total_PBT * 0.8  # Assuming 20% tax rate
                
                # Calculate RNAV using the same logic as display section
                try:
                    # Use the same totals calculation as the display section
                    total_weighted_revenue = 0
                    for year_offset in range(sales_years):
                        year_price = asp * (1 + price_increment_factor) ** year_offset
                        year_revenue = (nsa / sales_years) * year_price  # Equal sales distribution
                        total_weighted_revenue += year_revenue
                    display_total_revenue = total_weighted_revenue
                    display_total_construction_cost = -gfa * construction_cost_per_sqm
                    display_total_land_cost = -land_area * land_cost_per_sqm
                    display_total_sga_cost = -display_total_revenue * sga_percent

                    # Generate schedules (same as display section)
                    selling_progress = selling_progress_schedule(
                        display_total_revenue/(10**9), int(project_start_year), int(current_year), int(sales_start_year), int(sales_years), int(end_booking_year)
                    )
                    sga_payment = sga_payment_schedule(
                        display_total_sga_cost/(10**9), int(project_start_year), int(current_year), int(sales_start_year), int(sales_years), int(end_booking_year)
                    )
                    construction_payment = construction_payment_schedule(
                        display_total_construction_cost/(10**9), int(project_start_year), int(current_year), int(construction_start_year), int(construction_years), int(end_booking_year)
                    )
                    land_use_right_payment = land_use_right_payment_schedule_single_year(
                        display_total_land_cost/(10**9), int(project_start_year), int(current_year), int(land_payment_year), int(end_booking_year)
                    )

                    df_pnl = generate_pnl_schedule(
                        display_total_revenue/(10**9), display_total_land_cost/(10**9), display_total_construction_cost/(10**9), display_total_sga_cost/(10**9), int(project_start_year),
                        int(current_year), int(start_booking_year), int(end_booking_year), display_total_construction_cost/(10**9), construction_years, cost_of_debt
                    )
                    
                    # Create tax expense schedule
                    num_years = int(end_booking_year) - int(project_start_year) + 1
                    tax_expense = []
                    for year in range(int(project_start_year), int(end_booking_year) + 1):
                        year_data = df_pnl[df_pnl["Year"] == year]
                        if not year_data.empty and year_data["Type"].iloc[0] != "Summary":
                            tax_value = year_data["Tax Expense (20%)"].iloc[0]
                        else:
                            tax_value = 0.0
                        tax_expense.append(tax_value)

                    # Verify all schedules have the same length
                    schedules_info = {
                       "selling_progress": len(selling_progress),
                       "construction_payment": len(construction_payment), 
                       "sga_payment": len(sga_payment),
                       "tax_expense": len(tax_expense),
                       "land_use_right_payment": len(land_use_right_payment),
                    }
                    #st.write("**Schedule Lengths:**", schedules_info)
                    # Ensure all schedules have the same length
                    expected_length = num_years
                    if not all(length == expected_length for length in schedules_info.values()):
                        st.error(f"Schedule length mismatch! Expected: {expected_length}, Got: {schedules_info}")
                        st.stop()

                    # Calculate RNAV (same as display section)
                    df_rnav = RNAV_Calculation(
                        selling_progress, construction_payment, sga_payment, tax_expense, land_use_right_payment, wacc_rate, int(project_start_year), int(current_year)
                    )

                    # Get RNAV value (same logic as display section)
                    total_row = df_rnav[df_rnav["Year"] == "Total RNAV"]
                    if not total_row.empty:
                        rnav_value = total_row["Discounted Cash Flow"].iloc[0] * (10**9)
                    else:
                        st.warning("⚠️ RNAV 'Total' row not found, using fallback method")
                        rnav_value = df_rnav.loc[df_rnav.index[-1], 'Discounted Cash Flow'] * (10**9)

                    # Debug: Show RNAV calculation details
                    st.sidebar.markdown("---")
                    st.sidebar.subheader("🔍 Debug: RNAV Calculation")
                    st.sidebar.write(f"**Discounted Cash Flow (Billions):** {rnav_value / (10**9):.4f}")
                    st.sidebar.write(f"**RNAV Value to save:** {format_vnd_billions(rnav_value)}")
                    st.sidebar.write(f"**Raw RNAV Value:** {rnav_value:,.0f} VND")
                    
                    if not total_row.empty:
                        st.sidebar.success("✅ RNAV extracted from 'Total RNAV' row")
                        st.sidebar.write(f"**DCF from total row:** {total_row['Discounted Cash Flow'].iloc[0]:.4f}")
                    else:
                        st.sidebar.warning("⚠️ Using fallback method for RNAV")
                        st.sidebar.write(f"**Last row DCF:** {df_rnav.loc[df_rnav.index[-1], 'Discounted Cash Flow']:.4f}")

                except Exception as e:
                    st.sidebar.error(f"Error calculating RNAV: {str(e)}")
                    st.sidebar.write("🔍 **Debug: RNAV Calculation Failed**")
                    st.sidebar.write(f"Error details: {str(e)}")
                    rnav_value = None
                
                # Debug: Show what will be saved
                #st.sidebar.markdown("---")
                #st.sidebar.subheader("🔍 Debug: Data to Save")
                #st.sidebar.write(f"**Project Name:** {project_name}")
                #st.sidebar.write(f"**Company:** {company_ticker} - {company_name}")
                #st.sidebar.write(f"**RNAV Value:** {format_vnd_billions(rnav_value) if rnav_value else 'None'}")
                #st.sidebar.write(f"**Total Revenue:** {format_vnd_billions(calculated_total_revenue)}")
                #st.sidebar.write(f"**Total PAT:** {format_vnd_billions(calculated_total_PAT)}")
                #st.sidebar.write(f"**Location:** {location if location else 'Not specified'}")
                
                # Collect current project data including location, total revenue, and total PAT
                current_project_data = {
                    'company_ticker': company_ticker,
                    'company_name': company_name,
                    'location': location,  # Include location in saved data
                    'project_ownership': project_ownership,  # Include ownership in saved data
                    'total_units': total_units,
                    'average_unit_size': average_unit_size,
                    'average_selling_price': asp,
                    'price_increment_factor': price_increment_factor,
                    'gross_floor_area': gfa,
                    'land_area': land_area,
                    'construction_cost_per_sqm': construction_cost_per_sqm,
                    'land_cost_per_sqm': land_cost_per_sqm,
                    'construction_start_year': construction_start_year,
                    'sale_start_year': sales_start_year,
                    'land_payment_year': land_payment_year,
                    'construction_years': construction_years,
                    'sales_years': sales_years,
                    'revenue_booking_start_year': start_booking_year,
                    'project_completion_year': end_booking_year,
                    'sga_percentage': sga_percent,
                    'wacc_rate': wacc_rate,
                    'cost_of_debt': cost_of_debt,
                    'total_revenue': calculated_total_revenue,  # Add total revenue
                    'total_pat': calculated_total_PAT,  # Add total PAT for reference
                    'total_pbt': calculated_total_PBT,  # Add total PBT for reference
                    'total_construction_cost': calculated_total_construction_cost,  # Add total construction cost
                    'total_land_cost': calculated_total_land_cost,  # Add total land cost
                    'total_sga_cost': calculated_total_sga_cost,  # Add total SG&A cost
                }
                
                save_result = save_project_to_mongodb(current_project_data, project_name, rnav_value)
                if save_result["success"]:
                    # Debug: Confirm what was saved
                    st.sidebar.success("✅ Save operation completed!")
                    st.sidebar.write(f"🔍 **Saved RNAV:** {format_vnd_billions(rnav_value) if rnav_value else 'None'}")
                    
                    if rnav_value is not None:
                        st.sidebar.success(f"{save_result['message']}\n💰 RNAV: {format_vnd_billions(rnav_value)}\n💵 Total Revenue: {format_vnd_billions(calculated_total_revenue)}\n📈 Total PAT: {format_vnd_billions(calculated_total_PAT)}")
                    else:
                        st.sidebar.success(f"{save_result['message']}\n💵 Total Revenue: {format_vnd_billions(calculated_total_revenue)}\n📈 Total PAT: {format_vnd_billions(calculated_total_PAT)}")
                    
                    # Show action taken
                    if save_result["action"] == "saved":
                        st.sidebar.info(f"✅ New project '{project_name}' created for {company_ticker}")
                    elif save_result["action"] == "updated":
                        st.sidebar.info(f"🔄 Project '{project_name}' updated for {company_ticker}")
                    
                    # Refresh the database after save
                    st.rerun()
                else:
                    st.sidebar.error(save_result["message"])
        
        # Add Delete Project section
        if selected_project_data and project_name and selected_company_ticker != 'MANUAL':
            st.sidebar.markdown("---")
            st.sidebar.subheader("🗑️ Delete Project")
            
            st.sidebar.warning(f"⚠️ **Delete existing project:** {project_name}")
            st.sidebar.error("🚨 **This action cannot be undone!**")
            
            # Add confirmation checkbox
            confirm_delete = st.sidebar.checkbox(
                f"I confirm I want to permanently delete '{project_name}' from {selected_company_ticker}",
                key="confirm_delete"
            )
            
            # Delete button (only enabled if confirmed)
            if st.sidebar.button(
                "🗑️ Delete Project from MongoDB", 
                type="secondary",
                disabled=not confirm_delete,
                help="Permanently delete this project from the database"
            ):
                if confirm_delete:
                    # Perform the deletion
                    with st.spinner("Deleting project..."):
                        delete_result = delete_project_from_mongodb(selected_company_ticker, project_name)
                        
                    if delete_result["success"]:
                        st.sidebar.success(f"✅ {delete_result['message']}")
                        st.sidebar.info(f"🗑️ Project '{project_name}' has been permanently deleted from {selected_company_ticker}")
                        
                        # Clear the session state to prevent confusion
                        if 'preload_project_data' in st.session_state:
                            del st.session_state['preload_project_data']
                        if 'preload_project_name' in st.session_state:
                            del st.session_state['preload_project_name']
                        
                        # Refresh the page to show updated project list
                        st.rerun()
                    else:
                        st.sidebar.error(f"❌ {delete_result['message']}")
                else:
                    st.sidebar.error("❌ Please confirm deletion by checking the box above")
            
            if not confirm_delete:
                st.sidebar.caption("💡 Check the confirmation box above to enable the delete button")
    else:
        st.sidebar.info("💾 MongoDB not available - Cannot save projects")

    # Calculate totals
    total_weighted_revenue = 0
    for year_offset in range(sales_years):
        year_price = asp * (1 + price_increment_factor) ** year_offset
        year_revenue = (nsa / sales_years) * year_price  # Equal sales distribution
        total_weighted_revenue += year_revenue
    total_revenue = total_weighted_revenue
    total_construction_cost = -gfa * construction_cost_per_sqm
    total_land_cost = -land_area * land_cost_per_sqm
    total_sga_cost = -total_revenue * sga_percent
    total_estimated_PBT = total_revenue + total_land_cost + total_construction_cost + total_sga_cost
    total_estimated_PAT = total_estimated_PBT * 0.8  # Assuming 20% tax rate

# Show timeline summary
    st.markdown("---")
    st.markdown("**📊 Project Timeline Summary:**")
    
    # Create two parallel columns for Project Parameters and Timeline
    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**Construction:** {construction_start_year} - {construction_start_year + construction_years - 1}")
        st.write(f"**Sales:** {sales_start_year} - {sales_start_year + sales_years - 1}")
        st.write(f"**Land Payment:** {land_payment_year}")
        st.write(f"**Revenue Booking:** {start_booking_year} - {end_booking_year}")
        st.write(f"**Project Duration:** {end_booking_year - min(construction_start_year, sales_start_year) + 1} years")
    with col2:
        st.write(f"**Total Revenue:** {format_vnd_billions(total_revenue)}")
        st.write(f"**Total Construction Cost:** {format_vnd_billions(total_construction_cost)}")
        st.write(f"**Total Land Cost:** {format_vnd_billions(total_land_cost)}")
        st.write(f"**Total SG&A:** {format_vnd_billions(total_sga_cost)}")
        st.write(f"**Total Estimated PBT:** {format_vnd_billions(total_estimated_PBT)}")    
        st.write(f"**Total Estimated PAT:** {format_vnd_billions(total_estimated_PAT)}")

    
    # Update schedule calculations to use separate construction and sales years
    selling_progress = selling_progress_schedule(
        total_revenue/(10**9), int(project_start_year), int(current_year), int(sales_start_year), int(sales_years), int(end_booking_year)
    )
    sga_payment = sga_payment_schedule(
        total_sga_cost/(10**9), int(project_start_year), int(current_year), int(sales_start_year), int(sales_years), int(end_booking_year)
    )
    construction_payment = construction_payment_schedule(
        total_construction_cost/(10**9), int(project_start_year), int(current_year), int(construction_start_year), int(construction_years), int(end_booking_year)
    )

    df_pnl = generate_pnl_schedule(
        total_revenue/(10**9), total_land_cost/(10**9), total_construction_cost/(10**9), total_sga_cost/(10**9), int(project_start_year),
        int(current_year), int(start_booking_year), int(end_booking_year),total_construction_cost/(10**9),construction_years,cost_of_debt
    )

    # Create land use right payment schedule
    land_use_right_payment = land_use_right_payment_schedule_single_year(
        total_land_cost/(10**9), int(project_start_year), int(current_year), int(land_payment_year), int(end_booking_year)
    )

    # Create tax expense schedule that matches the time period from project start year to complete_year
    num_years = int(end_booking_year) - int(project_start_year) + 1

    # Get tax expense for each year from start_booking_year to complete_year
    tax_expense = []
    for year in range(int(project_start_year), int(end_booking_year) + 1):
        # Find tax expense for this year in the P&L schedule
        year_data = df_pnl[df_pnl["Year"] == year]
        if not year_data.empty and year_data["Type"].iloc[0] != "Summary":
            tax_value = year_data["Tax Expense (20%)"].iloc[0]
        else:
            # If year not found in P&L (e.g., before booking period), use 0
            tax_value = 0.0
        tax_expense.append(tax_value)
    
    # Verify all schedules have the same length
    schedules_info = {
       "selling_progress": len(selling_progress),
       "construction_payment": len(construction_payment), 
       "sga_payment": len(sga_payment),
       "tax_expense": len(tax_expense),
       "land_use_right_payment": len(land_use_right_payment),
    }
    #st.write("**Schedule Lengths:**", schedules_info)
    # Ensure all schedules have the same length
    expected_length = num_years
    if not all(length == expected_length for length in schedules_info.values()):
        st.error(f"Schedule length mismatch! Expected: {expected_length}, Got: {schedules_info}")
        st.stop()

    df_rnav = RNAV_Calculation(
        selling_progress, construction_payment, sga_payment, tax_expense, land_use_right_payment, wacc_rate, int(project_start_year), int(current_year)
    )

    # Create two parallel columns for P&L Schedule and RNAV Calculation
    pnl_col, rnav_col = st.columns(2)
    
    st.markdown("---")

    with pnl_col:
        st.header("P&L Schedule")
        # Create a copy and modify year labels to avoid duplicates
        df_pnl_display = df_pnl.copy()
        
        # Add suffix to years based on whether they're past, present, or future
        def format_year_label_unique(year, index):
            if isinstance(year, (int, float)) and not pd.isna(year):
                year_int = int(year)
                if year_int < current_year:
                    return f"{year_int}"
                elif year_int == current_year:
                    return f"{year_int}-Present"
                else:
                    return f"{year_int}F"
            else:
                return f"{str(year)}"  # Keep non-year values with index
        
        # Apply formatting to Year column if it exists with unique indices
        if 'Year' in df_pnl_display.columns:
            df_pnl_display['Year'] = [format_year_label_unique(year, i) for i, year in enumerate(df_pnl_display['Year'])]
        
        # Remove the Type column before transposing to avoid duplication issues
        if 'Type' in df_pnl_display.columns:
            df_pnl_display = df_pnl_display.drop('Type', axis=1)
        
        # Format numeric columns to remove decimals and add commas
        for col in df_pnl_display.columns:
            if col != 'Year':  # Don't format the Year column
                if df_pnl_display[col].dtype in ['float64', 'int64']:
                    df_pnl_display[col] = df_pnl_display[col].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
        
        # Transpose the P&L dataframe so years are columns
        try:
            df_pnl_transposed = df_pnl_display.set_index('Year').transpose()
            st.dataframe(df_pnl_transposed)
        except ValueError as e:
            st.error(f"Error transposing P&L data: {e}")
            st.dataframe(df_pnl_display)
    
    with rnav_col:
        st.header("RNAV Calculation")
        # Create a copy and modify year labels to avoid duplicates
        df_rnav_display = df_rnav.copy()
        
        # Apply the same year formatting to RNAV data with unique indices
        if 'Year' in df_rnav_display.columns:
            df_rnav_display['Year'] = [format_year_label_unique(year, i) for i, year in enumerate(df_rnav_display['Year'])]
        
        # Format numeric columns to remove decimals and add commas
        for col in df_rnav_display.columns:
            if col != 'Year' and col != 'Discount Factor':  # Don't format the Year column
                if df_rnav_display[col].dtype in ['float64', 'int64']:
                    df_rnav_display[col] = df_rnav_display[col].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "")
            if col == 'Discount Factor':
                # Format Discount Factor to 4 decimal places
                df_rnav_display[col] = df_rnav_display[col].apply(lambda x: f"{x:.4f}" if pd.notna(x) else "")

        # Transpose the RNAV dataframe so years are columns
        try:
            df_rnav_transposed = df_rnav_display.set_index('Year').transpose()
            st.dataframe(df_rnav_transposed)
        except ValueError as e:
            st.error(f"Error transposing RNAV data: {e}")
            st.dataframe(df_rnav_display)

    #st.subheader("RNAV (Total Discounted Cash Flow)")
    
    # Get RNAV value from the total row (using same logic as save section)
    try:
        total_row = df_rnav[df_rnav["Year"] == "Total RNAV"]
        if not total_row.empty:
            display_rnav_value = total_row["Discounted Cash Flow"].iloc[0] * (10**9)
        else:
            # Fallback to old method
            display_rnav_value = df_rnav.loc[df_rnav.index[-1], 'Discounted Cash Flow'] * (10**9)
    except:
        display_rnav_value = 0
    
    #st.write(f"**{format_vnd_billions(display_rnav_value)}**")
    
    
    # Show RNAV history if available
    if selected_project_data and 'rnav_value' in selected_project_data and selected_project_data['rnav_value'] is not None:
        stored_rnav = selected_project_data['rnav_value']
        last_updated = selected_project_data.get('last_updated', 'Unknown')
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Current RNAV", format_vnd_billions(display_rnav_value))
            st.metric("Current RNAV to Company", format_vnd_billions(display_rnav_value * project_ownership))
            st.metric("Total Revenue", format_vnd_billions(total_revenue))
            st.metric("Total PAT", format_vnd_billions(total_estimated_PAT))
        with col2:
            st.metric(
                "Stored RNAV", 
                format_vnd_billions(stored_rnav),
                delta=format_vnd_billions(display_rnav_value - stored_rnav)
            )
            st.metric(
                "Stored RNAV to Company", 
                format_vnd_billions(stored_rnav * project_ownership),
                delta=format_vnd_billions(display_rnav_value * project_ownership - stored_rnav * project_ownership)
            )
            # Show stored total revenue and PAT if available
            if 'total_revenue' in selected_project_data:
                stored_revenue = selected_project_data['total_revenue']
                st.metric("Stored Revenue", format_vnd_billions(stored_revenue),
                delta = format_vnd_billions(total_revenue - stored_revenue))
            if 'total_pat' in selected_project_data:
                stored_pat = selected_project_data['total_pat']
                st.metric("Stored PAT", format_vnd_billions(stored_pat),
                delta= format_vnd_billions(total_estimated_PAT - stored_pat))


        st.caption(f"📅 Last stored: {last_updated}")

    st.header("Cash Flow Chart")
    # Filter out the "Total" row and create chart with years on x-axis
    chart_data = df_rnav[~df_rnav["Year"].isin(["Total RNAV"])].copy()
    
    if len(chart_data) > 0:
        # Ensure Year column is integer for clean display
        chart_data["Year"] = chart_data["Year"].astype(int)
        chart_data = chart_data.set_index("Year")[["Net Cash Flow", "Discounted Cash Flow"]]
        
        # Use plotly for better control over x-axis formatting
        import plotly.express as px
        import plotly.graph_objects as go
        
        # Create plotly chart with clean year formatting
        fig = go.Figure()
        
        # Add Net Cash Flow line
        fig.add_trace(go.Scatter(
            x=chart_data.index,
            y=chart_data["Net Cash Flow"],
            mode='lines+markers',
            name='Net Cash Flow',
            line=dict(color='blue')
        ))
        
        # Add Discounted Cash Flow line
        fig.add_trace(go.Scatter(
            x=chart_data.index,
            y=chart_data["Discounted Cash Flow"],
            mode='lines+markers',
            name='Discounted Cash Flow',
            line=dict(color='red')
        ))
        
        # Add vertical line at current year
        fig.add_vline(
            x=current_year, 
            line_dash="dash", 
            line_color="green",
            annotation_text=f"Current Year ({current_year})",
            annotation_position="top"
        )
        
        # Update layout for clean year display
        fig.update_layout(
            title="Cash Flow Analysis",
            xaxis_title="Year",
            yaxis_title="Cash Flow (Billions VND)",
            xaxis=dict(
                tickmode='linear',
                tick0=chart_data.index.min(),
                dtick=1,
                tickformat='d'  # Display as integer without decimals
            ),
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No data available for chart display.")

# Ensure main function is called when the script runs
if __name__ == "__main__":
    main()
else:
    # For Streamlit, also call main when imported as a module
    main()

# %%
