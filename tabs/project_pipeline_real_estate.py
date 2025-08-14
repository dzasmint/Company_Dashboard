#%%
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import time


class ProjectPipelineRealEstateTab:
    """Project Pipeline tab specifically for Real Estate Financial Model"""
    
    def __init__(self, parent):
        self.parent = parent
        
    def render(self):
        """Render project pipeline and timeline"""
        
        df_projects = st.session_state.project_data
        
        if df_projects is None or (isinstance(df_projects, pd.DataFrame) and df_projects.empty):
            st.info("Click 'Sync Project Data' in the sidebar to load projects from MongoDB")
            return
        
        # Add project selector for individual project editing
        
        project_names = df_projects['project_name'].tolist()
        
        # Add "Create New Project" option at the beginning
        project_options = ["All Projects (Overview)", "➕ Create New Project"] + project_names
        
        # Use session state to preserve the selected project
        if 'selected_project_for_edit' not in st.session_state:
            st.session_state.selected_project_for_edit = "All Projects (Overview)"
        
        # Create a form to prevent auto-rerun on selection
        with st.container():
            selected_project_name = st.selectbox(
                "Choose a project to view/edit details:",
                options=project_options,
                key="selected_project_for_edit",
                index=project_options.index(st.session_state.selected_project_for_edit) if st.session_state.selected_project_for_edit in project_options else 0,
                help="Select a project to view or edit its details"
            )
        
        if selected_project_name == "➕ Create New Project":
            # Show new project creation form
            self.render_new_project_form()
            return
        elif selected_project_name != "All Projects (Overview)":
            # Show individual project editor
            self.render_individual_project_editor(selected_project_name, df_projects)
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
            display_df['average_selling_price'] = display_df['average_selling_price'].apply(lambda x: f"{x:,.0f}")
        if 'rnav_value' in display_df.columns:
            display_df['rnav_value'] = display_df['rnav_value'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A")
        
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
            
            # Calculate total revenue
            nsa = float(project.get('net_sellable_area', 0) or 0)
            asp = float(project.get('average_selling_price', 0) or 0)
            total_revenue = nsa * asp
            
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
        """Render form for creating a brand new project"""
        st.subheader("➕ Create New Project")
        st.info("Enter details for your new project. All fields start empty for a fresh start.")
        
        # Initialize empty project data if not exists
        if 'new_project_data' not in st.session_state:
            st.session_state.new_project_data = {}
        
        # Basic Information Section
        st.markdown("### Basic Information")
        col1, col2 = st.columns(2)
        
        with col1:
            project_name = st.text_input(
                "Project Name *",
                value="",
                placeholder="Enter project name",
                key="new_project_name"
            )
            
            company_ticker = st.text_input(
                "Company Ticker *",
                value=st.session_state.selected_company if st.session_state.selected_company else "",
                placeholder="e.g., VHM, NLG, KDH",
                key="new_project_ticker"
            )
            
            location = st.text_input(
                "Location",
                value="",
                placeholder="e.g., Ho Chi Minh City",
                key="new_project_location"
            )
            
            project_ownership = st.number_input(
                "Project Ownership (%)",
                min_value=0.0,
                max_value=100.0,
                value=100.0,
                step=0.1,
                key="new_project_ownership"
            )
        
        with col2:
            total_units = st.number_input(
                "Total Units",
                min_value=0,
                value=0,
                step=1,
                format="%d",
                key="new_project_units"
            )
            
            average_unit_size = st.number_input(
                "Average Unit Size (sqm)",
                min_value=0,
                value=0,
                step=1,
                format="%d",
                key="new_project_unit_size"
            )
            
            land_area = st.number_input(
                "Land Area (sqm)",
                min_value=0,
                value=0,
                step=1,
                format="%d",
                key="new_project_land_area"
            )
            
            gross_floor_area = st.number_input(
                "Gross Floor Area (sqm)",
                min_value=0,
                value=0,
                step=1,
                format="%d",
                key="new_project_gfa"
            )
        
        st.markdown("---")
        
        # Financial Parameters Section
        st.markdown("### Financial Parameters")
        col3, col4 = st.columns(2)
        
        with col3:
            average_selling_price = st.number_input(
                "Average Selling Price (VND/sqm)",
                min_value=0,
                value=0,
                step=1000000,
                format="%d",
                key="new_project_asp"
            )
            
            construction_cost_per_sqm = st.number_input(
                "Construction Cost (VND/sqm)",
                min_value=0,
                value=0,
                step=1000000,
                format="%d",
                key="new_project_construction_cost"
            )
            
            land_cost_per_sqm = st.number_input(
                "Land Cost (VND/sqm)",
                min_value=0,
                value=0,
                step=1000000,
                format="%d",
                key="new_project_land_cost"
            )
        
        with col4:
            sga_percentage = st.number_input(
                "SG&A (% of Revenue)",
                min_value=0.0,
                value=8.0,
                step=0.1,
                key="new_project_sga"
            )
            
            
            wacc_rate = st.number_input(
                "WACC (%)",
                min_value=0.0,
                max_value=30.0,
                value=12.0,
                step=0.1,
                key="new_project_wacc"
            )
            
            cost_of_debt = st.number_input(
                "Cost of Debt (%)",
                min_value=0.0,
                step=0.1,
                key="new_project_cost_of_debt"
            )
        
        st.markdown("---")
        
        # Timeline Section
        st.markdown("### Project Timeline")
        current_year = datetime.now().year
        col5, col6 = st.columns(2)
        
        with col5:
            construction_start_year = st.number_input(
                "Construction Start Year",
                value=current_year,
                step=1,
                key="new_project_construction_start"
            )
            
            construction_years = st.number_input(
                "Construction Duration (years)",
                min_value=1,
                value=3,
                step=1,
                key="new_project_construction_years"
            )
            
            sale_start_year = st.number_input(
                "Sales Start Year",
                value=current_year,
                step=1,
                key="new_project_sale_start"
            )
        
        with col6:
            sales_years = st.number_input(
                "Sales Duration (years)",
                min_value=1,
                value=3,
                step=1,
                key="new_project_sales_years"
            )
            
            revenue_booking_start_year = st.number_input(
                "Revenue Booking Start Year",
                value=current_year + 1,
                step=1,
                key="new_project_revenue_start"
            )
            
            project_completion_year = st.number_input(
                "Project Completion Year",
                value=current_year + 3,
                step=1,
                key="new_project_completion"
            )
        
        st.markdown("---")
        
        # Action Buttons
        col_save, col_cancel = st.columns(2)
        
        with col_save:
            if st.button("Save New Project", type="primary", use_container_width=True):
                # Validate required fields
                if not project_name:
                    st.error("Project Name is required!")
                    return
                if not company_ticker:
                    st.error("Company Ticker is required!")
                    return
                
                # Calculate total costs and debt
                total_construction_cost = gross_floor_area * construction_cost_per_sqm if gross_floor_area and construction_cost_per_sqm else 0
                total_land_cost = land_area * land_cost_per_sqm if land_area and land_cost_per_sqm else 0
                total_project_cost = total_construction_cost + total_land_cost
                
                # Calculate total debt using default 60% of project cost
                calculated_total_debt = total_project_cost * 0.6
                
                # Prepare project data
                new_project_data = {
                    'project_name': project_name,
                    'company_ticker': company_ticker.upper(),
                    'location': location,
                    'project_ownership': project_ownership / 100,  # Store as decimal
                    'total_units': total_units,
                    'average_unit_size': average_unit_size,
                    'net_sellable_area': total_units * average_unit_size if total_units and average_unit_size else 0,
                    'land_area': land_area,
                    'gross_floor_area': gross_floor_area,
                    'average_selling_price': average_selling_price,
                    'construction_cost_per_sqm': construction_cost_per_sqm,
                    'land_cost_per_sqm': land_cost_per_sqm,
                    'total_debt': calculated_total_debt,  # Add total debt field
                    'sga_percentage': sga_percentage / 100,  # Store as decimal
                    'wacc_rate': wacc_rate / 100,  # Store as decimal
                    'cost_of_debt': cost_of_debt / 100,  # Store as decimal
                    'construction_start_year': construction_start_year,
                    'construction_years': construction_years,
                    'sale_start_year': sale_start_year,
                    'sales_years': sales_years,
                    'revenue_booking_start_year': revenue_booking_start_year,
                    'project_completion_year': project_completion_year,
                    'land_payment_year': construction_start_year,  # Default to construction start
                    'revenue_distribution': {},  # Empty for new project
                    'presales_distribution': {},  # Empty for new project
                    'pnl_schedule': {},  # Empty for new project
                }
                
                # Calculate total values
                nsa = new_project_data['net_sellable_area']
                new_project_data['total_revenue'] = (nsa * average_selling_price) / 1e9 if nsa and average_selling_price else 0
                new_project_data['total_construction_cost'] = (gross_floor_area * construction_cost_per_sqm) / 1e9 if gross_floor_area and construction_cost_per_sqm else 0
                new_project_data['total_land_cost'] = (land_area * land_cost_per_sqm) / 1e9 if land_area and land_cost_per_sqm else 0
                new_project_data['total_sga_cost'] = new_project_data['total_revenue'] * (sga_percentage / 100) if new_project_data['total_revenue'] else 0
                
                # Save to MongoDB
                from utils.mongodb_utils import save_project_to_mongodb
                result = save_project_to_mongodb(new_project_data, project_name)
                
                if result['success']:
                    st.success(f"✅ {result['message']}")
                    
                    # Refresh project data
                    from utils.mongodb_utils import load_projects_data
                    df_projects = load_projects_data()
                    
                    # Filter for selected company if applicable
                    if st.session_state.selected_company:
                        df_projects = df_projects[df_projects['company_ticker'] == st.session_state.selected_company]
                    
                    st.session_state.project_data = df_projects
                    
                    # Clear the form by resetting session state
                    if 'new_project_data' in st.session_state:
                        del st.session_state.new_project_data
                    
                    # Switch to the newly created project
                    st.session_state.selected_project_for_edit = project_name
                    st.rerun()
                else:
                    st.error(f"❌ {result['message']}")
        
        with col_cancel:
            if st.button("❌ Cancel", use_container_width=True):
                # Clear form and go back to overview
                if 'new_project_data' in st.session_state:
                    del st.session_state.new_project_data
                st.session_state.selected_project_for_edit = "All Projects (Overview)"
                st.rerun()
    
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
                        
                        # Display summary in full width expander
                        with st.expander("AI Research Summary", expanded=True):
                            # Show basic info if available in full width
                            if parsed_info.get("basic_info"):
                                st.info(f"**Project Description:** {parsed_info['basic_info']}")
                            
                            # Show confidence level if available
                            if parsed_info.get("confidence"):
                                st.caption(f"**Confidence Level:** {parsed_info['confidence']}")
                            
                            # Show analysis method if available
                            if parsed_info.get("analysis_method"):
                                st.caption(f"**Analysis Method:** {parsed_info['analysis_method']}")
                            
                            # Show sources if available
                            if parsed_info.get("sources"):
                                st.caption(f"**Sources:** {parsed_info['sources']}")
                            
                            st.info("💡 AI suggestions are displayed below each input field. Review and modify values as needed before saving.")
                            
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
                                    suggestions.append({
                                        "Parameter": "Avg Selling Price (M VND/sqm)",
                                        "AI Suggestion": f"{ai_price:,.0f}",
                                        "Current Value": f"{float(project_data.get('average_selling_price', 0)):,.0f}"
                                    })
                                except (ValueError, TypeError):
                                    suggestions.append({
                                        "Parameter": "Avg Selling Price (M VND/sqm)",
                                        "AI Suggestion": str(parsed_info['avg_selling_price_per_sqm']),
                                        "Current Value": str(project_data.get('average_selling_price', 0))
                                    })
                            
                            if parsed_info.get("construction_cost_per_sqm"):
                                try:
                                    ai_cost = float(parsed_info['construction_cost_per_sqm'])
                                    suggestions.append({
                                        "Parameter": "Construction Cost (M VND/sqm)",
                                        "AI Suggestion": f"{ai_cost:,.0f}",
                                        "Current Value": f"{float(project_data.get('construction_cost_per_sqm', 0)):,.0f}"
                                    })
                                except (ValueError, TypeError):
                                    suggestions.append({
                                        "Parameter": "Construction Cost (M VND/sqm)",
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
                    else:
                        st.error("❌ Could not parse AI response. Please try again.")
                else:
                    st.error(f"❌ AI research failed: {response}")
                    
            except Exception as e:
                st.error(f"❌ Error during AI research: {str(e)}")
    
    def render_individual_project_editor(self, project_name, df_projects):
        """Render editor for individual project with revenue/presales distribution"""
        # Get the selected project data
        project_data = df_projects[df_projects['project_name'] == project_name].iloc[0].to_dict()
        
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
                self.get_ai_project_suggestions(project_name, project_data)
        
        # Check if we're switching to a different project
        if 'current_editing_project' not in st.session_state:
            st.session_state.current_editing_project = project_name
            st.session_state.edited_project = project_data.copy()
        elif st.session_state.current_editing_project != project_name:
            # Different project selected, reset the edited data
            st.session_state.current_editing_project = project_name
            st.session_state.edited_project = project_data.copy()
        elif 'edited_project' not in st.session_state:
            # Same project but edited_project was deleted (e.g., after save)
            st.session_state.edited_project = project_data.copy()
        
        # Render all sections in a single scrollable view
        st.markdown("---")
        self.render_project_basic_info(project_data)
        
        st.markdown("---")
        self.render_project_timeline(project_data)
        
        st.markdown("---")
        self.render_presales_distribution_editor(project_data)
        
        st.markdown("---")
        self.render_revenue_distribution_editor(project_data)
        
        st.markdown("---")
        self.render_project_balance_sheet_analysis(project_data)
        
        st.markdown("---")
        self.render_project_financial_analysis(project_data)
        
        st.markdown("---")
        self.render_project_save_interface(project_data)
    
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
        
        # Each field on its own row with label and input side by side
        
        # Project Ownership - moved to top and converted to percentage display
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Project Ownership (%)**")
        with col2:
            # Convert from decimal to percentage for display (0.5 -> 50)
            ownership_decimal = float(project_data.get('project_ownership', 1.0) or 1.0)
            ownership_percentage = ownership_decimal * 100
            
            ownership_input = st.number_input(
                "Project Ownership (%)",
                value=ownership_percentage,
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                format="%.1f",
                key="edit_ownership_pct",
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
                key="edit_location",
                label_visibility="collapsed"
            )
            if ai_suggestions.get("location"):
                st.caption(f"AI Suggestion: {ai_suggestions['location']}")
        st.session_state.edited_project['location'] = location
        
        # Total Units
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Total Units**")
        with col2:
            total_units = st.number_input(
                "Total Units",
                value=int(project_data.get('total_units', 0) or 0),
                min_value=0,
                step=1,
                format="%d",
                key="edit_total_units",
                label_visibility="collapsed"
            )
            if ai_suggestions.get("total_units"):
                try:
                    ai_units = float(ai_suggestions['total_units'])
                    st.caption(f"AI Suggestion: {ai_units:,.0f} units")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['total_units']} units")
        st.session_state.edited_project['total_units'] = total_units
        
        # Average Unit Size
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Average Unit Size (m²)**")
        with col2:
            avg_unit_size = st.number_input(
                "Average Unit Size (m²)",
                value=int(project_data.get('average_unit_size', 0) or 0),
                min_value=0,
                step=1,
                format="%d",
                key="edit_avg_unit_size",
                label_visibility="collapsed"
            )
            if ai_suggestions.get("average_unit_size"):
                try:
                    ai_size = float(ai_suggestions['average_unit_size'])
                    st.caption(f"AI Suggestion: {ai_size:,.0f} m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['average_unit_size']} m²")
        st.session_state.edited_project['average_unit_size'] = avg_unit_size
        
        # Calculate and display NSA
        nsa = total_units * avg_unit_size
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Net Sellable Area**")
        with col2:
            # Use a disabled text input for consistent height with other fields
            st.text_input(
                "Net Sellable Area",
                value=f"{nsa:,.0f} m² (calculated)",
                disabled=True,
                key="nsa_display",
                label_visibility="collapsed"
            )
        st.session_state.edited_project['net_sellable_area'] = nsa
        
        # Average Selling Price
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Average Selling Price (VND/m²)**")
        with col2:
            asp = st.number_input(
                "Average Selling Price (VND/m²)",
                value=int(project_data.get('average_selling_price', 0) or 0),
                min_value=0,
                step=1000000,
                format="%d",
                key="edit_asp",
                label_visibility="collapsed"
            )
            if ai_suggestions.get("avg_selling_price_per_sqm"):
                try:
                    ai_price = float(ai_suggestions['avg_selling_price_per_sqm'])
                    st.caption(f"AI Suggestion: {ai_price:,.0f} VND/m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['avg_selling_price_per_sqm']} VND/m²")
        st.session_state.edited_project['average_selling_price'] = asp
        
        # Land Area
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Land Area (m²)**")
        with col2:
            land_area = st.number_input(
                "Land Area (m²)",
                value=int(project_data.get('land_area', 0) or 0),
                min_value=0,
                step=1,
                format="%d",
                key="edit_land_area",
                label_visibility="collapsed"
            )
            if ai_suggestions.get("land_area_sqm"):
                try:
                    ai_land = float(ai_suggestions['land_area_sqm'])
                    st.caption(f"AI Suggestion: {ai_land:,.0f} m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['land_area_sqm']} m²")
        st.session_state.edited_project['land_area'] = land_area
        
        # Gross Floor Area
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Gross Floor Area (m²)**")
        with col2:
            gfa = st.number_input(
                "Gross Floor Area (m²)",
                value=int(project_data.get('gross_floor_area', 0) or 0),
                min_value=0,
                step=1,
                format="%d",
                key="edit_gfa",
                label_visibility="collapsed"
            )
            if ai_suggestions.get("total_area_sqm"):
                try:
                    ai_gfa = float(ai_suggestions['total_area_sqm'])
                    st.caption(f"AI Suggestion: {ai_gfa:,.0f} m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['total_area_sqm']} m²")
        st.session_state.edited_project['gross_floor_area'] = gfa
        
        # Construction Cost per sqm
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Construction Cost (VND/m²)**")
        with col2:
            const_cost = st.number_input(
                "Construction Cost (VND/m²)",
                value=int(project_data.get('construction_cost_per_sqm', 0) or 0),
                min_value=0,
                step=1000000,
                format="%d",
                key="edit_const_cost",
                label_visibility="collapsed"
            )
            if ai_suggestions.get("construction_cost_per_sqm"):
                try:
                    ai_const = float(ai_suggestions['construction_cost_per_sqm'])
                    st.caption(f"AI Suggestion: {ai_const:,.0f} VND/m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['construction_cost_per_sqm']} VND/m²")
        st.session_state.edited_project['construction_cost_per_sqm'] = const_cost
        
        # Land Cost per sqm
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Land Cost (VND/m²)**")
        with col2:
            land_cost = st.number_input(
                "Land Cost (VND/m²)",
                value=int(project_data.get('land_cost_per_sqm', 0) or 0),
                min_value=0,
                step=1000000,
                format="%d",
                key="edit_land_cost",
                label_visibility="collapsed"
            )
            if ai_suggestions.get("land_cost_per_sqm"):
                try:
                    ai_land_cost = float(ai_suggestions['land_cost_per_sqm'])
                    st.caption(f"AI Suggestion: {ai_land_cost:,.0f} VND/m²")
                except:
                    st.caption(f"AI Suggestion: {ai_suggestions['land_cost_per_sqm']} VND/m²")
        st.session_state.edited_project['land_cost_per_sqm'] = land_cost
        
        # Total Debt field
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Total Debt (VND)**")
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
            existing_total_debt = project_data.get('total_debt', default_total_debt)
            
            # Create detailed tooltip with calculation breakdown
            tooltip_text = (
                f"Default Calculation:\n"
                f"─────────────────────\n"
                f"Construction Cost: {total_const_cost/1e9:,.1f}B VND\n"
                f"  = GFA ({gfa:,.0f} m²) × Construction Cost ({const_cost_per_sqm/1e6:,.1f}M VND/m²)\n"
                f"Land Cost: {total_land_cost_calc/1e9:,.1f}B VND\n"
                f"  = Land Area ({land_area:,.0f} m²) × Land Cost ({land_cost_per_sqm/1e6:,.1f}M VND/m²)\n"
                f"─────────────────────\n"
                f"Total Project Cost: {total_project_cost/1e9:,.1f}B VND\n"
                f"Debt Financing: {debt_financing_pct*100:.0f}%\n"
                f"─────────────────────\n"
                f"Default Total Debt: {default_total_debt/1e9:,.1f}B VND\n"
                f"  = {total_project_cost/1e9:,.1f}B × {debt_financing_pct*100:.0f}%"
            )
            
            total_debt = st.number_input(
                "Total Debt (VND)",
                value=float(existing_total_debt),
                min_value=0.0,
                step=1000000000.0,  # 1 billion VND steps
                format="%.0f",
                key="edit_total_debt",
                label_visibility="collapsed",
                help=tooltip_text
            )
            
            # Show the default calculation for reference
            if abs(total_debt - default_total_debt) > 1:  # If user has modified from default
                st.caption(f"📝 Default: {default_total_debt/1e9:,.1f}B VND (Construction + Land) × {debt_financing_pct*100:.0f}%")
        st.session_state.edited_project['total_debt'] = total_debt
    
    def render_project_timeline(self, project_data):
        """Render project timeline editor"""
        st.subheader("Project Timeline")
        
        # Each field on its own row with label and input side by side
        
        # Construction Start Year
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Construction Start Year**")
        with col2:
            const_start = st.number_input(
                "Construction Start Year",
                value=int(project_data.get('construction_start_year', datetime.now().year) or datetime.now().year),
                min_value=2000,  # Allow historical years
                max_value=2040,
                key="edit_const_start",
                label_visibility="collapsed"
            )
        st.session_state.edited_project['construction_start_year'] = const_start
        
        # Construction Duration
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Construction Duration (years)**")
        with col2:
            const_years = st.number_input(
                "Construction Duration (years)",
                value=int(project_data.get('construction_years', 3) or 3),
                min_value=1,
                max_value=10,
                key="edit_const_years",
                label_visibility="collapsed"
            )
        st.session_state.edited_project['construction_years'] = const_years
        
        # Sales Start Year
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Sales Start Year**")
        with col2:
            sales_start = st.number_input(
                "Sales Start Year",
                value=int(project_data.get('sale_start_year', datetime.now().year) or datetime.now().year),
                min_value=2000,
                max_value=2040,
                key="edit_sales_start",
                label_visibility="collapsed"
            )
        st.session_state.edited_project['sale_start_year'] = sales_start
        
        # Sales Duration
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Sales Duration (years)**")
        with col2:
            sales_years = st.number_input(
                "Sales Duration (years)",
                value=int(project_data.get('sales_years', 3) or 3),
                min_value=1,
                max_value=10,
                key="edit_sales_years",
                label_visibility="collapsed"
            )
        st.session_state.edited_project['sales_years'] = sales_years
        
        # Revenue Booking Start Year
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Revenue Booking Start Year**")
        with col2:
            revenue_start = st.number_input(
                "Revenue Booking Start Year",
                value=int(project_data.get('revenue_booking_start_year', datetime.now().year + 1) or datetime.now().year + 1),
                min_value=2000,
                max_value=2040,
                key="edit_revenue_start",
                label_visibility="collapsed"
            )
        st.session_state.edited_project['revenue_booking_start_year'] = revenue_start
        
        # Project Completion Year
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Project Completion Year**")
            st.caption("(Revenue Booking End Year)")
        with col2:
            completion_year = st.number_input(
                "Project Completion Year",
                value=int(project_data.get('project_completion_year', datetime.now().year + 3) or datetime.now().year + 3),
                min_value=2000,
                max_value=2040,
                key="edit_completion",
                label_visibility="collapsed"
            )
        st.session_state.edited_project['project_completion_year'] = completion_year
        
        # Land Payment Year
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Land Payment Year**")
        with col2:
            land_payment = st.number_input(
                "Land Payment Year",
                value=int(project_data.get('land_payment_year', const_start) or const_start),
                min_value=2000,
                max_value=2040,
                key="edit_land_payment",
                label_visibility="collapsed"
            )
        st.session_state.edited_project['land_payment_year'] = land_payment
        
        # Financial Parameters Section
        st.markdown("---")
        st.markdown("### Financial Parameters (from Assumptions)")
        
        # Load assumptions once for all financial parameters
        from utils.mongodb_utils import load_assumptions_from_mongodb
        company_ticker = project_data.get('company_ticker', '')
        assumptions = load_assumptions_from_mongodb(company_ticker)
        
        # Helper function to get assumption value
        # Note: Assumptions are stored as decimal/float values (e.g., 0.12 for 12%)
        def get_assumption_value(assumptions, name, default_decimal):
            if assumptions:
                for assumption in assumptions:
                    if assumption.get('name') == name:
                        try:
                            # Value is already stored as decimal (e.g., 0.12 for 12%)
                            return float(assumption.get('value', default_decimal))
                        except (ValueError, TypeError):
                            return default_decimal
            return default_decimal
        
        # WACC Rate - loaded from Assumptions (non-editable)
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**WACC Rate (%)**")
        with col2:
            # Get WACC from assumptions
            wacc_decimal = get_assumption_value(assumptions, 'WACC', 0.12)
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
            # Get SG&A from assumptions
            sga_decimal = get_assumption_value(assumptions, 'SG&A % of Revenue', 0.08)
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
            debt_financing_decimal = get_assumption_value(assumptions, 'Debt Financing %', 0.30)
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
            cost_of_debt_decimal = get_assumption_value(assumptions, 'Cost of Debt', 0.08)
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
        """Render revenue distribution editor with year-by-year percentages"""
        st.subheader("Revenue Distribution Schedule")
        st.info("Enter percentage of total revenue to recognize in each year. Must sum to 100%.")
        
        # Get timeline parameters from edited project
        revenue_start = st.session_state.edited_project.get('revenue_booking_start_year', 
                                                             project_data.get('revenue_booking_start_year', datetime.now().year) or datetime.now().year)
        revenue_end = st.session_state.edited_project.get('project_completion_year',
                                                          project_data.get('project_completion_year', datetime.now().year + 3) or datetime.now().year + 3)
        
        # Get existing distribution from session state (which may have been updated by reset button)
        # If not in session state, get from project data
        existing_dist = st.session_state.edited_project.get('revenue_distribution', 
                                                            project_data.get('revenue_distribution', {}))
        if not isinstance(existing_dist, dict):
            existing_dist = {}
        
        # Create input fields for each year
        years = list(range(int(revenue_start), int(revenue_end) + 1))
        distribution = {}
        
        # If no existing distribution or empty, create even split
        if not existing_dist or len(existing_dist) == 0:
            for year in years:
                existing_dist[str(year)] = 100.0 / len(years) if len(years) > 0 else 100.0
        
        # Calculate totals for display
        edited = st.session_state.edited_project
        total_units = float(edited.get('total_units', 0) or 0)
        nsa = float(edited.get('net_sellable_area', 0) or 0)
        asp = float(edited.get('average_selling_price', 0) or 0)
        total_revenue = nsa * asp / 1e9  # Convert to billions
        
        cols = st.columns(min(len(years), 4))  # Max 4 columns
        
        for i, year in enumerate(years):
            col_idx = i % len(cols)
            with cols[col_idx]:
                default_val = existing_dist.get(str(year), 100.0/len(years))
                pct = st.number_input(
                    f"Year {year} (%)",
                    value=float(default_val),
                    min_value=0.0,
                    max_value=100.0,
                    step=0.1,
                    key=f"revenue_dist_{year}"
                )
                distribution[str(year)] = pct
                
                # Display calculated units and value
                units_for_year = int(total_units * pct / 100)
                value_for_year = total_revenue * pct / 100
                st.caption(f"Units: {units_for_year:,}")
                st.caption(f"Value: {value_for_year:.0f}B VND")
        
        # Validate percentages
        total_pct = sum(distribution.values())
        col1, col2 = st.columns(2)
        
        with col1:
            if abs(total_pct - 100.0) < 0.01:
                st.success(f"✅ Total: {total_pct:.1f}%")
            else:
                st.error(f"❌ Total: {total_pct:.1f}% (must be 100%)")
        
        with col2:
            if st.button("Reset to Linear Distribution", key="reset_revenue"):
                # Reset to even distribution across all years
                even_pct = 100.0 / len(years) if len(years) > 0 else 100.0
                reset_dist = {}
                for year in years:
                    reset_dist[str(year)] = even_pct
                st.session_state.edited_project['revenue_distribution'] = reset_dist
                st.rerun()
        
        st.session_state.edited_project['revenue_distribution'] = distribution
        
        # Show visual chart of distribution
        if years:
            import plotly.graph_objects as go
            
            # Calculate total revenue to show absolute values
            edited = st.session_state.edited_project
            nsa = float(edited.get('net_sellable_area', 0) or 0)
            asp = float(edited.get('average_selling_price', 0) or 0)
            total_revenue = nsa * asp / 1e9  # Convert to billions
            
            # Calculate absolute values for each year
            absolute_values = [total_revenue * distribution.get(str(y), 0) / 100 for y in years]
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=[str(y) for y in years],
                y=absolute_values,
                text=[f"{abs_val:.0f}B ({distribution.get(str(y), 0):.1f}%)" for y, abs_val in zip(years, absolute_values)],
                textposition='auto',
                marker_color='darkblue'
            ))
            fig.update_layout(
                title="Revenue Recognition Schedule",
                xaxis_title="Year",
                yaxis_title="Revenue (VND Billions)",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
    
    def render_presales_distribution_editor(self, project_data):
        """Render presales distribution editor with year-by-year percentages"""
        st.subheader("Presales Distribution Schedule")
        st.info("Enter percentage of total sales to achieve in each year. Must sum to 100%.")
        
        # Get timeline parameters from edited project
        sales_start = st.session_state.edited_project.get('sale_start_year',
                                                          project_data.get('sale_start_year', datetime.now().year) or datetime.now().year)
        sales_years = st.session_state.edited_project.get('sales_years',
                                                          project_data.get('sales_years', 3) or 3)
        sales_end = int(sales_start or datetime.now().year) + int(sales_years or 3) - 1
        
        # Get existing distribution from session state (which may have been updated by reset button)
        # If not in session state, get from project data
        existing_dist = st.session_state.edited_project.get('presales_distribution', 
                                                            project_data.get('presales_distribution', {}))
        if not isinstance(existing_dist, dict):
            existing_dist = {}
        
        # Create input fields for each year
        years = list(range(int(sales_start), int(sales_end) + 1))
        distribution = {}
        
        # If no existing distribution or empty, create even split
        if not existing_dist or len(existing_dist) == 0:
            for year in years:
                existing_dist[str(year)] = 100.0 / len(years) if len(years) > 0 else 100.0
        
        # Calculate totals for display
        edited = st.session_state.edited_project
        total_units = float(edited.get('total_units', 0) or 0)
        nsa = float(edited.get('net_sellable_area', 0) or 0)
        asp = float(edited.get('average_selling_price', 0) or 0)
        total_revenue = nsa * asp / 1e9  # Convert to billions
        
        cols = st.columns(min(len(years), 4))  # Max 4 columns
        
        for i, year in enumerate(years):
            col_idx = i % len(cols)
            with cols[col_idx]:
                default_val = existing_dist.get(str(year), 100.0/len(years))
                pct = st.number_input(
                    f"Year {year} (%)",
                    value=float(default_val),
                    min_value=0.0,
                    max_value=100.0,
                    step=0.1,
                    key=f"presales_dist_{year}"
                )
                distribution[str(year)] = pct
                
                # Display calculated units and value
                units_for_year = int(total_units * pct / 100)
                value_for_year = total_revenue * pct / 100
                st.caption(f"Units: {units_for_year:,}")
                st.caption(f"Value: {value_for_year:.0f}B VND")
        
        # Validate percentages
        total_pct = sum(distribution.values())
        col1, col2 = st.columns(2)
        
        with col1:
            if abs(total_pct - 100.0) < 0.01:
                st.success(f"✅ Total: {total_pct:.1f}%")
            else:
                st.error(f"❌ Total: {total_pct:.1f}% (must be 100%)")
        
        with col2:
            if st.button("Reset to Linear Distribution", key="reset_presales"):
                # Reset to even distribution across all years
                even_pct = 100.0 / len(years) if len(years) > 0 else 100.0
                reset_dist = {}
                for year in years:
                    reset_dist[str(year)] = even_pct
                st.session_state.edited_project['presales_distribution'] = reset_dist
                st.rerun()
        
        st.session_state.edited_project['presales_distribution'] = distribution
        
        # Show visual chart of distribution
        if years:
            import plotly.graph_objects as go
            
            # Calculate total revenue to show absolute values for presales
            edited = st.session_state.edited_project
            nsa = float(edited.get('net_sellable_area', 0) or 0)
            asp = float(edited.get('average_selling_price', 0) or 0)
            total_revenue = nsa * asp / 1e9  # Convert to billions
            
            # Calculate absolute values for each year
            absolute_values = [total_revenue * distribution.get(str(y), 0) / 100 for y in years]
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=[str(y) for y in years],
                y=absolute_values,
                text=[f"{abs_val:.0f}B ({distribution.get(str(y), 0):.1f}%)" for y, abs_val in zip(years, absolute_values)],
                textposition='auto',
                marker_color='lightblue'
            ))
            fig.update_layout(
                title="Presales Schedule",
                xaxis_title="Year",
                yaxis_title="Presales Value (VND Billions)",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)
    
    def render_project_balance_sheet_analysis(self, project_data):
        """Render balance sheet analysis using project data"""
        # First display Project Financial Summary
        st.subheader("📊 Project Financial Summary")
        
        # Get edited project data
        edited = st.session_state.edited_project
        
        # Calculate totals for summary
        nsa = float(edited.get('net_sellable_area', 0) or 0)
        asp = float(edited.get('average_selling_price', 0) or 0)
        gfa = float(edited.get('gross_floor_area', 0) or 0)
        const_cost = float(edited.get('construction_cost_per_sqm', 0) or 0)
        land_area = float(edited.get('land_area', 0) or 0)
        land_cost = float(edited.get('land_cost_per_sqm', 0) or 0)
        
        total_revenue = nsa * asp
        total_const_cost = gfa * const_cost
        total_land_cost = land_area * land_cost
        sga_pct = float(edited.get('sga_percentage', 0.08) or 0.08)
        total_sga = total_revenue * sga_pct
        
        # Get debt and financial parameters
        total_debt = float(edited.get('total_debt', 0) or 0)
        cost_of_debt = float(edited.get('cost_of_debt', 0.08) or 0.08)
        
        # Get timeline parameters
        const_start = int(edited.get('construction_start_year', 2025) or 2025)
        const_years = int(edited.get('construction_years', 3) or 3)
        const_end = const_start + const_years - 1
        
        revenue_booking_start = int(edited.get('revenue_booking_start_year', 2027) or 2027)
        revenue_booking_years = int(edited.get('revenue_booking_years', 2) or 2)
        revenue_booking_end = revenue_booking_start + revenue_booking_years - 1
        
        debt_repayment_start = int(edited.get('debt_repayment_year', revenue_booking_end) or revenue_booking_end)
        
        # Calculate financial metrics
        total_project_cost = total_const_cost + total_land_cost
        actual_debt_pct = (total_debt / total_project_cost * 100) if total_project_cost > 0 else 0
        
        # Create summary data (removed PBT and PAT)
        summary_data = {
            "Metric": [
                "Total Revenue",
                "Total Construction Cost",
                "Total Land Cost",
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
            height=350  # Reduced height since we have fewer rows
        )
        
        st.markdown("---")
        
        # Now display Balance Sheet Analysis
        st.subheader("📊 Balance Sheet Analysis")
        
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
        
        # Calculate totals
        total_revenue = nsa * asp
        total_const_cost = gfa * const_cost
        total_land_cost = land_area * land_cost
        sga_pct = float(edited.get('sga_percentage', 0.08) or 0.08)
        total_sga = total_revenue * sga_pct  # Calculate total SG&A
        
        # Get timeline parameters
        const_start = int(edited.get('construction_start_year', 2025) or 2025)
        const_years = int(edited.get('construction_years', 3) or 3)
        const_end = const_start + const_years - 1  # Calculate end year from duration
        
        land_payment_year = int(edited.get('land_payment_year', const_start) or const_start)
        
        # Debug: Show the timeline being used
        st.info(f"📅 Timeline: Land payment ({land_payment_year}), Construction ({const_start}-{const_end})")
        
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
        
        # Get distributions if available
        presales_dist = edited.get('presales_distribution', {})  # Fix: use presales_distribution
        revenue_dist = edited.get('revenue_distribution', {})  # This is for revenue recognition
        
        # Display key balance sheet parameters
        st.info("📈 **Balance Sheet Parameters** (derived from project data)")
        
        
        # Auto-calculate balance sheet analysis
        # Check if we have minimum required data to run analysis
        if total_revenue > 0 and (total_const_cost > 0 or total_land_cost > 0):
            try:
                # Get tax rate from assumptions or use default
                tax_rate = 0.2  # Default 20% corporate tax rate in Vietnam
                
                # Generate balance sheet schedules
                df = generate_simplified_balance_sheet_schedules(
                    total_debt=total_debt,
                    total_construction_cost=total_const_cost,
                    total_land_cost=total_land_cost,
                    land_payment_year=land_payment_year,
                    total_revenue=total_revenue,
                    interest_rate=cost_of_debt,  # Use cost_of_debt for interest calculations
                    sga_percentage=sga_pct,
                    construction_start_year=const_start,
                    construction_end_year=const_end,
                    sales_start_year=presales_start,
                    sales_end_year=presales_end,
                    debt_repayment_start_year=debt_repayment_start,
                    debt_repayment_end_year=debt_repayment_end,
                    revenue_booking_start_year=revenue_booking_start,
                    revenue_booking_end_year=revenue_booking_end,
                    presales_distribution=presales_dist if presales_dist else None,
                    revenue_distribution=revenue_dist if revenue_dist else None,
                    tax_rate=tax_rate
                )
                
                # Display Results
                st.success("✅ Balance sheet analysis completed!")
                
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
                    'Presales': 'Presales',
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
                    'Cash_Inflow_Presales': 'Cash Inflow (Presales)',
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
                        elif item_name in ['Presales', 'Customer Prepayment Balance']:
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
                cashflow_items = ['Cash Inflow (Presales)', 'Cash Inflow (Debt Disbursement)',
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
                           'Presales', 'Customer Prepayment Balance']
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
                st.subheader("📊 Balance Sheet")
                
                # Apply styling to balance sheet
                styled_bs_df = bs_df.style.apply(highlight_sections, axis=0).format(format_dict).set_properties(**{'text-align': 'left'}, subset=pd.IndexSlice[:, :])
                st.dataframe(
                    styled_bs_df,
                    use_container_width=True,
                    height=300
                )
                
                # Display P&L table
                st.subheader("💰 Profit & Loss Statement")
                
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
                st.subheader("💵 Cash Flow Statement")
                
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
                st.error(f"❌ Error running balance sheet analysis: {str(e)}")
        else:
            # Show info message when insufficient data
            st.info("ℹ️ Balance sheet analysis will be generated automatically once project parameters are configured (revenue and construction/land costs required)")
    
    def render_project_financial_analysis(self, project_data):
        """Render financial analysis including RNAV calculation"""
        st.subheader("Financial Analysis & RNAV Calculation")
        
        # Import RNAV utilities
        from utils.RNAV_utils import (
            selling_progress_schedule_custom,
            land_use_right_payment_schedule_single_year,
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
        
        total_revenue = nsa * asp
        total_const_cost = gfa * const_cost
        total_land_cost = land_area * land_cost
        sga_pct = float(edited.get('sga_percentage', 0.08) or 0.08)
        total_sga = total_revenue * sga_pct
        
        # Calculate PBT and PAT for RNAV calculation
        pbt = total_revenue - total_const_cost - total_land_cost - total_sga
        pat = pbt * 0.8  # 20% tax
        
        # Calculate RNAV if requested
        if st.button("Calculate RNAV", key="calc_rnav"):
            try:
                # Check if Balance Sheet Analysis is available
                if 'project_bs_analysis_results' not in st.session_state:
                    st.error("⚠️ Please wait for Balance Sheet Analysis to complete before calculating RNAV")
                    return
                
                bs_df = st.session_state['project_bs_analysis_results']
                current_year = datetime.now().year
                
                # Extract cash flows from Balance Sheet Analysis for RNAV calculation
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
                st.success(f"🎯 RNAV Calculated Successfully!")
                
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
                
                # Display RNAV Schedule (transposed with years as columns)
                st.subheader("📊 RNAV Calculation Details")
                
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
                
                # Format for display - all values in billions VND except Discount Factor
                format_dict = {}
                for col in df_transposed.columns:
                    format_dict[col] = "{:,.1f}"
                
                # Apply special formatting for Discount Factor row if it exists
                if 'Discount Factor' in df_transposed.index:
                    # Create a styled dataframe
                    styled_df = df_transposed.style.format(format_dict)
                    # Override format for Discount Factor row
                    for col in df_transposed.columns:
                        styled_df = styled_df.format({col: "{:.4f}"}, subset=(['Discount Factor'], [col]))
                else:
                    styled_df = df_transposed.style.format(format_dict)
                
                # Display the transposed table
                st.dataframe(styled_df, use_container_width=True)
                    
            except Exception as e:
                st.error(f"Error calculating RNAV: {str(e)}")
    
    def render_project_save_interface(self, project_data):
        """Render interface to save project changes to MongoDB"""
        st.subheader("Save Project Changes")
        
        # Show what has changed
        changes = []
        edited = st.session_state.edited_project
        
        for key, value in edited.items():
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
            st.info(f"🔄 {len(changes)} changes detected:")
            with st.expander("View changes"):
                for change in changes[:20]:  # Limit to 20 changes
                    st.write(f"- {change}")
                if len(changes) > 20:
                    st.write(f"... and {len(changes) - 20} more changes")
        else:
            st.info("✅ No changes detected. You can still save to update calculated fields.")
        
        # Get project name for use in buttons
        project_name = edited.get('project_name', project_data.get('project_name', 'Unnamed Project'))
        
        # Save and Delete buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("💾 Save Changes to MongoDB", type="primary"):
                try:
                    # Calculate financial metrics before saving
                    nsa = edited.get('net_sellable_area', 0)
                    asp = edited.get('average_selling_price', 0)
                    gfa = edited.get('gross_floor_area', 0)
                    land_area = edited.get('land_area', 0)
                    const_cost = edited.get('construction_cost_per_sqm', 0)
                    land_cost = edited.get('land_cost_per_sqm', 0)
                    
                    total_revenue = float(nsa) * float(asp)
                    total_const_cost = float(gfa) * float(const_cost)
                    total_land_cost = float(land_area) * float(land_cost)
                    sga_pct = float(edited.get('sga_percentage', 0.08))
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
                    
                    # Save Balance Sheet Analysis data if available
                    if 'project_bs_analysis_results' in st.session_state:
                        bs_df = st.session_state['project_bs_analysis_results']
                        
                        # Convert DataFrame to dictionary format for MongoDB storage
                        balance_sheet_data = {}
                        
                        # Process each year (excluding Total row)
                        for _, row in bs_df.iterrows():
                            if row['Year'] != 'Total':
                                year_str = str(int(row['Year']))
                                
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
                                    'cogs': float(row['COGS']),
                                    'sga_expense': float(row['SGA_Expense']),
                                    'interest_expense_cash': float(row['Interest_Expense_Cash']),
                                    'pbt': float(row['PBT']),
                                    'tax': float(row['Tax']),
                                    'pat': float(row['PAT']),
                                    
                                    # Cash Flow items
                                    'cash_inflow_presales': float(row['Cash_Inflow_Presales']),
                                    'debt_disbursement': float(row['Debt_Disbursement']),
                                    'debt_repayment': float(row['Debt_Repayment']),
                                    'cash_outflow_land': float(row['Cash_Outflow_Land']),
                                    'cash_outflow_construction': float(row['Cash_Outflow_Construction']),
                                    'cash_outflow_interest': float(row['Cash_Outflow_Interest']),
                                    'cash_outflow_sga': float(row['Cash_Outflow_SGA']),
                                    'cash_outflow_tax': float(row['Cash_Outflow_Tax']),
                                    'cash_balance_change': float(row['Cash_Balance_Change'])
                                }
                        
                        # Store complete balance sheet analysis in project data
                        edited['balance_sheet_analysis'] = balance_sheet_data
                        
                        # Also extract summary totals for quick access
                        total_row = bs_df[bs_df['Year'] == 'Total']
                        if not total_row.empty:
                            edited['balance_sheet_summary'] = {
                                'total_revenue': float(total_row['Revenue_Recognition'].iloc[0]),
                                'total_cogs': float(total_row['COGS'].iloc[0]),
                                'total_sga': float(total_row['SGA_Expense'].iloc[0]),
                                'total_interest': float(total_row['Interest_Expense_Cash'].iloc[0]),
                                'total_pbt': float(total_row['PBT'].iloc[0]),
                                'total_tax': float(total_row['Tax'].iloc[0]),
                                'total_pat': float(total_row['PAT'].iloc[0]),
                                'final_debt_balance': float(total_row['Debt_Balance'].iloc[0]),
                                'final_cash_balance': float(total_row['Cumulative_Cash_Balance'].iloc[0]),
                                'final_inventory_balance': float(total_row['Inventory_Balance'].iloc[0])
                            }
                    
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
                    
                    # Save to MongoDB
                    from utils.mongodb_utils import save_project_to_mongodb
                    
                    result = save_project_to_mongodb(
                        edited,
                        project_name,
                        rnav_value=rnav_to_save
                    )
                    
                    if result['success']:
                        st.success(result['message'])
                        # Clear editing state
                        if 'current_editing_project' in st.session_state:
                            del st.session_state.current_editing_project
                        st.rerun()
                    else:
                        st.error(result['message'])
                        
                except Exception as e:
                    st.error(f"Error saving project: {str(e)}")
        
        # Delete button
        with col2:
            if st.button("🗑️ Delete from MongoDB", type="secondary", use_container_width=True):
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
            if st.button("❌ Cancel", use_container_width=True):
                if 'current_editing_project' in st.session_state:
                    del st.session_state.current_editing_project
                if 'confirm_delete' in st.session_state:
                    del st.session_state.confirm_delete
                st.rerun()
