#%%
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime


class ProjectPipelineRealEstateTab:
    """Project Pipeline tab specifically for Real Estate Financial Model"""
    
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
                'Start': project.get('construction_start_year', 2025),
                'End': project.get('project_completion_year', 2028),
                'Revenue Start': project.get('revenue_booking_start_year', 2026)
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
        """Render form for creating a new project"""
        # This method will be moved from the parent class
        # For now, delegate to parent
        if hasattr(self.parent, 'render_new_project_form'):
            self.parent.render_new_project_form()
        else:
            st.info("New project form implementation will be added here")
    
    def render_individual_project_editor(self, project_name, df_projects):
        """Render individual project editor"""
        # This method will be moved from the parent class
        # For now, delegate to parent
        if hasattr(self.parent, 'render_individual_project_editor'):
            self.parent.render_individual_project_editor(project_name, df_projects)
        else:
            st.info("Individual project editor implementation will be added here")