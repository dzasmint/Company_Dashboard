#%%
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time
from utils.decimal_input import decimal_input, percentage_input, currency_input


class ProjectPipelineRealEstateTab:
    """Project Pipeline tab specifically for Real Estate Financial Model"""
    
    def __init__(self, parent):
        self.parent = parent
    
    def clear_project_input_cache(self):
        """Clear all cached input values when switching projects"""
        # List of keys to clear from session state
        keys_to_clear = []
        
        # Find all keys that might be cached input values
        for key in list(st.session_state.keys()):
            # Clear input-related keys
            if any(prefix in key for prefix in [
                'edit_', 'input_', 'select_', 'slider_', 
                'number_', 'text_', 'checkbox_', 'radio_',
                'low_rise_', 'high_rise_', 'presales_',
                'collection_', 'revenue_year_', 'cost_year_',
                'collect_relative_', 'relative_collection_schedule',
                'low_presales_dist_', 'high_presales_dist_',
                'low_revenue_dist_', 'high_revenue_dist_'
            ]):
                keys_to_clear.append(key)
        
        # Clear identified keys
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
    
    def calculate_total_presales_booking(self, project_data):
        """Calculate total presales booking with price increment for both low-rise and high-rise.
        This is the single source of truth for total revenue calculation.
        Total Revenue = Total Presales Booking = Total Cash Collection
        """
        price_increment = float(project_data.get('price_increment_factor', 0) or 0)
        
        # Get presales timeline
        presales_start = int(project_data.get('sale_start_year', 2025) or 2025)
        sales_years = int(project_data.get('sales_years', 3) or 3)
        presales_end = presales_start + sales_years - 1
        years = list(range(presales_start, presales_end + 1))
        
        total_presales = 0
        
        # Calculate low-rise presales
        low_rise_nsa = float(project_data.get('low_rise_nsa', 0) or 0)
        low_rise_asp = float(project_data.get('low_rise_asp', 0) or 0)
        low_rise_dist = project_data.get('low_rise_presales_distribution', {})
        
        if low_rise_dist:
            for i, year in enumerate(years):
                year_pct = low_rise_dist.get(str(year), 0) / 100
                year_nsa = low_rise_nsa * year_pct
                year_asp = low_rise_asp * (1 + price_increment) ** i
                total_presales += year_nsa * year_asp
        
        # Calculate high-rise presales
        high_rise_nsa = float(project_data.get('high_rise_nsa', 0) or 0)
        high_rise_asp = float(project_data.get('high_rise_asp', 0) or 0)
        high_rise_dist = project_data.get('high_rise_presales_distribution', {})
        
        if high_rise_dist:
            for i, year in enumerate(years):
                year_pct = high_rise_dist.get(str(year), 0) / 100
                year_nsa = high_rise_nsa * year_pct
                year_asp = high_rise_asp * (1 + price_increment) ** i
                total_presales += year_nsa * year_asp
        
        
        return total_presales / 1e9  # Return in billions
        
    def render(self):
        """Render project pipeline and timeline"""
        
        df_projects = st.session_state.project_data
        
        # Check if we have projects
        has_projects = df_projects is not None and isinstance(df_projects, pd.DataFrame) and not df_projects.empty
        
        if not has_projects:
            # Show message but still allow adding new projects
            st.info("No existing projects found. You can create a new project or click 'Sync Project Data' in the sidebar to load projects from MongoDB.")
            
            # Initialize empty dataframe if needed
            if df_projects is None:
                df_projects = pd.DataFrame()
                st.session_state.project_data = df_projects
        
        # Add project selector for individual project editing
        if has_projects:
            project_names = df_projects['project_name'].tolist()
        else:
            project_names = []
        
        # Add "Create New Project" option at the beginning
        project_options = ["All Projects (Overview)", "➕ Create New Project"] + project_names
        
        # Use session state to preserve the selected project
        if 'selected_project_for_edit' not in st.session_state:
            st.session_state.selected_project_for_edit = "All Projects (Overview)"
        
        # Handle pending project switch (after creating a new project)
        if 'pending_project_switch' in st.session_state:
            pending_project = st.session_state.pending_project_switch
            del st.session_state.pending_project_switch
            # Check if the new project exists in the options
            if pending_project in project_names:
                st.session_state.selected_project_for_edit = pending_project
        
        # Create a form to prevent auto-rerun on selection
        with st.container():
            # Store previous selection to detect changes
            prev_selection = st.session_state.get('prev_project_selection', None)
            
            selected_project_name = st.selectbox(
                "Choose a project to view/edit details:",
                options=project_options,
                key="selected_project_for_edit",
                index=project_options.index(st.session_state.selected_project_for_edit) if st.session_state.selected_project_for_edit in project_options else 0,
                help="Select a project to view or edit its details"
            )
            
            # Check if project selection changed
            if prev_selection and prev_selection != selected_project_name:
                st.session_state.prev_project_selection = selected_project_name
                # Clear cache and force reload
                self.clear_project_input_cache()
                st.rerun()
            
            st.session_state.prev_project_selection = selected_project_name
        
        if selected_project_name == "➕ Create New Project":
            # Show new project creation form
            self.render_new_project_form()
            return
        elif selected_project_name != "All Projects (Overview)":
            # Show individual project editor
            self.render_individual_project_editor(selected_project_name, df_projects)
            return
        
        # Only show overview if we have projects
        if not has_projects:
            st.warning("No projects to display. Please create a new project using the '➕ Create New Project' option above.")
            return
        
        # Project summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Projects", len(df_projects))
            
        with col2:
            total_units = df_projects['total_units'].sum() if 'total_units' in df_projects.columns else 0
            st.metric("Total Units", f"{int(total_units):,}")
            
        with col3:
            total_nsa = df_projects['net_sellable_area'].sum() if 'net_sellable_area' in df_projects.columns else 0
            st.metric("Total NSA", f"{total_nsa:,.0f} sqm")
            
        with col4:
            avg_price = df_projects['average_selling_price'].mean() if 'average_selling_price' in df_projects.columns else 0
            st.metric("Avg Price/sqm", f"{avg_price:,.0f}M VND")
        
        # Project timeline visualization
        st.subheader("Project Timeline")
        
        timeline_data = []
        for _, project in df_projects.iterrows():
            timeline_data.append({
                'Project': project['project_name'],
                'Start': project.get('construction_start_year', 9999),
                'End': project.get('project_completion_year', 9999),
                'Revenue Start': project.get('revenue_booking_start_year', 9999)
            })
        
        timeline_df = pd.DataFrame(timeline_data)
        
        # Create Gantt chart
        fig = go.Figure()
        
        for idx, row in timeline_df.iterrows():
            fig.add_trace(go.Scatter(
                x=[row['Start'], row['End']],
                y=[row['Project'], row['Project']],
                mode='lines',
                line=dict(width=20, color='lightblue'),
                name=row['Project'],
                showlegend=False,
                hovertemplate=f"Project: {row['Project']}<br>Period: {row['Start']}-{row['End']}<extra></extra>"
            ))
            
            # Add revenue start marker
            fig.add_trace(go.Scatter(
                x=[row['Revenue Start']],
                y=[row['Project']],
                mode='markers',
                marker=dict(size=10, color='red'),
                name='Revenue Start',
                showlegend=idx == 0
            ))
        
        fig.update_layout(
            title="Project Development Timeline",
            xaxis_title="Year",
            yaxis_title="Project",
            height=400,
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Project details table
        st.subheader("Project Details")
        
        # Prepare display columns
        display_columns = [
            'project_name', 'location', 'total_units', 'net_sellable_area',
            'average_selling_price', 'construction_start_year', 
            'project_completion_year', 'rnav_value'
        ]
        
        # Filter for existing columns
        available_columns = [col for col in display_columns if col in df_projects.columns]
        
        # Create display dataframe
        display_df = df_projects[available_columns].copy()
        
        # Format numeric columns
        if 'net_sellable_area' in display_df.columns:
            display_df['net_sellable_area'] = display_df['net_sellable_area'].apply(lambda x: f"{x:,.0f}")
        if 'average_selling_price' in display_df.columns:
            # Convert ASP to million VND for display
            display_df['average_selling_price'] = display_df['average_selling_price'].apply(lambda x: f"{x/1_000_000:,.1f}")
        if 'rnav_value' in display_df.columns:
            display_df['rnav_value'] = display_df['rnav_value'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
        
        # Rename columns for better display
        column_rename = {
            'project_name': 'Project Name',
            'location': 'Location',
            'total_units': 'Total Units',
            'net_sellable_area': 'Net Sellable Area (m²)',
            'average_selling_price': 'ASP (VND mn/m²)',
            'construction_start_year': 'Construction Start',
            'project_completion_year': 'Project Completion',
            'rnav_value': 'RNAV Value'
        }
        display_df = display_df.rename(columns=column_rename)
        
        st.dataframe(display_df, use_container_width=True)
        
        # Revenue forecast by project
        st.subheader("Revenue Forecast by Project")
        revenue_data = self.calculate_project_revenues(df_projects)
        
        if revenue_data:
            revenue_df = pd.DataFrame(revenue_data)
            revenue_pivot = revenue_df.pivot(index='Year', columns='Project', values='Revenue')
            revenue_pivot = revenue_pivot.fillna(0)
            
            # Create stacked bar chart
            fig = go.Figure()
            
            for project in revenue_pivot.columns:
                fig.add_trace(go.Bar(
                    name=project,
                    x=revenue_pivot.index,
                    y=revenue_pivot[project] / 1e9,  # Convert to billions
                    text=[f"{v:.1f}B" if v > 0 else "" for v in revenue_pivot[project] / 1e9],
                    textposition='inside'
                ))
            
            fig.update_layout(
                title="Revenue Forecast by Project (Billion VND)",
                xaxis_title="Year",
                yaxis_title="Revenue (Billion VND)",
                barmode='stack',
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    def calculate_project_revenues(self, df_projects):
        """Calculate revenue forecast for all projects"""
        revenue_data = []
        current_year = datetime.now().year
        
        for _, project in df_projects.iterrows():
            revenue_start = int(project.get('revenue_booking_start_year', current_year))
            project_end = int(project.get('project_completion_year', current_year + 3))
            
            # Calculate total revenue using consistent method
            # Create a dict-like object for the calculation method
            project_dict = dict(project)
            total_revenue_billions = self.calculate_total_presales_booking(project_dict)
            total_revenue = total_revenue_billions * 1e9  # Convert to raw value
            
            # Get revenue distribution
            revenue_dist = project.get('revenue_distribution', {})
            if not isinstance(revenue_dist, dict):
                revenue_dist = {}
            
            # If no distribution, create even split
            if not revenue_dist:
                booking_years = list(range(revenue_start, project_end + 1))
                if booking_years:
                    even_pct = 100.0 / len(booking_years)
                    for year in booking_years:
                        revenue_dist[str(year)] = even_pct
            
            # Add revenue data for each year
            for year_str, pct in revenue_dist.items():
                revenue_data.append({
                    'Project': project['project_name'],
                    'Year': int(year_str),
                    'Revenue': total_revenue * (pct / 100)
                })
        
        return revenue_data
    

    def render_new_project_form(self):
        """Render form for creating a brand new project - reuses the existing project editor"""
        st.subheader("➕ Create New Project")
        st.info("Enter details for your new project. All fields start with default values.")
        
        # Clear any existing editing state to ensure clean slate
        if 'edited_project' in st.session_state:
            del st.session_state.edited_project
        if 'current_editing_project' in st.session_state:
            del st.session_state.current_editing_project
        
        # Create a new project template with default values
        current_year = datetime.now().year
        new_project_template = {
            'project_name': 'New Project',
            'company_ticker': st.session_state.get('selected_company', ''),
            'location': '',
            # Low-rise fields
            'low_rise_units': 0,
            'low_rise_avg_unit_size': 0,
            'low_rise_nsa': 0,
            'low_rise_asp': 0,
            # High-rise fields
            'high_rise_units': 0,
            'high_rise_avg_unit_size': 0,
            'high_rise_nsa': 0,
            'high_rise_asp': 0,
            # Combined fields (calculated)
            'total_units': 0,
            'net_sellable_area': 0,
            'average_selling_price': 0,
            # Other fields
            'gross_floor_area': 0,
            'land_area': 0,
            'price_increment_factor': 0,  # Annual price increment percentage
            'construction_cost_per_sqm': 0,
            'land_cost_per_sqm': 0,
            'construction_start_year': current_year,
            'project_completion_year': current_year + 3,
            'revenue_booking_start_year': current_year + 1,
            'revenue_booking_end_year': current_year + 4,
            'construction_years': 3,
            'sales_years': 4,
            'project_ownership': 1.0,  # 100% ownership default
            # Separate distributions for low-rise and high-rise
            'low_rise_presales_distribution': {},
            'high_rise_presales_distribution': {},
            'low_rise_revenue_distribution': {},
            'high_rise_revenue_distribution': {},
            # Combined distributions (for backward compatibility)
            'revenue_distribution': {},
            'presales_distribution': {},
            'sga_percentage': 0.08,  # 8% default
            'cost_of_debt': 0.08,  # 8% default
            'wacc_rate': 0.11,  # 11% default
            'total_construction_cost': 0,
            'total_land_cost': 0,
            'total_debt': 0,
            'equity_investment': 0,
            'rnav_value': 0,
            'is_new_project': True  # Flag to indicate this is a new project
        }
        
        # Create a temporary DataFrame with this single project for the editor
        temp_df = pd.DataFrame([new_project_template])
        
        # Use the existing project editor with the template
        self.render_individual_project_editor('New Project', temp_df)
    
    def get_ai_project_suggestions(self, project_name, project_data):
        """Use Perplexity AI to research and suggest project parameters"""
        import os
        from utils.perplexity_utils import get_project_basic_info_perplexity, parse_perplexity_response
        
        # Get API key
        perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
        
        if not perplexity_api_key:
            st.error("❌ PERPLEXITY_API_KEY not configured. Please add it to your .env file.")
            return
        
        # Extract company information for comprehensive search
        company_ticker = project_data.get('company_ticker', '')
        company_name = project_data.get('company_name', '')
        location = project_data.get('location', '')
        
        # Create detailed search query with all available information
        search_parts = [project_name]
        if company_ticker:
            search_parts.append(f"by {company_ticker}")
        if company_name:
            search_parts.append(company_name)
        if location:
            search_parts.append(f"in {location}")
        search_parts.append("Vietnam real estate project")
        
        search_query = " ".join(search_parts)
        
        with st.spinner(f"AI researching {project_name} - gathering market data and comparable projects..."):
            try:
                # Call Perplexity API with the full project name
                response = get_project_basic_info_perplexity(project_name, perplexity_api_key)
                
                if isinstance(response, str):
                    # Parse the response
                    parsed_info = parse_perplexity_response(response)
                    
                    if parsed_info and not parsed_info.get("error"):
                        st.success("✅ AI research completed successfully!")
                        
                        # Store AI suggestions in session state for inline display
                        ai_suggestions_key = f"ai_suggestions_{project_name}"
                        st.session_state[ai_suggestions_key] = parsed_info
                        
                        # Also store raw response for reference
                        st.session_state[f"ai_raw_response_{project_name}"] = response
                        
                        # Now display the summary using the dedicated method
                        self.display_ai_research_summary(project_name, project_data)
                    else:
                        st.error("❌ Could not parse AI response. Please try again.")
                else:
                    st.error(f"❌ AI research failed: {response}")
                    
            except Exception as e:
                st.error(f"❌ Error during AI research: {str(e)}")
    
    def display_ai_research_summary(self, project_name, project_data):
        """Display AI Research Summary in full width"""
        parsed_info = st.session_state.get(f"ai_suggestions_{project_name}", {})
        
        if not parsed_info:
            return
        
        # Display summary without any container constraints - use full width
        st.markdown("---")
        st.markdown("### AI Research Summary")
        
        # Show basic info if available in full width
        if parsed_info.get("basic_info"):
            st.info(f"**Project Description:** {parsed_info['basic_info']}")
        
        # Display metadata in columns for better layout
        meta_cols = st.columns(3)
        
        with meta_cols[0]:
            if parsed_info.get("confidence"):
                st.metric("Confidence Level", parsed_info['confidence'])
        
        with meta_cols[1]:
            if parsed_info.get("analysis_method"):
                st.metric("Analysis Method", parsed_info['analysis_method'])
        
        with meta_cols[2]:
            if parsed_info.get("sources"):
                st.metric("Data Sources", parsed_info['sources'])
        
        st.info("💡 AI suggestions are displayed below. Review and modify values as needed before saving.")
        
        # Create a table for suggested values comparison
        suggestions = []
        
        # Map parsed fields to project parameters
        if parsed_info.get("location"):
            suggestions.append({
                "Parameter": "Location",
                "AI Suggestion": str(parsed_info["location"]),
                "Current Value": str(project_data.get('location', 'N/A'))
            })
        
        if parsed_info.get("total_units"):
            try:
                ai_units = float(parsed_info['total_units'])
                suggestions.append({
                    "Parameter": "Total Units",
                    "AI Suggestion": f"{ai_units:,.0f}",
                    "Current Value": f"{float(project_data.get('total_units', 0)):,.0f}"
                })
            except (ValueError, TypeError):
                suggestions.append({
                    "Parameter": "Total Units",
                    "AI Suggestion": str(parsed_info['total_units']),
                    "Current Value": str(project_data.get('total_units', 0))
                })
        
        if parsed_info.get("total_area_sqm"):
            try:
                ai_area = float(parsed_info['total_area_sqm'])
                suggestions.append({
                    "Parameter": "Gross Floor Area (sqm)",
                    "AI Suggestion": f"{ai_area:,.0f}",
                    "Current Value": f"{float(project_data.get('gross_floor_area', 0)):,.0f}"
                })
            except (ValueError, TypeError):
                suggestions.append({
                    "Parameter": "Gross Floor Area (sqm)",
                    "AI Suggestion": str(parsed_info['total_area_sqm']),
                    "Current Value": str(project_data.get('gross_floor_area', 0))
                })
        
        if parsed_info.get("land_area_sqm"):
            try:
                ai_land = float(parsed_info['land_area_sqm'])
                suggestions.append({
                    "Parameter": "Land Area (sqm)",
                    "AI Suggestion": f"{ai_land:,.0f}",
                    "Current Value": f"{float(project_data.get('land_area', 0)):,.0f}"
                })
            except (ValueError, TypeError):
                suggestions.append({
                    "Parameter": "Land Area (sqm)",
                    "AI Suggestion": str(parsed_info['land_area_sqm']),
                    "Current Value": str(project_data.get('land_area', 0))
                })
        
        if parsed_info.get("avg_selling_price_per_sqm"):
            try:
                ai_price = float(parsed_info['avg_selling_price_per_sqm'])
                current_price = float(project_data.get('average_selling_price', 0))
                suggestions.append({
                    "Parameter": "Avg Selling Price (mn VND/m²)",
                    "AI Suggestion": f"{ai_price/1_000_000:,.0f}",
                    "Current Value": f"{current_price/1_000_000:,.0f}"
                })
            except (ValueError, TypeError):
                suggestions.append({
                    "Parameter": "Avg Selling Price (mn VND/m²)",
                    "AI Suggestion": str(parsed_info['avg_selling_price_per_sqm']),
                    "Current Value": str(project_data.get('average_selling_price', 0))
                })
        
        if parsed_info.get("construction_cost_per_sqm"):
            try:
                ai_cost = float(parsed_info['construction_cost_per_sqm'])
                current_cost = float(project_data.get('construction_cost_per_sqm', 0))
                suggestions.append({
                    "Parameter": "Construction Cost (mn VND/m²)",
                    "AI Suggestion": f"{ai_cost/1_000_000:,.0f}",
                    "Current Value": f"{current_cost/1_000_000:,.0f}"
                })
            except (ValueError, TypeError):
                suggestions.append({
                    "Parameter": "Construction Cost (mn VND/m²)",
                    "AI Suggestion": str(parsed_info['construction_cost_per_sqm']),
                    "Current Value": str(project_data.get('construction_cost_per_sqm', 0))
                })
        
        if parsed_info.get("project_duration"):
            suggestions.append({
                "Parameter": "Construction Years",
                "AI Suggestion": parsed_info["project_duration"],
                "Current Value": project_data.get('construction_years', 'N/A')
            })
        
        if suggestions:
            df_suggestions = pd.DataFrame(suggestions)
            st.dataframe(df_suggestions, use_container_width=True)
        else:
            st.warning("No specific parameter suggestions found. The AI may need more specific information about this project.")
    
    def render_individual_project_editor(self, project_name, df_projects):
        """Render editor for individual project with revenue/presales distribution"""
        
        # Check if this is a new project (indicated by special flag or project name)
        is_new_project = False
        if 'project_name' not in df_projects.columns:
            # This is a new project template DataFrame
            is_new_project = True
            project_data = df_projects.iloc[0].to_dict()
        else:
            # Check for the is_new_project flag in the data
            if len(df_projects) == 1:
                row_data = df_projects.iloc[0].to_dict()
                if row_data.get('is_new_project', False):
                    is_new_project = True
                    project_data = row_data
                else:
                    # Not a new project, proceed with normal flow
                    is_new_project = False
                    project_data = row_data  # Set project_data for existing projects too
            else:
                # Always use the most recent data from session state if available for existing projects
                if 'project_data' in st.session_state and st.session_state.project_data is not None and 'project_name' in st.session_state.project_data.columns:
                    df_projects = st.session_state.project_data
                
                # Get the selected project data
                filtered_df = df_projects[df_projects['project_name'] == project_name]
                
                if filtered_df.empty:
                    st.error(f"Project '{project_name}' not found.")
                    return
                else:
                    project_data = filtered_df.iloc[0].to_dict()
        
        # Add default values for new fields if they don't exist
        defaults = {
            'revenue_distribution': {},
            'presales_distribution': {},
            'sga_percentage': 0.0,
            'cost_of_debt': 0.0,
            'wacc_rate': 0.0,
            'sales_years': 1,
            'construction_years': 1
        }
        
        for key, default_value in defaults.items():
            if key not in project_data or project_data[key] is None:
                project_data[key] = default_value
            # Special handling for distribution fields - ensure they're dictionaries
            elif key in ['revenue_distribution', 'presales_distribution']:
                if not isinstance(project_data[key], dict):
                    project_data[key] = default_value
        
        st.subheader(f"Project: {project_name}")
        
        # Add AI Suggestion button
        col_ai, col_space = st.columns([2, 3])
        with col_ai:
            if st.button("AI Suggest Parameters", key=f"ai_suggest_{project_name}", type="primary"):
                st.session_state[f"show_ai_research_{project_name}"] = True
                st.session_state[f"pending_ai_research_{project_name}"] = True
        
        # Display AI Research Summary outside of columns for full width
        if st.session_state.get(f"pending_ai_research_{project_name}", False):
            self.get_ai_project_suggestions(project_name, project_data)
            st.session_state[f"pending_ai_research_{project_name}"] = False
        elif st.session_state.get(f"ai_suggestions_{project_name}"):
            # Display previously generated AI suggestions
            self.display_ai_research_summary(project_name, project_data)
        
        # Check if this is a new project
        is_creating_new = project_data.get('is_new_project', False)
        
        # Check if we're switching to a different project or creating new
        if is_creating_new:
            # For new projects, always use fresh template data
            st.session_state.current_editing_project = 'NEW_PROJECT_TEMP'
            st.session_state.edited_project = project_data.copy()
            # Clear the relative collection schedule for new projects
            if 'relative_collection_schedule' in st.session_state:
                del st.session_state.relative_collection_schedule
            # Clear all cached input values to force reload
            self.clear_project_input_cache()
        elif 'current_editing_project' not in st.session_state:
            st.session_state.current_editing_project = project_name
            st.session_state.edited_project = project_data.copy()
            # Clear the relative collection schedule to force reload from new project
            if 'relative_collection_schedule' in st.session_state:
                del st.session_state.relative_collection_schedule
            # Clear all cached input values to force reload
            self.clear_project_input_cache()
        elif st.session_state.current_editing_project != project_name:
            # Different project selected, reset the edited data
            st.session_state.current_editing_project = project_name
            st.session_state.edited_project = project_data.copy()
            # Clear the relative collection schedule to force reload from new project
            if 'relative_collection_schedule' in st.session_state:
                del st.session_state.relative_collection_schedule
            # Clear all cached input values to force reload
            self.clear_project_input_cache()
        elif 'edited_project' not in st.session_state:
            # Same project but edited_project was deleted (e.g., after save)
            st.session_state.edited_project = project_data.copy()
        
        # Render all sections in a single scrollable view
        st.markdown("---")
        self.render_project_basic_info(project_data)
        
        st.markdown("---")
        self.render_project_timeline(project_data)
        
        st.markdown("---")
        self.render_project_financial_summary(project_data)
        
        st.markdown("---")
        self.render_presales_distribution_editor(project_data)
        
        st.markdown("---")
        self.render_cash_collection_schedule(project_data)
        
        st.markdown("---")
        self.render_revenue_distribution_editor(project_data)
        
        st.markdown("---")
        self.render_project_balance_sheet_analysis(project_data)
        
        st.markdown("---")
        self.render_project_financial_analysis(project_data)
        
        st.markdown("---")
        # Pass the is_new_project flag explicitly to save interface
        project_data_with_flag = project_data.copy()
        project_data_with_flag['is_new_project'] = is_new_project
        self.render_project_save_interface(project_data_with_flag)
    
    def render_project_basic_info(self, project_data):
        """Render basic project information editor"""
        st.subheader("Basic Project Information")
        
        # Ensure project_data is a dictionary
        if not isinstance(project_data, dict):
            st.error("Invalid project data format")
            return
        
        # Get AI suggestions if available
        project_name = project_data.get('project_name', '')
        ai_suggestions_key = f"ai_suggestions_{project_name}"
        ai_suggestions = st.session_state.get(ai_suggestions_key, {})
        
        # Create a unique key prefix for this project to avoid caching issues
        key_prefix = f"{project_name}_" if project_name else "new_"
        
        # Each field on its own row with label and input side by side
        
        # Project Name - FIRST field for new projects
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Project Name**")
        with col2:
            # Check if this is a new project
            is_new_project = project_data.get('is_new_project', False)
            
            if is_new_project:
                # For new projects, allow editing the name
                project_name_input = st.text_input(
                    "Project Name",
                    value=str(project_data.get('project_name', 'New Project') or 'New Project'),
                    key="edit_project_name",
                    label_visibility="collapsed",
                    placeholder="Enter a unique project name",
                    help="Please enter a unique project name (not 'New Project')"
                )
                
                # Validate project name
                if project_name_input == 'New Project' or not project_name_input.strip():
                    st.error("⚠️ Please enter a unique project name (not 'New Project')")
                
                st.session_state.edited_project['project_name'] = project_name_input
            else:
                # For existing projects, show as disabled
                st.text_input(
                    "Project Name",
                    value=str(project_data.get('project_name', '') or ''),
                    disabled=True,
                    key="display_project_name",
                    label_visibility="collapsed"
                )
                st.session_state.edited_project['project_name'] = project_data.get('project_name', '')
        
        # Project Ownership - moved to second position
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Project Ownership (%)**")
        with col2:
            # Convert from decimal to percentage for display (0.5 -> 50)
            ownership_decimal = float(project_data.get('project_ownership', 1.0) or 1.0)
            ownership_percentage = ownership_decimal * 100
            
            ownership_input = percentage_input(
                label="Project Ownership (%)",
                value=ownership_percentage,
                max_value=100.0,
                key=f"{key_prefix}edit_ownership_pct",
                label_visibility="collapsed"
            )
            # Convert back from percentage to decimal for storage (50 -> 0.5)
            ownership_decimal_value = ownership_input / 100.0
        st.session_state.edited_project['project_ownership'] = ownership_decimal_value
        
        # Location
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Location**")
        with col2:
            location = st.text_input(
                "Location",
                value=str(project_data.get('location', '') or ''),
                key=f"{key_prefix}edit_location",
                label_visibility="collapsed"
            )
            if ai_suggestions.get("location"):
                st.caption(f"AI Suggestion: {ai_suggestions['location']}")
        st.session_state.edited_project['location'] = location
        
        # Get current values for calculations (needed across all tabs)
        low_rise_units_current = int(project_data.get('low_rise_units', 0) or 0)
        low_rise_avg_unit_size_current = int(project_data.get('low_rise_avg_unit_size', 0) or 0)
        low_rise_asp_current = float(project_data.get('low_rise_asp', 0) or 0)
        
        high_rise_units_current = int(project_data.get('high_rise_units', 0) or 0)
        high_rise_avg_unit_size_current = int(project_data.get('high_rise_avg_unit_size', 0) or 0)
        high_rise_asp_current = float(project_data.get('high_rise_asp', 0) or 0)
        
        # Create tabs for unit information
        st.markdown("#### Unit Information")
        tab_low_rise, tab_high_rise, tab_combined = st.tabs(["Low-Rise Units", "High-Rise Units", "Combined Totals"])
        
        with tab_low_rise:
            # Low-Rise Units
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown("**Low-Rise Units**")
            with col2:
                low_rise_units = int(decimal_input(
                    label="Low-Rise Units",
                    value=float(project_data.get('low_rise_units', 0) or 0),
                    min_value=0.0,
                    key=f"{key_prefix}edit_low_rise_units",
                    label_visibility="collapsed",
                    help="Number of low-rise units"
                ))
            st.session_state.edited_project['low_rise_units'] = low_rise_units
            
            # Low-Rise Average Unit Size
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown("**Low-Rise Avg Unit Size (m²)**")
            with col2:
                low_rise_avg_unit_size = int(decimal_input(
                    label="Low-Rise Average Unit Size (m²)",
                    value=float(project_data.get('low_rise_avg_unit_size', 0) or 0),
                    min_value=0.0,
                    key=f"{key_prefix}edit_low_rise_avg_unit_size",
                    label_visibility="collapsed",
                    help="Average unit size in square meters"
                ))
            st.session_state.edited_project['low_rise_avg_unit_size'] = low_rise_avg_unit_size
            
            # Calculate and display Low-Rise NSA
            low_rise_nsa = low_rise_units * low_rise_avg_unit_size
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown("**Low-Rise NSA**")
            with col2:
                st.text_input(
                    "Low-Rise Net Sellable Area",
                    value=f"{low_rise_nsa:,.0f} m² (calculated)",
                    disabled=True,
                    key="low_rise_nsa_display",
                    label_visibility="collapsed"
                )
            st.session_state.edited_project['low_rise_nsa'] = low_rise_nsa
            
            # Low-Rise Average Selling Price
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown("**Low-Rise ASP (VND mn/m²)**")
            with col2:
                low_rise_asp_raw = float(project_data.get('low_rise_asp', 0) or 0)
                low_rise_asp_million = low_rise_asp_raw / 1_000_000
                
                low_rise_asp_million_input = decimal_input(
                    label="Low-Rise Average Selling Price (VND mn/m²)",
                    value=low_rise_asp_million,
                    min_value=0.0,
                    key="edit_low_rise_asp",
                    label_visibility="collapsed",
                    help="Selling price in million VND per square meter"
                )
                low_rise_asp_value = low_rise_asp_million_input * 1_000_000
            st.session_state.edited_project['low_rise_asp'] = low_rise_asp_value
        
        with tab_high_rise:
            # High-Rise Units
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown("**High-Rise Units**")
            with col2:
                high_rise_units = int(decimal_input(
                    label="High-Rise Units",
                    value=float(project_data.get('high_rise_units', 0) or 0),
                    min_value=0.0,
                    key="edit_high_rise_units",
                    label_visibility="collapsed",
                    help="Number of high-rise units"
                ))
            st.session_state.edited_project['high_rise_units'] = high_rise_units
            
            # High-Rise Average Unit Size
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown("**High-Rise Avg Unit Size (m²)**")
            with col2:
                high_rise_avg_unit_size = int(decimal_input(
                    label="High-Rise Average Unit Size (m²)",
                    value=float(project_data.get('high_rise_avg_unit_size', 0) or 0),
                    min_value=0.0,
                    key="edit_high_rise_avg_unit_size",
                    label_visibility="collapsed",
                    help="Average unit size in square meters"
                ))
            st.session_state.edited_project['high_rise_avg_unit_size'] = high_rise_avg_unit_size
            
            # Calculate and display High-Rise NSA
            high_rise_nsa = high_rise_units * high_rise_avg_unit_size
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown("**High-Rise NSA**")
            with col2:
                st.text_input(
                    "High-Rise Net Sellable Area",
                    value=f"{high_rise_nsa:,.0f} m² (calculated)",
                    disabled=True,
                    key="high_rise_nsa_display",
                    label_visibility="collapsed"
                )
            st.session_state.edited_project['high_rise_nsa'] = high_rise_nsa
            
            # High-Rise Average Selling Price
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown("**High-Rise ASP (VND mn/m²)**")
            with col2:
                high_rise_asp_raw = float(project_data.get('high_rise_asp', 0) or 0)
                high_rise_asp_million = high_rise_asp_raw / 1_000_000
                
                high_rise_asp_million_input = decimal_input(
                    label="High-Rise Average Selling Price (VND mn/m²)",
                    value=high_rise_asp_million,
                    min_value=0.0,
                    key="edit_high_rise_asp",
                    label_visibility="collapsed",
                    help="Selling price in million VND per square meter"
                )
                high_rise_asp_value = high_rise_asp_million_input * 1_000_000
            st.session_state.edited_project['high_rise_asp'] = high_rise_asp_value
        
        with tab_combined:
            # Get the latest values from session state for combined calculations
            low_rise_units = st.session_state.edited_project.get('low_rise_units', 0)
            high_rise_units = st.session_state.edited_project.get('high_rise_units', 0)
            low_rise_nsa = st.session_state.edited_project.get('low_rise_nsa', 0)
            high_rise_nsa = st.session_state.edited_project.get('high_rise_nsa', 0)
            low_rise_asp_value = st.session_state.edited_project.get('low_rise_asp', 0)
            high_rise_asp_value = st.session_state.edited_project.get('high_rise_asp', 0)
            
            # Calculate combined values
            total_units = low_rise_units + high_rise_units
            total_nsa = low_rise_nsa + high_rise_nsa
            # Weighted average ASP
            if total_nsa > 0:
                weighted_asp = (low_rise_nsa * low_rise_asp_value + high_rise_nsa * high_rise_asp_value) / total_nsa
            else:
                weighted_asp = 0
            
            # Display combined totals
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown("**Total Units**")
            with col2:
                st.text_input(
                    "Total Units",
                    value=f"{total_units:,.0f} units",
                    disabled=True,
                    key="total_units_display",
                    label_visibility="collapsed"
                )
            st.session_state.edited_project['total_units'] = total_units
            
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown("**Total NSA**")
            with col2:
                st.text_input(
                    "Total Net Sellable Area",
                    value=f"{total_nsa:,.0f} m²",
                    disabled=True,
                    key="total_nsa_display",
                    label_visibility="collapsed"
                )
            st.session_state.edited_project['net_sellable_area'] = total_nsa
            
            # Calculate and display average unit size
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown("**Average Unit Size**")
            with col2:
                avg_unit_size = total_nsa / total_units if total_units > 0 else 0
                st.text_input(
                    "Average Unit Size",
                    value=f"{avg_unit_size:.1f} m²",
                    disabled=True,
                    key="avg_unit_size_display",
                    label_visibility="collapsed"
                )
            
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown("**Weighted Avg ASP (VND mn/m²)**")
            with col2:
                st.text_input(
                    "Weighted Average Selling Price",
                    value=f"{weighted_asp/1_000_000:.1f}",
                    disabled=True,
                    key="weighted_asp_display",
                    label_visibility="collapsed"
                )
            st.session_state.edited_project['average_selling_price'] = weighted_asp
        
        # Price Annual Increment
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Price Annual Increment (%)**")
        with col2:
            # Load price_increment_factor from MongoDB (stored as decimal, e.g., 0.05 for 5%)
            price_increment_raw = float(project_data.get('price_increment_factor', 0) or 0)
            # Convert to percentage for display
            price_increment_pct = price_increment_raw * 100
            
            price_increment_input = percentage_input(
                label="Price Annual Increment (%)",
                value=price_increment_pct,
                max_value=100.0,
                key="edit_price_increment",
                label_visibility="collapsed",
                help="Annual percentage increase in selling price (e.g., 5 for 5% annual increase)"
            )
            # Convert back to decimal for storage (e.g., 5% -> 0.05)
            price_increment_decimal = price_increment_input / 100
        st.session_state.edited_project['price_increment_factor'] = price_increment_decimal
        
        # Section separator and header for Land and Construction Information
        st.markdown("---")
        st.markdown("#### Land and Construction Information")
        
        # Land Area
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Land Area (m²)**")
        with col2:
            land_area = int(decimal_input(
                label="Land Area (m²)",
                value=float(project_data.get('land_area', 0) or 0),
                min_value=0.0,
                key="edit_land_area",
                label_visibility="collapsed",
                help="Total land area in square meters"
            ))
            if ai_suggestions.get("land_area_sqm"):
                try:
                    ai_land = float(ai_suggestions['land_area_sqm'])
                    st.caption(f"AI Suggestion: {ai_land:,.0f} m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['land_area_sqm']} m²")
        st.session_state.edited_project['land_area'] = land_area
        
        # Land Cost per sqm (in VND million per m2 for user input) - moved here after Land Area
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Land Cost (VND mn/m²)**")
        with col2:
            # Convert from raw VND to VND million for display
            land_cost_raw = float(project_data.get('land_cost_per_sqm', 0) or 0)
            land_cost_million = land_cost_raw / 1_000_000  # Convert to million VND
            
            land_cost_million_input = decimal_input(
                label="Land Cost (VND mn/m²)",
                value=land_cost_million,
                min_value=0.0,
                key="edit_land_cost",
                label_visibility="collapsed",
                help="Enter cost in million VND per m² (e.g., 25.5 for 25.5 million VND/m²)"
            )
            
            # Convert back to raw VND for storage and calculations
            land_cost = int(land_cost_million_input * 1_000_000)
            
            if ai_suggestions.get("land_cost_per_sqm"):
                try:
                    ai_land_cost = float(ai_suggestions['land_cost_per_sqm'])
                    ai_land_cost_million = ai_land_cost / 1_000_000
                    st.caption(f"AI Suggestion: {ai_land_cost_million:.1f} mn VND/m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['land_cost_per_sqm']} VND/m²")
        st.session_state.edited_project['land_cost_per_sqm'] = land_cost
        
        # Total Land Cost (calculated, non-editable)
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Total Land Cost (VND bn)**")
        with col2:
            # Calculate total land cost from Land Area and Land Cost per sqm
            land_area_value = float(st.session_state.edited_project.get('land_area', 0) or 0)
            land_cost_value = float(st.session_state.edited_project.get('land_cost_per_sqm', 0) or 0)
            total_land_cost = land_area_value * land_cost_value / 1_000_000_000  # Convert to billions VND
            
            # Display as disabled text input
            st.text_input(
                "Total Land Cost (VND bn)",
                value=f"{total_land_cost:,.1f}",
                disabled=True,
                key="total_land_cost_display",
                label_visibility="collapsed",
                help="Automatically calculated: Land Area × Land Cost per m²"
            )
        
        # Gross Floor Area
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Gross Floor Area (m²)**")
        with col2:
            gfa = int(decimal_input(
                label="Gross Floor Area (m²)",
                value=float(project_data.get('gross_floor_area', 0) or 0),
                min_value=0.0,
                key="edit_gfa",
                label_visibility="collapsed",
                help="Gross floor area in square meters"
            ))
            if ai_suggestions.get("total_area_sqm"):
                try:
                    ai_gfa = float(ai_suggestions['total_area_sqm'])
                    st.caption(f"AI Suggestion: {ai_gfa:,.0f} m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['total_area_sqm']} m²")
        st.session_state.edited_project['gross_floor_area'] = gfa
        
        # Construction Cost per sqm (in VND million per m2 for user input)
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Construction Cost (VND mn/m²)**")
        with col2:
            # Convert from raw VND to VND million for display
            const_cost_raw = float(project_data.get('construction_cost_per_sqm', 0) or 0)
            const_cost_million = const_cost_raw / 1_000_000  # Convert to million VND
            
            const_cost_million_input = decimal_input(
                label="Construction Cost (VND mn/m²)",
                value=const_cost_million,
                min_value=0.0,
                key="edit_const_cost",
                label_visibility="collapsed",
                help="Enter cost in million VND per m² (e.g., 15.5 for 15.5 million VND/m²)"
            )
            
            # Convert back to raw VND for storage and calculations
            const_cost = int(const_cost_million_input * 1_000_000)
            
            if ai_suggestions.get("construction_cost_per_sqm"):
                try:
                    ai_const = float(ai_suggestions['construction_cost_per_sqm'])
                    ai_const_million = ai_const / 1_000_000
                    st.caption(f"AI Suggestion: {ai_const_million:.0f} mn VND/m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['construction_cost_per_sqm']} VND/m²")
        st.session_state.edited_project['construction_cost_per_sqm'] = const_cost
        
        # Total Construction Cost (calculated, non-editable)
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Total Construction Cost (VND bn)**")
        with col2:
            # Calculate total construction cost from GFA and construction cost per sqm
            gfa_value = float(st.session_state.edited_project.get('gross_floor_area', 0) or 0)
            const_cost_value = float(st.session_state.edited_project.get('construction_cost_per_sqm', 0) or 0)
            total_const_cost = gfa_value * const_cost_value / 1_000_000_000  # Convert to billions VND
            
            # Display as disabled text input
            st.text_input(
                "Total Construction Cost (VND bn)",
                value=f"{total_const_cost:,.1f}",
                disabled=True,
                key="total_construction_cost_display",
                label_visibility="collapsed",
                help="Automatically calculated: GFA × Construction Cost per m²"
            )
        
        # Total Debt field (in VND billions for user input)
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Total Debt (VND bn)**")
        with col2:
            # Calculate default total debt if not present in MongoDB
            gfa = float(st.session_state.edited_project.get('gross_floor_area', 0) or 0)
            land_area = float(st.session_state.edited_project.get('land_area', 0) or 0)
            const_cost_per_sqm = float(st.session_state.edited_project.get('construction_cost_per_sqm', 0) or 0)
            land_cost_per_sqm = float(st.session_state.edited_project.get('land_cost_per_sqm', 0) or 0)
            
            total_const_cost = gfa * const_cost_per_sqm
            total_land_cost_calc = land_area * land_cost_per_sqm
            total_project_cost = total_const_cost + total_land_cost_calc
            
            # Get debt financing percentage from edited project (fallback to 30%)
            debt_financing_pct = float(st.session_state.edited_project.get('debt_financing_pct', 0.3) or 0.3)
            
            # Calculate default total debt
            default_total_debt = total_project_cost * debt_financing_pct
            
            # Get existing total debt from project data or use calculated default
            existing_total_debt_raw = project_data.get('total_debt', default_total_debt)
            
            # Convert to billions for display
            existing_total_debt_bn = existing_total_debt_raw / 1_000_000_000
            default_total_debt_bn = default_total_debt / 1_000_000_000
            
            # Create detailed tooltip with calculation breakdown
            tooltip_text = (
                f"Default Calculation:\n"
                f"─────────────────────\n"
                f"Construction Cost: {total_const_cost/1e9:,.1f} bn VND\n"
                f"  = GFA ({gfa:,.0f} m²) × Construction Cost ({const_cost_per_sqm/1e6:,.1f} mn VND/m²)\n"
                f"Land Cost: {total_land_cost_calc/1e9:,.1f} bn VND\n"
                f"  = Land Area ({land_area:,.0f} m²) × Land Cost ({land_cost_per_sqm/1e6:,.1f} mn VND/m²)\n"
                f"─────────────────────\n"
                f"Total Project Cost: {total_project_cost/1e9:,.1f} bn VND\n"
                f"Debt Financing: {debt_financing_pct*100:.0f}%\n"
                f"─────────────────────\n"
                f"Default Total Debt: {default_total_debt_bn:,.1f} bn VND\n"
                f"  = {total_project_cost/1e9:,.1f} bn × {debt_financing_pct*100:.0f}%\n\n"
                f"Enter debt amount in billions VND (e.g., 500 for 500 billion VND)"
            )
            
            total_debt_bn_input = decimal_input(
                label="Total Debt (VND bn)",
                value=existing_total_debt_bn,
                min_value=0.0,
                key="edit_total_debt",
                label_visibility="collapsed",
                help=tooltip_text
            )
            
            # Convert back to raw VND for storage and calculations
            total_debt = int(total_debt_bn_input * 1_000_000_000)
            
            # Show the default calculation for reference
            if abs(total_debt_bn_input - default_total_debt_bn) > 0.1:  # If user has modified from default
                st.caption(f"📝 Default: {default_total_debt_bn:,.1f} bn VND (Construction + Land) × {debt_financing_pct*100:.0f}%")
        st.session_state.edited_project['total_debt'] = total_debt
    
    def render_project_timeline(self, project_data):
        """Render project timeline editor"""
        st.subheader("Project Timeline")
        
        # Create a unique key prefix for this project to avoid caching issues
        project_name = project_data.get('project_name', '')
        key_prefix = f"{project_name}_" if project_name else "new_"
        
        # Each field on its own row with label and input side by side
        
        # Land Payment Period - moved to top
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Land Payment Period**")
        with col2:
            current_year = datetime.now().year
            min_year = current_year - 15
            max_year = current_year + 15
            
            # Get default values - check for new fields first, fallback to old single year
            land_start_val = project_data.get('land_payment_start_year')
            land_years_val = project_data.get('land_payment_years')
            
            if land_start_val is not None and not pd.isna(land_start_val) and land_years_val is not None and not pd.isna(land_years_val):
                # New multi-year format with valid values
                default_start = int(land_start_val)
                default_duration = int(land_years_val)
                default_end = default_start + default_duration - 1
            else:
                # Old single year format or missing data - convert to period
                old_land_year_val = project_data.get('land_payment_year')
                if old_land_year_val is not None and not pd.isna(old_land_year_val):
                    default_start = int(old_land_year_val)
                else:
                    # Fallback to construction start year or current year
                    const_start_val = project_data.get('construction_start_year')
                    if const_start_val is not None and not pd.isna(const_start_val):
                        default_start = int(const_start_val)
                    else:
                        default_start = current_year
                default_end = default_start  # Single year payment
            
            # Ensure defaults are within range
            if default_start < min_year:
                default_start = min_year
            elif default_start > max_year:
                default_start = max_year
                
            if default_end < min_year:
                default_end = min_year
            elif default_end > max_year:
                default_end = max_year
                
            # Ensure end is not before start
            if default_end < default_start:
                default_end = default_start
            
            land_payment_period = st.slider(
                "Land Payment Period",
                min_value=min_year,
                max_value=max_year,
                value=(default_start, default_end),
                step=1,
                format="%d",
                key="edit_land_payment_period",
                label_visibility="collapsed",
                help=f"Select land payment start and end years (Range: {min_year} - {max_year})"
            )
            
            land_start = land_payment_period[0]
            land_end = land_payment_period[1]
            land_years = max(1, land_end - land_start + 1)  # Calculate duration
            
            # Display the calculated duration
            st.caption(f"Duration: {land_years} year{'s' if land_years > 1 else ''} ({land_start} - {land_end})")
        
        # Store both new fields and keep old field for backwards compatibility
        st.session_state.edited_project['land_payment_start_year'] = land_start
        st.session_state.edited_project['land_payment_years'] = land_years
        st.session_state.edited_project['land_payment_year'] = land_start  # Keep for backwards compatibility
        
        # Construction Period (Start and End Year)
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Construction Period**")
        with col2:
            current_year = datetime.now().year
            min_year = current_year - 15
            max_year = current_year + 15
            
            # Get default values
            default_start = int(project_data.get('construction_start_year', current_year) or current_year)
            default_duration = int(project_data.get('construction_years', 1) or 1)
            default_end = default_start + default_duration - 1
            
            # Ensure defaults are within range
            if default_start < min_year:
                default_start = min_year
            elif default_start > max_year:
                default_start = max_year
                
            if default_end < min_year:
                default_end = min_year
            elif default_end > max_year:
                default_end = max_year
                
            # Ensure end is not before start
            if default_end < default_start:
                default_end = default_start
            
            construction_period = st.slider(
                "Construction Period",
                min_value=min_year,
                max_value=max_year,
                value=(default_start, default_end),
                step=1,
                format="%d",
                key="edit_const_period",
                label_visibility="collapsed",
                help=f"Select construction start and end years (Range: {min_year} - {max_year})"
            )
            
            const_start = construction_period[0]
            const_end = construction_period[1]
            const_years = max(1, const_end - const_start + 1)  # Calculate duration
            
            # Display the calculated duration
            st.caption(f"Duration: {const_years} year{'s' if const_years > 1 else ''} ({const_start} - {const_end})")
        
        st.session_state.edited_project['construction_start_year'] = const_start
        st.session_state.edited_project['construction_years'] = const_years
        
        # Sales Period (Start and End Year)
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Sales Period**")
        with col2:
            current_year = datetime.now().year
            min_year = current_year - 15
            max_year = current_year + 15
            
            # Get default values
            default_sales_start = int(project_data.get('sale_start_year', current_year) or current_year)
            default_sales_duration = int(project_data.get('sales_years', 3) or 3)
            default_sales_end = default_sales_start + default_sales_duration - 1
            
            # Ensure defaults are within range
            if default_sales_start < min_year:
                default_sales_start = min_year
            elif default_sales_start > max_year:
                default_sales_start = max_year
                
            if default_sales_end < min_year:
                default_sales_end = min_year
            elif default_sales_end > max_year:
                default_sales_end = max_year
                
            # Ensure end is not before start
            if default_sales_end < default_sales_start:
                default_sales_end = default_sales_start
            
            sales_period = st.slider(
                "Sales Period",
                min_value=min_year,
                max_value=max_year,
                value=(default_sales_start, default_sales_end),
                step=1,
                format="%d",
                key="edit_sales_period",
                label_visibility="collapsed",
                help=f"Select sales start and end years (Range: {min_year} - {max_year})"
            )
            
            sales_start = sales_period[0]
            sales_end = sales_period[1]
            sales_years = max(1, sales_end - sales_start + 1)  # Calculate duration
            
            # Display the calculated duration
            st.caption(f"Duration: {sales_years} year{'s' if sales_years > 1 else ''} ({sales_start} - {sales_end})")
        
        # Store using existing variable names
        st.session_state.edited_project['sale_start_year'] = sales_start
        st.session_state.edited_project['sales_years'] = sales_years
        
        # Revenue Booking Period (Start to Completion)
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Revenue Booking Period**")
            st.caption("(Start to Project Completion)")
        with col2:
            current_year = datetime.now().year
            min_year = current_year - 15
            max_year = current_year + 15
            
            # Get default values
            default_revenue_start = int(project_data.get('revenue_booking_start_year', current_year + 1) or current_year + 1)
            default_completion = int(project_data.get('project_completion_year', current_year + 3) or current_year + 3)
            
            # Ensure defaults are within range
            if default_revenue_start < min_year:
                default_revenue_start = min_year
            elif default_revenue_start > max_year:
                default_revenue_start = max_year
                
            if default_completion < min_year:
                default_completion = min_year
            elif default_completion > max_year:
                default_completion = max_year
                
            # Ensure completion is not before start
            if default_completion < default_revenue_start:
                default_completion = default_revenue_start
            
            revenue_booking_period = st.slider(
                "Revenue Booking Period",
                min_value=min_year,
                max_value=max_year,
                value=(default_revenue_start, default_completion),
                step=1,
                format="%d",
                key="edit_revenue_booking_period",
                label_visibility="collapsed",
                help=f"Select revenue booking start year and project completion year (Range: {min_year} - {max_year})"
            )
            
            revenue_start = revenue_booking_period[0]
            completion_year = revenue_booking_period[1]
            revenue_booking_years = max(1, completion_year - revenue_start + 1)  # Calculate duration
            
            # Display the calculated duration
            st.caption(f"Duration: {revenue_booking_years} year{'s' if revenue_booking_years > 1 else ''} ({revenue_start} - {completion_year})")
        
        # Store using existing variable names
        st.session_state.edited_project['revenue_booking_start_year'] = revenue_start
        st.session_state.edited_project['project_completion_year'] = completion_year
        
        # Financial Parameters Section
        st.markdown("---")
        st.markdown("### Financial Parameters (from Assumptions)")
        
        # Load assumptions once for all financial parameters
        from utils.mongodb_utils import load_assumptions_from_mongodb
        company_ticker = project_data.get('company_ticker', '')
        assumptions = load_assumptions_from_mongodb(company_ticker)
        
        # Helper function to get assumption value
        # Note: Assumptions are stored with Category, Type, Item, Value fields
        def get_assumption_value(assumptions, item_name, default_decimal):
            if assumptions:
                for assumption in assumptions:
                    # Check if this is a Financial category entry with the matching Item name
                    if (assumption.get('Category') == 'Financial' and 
                        assumption.get('Item') == item_name):
                        try:
                            # Value is stored in percentage (e.g., 12 for 12%), convert to decimal
                            value = float(assumption.get('Value', 0))
                            # Convert percentage to decimal (12 -> 0.12)
                            return value / 100
                        except (ValueError, TypeError):
                            return default_decimal
            return default_decimal
        
        # WACC Rate - loaded from Assumptions (non-editable)
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**WACC Rate (%)**")
        with col2:
            # Get WACC from assumptions
            wacc_decimal = get_assumption_value(assumptions, 'WACC', 0.0)
            wacc_percentage = wacc_decimal * 100
            
            # Display as disabled text input
            st.text_input(
                "WACC Rate (%)",
                value=f"{wacc_percentage:.1f}%",
                disabled=True,
                key="wacc_display",
                label_visibility="collapsed",
                help="To edit this value, go to the Assumptions tab"
            )
        st.session_state.edited_project['wacc_rate'] = wacc_decimal
        
        # SG&A Percentage - loaded from Assumptions (non-editable)
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**SG&A (% of Revenue)**")
        with col2:
            # Get SG&A from assumptions - company-wide SG&A stored as Financial category
            sga_decimal = get_assumption_value(assumptions, 'SG&A % of Revenue', 0.0)
            sga_percentage = sga_decimal * 100
            
            # Display as disabled text input
            st.text_input(
                "SG&A (% of Revenue)",
                value=f"{sga_percentage:.1f}%",
                disabled=True,
                key="sga_display",
                label_visibility="collapsed",
                help="To edit this value, go to the Assumptions tab"
            )
        st.session_state.edited_project['sga_percentage'] = sga_decimal
        
        # Debt Financing % - loaded from Assumptions (non-editable)
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Debt Financing (% of project)**")
        with col2:
            # Get debt financing from assumptions (stored as percentage like others)
            debt_financing_decimal = get_assumption_value(assumptions, 'Debt Financing %', 0.0)
            debt_financing_percentage = debt_financing_decimal * 100
            
            # Display as disabled text input
            st.text_input(
                "Debt Financing (%)",
                value=f"{debt_financing_percentage:.1f}%",
                disabled=True,
                key="debt_financing_display",
                label_visibility="collapsed",
                help="To edit this value, go to the Assumptions tab"
            )
        st.session_state.edited_project['debt_financing_pct'] = debt_financing_decimal
        
        # Cost of Debt - loaded from Assumptions (non-editable)
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Cost of Debt (%)**")
        with col2:
            # Get cost of debt from assumptions
            cost_of_debt_decimal = get_assumption_value(assumptions, 'Cost of Debts', 0.0)
            cost_of_debt_percentage = cost_of_debt_decimal * 100
            
            # Display as disabled text input
            st.text_input(
                "Cost of Debt (%)",
                value=f"{cost_of_debt_percentage:.1f}%",
                disabled=True,
                key="cost_of_debt_display",
                label_visibility="collapsed",
                help="To edit this value, go to the Assumptions tab"
            )
        st.session_state.edited_project['cost_of_debt'] = cost_of_debt_decimal
    
    def render_revenue_distribution_editor(self, project_data):
        """Render revenue distribution editor with year-by-year percentages for low-rise and high-rise"""
        st.subheader("Revenue Distribution Schedule")
        st.info("Enter percentage of revenue to recognize in each year for Low-Rise and High-Rise units. Each must sum to 100%.")
        
        # Create a unique key prefix for this project to avoid caching issues
        project_name = project_data.get('project_name', '')
        key_prefix = f"{project_name}_" if project_name else "new_"
        
        # Get timeline parameters from edited project
        revenue_start = st.session_state.edited_project.get('revenue_booking_start_year', 
                                                             project_data.get('revenue_booking_start_year', datetime.now().year) or datetime.now().year)
        revenue_end = st.session_state.edited_project.get('project_completion_year',
                                                          project_data.get('project_completion_year', datetime.now().year + 3) or datetime.now().year + 3)
        
        # Create input fields for each year
        years = list(range(int(revenue_start), int(revenue_end) + 1))
        
        # Get values from edited project
        edited = st.session_state.edited_project
        
        # Calculate total revenue for each type using presales booking
        price_increment = float(edited.get('price_increment_factor', 0) or 0)
        
        # Get presales timeline for revenue calculation
        presales_start = int(edited.get('sale_start_year', 2025) or 2025)
        sales_years = int(edited.get('sales_years', 3) or 3)
        presales_end = presales_start + sales_years - 1
        presales_years = list(range(presales_start, presales_end + 1))
        
        # Calculate low-rise total revenue
        low_rise_nsa = float(edited.get('low_rise_nsa', 0) or 0)
        low_rise_asp = float(edited.get('low_rise_asp', 0) or 0)
        low_rise_presales_dist = edited.get('low_rise_presales_distribution', {})
        
        total_low_revenue = 0
        if low_rise_presales_dist:
            for i, year in enumerate(presales_years):
                year_pct = low_rise_presales_dist.get(str(year), 0) / 100
                year_nsa = low_rise_nsa * year_pct
                year_asp = low_rise_asp * (1 + price_increment) ** i
                total_low_revenue += year_nsa * year_asp / 1e9
        
        # Calculate high-rise total revenue
        high_rise_nsa = float(edited.get('high_rise_nsa', 0) or 0)
        high_rise_asp = float(edited.get('high_rise_asp', 0) or 0)
        high_rise_presales_dist = edited.get('high_rise_presales_distribution', {})
        
        total_high_revenue = 0
        if high_rise_presales_dist:
            for i, year in enumerate(presales_years):
                year_pct = high_rise_presales_dist.get(str(year), 0) / 100
                year_nsa = high_rise_nsa * year_pct
                year_asp = high_rise_asp * (1 + price_increment) ** i
                total_high_revenue += year_nsa * year_asp / 1e9
        
        # Create tabs for Low-Rise and High-Rise
        tab_low, tab_high, tab_combined = st.tabs(["Low-Rise Distribution", "High-Rise Distribution", "Combined View"])
        
        with tab_low:
            st.markdown("### Low-Rise Revenue Distribution")
            st.metric("Total Low-Rise Revenue", f"{total_low_revenue:.1f}B VND")
            
            # Get existing low-rise distribution
            existing_low_dist = edited.get('low_rise_revenue_distribution',
                                          project_data.get('low_rise_revenue_distribution', {}))
            if not isinstance(existing_low_dist, dict):
                existing_low_dist = {}
            
            # If no existing distribution, create even split
            if not existing_low_dist:
                for year in years:
                    existing_low_dist[str(year)] = 100.0 / len(years) if len(years) > 0 else 100.0
            
            low_rise_distribution = {}
            
            cols = st.columns(min(len(years), 4))
            for i, year in enumerate(years):
                col_idx = i % len(cols)
                with cols[col_idx]:
                    widget_key = f"{key_prefix}low_revenue_dist_{year}"
                    default_val = existing_low_dist.get(str(year), 100.0/len(years))
                    
                    pct = percentage_input(
                        label=f"Year {year} (%)",
                        value=float(default_val),
                        max_value=100.0,
                        key=widget_key,
                        help=f"Percentage of revenue to recognize in {year}"
                    )
                    low_rise_distribution[str(year)] = pct
                    
                    # Display calculated value
                    year_revenue = total_low_revenue * pct / 100
                    st.caption(f"Value: {year_revenue:.1f}B VND")
            
            # Validate percentages
            total_pct = sum(low_rise_distribution.values())
            if abs(total_pct - 100.0) < 0.01:
                st.success(f"✅ Total: {total_pct:.1f}%")
            else:
                st.error(f"❌ Total: {total_pct:.1f}% (must be 100%)")
            
            st.session_state.edited_project['low_rise_revenue_distribution'] = low_rise_distribution
        
        with tab_high:
            st.markdown("### High-Rise Revenue Distribution")
            st.metric("Total High-Rise Revenue", f"{total_high_revenue:.1f}B VND")
            
            # Get existing high-rise distribution
            existing_high_dist = edited.get('high_rise_revenue_distribution',
                                           project_data.get('high_rise_revenue_distribution', {}))
            if not isinstance(existing_high_dist, dict):
                existing_high_dist = {}
            
            # If no existing distribution, create even split
            if not existing_high_dist:
                for year in years:
                    existing_high_dist[str(year)] = 100.0 / len(years) if len(years) > 0 else 100.0
            
            high_rise_distribution = {}
            
            cols = st.columns(min(len(years), 4))
            for i, year in enumerate(years):
                col_idx = i % len(cols)
                with cols[col_idx]:
                    widget_key = f"{key_prefix}high_revenue_dist_{year}"
                    default_val = existing_high_dist.get(str(year), 100.0/len(years))
                    
                    pct = percentage_input(
                        label=f"Year {year} (%)",
                        value=float(default_val),
                        max_value=100.0,
                        key=widget_key,
                        help=f"Percentage of revenue to recognize in {year}"
                    )
                    high_rise_distribution[str(year)] = pct
                    
                    # Display calculated value
                    year_revenue = total_high_revenue * pct / 100
                    st.caption(f"Value: {year_revenue:.1f}B VND")
            
            # Validate percentages
            total_pct = sum(high_rise_distribution.values())
            if abs(total_pct - 100.0) < 0.01:
                st.success(f"✅ Total: {total_pct:.1f}%")
            else:
                st.error(f"❌ Total: {total_pct:.1f}% (must be 100%)")
            
            st.session_state.edited_project['high_rise_revenue_distribution'] = high_rise_distribution
        
        with tab_combined:
            st.markdown("### Combined Revenue View")
            
            # Calculate combined revenue for each year
            combined_distribution = {}
            combined_values = []
            
            for year in years:
                # Low-rise for this year
                low_pct = low_rise_distribution.get(str(year), 0) / 100
                low_year_value = total_low_revenue * low_pct
                
                # High-rise for this year
                high_pct = high_rise_distribution.get(str(year), 0) / 100
                high_year_value = total_high_revenue * high_pct
                
                # Combined
                combined_value = low_year_value + high_year_value
                combined_values.append(combined_value)
                
                # Calculate combined percentage (for backward compatibility)
                total_revenue = total_low_revenue + total_high_revenue
                if total_revenue > 0:
                    combined_pct = (combined_value / total_revenue) * 100
                else:
                    combined_pct = 0
                combined_distribution[str(year)] = combined_pct
            
            # Display combined chart
            if years and combined_values:
                import plotly.graph_objects as go
                
                fig = go.Figure()
                
                # Add low-rise bars
                low_values = []
                for year in years:
                    low_pct = low_rise_distribution.get(str(year), 0) / 100
                    low_values.append(total_low_revenue * low_pct)
                
                # Add high-rise bars
                high_values = []
                for year in years:
                    high_pct = high_rise_distribution.get(str(year), 0) / 100
                    high_values.append(total_high_revenue * high_pct)
                
                fig.add_trace(go.Bar(
                    x=years,
                    y=low_values,
                    name='Low-Rise',
                    marker_color='lightgreen',
                    text=[f'{v:.1f}B' for v in low_values],
                    textposition='inside'
                ))
                
                fig.add_trace(go.Bar(
                    x=years,
                    y=high_values,
                    name='High-Rise',
                    marker_color='darkgreen',
                    text=[f'{v:.1f}B' for v in high_values],
                    textposition='inside'
                ))
                
                fig.update_layout(
                    title="Combined Revenue Recognition (Billion VND)",
                    xaxis_title="Year",
                    yaxis_title="Revenue (Billion VND)",
                    barmode='stack',
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            # Display totals
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Low-Rise Total", f"{total_low_revenue:.1f}B VND")
            with col2:
                st.metric("High-Rise Total", f"{total_high_revenue:.1f}B VND")
            with col3:
                total_combined = total_low_revenue + total_high_revenue
                st.metric("Combined Total", f"{total_combined:.1f}B VND")
            
            # Store combined distribution for backward compatibility
            st.session_state.edited_project['revenue_distribution'] = combined_distribution
    
    def render_presales_distribution_editor(self, project_data):
        """Render presales distribution editor with year-by-year percentages for low-rise and high-rise"""
        st.subheader("Presales Distribution Schedule")
        st.info("Enter percentage of sales to achieve in each year for Low-Rise and High-Rise units. Each must sum to 100%.")
        
        # Create a unique key prefix for this project to avoid caching issues
        project_name = project_data.get('project_name', '')
        key_prefix = f"{project_name}_" if project_name else "new_"
        
        # Get timeline parameters from edited project
        sales_start = st.session_state.edited_project.get('sale_start_year',
                                                          project_data.get('sale_start_year', datetime.now().year) or datetime.now().year)
        sales_years = st.session_state.edited_project.get('sales_years',
                                                          project_data.get('sales_years', 3) or 3)
        sales_end = int(sales_start or datetime.now().year) + int(sales_years or 3) - 1
        
        # Create input fields for each year
        years = list(range(int(sales_start), int(sales_end) + 1))
        
        # Get values from edited project
        edited = st.session_state.edited_project
        price_increment = float(edited.get('price_increment_factor', 0) or 0)
        
        # Low-Rise values
        low_rise_nsa = float(edited.get('low_rise_nsa', 0) or 0)
        low_rise_asp = float(edited.get('low_rise_asp', 0) or 0)
        low_rise_units = float(edited.get('low_rise_units', 0) or 0)
        
        # High-Rise values
        high_rise_nsa = float(edited.get('high_rise_nsa', 0) or 0)
        high_rise_asp = float(edited.get('high_rise_asp', 0) or 0)
        high_rise_units = float(edited.get('high_rise_units', 0) or 0)
        
        # Create tabs for Low-Rise and High-Rise
        tab_low, tab_high, tab_combined = st.tabs(["Low-Rise Distribution", "High-Rise Distribution", "Combined View"])
        
        with tab_low:
            st.markdown("### Low-Rise Presales Distribution")
            
            # Get existing low-rise distribution
            existing_low_dist = edited.get('low_rise_presales_distribution', 
                                          project_data.get('low_rise_presales_distribution', {}))
            if not isinstance(existing_low_dist, dict):
                existing_low_dist = {}
            
            # If no existing distribution, create even split
            if not existing_low_dist:
                for year in years:
                    existing_low_dist[str(year)] = 100.0 / len(years) if len(years) > 0 else 100.0
            
            low_rise_distribution = {}
            
            cols = st.columns(min(len(years), 4))
            for i, year in enumerate(years):
                col_idx = i % len(cols)
                with cols[col_idx]:
                    widget_key = f"{key_prefix}low_presales_dist_{year}"
                    default_val = existing_low_dist.get(str(year), 100.0/len(years))
                    
                    pct = percentage_input(
                        label=f"Year {year} (%)",
                        value=float(default_val),
                        max_value=100.0,
                        key=widget_key,
                        help=f"Percentage of revenue to recognize in {year}"
                    )
                    low_rise_distribution[str(year)] = pct
                    
                    # Display calculated values
                    units_for_year = int(low_rise_units * pct / 100)
                    year_nsa = low_rise_nsa * pct / 100
                    year_asp_adjusted = low_rise_asp * (1 + price_increment) ** i
                    year_presales = year_nsa * year_asp_adjusted / 1e9
                    
                    st.caption(f"Units: {units_for_year:,}")
                    st.caption(f"Value: {year_presales:.1f}B VND")
                    if price_increment > 0:
                        st.caption(f"ASP: {year_asp_adjusted/1e6:.1f}M VND/m²")
            
            # Calculate total low-rise presales
            total_low_presales = 0
            for i, year in enumerate(years):
                year_pct = low_rise_distribution.get(str(year), 0) / 100
                year_nsa = low_rise_nsa * year_pct
                year_asp = low_rise_asp * (1 + price_increment) ** i
                total_low_presales += year_nsa * year_asp / 1e9
            
            st.metric("Total Low-Rise Presales", f"{total_low_presales:.1f}B VND")
            
            # Validate percentages
            total_pct = sum(low_rise_distribution.values())
            if abs(total_pct - 100.0) < 0.01:
                st.success(f"✅ Total: {total_pct:.1f}%")
            else:
                st.error(f"❌ Total: {total_pct:.1f}% (must be 100%)")
            
            st.session_state.edited_project['low_rise_presales_distribution'] = low_rise_distribution
        
        with tab_high:
            st.markdown("### High-Rise Presales Distribution")
            
            # Get existing high-rise distribution
            existing_high_dist = edited.get('high_rise_presales_distribution',
                                           project_data.get('high_rise_presales_distribution', {}))
            if not isinstance(existing_high_dist, dict):
                existing_high_dist = {}
            
            # If no existing distribution, create even split
            if not existing_high_dist:
                for year in years:
                    existing_high_dist[str(year)] = 100.0 / len(years) if len(years) > 0 else 100.0
            
            high_rise_distribution = {}
            
            cols = st.columns(min(len(years), 4))
            for i, year in enumerate(years):
                col_idx = i % len(cols)
                with cols[col_idx]:
                    widget_key = f"{key_prefix}high_presales_dist_{year}"
                    default_val = existing_high_dist.get(str(year), 100.0/len(years))
                    
                    pct = percentage_input(
                        label=f"Year {year} (%)",
                        value=float(default_val),
                        max_value=100.0,
                        key=widget_key,
                        help=f"Percentage of revenue to recognize in {year}"
                    )
                    high_rise_distribution[str(year)] = pct
                    
                    # Display calculated values
                    units_for_year = int(high_rise_units * pct / 100)
                    year_nsa = high_rise_nsa * pct / 100
                    year_asp_adjusted = high_rise_asp * (1 + price_increment) ** i
                    year_presales = year_nsa * year_asp_adjusted / 1e9
                    
                    st.caption(f"Units: {units_for_year:,}")
                    st.caption(f"Value: {year_presales:.1f}B VND")
                    if price_increment > 0:
                        st.caption(f"ASP: {year_asp_adjusted/1e6:.1f}M VND/m²")
            
            # Calculate total high-rise presales
            total_high_presales = 0
            for i, year in enumerate(years):
                year_pct = high_rise_distribution.get(str(year), 0) / 100
                year_nsa = high_rise_nsa * year_pct
                year_asp = high_rise_asp * (1 + price_increment) ** i
                total_high_presales += year_nsa * year_asp / 1e9
            
            st.metric("Total High-Rise Presales", f"{total_high_presales:.1f}B VND")
            
            # Validate percentages
            total_pct = sum(high_rise_distribution.values())
            if abs(total_pct - 100.0) < 0.01:
                st.success(f"✅ Total: {total_pct:.1f}%")
            else:
                st.error(f"❌ Total: {total_pct:.1f}% (must be 100%)")
            
            st.session_state.edited_project['high_rise_presales_distribution'] = high_rise_distribution
        
        with tab_combined:
            st.markdown("### Combined Presales View")
            
            # Calculate combined presales for each year
            combined_distribution = {}
            combined_values = []
            
            for i, year in enumerate(years):
                # Low-rise for this year
                low_pct = low_rise_distribution.get(str(year), 0) / 100
                low_year_nsa = low_rise_nsa * low_pct
                low_year_asp = low_rise_asp * (1 + price_increment) ** i
                low_year_value = low_year_nsa * low_year_asp / 1e9
                
                # High-rise for this year
                high_pct = high_rise_distribution.get(str(year), 0) / 100
                high_year_nsa = high_rise_nsa * high_pct
                high_year_asp = high_rise_asp * (1 + price_increment) ** i
                high_year_value = high_year_nsa * high_year_asp / 1e9
                
                # Combined
                combined_value = low_year_value + high_year_value
                combined_values.append(combined_value)
                
                # Calculate combined percentage (for backward compatibility)
                total_nsa = low_rise_nsa + high_rise_nsa
                if total_nsa > 0:
                    combined_nsa = low_year_nsa + high_year_nsa
                    combined_pct = (combined_nsa / total_nsa) * 100
                else:
                    combined_pct = 0
                combined_distribution[str(year)] = combined_pct
            
            # Display combined chart
            if years and combined_values:
                import plotly.graph_objects as go
                
                fig = go.Figure()
                
                # Add low-rise bars
                low_values = []
                for i, year in enumerate(years):
                    low_pct = low_rise_distribution.get(str(year), 0) / 100
                    low_year_nsa = low_rise_nsa * low_pct
                    low_year_asp = low_rise_asp * (1 + price_increment) ** i
                    low_values.append(low_year_nsa * low_year_asp / 1e9)
                
                # Add high-rise bars
                high_values = []
                for i, year in enumerate(years):
                    high_pct = high_rise_distribution.get(str(year), 0) / 100
                    high_year_nsa = high_rise_nsa * high_pct
                    high_year_asp = high_rise_asp * (1 + price_increment) ** i
                    high_values.append(high_year_nsa * high_year_asp / 1e9)
                
                fig.add_trace(go.Bar(
                    x=years,
                    y=low_values,
                    name='Low-Rise',
                    marker_color='lightblue',
                    text=[f'{v:.1f}B' for v in low_values],
                    textposition='inside'
                ))
                
                fig.add_trace(go.Bar(
                    x=years,
                    y=high_values,
                    name='High-Rise',
                    marker_color='darkblue',
                    text=[f'{v:.1f}B' for v in high_values],
                    textposition='inside'
                ))
                
                fig.update_layout(
                    title="Combined Presales Distribution (Billion VND)",
                    xaxis_title="Year",
                    yaxis_title="Presales (Billion VND)",
                    barmode='stack',
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            # Display totals
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Low-Rise Total", f"{total_low_presales:.1f}B VND")
            with col2:
                st.metric("High-Rise Total", f"{total_high_presales:.1f}B VND")
            with col3:
                total_combined = total_low_presales + total_high_presales
                st.metric("Combined Total", f"{total_combined:.1f}B VND")
            
            # Store combined distribution for backward compatibility
            st.session_state.edited_project['presales_distribution'] = combined_distribution
            
            # Calculate combined total for validation
            total_combined_presales = total_low_presales + total_high_presales
            
            # Show cash collection schedule based on tranche logic
            # Note: Cash collection schedule has been moved to its own section
            # The actual implementation is now in render_cash_collection_schedule() method
    def render_cash_collection_schedule(self, project_data):
        """Render cash collection schedule section (separated from presales distribution)"""
        st.subheader("Actual Cash Collection Schedule")
        #st.info("Define cash collection percentages for each presale year. This schedule determines when cash is actually collected from presales bookings.")
        
        # Create a unique key prefix for this project to avoid caching issues
        project_name = project_data.get('project_name', '')
        key_prefix = f"{project_name}_" if project_name else "new_"
        
        # Get edited project data
        edited = st.session_state.edited_project
        
        # Get unit information
        low_rise_nsa = float(edited.get('low_rise_nsa', 0) or 0)
        low_rise_asp = float(edited.get('low_rise_asp', 0) or 0)
        high_rise_nsa = float(edited.get('high_rise_nsa', 0) or 0)
        high_rise_asp = float(edited.get('high_rise_asp', 0) or 0)
        
        # Get price increment
        price_increment = float(edited.get('price_increment_factor', 0) or 0)
        
        # Get presales distributions
        low_rise_distribution = edited.get('low_rise_presales_distribution', {})
        high_rise_distribution = edited.get('high_rise_presales_distribution', {})
        
        # Get timeline parameters
        sales_start = edited.get('sale_start_year', datetime.now().year)
        sales_years = edited.get('sales_years', 3)
        sales_end = int(sales_start or datetime.now().year) + int(sales_years or 3) - 1
        years = list(range(int(sales_start), sales_end + 1))
        
        # Calculate total combined presales
        total_combined_presales = 0
        for i, year in enumerate(years):
            low_pct = low_rise_distribution.get(str(year), 0) / 100
            low_year_nsa = low_rise_nsa * low_pct
            low_year_asp = low_rise_asp * (1 + price_increment) ** i
            low_year_value = low_year_nsa * low_year_asp / 1e9
            
            high_pct = high_rise_distribution.get(str(year), 0) / 100
            high_year_nsa = high_rise_nsa * high_pct
            high_year_asp = high_rise_asp * (1 + price_increment) ** i
            high_year_value = high_year_nsa * high_year_asp / 1e9
            
            total_combined_presales += low_year_value + high_year_value
        
        # Check if distributions are valid
        low_total_pct = sum(low_rise_distribution.values())
        high_total_pct = sum(high_rise_distribution.values())
        
        if abs(low_total_pct - 100.0) > 0.01 or abs(high_total_pct - 100.0) > 0.01:
            st.warning("⚠️ Please ensure both Low-Rise and High-Rise presales distributions sum to 100% before defining cash collection schedule.")
            return
        
        if total_combined_presales <= 0:
            st.warning("⚠️ No presales to schedule cash collection for. Please define presales distributions first.")
            return
        
        # Get project timeline
        const_start = edited.get('construction_start_year', datetime.now().year)
        const_years = edited.get('construction_years', 3)
        
        if not const_start or not const_years:
            st.error("⚠️ Construction Start Year and Construction Years are required to calculate cash collection schedule. Please set them in the Project Timeline section.")
            return
        
        # Calculate construction end year for reference
        construction_end = int(const_start) + int(const_years) - 1
        
        # First, collect all presale years and amounts
        presales_by_year = {}
        for i, year in enumerate(years):
            low_year_pct = low_rise_distribution.get(str(year), 0) / 100
            low_year_nsa = low_rise_nsa * low_year_pct
            low_year_asp = low_rise_asp * (1 + price_increment) ** i
            low_presale_amount = low_year_nsa * low_year_asp / 1e9
            
            high_year_pct = high_rise_distribution.get(str(year), 0) / 100
            high_year_nsa = high_rise_nsa * high_year_pct
            high_year_asp = high_rise_asp * (1 + price_increment) ** i
            high_presale_amount = high_year_nsa * high_year_asp / 1e9
            
            presale_amount = low_presale_amount + high_presale_amount
            if presale_amount > 0:
                presales_by_year[year] = presale_amount
        
        # Create UI for collection percentage inputs
        #st.markdown("#### Define Cash Collection Schedule (Relative to Presale Year)")
        st.info("This schedule will apply to ALL presales. Year 1 = presale year, Year 2 = presale year + 1, etc.")
        
        # Initialize relative collection schedule with project-specific key
        collection_key = f"{key_prefix}relative_collection_schedule"
        if collection_key not in st.session_state:
            saved_schedule = edited.get('relative_collection_schedule', {})
            if saved_schedule:
                st.session_state[collection_key] = saved_schedule
            else:
                # Default: 30% in year 1, 70% spread over years 2-3
                st.session_state[collection_key] = {
                    1: 30.0,  # Year 1 (presale year)
                    2: 35.0,  # Year 2 
                    3: 35.0,  # Year 3
                    4: 0.0,   # Year 4
                    5: 0.0    # Year 5
                }
        
        # Create exactly 5 columns for the 5 year inputs
        cols = st.columns(5)
        relative_schedule = {}
        
        for relative_year in range(1, 6):  # 1 to 5
            col_idx = relative_year - 1
            current_pct = st.session_state[collection_key].get(relative_year, 0.0)
            
            with cols[col_idx]:
                pct = percentage_input(
                    label=f"Year {relative_year}",
                    value=float(current_pct),
                    max_value=100.0,
                    key=f"{key_prefix}collect_relative_year_{relative_year}",
                    help=f"% collected in year {relative_year} after presale"
                )
                relative_schedule[relative_year] = pct
        
        # Validate percentages
        total_pct = sum(relative_schedule.values())
        if abs(total_pct - 100.0) > 0.01:
            st.error(f"❌ Collection percentages sum to {total_pct:.1f}%, must equal 100%")
        else:
            st.success(f"✅ Collection schedule is valid (100%)")
        
        # Store the relative schedule with project-specific key
        st.session_state[collection_key] = relative_schedule
        st.session_state.edited_project['relative_collection_schedule'] = relative_schedule
        
        # Show how this applies to each presale
        if presales_by_year and relative_schedule:
            #st.markdown("##### 📊 Application to Each Presale:")
            
            collection_schedules = {}
            for presale_year, presale_amount in presales_by_year.items():
                #st.markdown(f"**Presales in {presale_year}: {presale_amount:.1f}B VND**")
                
                year_schedule = {}
                #schedule_text = []
                for relative_year, pct in relative_schedule.items():
                    if pct > 0:
                        actual_year = presale_year + relative_year - 1
                        collection_amount = presale_amount * (pct / 100)
                        year_schedule[actual_year] = pct
                        #schedule_text.append(f"  • Year {relative_year} ({actual_year}): {collection_amount:.1f}B VND ({pct:.1f}%)")
                
                #st.markdown("\n".join(schedule_text))
                collection_schedules[presale_year] = year_schedule
            
            # Save schedules
            if collection_schedules:
                st.session_state.edited_project['cash_collection_schedules'] = collection_schedules
            
            # Calculate actual cash collection
            cash_collection = {}
            for presale_year, presale_amount in presales_by_year.items():
                schedule = collection_schedules.get(presale_year, {})
                for col_year, pct in schedule.items():
                    if col_year not in cash_collection:
                        cash_collection[col_year] = 0
                    cash_collection[col_year] += presale_amount * (pct / 100)
            
            # Create visualization
            all_years = sorted(set(years) | set(cash_collection.keys()))
            
            # Calculate presales values for visualization
            presales_values = []
            for y in all_years:
                if y in years:
                    year_idx = years.index(y)
                    
                    low_year_pct = low_rise_distribution.get(str(y), 0) / 100
                    low_year_nsa = low_rise_nsa * low_year_pct
                    low_year_asp = low_rise_asp * (1 + price_increment) ** year_idx
                    low_year_value = low_year_nsa * low_year_asp / 1e9
                    
                    high_year_pct = high_rise_distribution.get(str(y), 0) / 100
                    high_year_nsa = high_rise_nsa * high_year_pct
                    high_year_asp = high_rise_asp * (1 + price_increment) ** year_idx
                    high_year_value = high_year_nsa * high_year_asp / 1e9
                    
                    presales_values.append(low_year_value + high_year_value)
                else:
                    presales_values.append(0)
            
            cash_values = [cash_collection.get(y, 0) for y in all_years]
            
            # Create chart
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                name='Presales Booking',
                x=[str(y) for y in all_years],
                y=presales_values,
                text=[f"{val:.0f}B" if val > 0 else "" for val in presales_values],
                textposition='auto',
                marker_color='lightblue',
                offsetgroup=1
            ))
            
            fig.add_trace(go.Bar(
                name='Cash Collection',
                x=[str(y) for y in all_years],
                y=cash_values,
                text=[f"{val:.0f}B" if val > 0 else "" for val in cash_values],
                textposition='auto',
                marker_color='lightgreen',
                offsetgroup=2
            ))
            
            fig.update_layout(
                title="Presales Booking vs Actual Cash Collection",
                xaxis_title="Year",
                yaxis_title="Amount (Billion VND)",
                barmode='group',
                height=400,
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                hovermode='x unified'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Show totals
            total_presales = sum(presales_values)
            total_cash = sum(cash_collection.values())
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Presales Booking", f"{total_presales:,.1f} Bn VND")
            with col2:
                st.metric("Total Cash Collection", f"{total_cash:,.1f} Bn VND")
            with col3:
                if total_presales > 0:
                    collection_pct = (total_cash / total_presales) * 100
                    st.metric("Collection Rate", f"{collection_pct:.1f}%")
            
            # Detailed table
            #with st.expander("📊 View Detailed Cash Collection Table", expanded=False):
            #    cash_data = []
            #    for year in all_years:
            #        if year in years:
            #            year_idx = years.index(year)
            #            
            #            low_year_pct = low_rise_distribution.get(str(year), 0) / 100
            #            low_year_nsa = low_rise_nsa * low_year_pct
            #            low_year_asp = low_rise_asp * (1 + price_increment) ** year_idx
            #            low_year_value = low_year_nsa * low_year_asp / 1e9
            #            
            #            high_year_pct = high_rise_distribution.get(str(year), 0) / 100
            #            high_year_nsa = high_rise_nsa * high_year_pct
            #            high_year_asp = high_rise_asp * (1 + price_increment) ** year_idx
            #            high_year_value = high_year_nsa * high_year_asp / 1e9
            #            
            #            presale_val = low_year_value + high_year_value
            #        else:
            #            presale_val = 0
            #        
            #        cash_val = cash_collection.get(year, 0)
            #        
            #        cash_data.append({
            #            "Year": str(year),
            #            "Presales Booking": f"{presale_val:,.1f}" if presale_val > 0 else "-",
            #            "Cash Collection": f"{cash_val:,.1f}" if cash_val > 0 else "-",
            #            "Difference": f"{(cash_val - presale_val):+,.1f}" if (presale_val > 0 or cash_val > 0) else "-"
            #        })
            #    
            #    cash_df = pd.DataFrame(cash_data)
            #    st.dataframe(cash_df, hide_index=True, use_container_width=True)
        
    def render_project_financial_summary(self, project_data):
        """Render project financial summary section"""
        st.subheader("Project Financial Summary")
        
        # Create a unique key prefix for this project to avoid caching issues
        project_name = project_data.get('project_name', '')
        key_prefix = f"{project_name}_" if project_name else "new_"
        
        # Get edited project data
        edited = st.session_state.edited_project
        
        # Calculate totals for summary
        nsa = float(edited.get('net_sellable_area', 0) or 0)
        asp = float(edited.get('average_selling_price', 0) or 0)
        gfa = float(edited.get('gross_floor_area', 0) or 0)
        const_cost = float(edited.get('construction_cost_per_sqm', 0) or 0)
        land_area = float(edited.get('land_area', 0) or 0)
        land_cost = float(edited.get('land_cost_per_sqm', 0) or 0)
        
        # Use the consistent calculation method for total revenue
        # Total Revenue = Total Presales Booking = Total Cash Collection
        total_revenue_billions = self.calculate_total_presales_booking(edited)
        total_revenue = total_revenue_billions * 1e9  # Convert back to raw value for calculations
            
        total_const_cost = gfa * const_cost
        total_land_cost = land_area * land_cost
        sga_pct = float(edited.get('sga_percentage', 0.0) or 0.0)
        total_sga = total_revenue * sga_pct
        
        # Get debt and financial parameters
        total_debt = float(edited.get('total_debt', 0) or 0)
        cost_of_debt = float(edited.get('cost_of_debt', 0.08) or 0.08)
        
        # Get timeline parameters
        const_start = int(edited.get('construction_start_year', 2025) or 2025)
        const_years = int(edited.get('construction_years', 3) or 3)
        const_end = const_start + const_years - 1
        
        # Revenue recognition period: from revenue_booking_start_year to project_completion_year
        revenue_booking_start = int(edited.get('revenue_booking_start_year', 2027) or 2027)
        revenue_booking_end = int(edited.get('project_completion_year', revenue_booking_start + 1) or revenue_booking_start + 1)
        
        debt_repayment_start = int(edited.get('debt_repayment_year', revenue_booking_end) or revenue_booking_end)
        
        # Calculate financial metrics
        total_project_cost = total_const_cost + total_land_cost
        total_gross_profit = total_revenue - total_const_cost - total_land_cost
        gross_profit_margin = (total_gross_profit / total_revenue * 100) if total_revenue > 0 else 0
        actual_debt_pct = (total_debt / total_project_cost * 100) if total_project_cost > 0 else 0
        
        # Create summary data with Gross Profit added
        summary_data = {
            "Metric": [
                "Total Revenue",
                "Total Construction Cost",
                "Total Land Cost",
                "Total Gross Profit",
                "Gross Profit Margin (%)",
                "Total SG&A",
                "Total Debt",
                "Debt/Project Ratio",
                "Cost of Debt",
                "Construction Period",
                "Revenue Recognition",
                "Debt Repayment Year"
            ],
            "Value": [
                f"{total_revenue/1e9:,.1f}B VND",
                f"{total_const_cost/1e9:,.1f}B VND",
                f"{total_land_cost/1e9:,.1f}B VND",
                f"{total_gross_profit/1e9:,.1f}B VND",
                f"{gross_profit_margin:.1f}%",
                f"{total_sga/1e9:,.1f}B VND",
                f"{total_debt/1e9:,.1f}B VND",
                f"{actual_debt_pct:.0f}%",
                f"{cost_of_debt*100:.1f}%",
                f"{const_start}-{const_end}",
                f"{revenue_booking_start}-{revenue_booking_end}",
                f"Year {debt_repayment_start}"
            ]
        }
        
        # Display as DataFrame
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True,
            height=460  # Adjusted height for additional rows
        )

    def render_project_balance_sheet_analysis(self, project_data):
        """Render comprehensive financial statements forecast using project data"""
        # Now display Comprehensive Financial Statements Forecast
        st.subheader("Comprehensive Financial Statements Forecast")
        # st.info("💡 **Key Difference**: 'Presales (Bookings)' = contractual sales. 'Cash Inflow (Actual Collection)' = cash received (30% upfront, 70% distributed). Customer Prepayment Balance is based on actual cash received.")
        
        # Import balance sheet manager
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from balance_sheet_manager import generate_simplified_balance_sheet_schedules
        
        # Get all parameters from edited project
        edited = st.session_state.edited_project
        
        # Extract project parameters with proper defaults
        nsa = float(edited.get('net_sellable_area', 0) or 0)
        asp = float(edited.get('average_selling_price', 0) or 0)
        gfa = float(edited.get('gross_floor_area', 0) or 0)
        land_area = float(edited.get('land_area', 0) or 0)
        const_cost = float(edited.get('construction_cost_per_sqm', 0) or 0)
        land_cost = float(edited.get('land_cost_per_sqm', 0) or 0)
        price_increment = float(edited.get('price_increment_factor', 0) or 0)
        
        # Use the consistent calculation method for total revenue
        # Total Revenue = Total Presales Booking = Total Cash Collection
        total_revenue_billions = self.calculate_total_presales_booking(edited)
        total_revenue = total_revenue_billions * 1e9  # Convert back to raw value for calculations
        total_const_cost = gfa * const_cost
        total_land_cost = land_area * land_cost
        sga_pct = float(edited.get('sga_percentage', 0.0) or 0.0)
        total_sga = total_revenue * sga_pct  # Calculate total SG&A
        
        # Get timeline parameters
        const_start = int(edited.get('construction_start_year', 2025) or 2025)
        const_years = int(edited.get('construction_years', 3) or 3)
        const_end = const_start + const_years - 1  # Calculate end year from duration
        
        # Get land payment timeline (support both old and new format)
        if 'land_payment_start_year' in edited and 'land_payment_years' in edited:
            # New multi-year format
            land_payment_start = int(edited.get('land_payment_start_year', const_start) or const_start)
            land_payment_years = int(edited.get('land_payment_years', 1) or 1)
            land_payment_year = land_payment_start  # Keep for backwards compatibility
        else:
            # Old single year format
            land_payment_year = int(edited.get('land_payment_year', const_start) or const_start)
            land_payment_start = land_payment_year
            land_payment_years = 1
        
        # Sales/Presales timeline
        presales_start = int(edited.get('sale_start_year', const_start) or const_start)
        sales_years = int(edited.get('sales_years', 3) or 3)
        presales_end = presales_start + sales_years - 1  # Calculate end year from duration
        
        # Get debt parameters
        # Use total_debt field if available, otherwise calculate from debt financing percentage
        if 'total_debt' in edited and edited['total_debt']:
            total_debt = float(edited['total_debt'])
        else:
            # Fallback to calculation using debt_financing_pct
            total_project_cost = total_const_cost + total_land_cost
            
            # Use debt_financing_pct from assumptions
            if 'debt_financing_pct' in edited and edited['debt_financing_pct']:
                debt_financing_pct = float(edited['debt_financing_pct'])
                total_debt = total_project_cost * debt_financing_pct
            else:
                # Default to 30% debt financing
                total_debt = total_project_cost * 0.3
        
        # Use cost_of_debt instead of interest_rate
        cost_of_debt = float(edited.get('cost_of_debt', 0.08) or 0.08)
        
        # Get revenue recognition timeline
        revenue_booking_start = int(edited.get('revenue_booking_start_year', const_end) or const_end)
        project_completion = int(edited.get('project_completion_year', const_end + 1) or const_end + 1)
        revenue_booking_end = project_completion  # Revenue typically recognized by project completion
        
        # Set debt repayment to occur only in the final year of revenue recognition
        debt_repayment_start = revenue_booking_end  # Repay all debt in final year
        debt_repayment_end = revenue_booking_end    # Single year repayment
        
        # Get distributions - create combined distributions if using low-rise/high-rise
        # For presales distribution
        low_rise_presales_dist = edited.get('low_rise_presales_distribution', {})
        high_rise_presales_dist = edited.get('high_rise_presales_distribution', {})
        
        if low_rise_presales_dist or high_rise_presales_dist:
            # Create combined presales distribution
            presales_dist = {}
            low_rise_nsa = float(edited.get('low_rise_nsa', 0) or 0)
            high_rise_nsa = float(edited.get('high_rise_nsa', 0) or 0)
            total_nsa_calc = low_rise_nsa + high_rise_nsa
            
            if total_nsa_calc > 0:
                years = set()
                if low_rise_presales_dist:
                    years.update(low_rise_presales_dist.keys())
                if high_rise_presales_dist:
                    years.update(high_rise_presales_dist.keys())
                
                for year_str in years:
                    low_pct = low_rise_presales_dist.get(year_str, 0) / 100
                    high_pct = high_rise_presales_dist.get(year_str, 0) / 100
                    
                    combined_nsa = (low_rise_nsa * low_pct) + (high_rise_nsa * high_pct)
                    combined_pct = (combined_nsa / total_nsa_calc) * 100 if total_nsa_calc > 0 else 0
                    presales_dist[year_str] = combined_pct
            else:
                presales_dist = edited.get('presales_distribution', {})
        else:
            # Fallback to combined distribution
            presales_dist = edited.get('presales_distribution', {})
        
        # For revenue distribution
        low_rise_revenue_dist = edited.get('low_rise_revenue_distribution', {})
        high_rise_revenue_dist = edited.get('high_rise_revenue_distribution', {})
        
        if low_rise_revenue_dist or high_rise_revenue_dist:
            # Create combined revenue distribution weighted by revenue amounts
            revenue_dist = {}
            
            # Calculate total revenues for weighting
            low_rise_revenue = 0
            high_rise_revenue = 0
            
            # Calculate low-rise total revenue
            low_rise_nsa = float(edited.get('low_rise_nsa', 0) or 0)
            low_rise_asp = float(edited.get('low_rise_asp', 0) or 0)
            low_rise_presales = edited.get('low_rise_presales_distribution', {})
            
            if low_rise_presales:
                for i, year in enumerate(range(presales_start, presales_end + 1)):
                    year_pct = low_rise_presales.get(str(year), 0) / 100
                    year_nsa = low_rise_nsa * year_pct
                    year_asp = low_rise_asp * (1 + price_increment) ** i
                    low_rise_revenue += year_nsa * year_asp / 1e9
            
            # Calculate high-rise total revenue
            high_rise_nsa = float(edited.get('high_rise_nsa', 0) or 0)
            high_rise_asp = float(edited.get('high_rise_asp', 0) or 0)
            high_rise_presales = edited.get('high_rise_presales_distribution', {})
            
            if high_rise_presales:
                for i, year in enumerate(range(presales_start, presales_end + 1)):
                    year_pct = high_rise_presales.get(str(year), 0) / 100
                    year_nsa = high_rise_nsa * year_pct
                    year_asp = high_rise_asp * (1 + price_increment) ** i
                    high_rise_revenue += year_nsa * year_asp / 1e9
            
            total_combined_revenue = low_rise_revenue + high_rise_revenue
            
            if total_combined_revenue > 0:
                years = set()
                if low_rise_revenue_dist:
                    years.update(low_rise_revenue_dist.keys())
                if high_rise_revenue_dist:
                    years.update(high_rise_revenue_dist.keys())
                
                for year_str in years:
                    low_pct = low_rise_revenue_dist.get(year_str, 0) / 100
                    high_pct = high_rise_revenue_dist.get(year_str, 0) / 100
                    
                    low_year_value = low_rise_revenue * low_pct
                    high_year_value = high_rise_revenue * high_pct
                    combined_value = low_year_value + high_year_value
                    
                    combined_pct = (combined_value / total_combined_revenue) * 100 if total_combined_revenue > 0 else 0
                    revenue_dist[year_str] = combined_pct
            else:
                revenue_dist = edited.get('revenue_distribution', {})
        else:
            # Fallback to combined distribution
            revenue_dist = edited.get('revenue_distribution', {})
        
        # Auto-calculate balance sheet analysis
        # Check if we have minimum required data to run analysis
        if total_revenue >= 0 and (total_const_cost >= 0 or total_land_cost >= 0):
            try:
                # Load assumptions to get tax rate
                from utils.mongodb_utils import load_assumptions_from_mongodb
                company_ticker = edited.get('company_ticker', st.session_state.get('selected_company', ''))
                assumptions = load_assumptions_from_mongodb(company_ticker)
                
                # Get tax rate from assumptions
                tax_rate = 0.0  # Default to 0
                if assumptions:
                    for assumption in assumptions:
                        if assumption.get('Category') == 'Financial' and assumption.get('Item') == 'Tax Rate':
                            try:
                                tax_rate = float(assumption.get('Value', 0)) / 100  # Convert from percentage
                                break
                            except (ValueError, TypeError):
                                pass
                
                # Show warning if tax rate is 0
                if tax_rate == 0:
                    st.warning("⚠️ Tax Rate is 0%. Please set Tax Rate in the Assumptions tab for accurate calculations.")
                
                # Import the main balance sheet function directly to pass presales schedule
                from balance_sheet_manager import generate_balance_sheet_schedules
                
                # Calculate the actual presales schedule combining low-rise and high-rise
                # This ensures consistency with the presales distribution display
                presales_schedule = {}
                for i, year in enumerate(range(presales_start, presales_end + 1)):
                    # Low-rise presales for this year
                    if isinstance(low_rise_presales_dist, dict):
                        low_pct = low_rise_presales_dist.get(str(year), 0) / 100
                    else:
                        low_pct = 0
                    low_year_nsa = float(edited.get('low_rise_nsa', 0) or 0) * low_pct
                    low_year_asp = float(edited.get('low_rise_asp', 0) or 0) * (1 + price_increment) ** i
                    low_presale = low_year_nsa * low_year_asp
                    
                    # High-rise presales for this year
                    if isinstance(high_rise_presales_dist, dict):
                        high_pct = high_rise_presales_dist.get(str(year), 0) / 100
                    else:
                        high_pct = 0
                    high_year_nsa = float(edited.get('high_rise_nsa', 0) or 0) * high_pct
                    high_year_asp = float(edited.get('high_rise_asp', 0) or 0) * (1 + price_increment) ** i
                    high_presale = high_year_nsa * high_year_asp
                    
                    # Combined presales for this year (in raw value, not billions)
                    presales_schedule[year] = low_presale + high_presale
                
                # Convert revenue distribution to the format expected by balance sheet manager
                revenue_dist_converted = None
                if revenue_dist:
                    revenue_dist_converted = {}
                    for year_str, percentage in revenue_dist.items():
                        year = int(year_str)
                        revenue_dist_converted[year] = percentage / 100.0
                
                # Prepare cash collection schedules from relative schedule
                cash_collection_schedules_dict = {}
                relative_schedule = st.session_state.edited_project.get('relative_collection_schedule', {})
                
                if relative_schedule:
                    # Convert relative schedule to absolute year schedules for each presale year
                    for presale_year in range(presales_start, presales_end + 1):
                        year_schedule = {}
                        for relative_year, pct in relative_schedule.items():
                            if pct > 0:
                                actual_year = presale_year + relative_year - 1
                                year_schedule[actual_year] = pct
                        if year_schedule:
                            cash_collection_schedules_dict[presale_year] = year_schedule
                
                # Generate balance sheet schedules with pre-calculated presales
                df = generate_balance_sheet_schedules(
                    total_debt=total_debt,
                    total_construction_cost=total_const_cost,
                    total_land_cost=total_land_cost,
                    land_payment_year=land_payment_year,  # Keep for backwards compatibility
                    land_payment_start_year=land_payment_start,  # New multi-year parameter
                    land_payment_years=land_payment_years,  # New duration parameter
                    presales_schedule=presales_schedule,  # Pass the pre-calculated presales schedule
                    interest_rate=cost_of_debt,
                    sga_percentage=sga_pct,
                    debt_disbursement_start_year=const_start,
                    debt_disbursement_end_year=const_end,
                    debt_repayment_start_year=debt_repayment_start,
                    debt_repayment_end_year=debt_repayment_end,
                    revenue_booking_start_year=revenue_booking_start,
                    revenue_booking_end_year=revenue_booking_end,
                    revenue_distribution=revenue_dist_converted,
                    tax_rate=tax_rate,
                    cash_collection_schedules=cash_collection_schedules_dict if cash_collection_schedules_dict else None
                )
                
                # Format the dataframe for display - exclude Total row
                display_df = df[df['Year'] != 'Total'].copy()
                
                # Convert to billions VND for better readability
                value_columns = [col for col in df.columns if col != 'Year']
                for col in value_columns:
                    if col in display_df.columns:
                        display_df[col] = display_df[col] / 1e9
                
                # Transpose the dataframe
                display_df = display_df.set_index('Year')
                display_df = display_df.T
                
                # Rename index with more readable labels - in the new order
                index_labels = {
                    # Debt section
                    'Debt_Balance': 'Debt Balance',
                    # Cost section
                    'Land_Cost': 'Land Cost',
                    'Construction_Cost': 'Construction Cost',
                    'Interest_Capitalized': 'Interest Capitalized',
                    # Inventory section
                    'Inventory_Addition': 'Inventory Addition',
                    'Inventory_Balance': 'Inventory Balance',
                    # Presales and Revenue section
                    'Cash_Inflow_Presales': 'Actual Presales Cash Collection',
                    'Customer_Prepayment_Balance': 'Customer Prepayment Balance',
                    # P&L section
                    'Revenue_Recognition': 'Revenue (P&L)',
                    'COGS': 'COGS (P&L)',
                    'SGA_Expense': 'SG&A Expense (P&L)',
                    'Interest_Expense_Cash': 'Interest Expense (P&L)',
                    'PBT': 'PBT (P&L)',
                    'Tax': 'Tax (P&L)',
                    'PAT': 'PAT (P&L)',
                    # Cash flow section
                    'Presales': 'Presales (Bookings)',  # Keep presales bookings with different label
                    'Debt_Disbursement': 'Cash Inflow (Debt Disbursement)',
                    'Debt_Repayment': 'Cash Outflow (Debt Repayment)',
                    'Cash_Outflow_Land': 'Cash Outflow (Land)',
                    'Cash_Outflow_Construction': 'Cash Outflow (Construction)',
                    'Cash_Outflow_Interest': 'Cash Outflow (Interest)',
                    'Cash_Outflow_SGA': 'Cash Outflow (SG&A)',
                    'Cash_Outflow_Tax': 'Cash Outflow (Tax)',
                    'Cash_Balance_Change': 'Cash Balance Change',
                    'Cumulative_Cash_Balance': 'Cash Balance'
                }
                display_df.index = display_df.index.map(lambda x: index_labels.get(x, x))
                display_df.index.name = 'Balance Sheet Item'
                
                # Adjust P&L expense values to display as negative
                for idx in display_df.index:
                    if idx in ['COGS (P&L)', 'SG&A Expense (P&L)', 'Interest Expense (P&L)', 'Tax (P&L)']:
                        for col in display_df.columns:
                            if isinstance(display_df.loc[idx, col], (int, float)) and display_df.loc[idx, col] > 0:
                                display_df.loc[idx, col] = -display_df.loc[idx, col]
                
                # Apply alternating background colors for sections
                def highlight_sections(s):
                    """Apply background colors to different sections"""
                    colors = []
                    
                    for idx in s.index:
                        item_name = idx  # idx is already the mapped label
                        
                        # Debt and Cash section - light blue
                        if item_name in ['Debt Balance', 'Cash Balance']:
                            colors.append('background-color: #E3F2FD')
                        # Cost section - light gray
                        elif item_name in ['Land Cost', 'Construction Cost', 'Interest Capitalized']:
                            colors.append('background-color: #F5F5F5')
                        # Inventory section - light green
                        elif item_name in ['Inventory Addition', 'Inventory Balance']:
                            colors.append('background-color: #E8F5E9')
                        # Presales and Customer Prepayment section - light purple
                        elif item_name in ['Actual Presales Cash Collection', 'Customer Prepayment Balance']:
                            colors.append('background-color: #F3E5F5')
                        # P&L section - light yellow (all P&L items grouped together)
                        elif item_name in ['Revenue (P&L)', 'COGS (P&L)', 'SG&A Expense (P&L)', 
                                        'Interest Expense (P&L)', 'PBT (P&L)', 'Tax (P&L)', 'PAT (P&L)']:
                            colors.append('background-color: #FFF9C4')
                        # Cash flow section - light orange
                        else:
                            colors.append('background-color: #FFE0B2')
                    
                    return colors
                
                # Create format dictionary for all year columns
                format_dict = {col: "{:.1f}" for col in display_df.columns}
                
                # Split into three separate dataframes
                # P&L items
                pnl_items = ['Revenue (P&L)', 'COGS (P&L)', 'SG&A Expense (P&L)', 
                            'Interest Expense (P&L)', 'PBT (P&L)', 'Tax (P&L)', 'PAT (P&L)']
                
                # Cash flow items (Cash Balance included in both Balance Sheet and Cash Flow)
                cashflow_items = ['Actual Presales Cash Collection', 'Cash Inflow (Debt Disbursement)',
                                 'Cash Outflow (Debt Repayment)', 'Cash Outflow (Land)',
                                 'Cash Outflow (Construction)', 'Cash Outflow (Interest)',
                                 'Cash Outflow (SG&A)', 'Cash Outflow (Tax)',
                                 'Cash Balance Change', 'Cash Balance']
                
                # Create separate dataframes
                pnl_df = display_df.loc[display_df.index.isin(pnl_items)].copy()
                cashflow_df = display_df.loc[display_df.index.isin(cashflow_items)].copy()
                
                # Balance sheet items - explicitly define order including Cash Balance
                bs_items = ['Debt Balance', 'Cash Balance', 'Land Cost', 'Construction Cost', 
                           'Interest Capitalized', 'Inventory Addition', 'Inventory Balance',
                           'Actual Presales Cash Collection', 'Customer Prepayment Balance']
                # Filter to only include items that exist in display_df
                bs_items = [item for item in bs_items if item in display_df.index]
                bs_df = display_df.loc[bs_items].copy()
                
                # Update index names for each dataframe
                pnl_df.index.name = 'Profit & Loss Item'
                cashflow_df.index.name = 'Cash Flow Item'
                # Balance Sheet keeps the original name
                
                # Set consistent styling for first column width
                # Use CSS to ensure consistent first column width across all tables
                st.markdown("""
                <style>
                    /* Set consistent width for first column (index) in all dataframes */
                    .stDataFrame [data-testid="StyledDataTable"] > div > div > div > div:first-child {
                        min-width: 250px !important;
                        max-width: 250px !important;
                    }
                </style>
                """, unsafe_allow_html=True)
                
                # Display Balance Sheet table
                st.subheader("Balance Sheet")
                
                # Apply styling to balance sheet
                styled_bs_df = bs_df.style.apply(highlight_sections, axis=0).format(format_dict).set_properties(**{'text-align': 'left'}, subset=pd.IndexSlice[:, :])
                st.dataframe(
                    styled_bs_df,
                    use_container_width=True,
                    height=300
                )
                
                # Display P&L table
                st.subheader("Profit & Loss Statement")
                
                # Apply yellow background to P&L table
                def highlight_pnl(df):
                    """Apply yellow background to P&L table"""
                    return pd.DataFrame('background-color: #FFF9C4', 
                                      index=df.index, columns=df.columns)
                
                styled_pnl_df = pnl_df.style.apply(highlight_pnl, axis=None).format(format_dict).set_properties(**{'text-align': 'left'}, subset=pd.IndexSlice[:, :])
                st.dataframe(
                    styled_pnl_df,
                    use_container_width=True,
                    height=250
                )
                
                # Display Cash Flow table
                st.subheader("Cash Flow Statement")
                
                # Apply orange background to cash flow table
                def highlight_cashflow(df):
                    """Apply orange background to cash flow table"""
                    return pd.DataFrame('background-color: #FFE0B2', 
                                      index=df.index, columns=df.columns)
                
                styled_cashflow_df = cashflow_df.style.apply(highlight_cashflow, axis=None).format(format_dict).set_properties(**{'text-align': 'left'}, subset=pd.IndexSlice[:, :])
                st.dataframe(
                    styled_cashflow_df,
                    use_container_width=True,
                    height=300
                )
                
                # Store results in session state for potential export
                st.session_state['project_bs_analysis_results'] = df
                
            except Exception as e:
                st.error(f"❌ Error running financial statements forecast: {str(e)}")
        else:
            # Show info message when insufficient data
            st.info("ℹ️ Financial statements forecast will be generated automatically once project parameters are configured (revenue and construction/land costs required)")
    
    def render_project_financial_analysis(self, project_data):
        """Render financial analysis including RNAV calculation"""
        st.subheader("Financial Analysis & RNAV Calculation")
        
        # Import RNAV utilities
        from utils.RNAV_utils import (
            selling_progress_schedule_custom,
            land_use_right_payment_schedule_single_year,
            land_use_right_payment_schedule_multi_year,
            construction_payment_schedule,
            sga_payment_schedule_custom,
            generate_pnl_schedule_custom,
            RNAV_Calculation
        )
        
        # Get all parameters from edited project
        edited = st.session_state.edited_project
        
        # Calculate total values with proper defaults and type conversion
        nsa = float(edited.get('net_sellable_area', 0) or 0)
        asp = float(edited.get('average_selling_price', 0) or 0)
        gfa = float(edited.get('gross_floor_area', 0) or 0)
        land_area = float(edited.get('land_area', 0) or 0)
        const_cost = float(edited.get('construction_cost_per_sqm', 0) or 0)
        land_cost = float(edited.get('land_cost_per_sqm', 0) or 0)
        
        # Use consistent calculation for total revenue
        total_revenue_billions = self.calculate_total_presales_booking(edited)
        total_revenue = total_revenue_billions * 1e9  # Convert to raw value
        total_const_cost = gfa * const_cost
        total_land_cost = land_area * land_cost
        sga_pct = float(edited.get('sga_percentage', 0.0) or 0.0)
        total_sga = total_revenue * sga_pct
        
        # Calculate PBT for RNAV calculation
        # pbt = total_revenue - total_const_cost - total_land_cost - total_sga
        
        # Calculate RNAV if requested
        # if st.button("Calculate RNAV", key="calc_rnav"):
        try:
            # Check if Financial Statements Forecast is available
            if 'project_bs_analysis_results' not in st.session_state:
                st.error("⚠️ Please wait for Financial Statements Forecast to complete before calculating RNAV")
                return
            
            bs_df = st.session_state['project_bs_analysis_results']
            current_year = datetime.now().year
            
            # Extract cash flows from Financial Statements Forecast for RNAV calculation
            # We need: presales inflows, construction outflows, land outflows, SG&A outflows, and tax outflows
            
            # Determine project timeline from balance sheet
            years_df = bs_df[bs_df['Year'] != 'Total']
            project_years = sorted([int(y) for y in years_df['Year'].values])
            project_start = project_years[0] if project_years else current_year
            project_end = project_years[-1] if project_years else current_year + 3
            
            # Initialize arrays for RNAV calculation (in billions VND)
            selling_progress = []  # Cash inflow from presales
            construction_payment = []  # Cash outflow for construction
            land_payment = []  # Cash outflow for land
            sga_payment = []  # Cash outflow for SG&A
            tax_expense = []  # Cash outflow for tax
            
            # Extract cash flows for each year
            for year in range(project_start, project_end + 1):
                year_data = bs_df[bs_df["Year"] == year]
                
                if not year_data.empty:
                    # Presales cash inflow (positive)
                    selling_progress.append(float(year_data["Cash_Inflow_Presales"].iloc[0]) / 1e9)
                    
                    # Construction cash outflow (should be negative)
                    construction_payment.append(float(year_data["Cash_Outflow_Construction"].iloc[0]) / 1e9)
                    
                    # Land cash outflow (should be negative)
                    land_payment.append(float(year_data["Cash_Outflow_Land"].iloc[0]) / 1e9)
                    
                    # SG&A cash outflow (should be negative)
                    sga_payment.append(float(year_data["Cash_Outflow_SGA"].iloc[0]) / 1e9)
                    
                    # Tax cash outflow (should be negative)
                    tax_expense.append(float(year_data["Cash_Outflow_Tax"].iloc[0]) / 1e9)
                else:
                    # Year not in balance sheet data
                    selling_progress.append(0.0)
                    construction_payment.append(0.0)
                    land_payment.append(0.0)
                    sga_payment.append(0.0)
                    tax_expense.append(0.0)
            
            # Calculate RNAV using extracted cash flows
            df_rnav = RNAV_Calculation(
                selling_progress,
                construction_payment,
                sga_payment,
                tax_expense,
                land_payment,
                float(edited.get('wacc_rate', 0.12)),
                int(project_start),
                int(current_year)
            )
            
            # Get RNAV value - handle both cases where Total RNAV row exists or not
            try:
                # Try to get from Total RNAV row
                total_row = df_rnav[df_rnav["Year"] == "Total RNAV"]
                if not total_row.empty:
                    rnav_value = float(total_row["Discounted Cash Flow"].iloc[0]) * 1e9
                else:
                    # Get from last numeric year row
                    numeric_rows = df_rnav[df_rnav["Year"].apply(lambda x: str(x).isdigit())]
                    if not numeric_rows.empty:
                        rnav_value = float(numeric_rows.iloc[-1]["Discounted Cash Flow"]) * 1e9
                    else:
                        # Fallback to last row
                        rnav_value = float(df_rnav.iloc[-1]["Discounted Cash Flow"]) * 1e9
            except Exception as e:
                st.error(f"Error extracting RNAV value: {e}")
                rnav_value = 0
            
            # Display RNAV result
            st.success(f"RNAV Calculated Successfully!")
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Project RNAV", f"{rnav_value/1e9:,.1f}B VND")
                ownership = edited.get('project_ownership', 1.0)
                st.metric("RNAV to Company", f"{(rnav_value * ownership)/1e9:,.1f}B VND")
            
            with col2:
                if 'rnav_value' in project_data and project_data['rnav_value']:
                    old_rnav = project_data['rnav_value']
                    st.metric(
                        "Previous RNAV",
                        f"{old_rnav/1e9:,.1f}B VND",
                        delta=f"{(rnav_value - old_rnav)/1e9:,.1f}B"
                    )
            
            # Store RNAV in both places for consistency (ensure it's a float)
            rnav_value_float = float(rnav_value) if rnav_value else 0
            st.session_state.edited_project['rnav_value'] = rnav_value_float
            st.session_state['last_calculated_rnav'] = rnav_value_float
            
            # Store RNAV calculation details for saving to MongoDB
            rnav_details = df_rnav.to_dict('records')
            st.session_state.edited_project['rnav_calculation_details'] = rnav_details
            st.session_state['current_rnav_df'] = df_rnav.copy()
            
            # Display RNAV Schedule (transposed with years as columns)
            col_header, col_compare = st.columns([3, 1])
            with col_header:
                st.subheader("RNAV Calculation Details")
            with col_compare:
                # Add comparison toggle
                show_comparison = st.toggle("Compare with previous", key="compare_rnav_toggle")
            
            # Prepare dataframe for transposition
            # Separate the Total RNAV row
            total_row = df_rnav[df_rnav["Year"] == "Total RNAV"]
            year_rows = df_rnav[df_rnav["Year"] != "Total RNAV"].copy()
            
            # Set Year as index for year rows
            year_rows = year_rows.set_index("Year")
            
            # Transpose so years become columns
            df_transposed = year_rows.T
            
            # Add Total RNAV column if it exists
            if not total_row.empty:
                # Get the total values (excluding Year column)
                total_values = total_row.drop(columns=["Year"]).iloc[0]
                df_transposed["Total"] = total_values
            
            # Rename the index to be more descriptive
            index_labels = {
                'Inflow (Revenue)': 'Revenue Inflow',
                'Construction Cost': 'Construction Cost',
                'Land Cost': 'Land Cost', 
                'SG&A': 'SG&A Expense',
                'Tax': 'Tax Payment',
                'Total Outflow': 'Total Cash Outflow',
                'Net Cash Flow': 'Net Cash Flow',
                'Discount Factor': 'Discount Factor',
                'Discounted Cash Flow': 'NPV (Discounted CF)'
            }
            df_transposed.index = df_transposed.index.map(lambda x: index_labels.get(x, x))
            
            # Check if we should show comparison and have previous data
            if show_comparison and 'rnav_calculation_details' in project_data:
                # Load previous RNAV calculation details
                previous_rnav_details = project_data.get('rnav_calculation_details', [])
                
                if previous_rnav_details:
                    # Convert previous details back to DataFrame
                    df_previous = pd.DataFrame(previous_rnav_details)
                    
                    # Process previous data same way as current
                    prev_total_row = df_previous[df_previous["Year"] == "Total RNAV"]
                    prev_year_rows = df_previous[df_previous["Year"] != "Total RNAV"].copy()
                    prev_year_rows = prev_year_rows.set_index("Year")
                    df_prev_transposed = prev_year_rows.T
                    
                    if not prev_total_row.empty:
                        prev_total_values = prev_total_row.drop(columns=["Year"]).iloc[0]
                        df_prev_transposed["Total"] = prev_total_values
                    
                    df_prev_transposed.index = df_prev_transposed.index.map(lambda x: index_labels.get(x, x))
                    
                    # Create comparison DataFrame showing changes
                    comparison_data = []
                    for row_idx in df_transposed.index:
                        row_data = {'Metric': row_idx}
                        for col in df_transposed.columns:
                            current_val = df_transposed.loc[row_idx, col] if row_idx in df_transposed.index and col in df_transposed.columns else 0
                            prev_val = df_prev_transposed.loc[row_idx, col] if row_idx in df_prev_transposed.index and col in df_prev_transposed.columns else 0
                            
                            # Check if values are different
                            if row_idx == 'Discount Factor':
                                # For discount factor, check with precision
                                if abs(current_val - prev_val) > 0.0001:
                                    row_data[col] = f"{current_val:.4f} ({prev_val:.4f})"
                                else:
                                    row_data[col] = f"{current_val:.4f}"
                            else:
                                # For other values, compare as integers
                                if abs(current_val - prev_val) > 1:
                                    row_data[col] = f"{int(current_val):,} ({int(prev_val):,})"
                                else:
                                    row_data[col] = f"{int(current_val):,}"
                        comparison_data.append(row_data)
                    
                    df_comparison = pd.DataFrame(comparison_data).set_index('Metric')
                    
                    # Style the comparison DataFrame
                    def highlight_changes(val):
                        """Highlight cells that have changed"""
                        if '(' in str(val) and ')' in str(val):
                            return 'background-color: #E8F5E9'  # Very light green for changed values
                        return ''
                    
                    styled_df = df_comparison.style.applymap(highlight_changes)
                    
                    # st.info("📊 Comparison with previous calculation - Changed values shown as: new (old) with green background")
                    st.dataframe(styled_df, use_container_width=True)
                else:
                    st.warning("No previous RNAV calculation details found for comparison")
            else:
                # Display normal table without comparison
                # Create a styled dataframe with custom formatting
                styled_df = df_transposed.style
                
                # Apply formatting for each cell based on row
                for col in df_transposed.columns:
                    for row in df_transposed.index:
                        if row == 'Discount Factor':
                            styled_df = styled_df.format({col: "{:.4f}"}, subset=([row], [col]))
                        else:
                            styled_df = styled_df.format({col: lambda x: f"{int(x):,}"}, subset=([row], [col]))
                
                # Display the transposed table
                st.dataframe(styled_df, use_container_width=True)
                
        except Exception as e:
            st.error(f"Error calculating RNAV: {str(e)}")
    
    def render_project_save_interface(self, project_data):
        """Render interface to save project changes to MongoDB"""
        
        st.subheader("Project Actions")
        
        # Show what has changed
        changes = []
        edited = st.session_state.edited_project
        
        # Check what has been modified
        for key, value in edited.items():
            # Skip RNAV calculation details as they have their own comparison view
            if key == 'rnav_calculation_details':
                continue
                
            try:
                if key in project_data:
                    old_value = project_data[key]
                    if isinstance(value, dict):
                        # For distribution dictionaries, check if they're different
                        old_dict = old_value if isinstance(old_value, dict) else {}
                        if value != old_dict:
                            changes.append(f"{key}: Updated")
                    elif isinstance(value, (int, float)):
                        # Compare numeric values
                        if isinstance(old_value, (int, float)):
                            if abs(float(old_value) - float(value)) > 0.001:
                                changes.append(f"{key}: {old_value} → {value}")
                        else:
                            # Old value is not numeric, just note the change
                            changes.append(f"{key}: {old_value} → {value}")
                    else:
                        # Compare other types (strings, etc.)
                        if old_value != value:
                            changes.append(f"{key}: {old_value} → {value}")
                else:
                    if value:  # Only show if new value is not empty
                        changes.append(f"{key}: New value = {value}")
            except Exception as e:
                # If any error in comparison, just note it as changed
                changes.append(f"{key}: Modified")
        
        if changes:
            st.info(f"{len(changes)} changes detected:")
            with st.expander("View changes"):
                for change in changes[:20]:  # Limit to 20 changes
                    st.write(f"- {change}")
                if len(changes) > 20:
                    st.write(f"... and {len(changes) - 20} more changes")
        else:
            st.info("✅ No changes detected. You can still save to update calculated fields.")
        
        # Get project name for use in buttons
        project_name = edited.get('project_name', project_data.get('project_name', 'Unnamed Project'))
        
        # Check if this is a new project (for validation purposes)
        is_new_project = (
            project_data.get('is_new_project', False) == True or 
            project_data.get('project_name', '') in ['New Project', '', None]
        )
        
        # Save, Delete, and Cancel buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Save to MongoDB", type="primary", use_container_width=True):
                try:
                    # For new projects, validate the project name
                    if is_new_project:
                        new_name = edited.get('project_name', '').strip()
                        if not new_name or new_name == 'New Project':
                            st.error("❌ Please enter a unique project name (not 'New Project')")
                            return
                        
                        # Check for duplicate project name
                        if 'project_data' in st.session_state and st.session_state.project_data is not None:
                            existing_projects = st.session_state.project_data
                            if not existing_projects.empty and 'project_name' in existing_projects.columns:
                                if new_name in existing_projects['project_name'].values:
                                    st.error(f"❌ A project with the name '{new_name}' already exists. Please choose a different name.")
                                    return
                        
                        if not edited.get('company_ticker'):
                            st.error("❌ Company ticker is required")
                            return
                    
                    # Calculate financial metrics before saving
                    gfa = edited.get('gross_floor_area', 0)
                    land_area = edited.get('land_area', 0)
                    const_cost = edited.get('construction_cost_per_sqm', 0)
                    land_cost = edited.get('land_cost_per_sqm', 0)
                    
                    # Use consistent calculation for total revenue
                    total_revenue_billions = self.calculate_total_presales_booking(edited)
                    total_revenue = total_revenue_billions * 1e9  # Convert to raw value
                    total_const_cost = float(gfa) * float(const_cost)
                    total_land_cost = float(land_area) * float(land_cost)
                    sga_pct = float(edited.get('sga_percentage', 0.0))
                    total_sga = total_revenue * sga_pct
                    pbt = total_revenue - total_const_cost - total_land_cost - total_sga
                    pat = pbt * 0.8
                    
                    # Update financial totals
                    edited['total_revenue'] = total_revenue
                    edited['total_construction_cost'] = total_const_cost
                    edited['total_land_cost'] = total_land_cost
                    edited['total_sga_cost'] = total_sga
                    edited['total_pbt'] = pbt
                    edited['total_pat'] = pat
                    
                    # Save Financial Statements Forecast data if available
                    if 'project_bs_analysis_results' in st.session_state:
                        bs_df = st.session_state['project_bs_analysis_results']
                        
                        # Debug: Show DataFrame info
                        st.info(f"Found Financial Statements DataFrame with {len(bs_df)} rows")
                        
                        # Convert DataFrame to dictionary format for MongoDB storage
                        balance_sheet_data = {}
                        
                        # Process each year (excluding Total row)
                        for _, row in bs_df.iterrows():
                            year_value = row['Year']
                            
                            if str(year_value) != 'Total':
                                try:
                                    year_str = str(int(year_value))
                                    
                                    # Store all balance sheet, P&L, and cash flow data
                                    balance_sheet_data[year_str] = {
                                        # Balance Sheet items
                                        'debt_balance': float(row['Debt_Balance']),
                                        'cash_balance': float(row['Cumulative_Cash_Balance']),
                                        'land_cost': float(row['Land_Cost']),
                                        'construction_cost': float(row['Construction_Cost']),
                                        'interest_capitalized': float(row['Interest_Capitalized']),
                                        'inventory_addition': float(row['Inventory_Addition']),
                                        'inventory_balance': float(row['Inventory_Balance']),
                                        'presales': float(row['Presales']),
                                        'customer_prepayment_balance': float(row['Customer_Prepayment_Balance']),
                                        
                                        # P&L items
                                        'revenue_recognition': float(row['Revenue_Recognition']),
                                        'cogs': -abs(float(row['COGS'])) if float(row['COGS']) != 0 else 0,  # Ensure negative
                                        'sga_expense': -abs(float(row['SGA_Expense'])) if float(row['SGA_Expense']) != 0 else 0,  # Ensure negative
                                        'interest_expense_cash': -abs(float(row['Interest_Expense_Cash'])) if float(row['Interest_Expense_Cash']) != 0 else 0,  # Ensure negative
                                        'pbt': float(row['PBT']),
                                        'tax': -abs(float(row['Tax'])) if float(row['Tax']) != 0 else 0,  # Ensure negative
                                        'pat': float(row['PAT']),
                                        
                                        # Cash Flow items
                                        'cash_inflow_presales': float(row['Cash_Inflow_Presales']),
                                        'debt_disbursement': float(row['Debt_Disbursement']),
                                        'debt_repayment': -abs(float(row['Debt_Repayment'])) if float(row['Debt_Repayment']) != 0 else 0,  # Ensure negative
                                        'cash_outflow_land': -abs(float(row['Cash_Outflow_Land'])) if float(row['Cash_Outflow_Land']) != 0 else 0,  # Ensure negative
                                        'cash_outflow_construction': -abs(float(row['Cash_Outflow_Construction'])) if float(row['Cash_Outflow_Construction']) != 0 else 0,  # Ensure negative
                                        'cash_outflow_interest': -abs(float(row['Cash_Outflow_Interest'])) if float(row['Cash_Outflow_Interest']) != 0 else 0,  # Ensure negative
                                        'cash_outflow_sga': -abs(float(row['Cash_Outflow_SGA'])) if float(row['Cash_Outflow_SGA']) != 0 else 0,  # Ensure negative
                                        'cash_outflow_tax': -abs(float(row['Cash_Outflow_Tax'])) if float(row['Cash_Outflow_Tax']) != 0 else 0,  # Ensure negative
                                        'cash_balance_change': float(row['Cash_Balance_Change'])
                                    }
                                except Exception as e:
                                    st.error(f"Error processing year data: {e}")
                        
                        # Store complete financial statements in project data
                        edited['comprehensive_financial_statements'] = balance_sheet_data
                        
                        # Debug: Show how many years of data we're saving
                        st.success(f"✅ Captured {len(balance_sheet_data)} years of financial statements data")
                        
                        # Also extract summary totals for quick access
                        total_row = bs_df[bs_df['Year'] == 'Total']
                        if not total_row.empty:
                            edited['financial_statements_summary'] = {
                                'total_revenue': float(total_row['Revenue_Recognition'].iloc[0]),
                                'total_cogs': -abs(float(total_row['COGS'].iloc[0])) if float(total_row['COGS'].iloc[0]) != 0 else 0,  # Ensure negative
                                'total_sga': -abs(float(total_row['SGA_Expense'].iloc[0])) if float(total_row['SGA_Expense'].iloc[0]) != 0 else 0,  # Ensure negative
                                'total_interest': -abs(float(total_row['Interest_Expense_Cash'].iloc[0])) if float(total_row['Interest_Expense_Cash'].iloc[0]) != 0 else 0,  # Ensure negative
                                'total_pbt': float(total_row['PBT'].iloc[0]),
                                'total_tax': -abs(float(total_row['Tax'].iloc[0])) if float(total_row['Tax'].iloc[0]) != 0 else 0,  # Ensure negative
                                'total_pat': float(total_row['PAT'].iloc[0]),
                                'final_debt_balance': float(total_row['Debt_Balance'].iloc[0]),
                                'final_cash_balance': float(total_row['Cumulative_Cash_Balance'].iloc[0]),
                                'final_inventory_balance': float(total_row['Inventory_Balance'].iloc[0])
                            }
                    else:
                        st.warning("⚠️ No Financial Statements Forecast available yet. The forecast will be generated automatically when sufficient project parameters are provided.")
                    
                    # Get RNAV value from either session state or edited project
                    rnav_to_save = st.session_state.get('last_calculated_rnav', 
                                                        edited.get('rnav_value', None))
                    
                    # Ensure RNAV is a proper number or None
                    if rnav_to_save is not None:
                        try:
                            rnav_to_save = float(rnav_to_save)
                            # Also ensure it's in the edited data for consistency
                            edited['rnav_value'] = rnav_to_save
                        except (TypeError, ValueError):
                            rnav_to_save = None
                            edited['rnav_value'] = None
                    else:
                        edited['rnav_value'] = None
                    
                    # Debug: Check what's in edited before saving
                    if 'comprehensive_financial_statements' in edited:
                        st.info(f"About to save {len(edited['comprehensive_financial_statements'])} years of financial data to MongoDB")
                    else:
                        st.warning("⚠️ Note: Financial statements data not found in save data")
                    
                    # Check if RNAV calculation details are present
                    if 'rnav_calculation_details' in edited:
                        st.info(f"✅ RNAV calculation details will be saved ({len(edited['rnav_calculation_details'])} rows)")
                    else:
                        st.info("ℹ️ RNAV calculation details not available yet")
                    
                    # Save to MongoDB
                    from utils.mongodb_utils import save_project_to_mongodb
                    
                    result = save_project_to_mongodb(
                        edited,
                        project_name,
                        rnav_value=rnav_to_save
                    )
                    
                    if result['success']:
                        st.success(result['message'])
                        
                        # Always refresh project data from MongoDB after save
                        from utils.mongodb_utils import load_projects_data
                        df_projects = load_projects_data()
                        
                        # Filter for selected company if applicable
                        if st.session_state.selected_company:
                            df_projects = df_projects[df_projects['company_ticker'] == st.session_state.selected_company]
                        
                        # Update session state with fresh project data
                        st.session_state.project_data = df_projects
                        
                        # Clear editing state to force reload
                        # This ensures the comparison values are refreshed
                        if 'current_editing_project' in st.session_state:
                            del st.session_state.current_editing_project
                        if 'edited_project' in st.session_state:
                            del st.session_state.edited_project
                        
                        # For new projects, we need to set a flag to switch to the new project on next render
                        if is_new_project:
                            st.session_state.pending_project_switch = edited.get('project_name')
                        
                        # Clear any temporary editing state
                        if 'confirm_delete' in st.session_state:
                            del st.session_state.confirm_delete
                        
                        # Rerun to refresh the UI with new data
                        st.rerun()
                    else:
                        st.error(result['message'])
                        
                except Exception as e:
                    st.error(f"Error saving project: {str(e)}")
        
        # Delete button
        with col2:
            if st.button("Delete from MongoDB", type="secondary", use_container_width=True):
                # Add confirmation dialog
                if 'confirm_delete' not in st.session_state:
                    st.session_state.confirm_delete = True
                    st.warning(f"⚠️ Are you sure you want to delete '{project_name}'? Click again to confirm.")
                else:
                    # Delete the project
                    from utils.mongodb_utils import delete_project_from_mongodb
                    company_ticker = project_data.get('company_ticker', '')
                    result = delete_project_from_mongodb(company_ticker, project_name)
                    if result['success']:
                        st.success(f"✅ Project '{project_name}' deleted successfully!")
                        # Clean up session state
                        if 'current_editing_project' in st.session_state:
                            del st.session_state.current_editing_project
                        if 'edited_project' in st.session_state:
                            del st.session_state.edited_project
                        if 'confirm_delete' in st.session_state:
                            del st.session_state.confirm_delete
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ Failed to delete project: {result.get('message', 'Unknown error')}")
                        if 'confirm_delete' in st.session_state:
                            del st.session_state.confirm_delete
        
        # Cancel button
        with col3:
            if st.button("Cancel", use_container_width=True):
                if 'current_editing_project' in st.session_state:
                    del st.session_state.current_editing_project
                if 'confirm_delete' in st.session_state:
                    del st.session_state.confirm_delete
                st.rerun()
