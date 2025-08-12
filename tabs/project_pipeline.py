#%%
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime


class ProjectPipelineTab:
    """Project pipeline analysis tab with vectorized operations"""
    
    def __init__(self, parent):
        self.parent = parent
    
    def render(self):
        """Render project pipeline and timeline"""
        st.header("Project Pipeline Analysis")
        
        df_projects = st.session_state.project_data
        
        if df_projects is None or (isinstance(df_projects, pd.DataFrame) and df_projects.empty):
            st.info("👈 Click 'Sync Project Data' in the sidebar to load projects from MongoDB")
            return
        
        # Add project selector for individual project editing
        st.subheader("🎯 Select Individual Project")
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
        
        # Project summary metrics with vectorized calculations
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Projects", len(df_projects))
            
        with col2:
            total_units = self._calculate_total_units(df_projects)
            st.metric("Total Units", f"{int(total_units):,}")
            
        with col3:
            total_nsa = self._calculate_total_nsa(df_projects)
            st.metric("Total NSA", f"{total_nsa:,.0f} sqm")
            
        with col4:
            avg_price = self._calculate_avg_price(df_projects)
            st.metric("Avg Price/sqm", f"{avg_price:,.0f}M VND")
        
        # Project timeline visualization
        st.subheader("Project Timeline")
        self._render_timeline_chart(df_projects)
        
        # Project details table
        st.subheader("Project Details")
        self._render_project_details_table(df_projects)
    
    def _calculate_total_units(self, df_projects):
        """Vectorized calculation of total units"""
        if 'total_units' in df_projects.columns:
            return df_projects['total_units'].fillna(0).sum()
        return 0
    
    def _calculate_total_nsa(self, df_projects):
        """Vectorized calculation of total NSA"""
        if 'net_sellable_area' in df_projects.columns:
            return df_projects['net_sellable_area'].fillna(0).sum()
        return 0
    
    def _calculate_avg_price(self, df_projects):
        """Vectorized calculation of average price"""
        if 'average_selling_price' in df_projects.columns:
            return df_projects['average_selling_price'].fillna(0).mean()
        return 0
    
    def _render_timeline_chart(self, df_projects):
        """Render project timeline with vectorized data preparation"""
        # Vectorized timeline data extraction
        required_columns = ['project_name', 'construction_start_year', 'project_completion_year', 'revenue_booking_start_year']
        timeline_data = {}
        
        for col in required_columns:
            if col in df_projects.columns:
                timeline_data[col.replace('_', ' ').title()] = df_projects[col]
            else:
                # Default values
                if 'start' in col.lower():
                    timeline_data[col.replace('_', ' ').title()] = 2025
                elif 'completion' in col.lower():
                    timeline_data[col.replace('_', ' ').title()] = 2028
                elif 'revenue' in col.lower():
                    timeline_data[col.replace('_', ' ').title()] = 2026
                else:
                    timeline_data[col.replace('_', ' ').title()] = df_projects['project_name'] if col == 'project_name' else 2025
        
        timeline_df = pd.DataFrame(timeline_data)
        timeline_df.columns = ['Project', 'Start', 'End', 'Revenue Start']
        
        # Create Gantt chart
        fig = go.Figure()
        
        # Vectorized chart creation
        projects = timeline_df['Project'].values
        starts = timeline_df['Start'].values
        ends = timeline_df['End'].values
        revenue_starts = timeline_df['Revenue Start'].values
        
        # Add project bars
        for i, (project, start, end, rev_start) in enumerate(zip(projects, starts, ends, revenue_starts)):
            fig.add_trace(go.Scatter(
                x=[start, end],
                y=[project, project],
                mode='lines',
                line=dict(width=20, color='lightblue'),
                name=project,
                showlegend=False,
                hovertemplate=f"Project: {project}<br>Period: {start}-{end}<extra></extra>"
            ))
            
            # Add revenue start marker
            fig.add_trace(go.Scatter(
                x=[rev_start],
                y=[project],
                mode='markers',
                marker=dict(size=10, color='red'),
                name='Revenue Start',
                showlegend=i == 0
            ))
        
        fig.update_layout(
            title="Project Development Timeline",
            xaxis_title="Year",
            yaxis_title="Project",
            height=400,
            showlegend=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_project_details_table(self, df_projects):
        """Render project details table with vectorized formatting"""
        # Define columns to display
        display_columns = [
            'project_name', 'location', 'total_units', 'net_sellable_area',
            'average_selling_price', 'construction_start_year', 
            'project_completion_year', 'rnav_value', 'last_updated'
        ]
        
        # Check which columns are actually available
        available_columns = [col for col in display_columns if col in df_projects.columns]
        
        if available_columns:
            # Create a display dataframe with formatting
            display_df = df_projects[available_columns].copy()
            
            # Vectorized formatting
            self._format_display_columns(display_df)
            
            # Rename columns for better display
            column_rename = {
                'project_name': 'Project Name',
                'location': 'Location',
                'total_units': 'Total Units',
                'net_sellable_area': 'NSA (sqm)',
                'average_selling_price': 'Avg Price (M VND/sqm)',
                'construction_start_year': 'Construction Start',
                'project_completion_year': 'Completion Year',
                'rnav_value': 'RNAV (VND)',
                'last_updated': 'Last Updated'
            }
            
            display_df = display_df.rename(columns=column_rename)
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            # If no standard columns found, display all available columns
            st.dataframe(
                df_projects,
                use_container_width=True,
                hide_index=True
            )
    
    def _format_display_columns(self, display_df):
        """Vectorized formatting of display columns"""
        # Format numeric columns using vectorized operations
        if 'net_sellable_area' in display_df.columns:
            display_df['net_sellable_area'] = display_df['net_sellable_area'].apply(
                lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
            )
        
        if 'total_units' in display_df.columns:
            display_df['total_units'] = display_df['total_units'].apply(
                lambda x: f"{int(x):,}" if pd.notna(x) else "N/A"
            )
        
        if 'average_selling_price' in display_df.columns:
            display_df['average_selling_price'] = display_df['average_selling_price'].apply(
                lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
            )
        
        if 'rnav_value' in display_df.columns:
            display_df['rnav_value'] = display_df['rnav_value'].apply(
                lambda x: f"{x/1e9:,.1f}B" if pd.notna(x) and x > 0 else "N/A"
            )
    
    def render_new_project_form(self):
        """Render form for creating a brand new project"""
        st.subheader("➕ Create New Project")
        st.info("Enter details for your new project. All fields start empty for a fresh start.")
        
        # Initialize empty project data if not exists
        if 'new_project_data' not in st.session_state:
            st.session_state.new_project_data = {}
        
        # Basic Information Section
        st.markdown("### 📋 Basic Information")
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
        
        # Additional form fields would go here...
        # For brevity, just showing the basic structure
        
        if st.button("💾 Save New Project"):
            if project_name and company_ticker:
                # Create new project data structure
                new_project = {
                    'project_name': project_name,
                    'company_ticker': company_ticker,
                    'location': location,
                    # Add other fields...
                }
                
                # Save to MongoDB
                result = self.parent.save_new_project(new_project)
                if result['success']:
                    st.success("✅ New project created successfully!")
                    # Clear form
                    st.session_state.new_project_data = {}
                    st.rerun()
                else:
                    st.error(f"❌ Failed to create project: {result['message']}")
            else:
                st.error("❌ Please fill in required fields: Project Name and Company Ticker")
    
    def render_individual_project_editor(self, project_name, df_projects):
        """Render individual project editor - delegated to parent for now"""
        # This would be extracted to its own component later
        self.parent.render_individual_project_editor(project_name, df_projects)