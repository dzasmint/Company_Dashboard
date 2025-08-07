import streamlit as st
import pandas as pd
import os
from urllib.parse import urlencode

# Page configuration
st.set_page_config(
    page_title="Real Estate Dashboard",
    page_icon="🏢",
    layout="wide"
)

def load_projects_data():
    """Load real estate projects from CSV database"""
    try:
        csv_path = os.path.join("data", "real_estate_projects.csv")
        df = pd.read_csv(csv_path)
        return df
    except FileNotFoundError:
        st.error("❌ Real estate projects database not found. Please ensure 'data/real_estate_projects.csv' exists.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ Error loading projects data: {str(e)}")
        return pd.DataFrame()

def format_vnd_display(value):
    """Format VND values for display"""
    if pd.isna(value) or value == 0:
        return "N/A"
    
    if value >= 1_000_000_000:
        return f"{value/1_000_000_000:,.1f}B VND"
    elif value >= 1_000_000:
        return f"{value/1_000_000:,.0f}M VND"
    else:
        return f"{value:,.0f} VND"

def format_area_display(value):
    """Format area values for display"""
    if pd.isna(value) or value == 0:
        return "N/A"
    return f"{value:,.0f} m²"

def format_units_display(value):
    """Format unit count for display"""
    if pd.isna(value) or value == 0:
        return "N/A"
    return f"{int(value):,} units"

def main():
    st.title("🏢 Real Estate Company Dashboard")
    
    # Load projects data
    df_projects = load_projects_data()
    
    if df_projects.empty:
        st.warning("No project data available. Please check the database file.")
        return
    
    # Sidebar for company selection
    st.sidebar.header("🔍 Company Selection")
    
    # Get unique companies
    companies = df_projects[['company_ticker', 'company_name']].drop_duplicates()
    company_options = [f"{row['company_ticker']} - {row['company_name']}" for _, row in companies.iterrows()]
    
    selected_company = st.sidebar.selectbox(
        "Select Company:",
        options=["Select a company..."] + company_options,
        index=0
    )
    
    if selected_company == "Select a company...":
        # Show overview of all companies
        st.header("📊 Company Overview")
        
        # Calculate summary statistics by company including RNAV
        company_summary = df_projects.groupby(['company_ticker', 'company_name']).agg({
            'project_name': 'count',
            'total_units': 'sum',
            'net_sellable_area': 'sum',
            'average_selling_price': 'mean',
            'rnav_value': 'sum'
        }).reset_index()
        
        company_summary.columns = ['Ticker', 'Company Name', 'Total Projects', 'Total Units', 'Total NSA (m²)', 'Avg Price (VND/m²)', 'Total RNAV']
        
        # Sort by Total RNAV descending
        company_summary = company_summary.sort_values('Total RNAV', ascending=False, na_position='last')
        
        # Format the summary table
        for idx, row in company_summary.iterrows():
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            
            with col1:
                st.metric("Ticker", row['Ticker'])
            with col2:
                st.metric("Projects", f"{int(row['Total Projects'])}")
            with col3:
                st.metric("Total Units", format_units_display(row['Total Units']))
            with col4:
                st.metric("Total NSA", format_area_display(row['Total NSA (m²)']))
            with col5:
                st.metric("Avg Price", format_vnd_display(row['Avg Price (VND/m²)']))
            with col6:
                st.metric("🏆 Total RNAV", format_vnd_display(row['Total RNAV']))
            
            st.markdown("---")
        
        st.info("👆 Select a company from the sidebar to view detailed project information and individual RNAVs.")
        
    else:
        # Extract ticker from selection
        selected_ticker = selected_company.split(" - ")[0]
        
        # Filter projects for selected company
        company_projects = df_projects[df_projects['company_ticker'] == selected_ticker].copy()
        
        if company_projects.empty:
            st.warning(f"No projects found for {selected_company}")
            return
        
        # Display company header
        company_name = company_projects.iloc[0]['company_name']
        st.header(f"🏢 {selected_ticker} - {company_name}")
        
        # Company statistics including total RNAV
        total_projects = len(company_projects)
        total_units = company_projects['total_units'].sum()
        total_nsa = company_projects['net_sellable_area'].sum()
        avg_price = company_projects['average_selling_price'].mean()
        total_rnav = company_projects['rnav_value'].sum()
        
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total Projects", total_projects)
        with col2:
            st.metric("Total Units", format_units_display(total_units))
        with col3:
            st.metric("Total NSA", format_area_display(total_nsa))
        with col4:
            st.metric("Avg Selling Price", format_vnd_display(avg_price))
        with col5:
            st.metric("🏆 Total Portfolio RNAV", format_vnd_display(total_rnav))
        
        st.markdown("---")
        
        # Projects table with RNAV
        st.subheader("📋 Project Portfolio with RNAV")
        
        # Sort projects by RNAV descending
        company_projects = company_projects.sort_values('rnav_value', ascending=False, na_position='last')
        
        # Create display table with formatted values
        display_projects = company_projects.copy()
        
        # Format columns for display
        display_projects['Units'] = display_projects['total_units'].apply(format_units_display)
        display_projects['ASP (VND/m²)'] = display_projects['average_selling_price'].apply(format_vnd_display)
        display_projects['NSA'] = display_projects['net_sellable_area'].apply(format_area_display)
        display_projects['RNAV'] = display_projects['rnav_value'].apply(format_vnd_display)
        display_projects['Last Updated'] = pd.to_datetime(display_projects['last_updated'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # Select columns for display - reordered to show RNAV prominently
        display_cols = [
            'project_name', 'RNAV', 'Units', 'ASP (VND/m²)', 'NSA',
            'construction_start_year', 'project_completion_year', 'Last Updated'
        ]
        
        # Rename columns for better display
        column_names = {
            'project_name': 'Project Name',
            'construction_start_year': 'Start Year',
            'project_completion_year': 'Completion Year'
        }
        
        display_table = display_projects[display_cols].rename(columns=column_names)
        
        # Use data editor for interactive table
        st.data_editor(
            display_table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Project Name": st.column_config.TextColumn("Project Name", width="large"),
                "RNAV": st.column_config.TextColumn("🏆 RNAV", width="medium"),
                "Units": st.column_config.TextColumn("Units", width="small"),
                "ASP (VND/m²)": st.column_config.TextColumn("ASP", width="small"),
                "NSA": st.column_config.TextColumn("NSA", width="small"),
                "Start Year": st.column_config.NumberColumn("Start", width="small"),
                "Completion Year": st.column_config.NumberColumn("Complete", width="small"),
                "Last Updated": st.column_config.TextColumn("Updated", width="small")
            },
            disabled=True
        )
        
        # Show RNAV statistics
        st.markdown("---")
        st.subheader("📊 RNAV Analysis")
        
        # Filter projects with RNAV data
        projects_with_rnav = company_projects[company_projects['rnav_value'].notna() & (company_projects['rnav_value'] > 0)]
        
        if len(projects_with_rnav) > 0:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Projects with RNAV", f"{len(projects_with_rnav)}/{total_projects}")
            with col2:
                avg_rnav = projects_with_rnav['rnav_value'].mean()
                st.metric("Avg RNAV per Project", format_vnd_display(avg_rnav))
            with col3:
                max_rnav = projects_with_rnav['rnav_value'].max()
                st.metric("Highest RNAV", format_vnd_display(max_rnav))
            with col4:
                max_project = projects_with_rnav.loc[projects_with_rnav['rnav_value'].idxmax(), 'project_name']
                st.metric("Top Project", max_project)
        else:
            st.warning("⚠️ No RNAV data available for projects in this company. Calculate RNAV for projects to see analysis.")
        
        st.markdown("---")
        
        # Project selection for RNAV calculator
        st.subheader("🧮 Open RNAV Calculator")
        
        project_names = company_projects['project_name'].tolist()
        selected_project = st.selectbox(
            "Select a project to analyze:",
            options=["Select a project..."] + project_names,
            index=0
        )
        
        if selected_project != "Select a project...":
            # Get project data
            project_data = company_projects[company_projects['project_name'] == selected_project].iloc[0]
            
            # Display project summary with RNAV
            st.info(f"📊 **Selected Project:** {selected_project}")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.write(f"**Units:** {format_units_display(project_data['total_units'])}")
                st.write(f"**NSA:** {format_area_display(project_data['net_sellable_area'])}")
            with col2:
                st.write(f"**ASP:** {format_vnd_display(project_data['average_selling_price'])}")
                st.write(f"**GFA:** {format_area_display(project_data['gross_floor_area'])}")
            with col3:
                st.write(f"**Land Area:** {format_area_display(project_data['land_area'])}")
                st.write(f"**Construction Cost:** {format_vnd_display(project_data['construction_cost_per_sqm'])}")
            with col4:
                st.write(f"**🏆 Current RNAV:** {format_vnd_display(project_data['rnav_value'])}")
                if pd.notna(project_data['last_updated']):
                    st.write(f"**Last Updated:** {project_data['last_updated']}")
                else:
                    st.write("**Status:** Not calculated")
            
            # Button to open RNAV calculator
            if st.button(f"🧮 Open RNAV Calculator for {selected_project}", type="primary"):
                # Store project data in session state
                st.session_state['preload_project_data'] = project_data.to_dict()
                st.session_state['preload_project_name'] = selected_project
                
                # Show success message and navigation instruction
                st.success(f"✅ Project data loaded! Navigate to 'Real Estate RNAV Copy' page to see the pre-loaded calculator.")
                st.info("💡 **Next Step:** Use the sidebar navigation to go to 'Real Estate RNAV Copy' page.")

if __name__ == "__main__":
    main()
