import streamlit as st
import pandas as pd
import os
from pymongo import MongoClient
from datetime import datetime
import certifi
from dotenv import load_dotenv
import sys

# Load environment variables from .env file
load_dotenv()

# Add the parent directory to sys.path to import from utils
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import MongoDB utilities
from utils.mongodb_utils import (
    get_financials_for_company
)


# Page configuration
st.set_page_config(
    page_title="Real Estate Dashboard (MongoDB)",
    page_icon="🏢",
    layout="wide"
)

@st.cache_resource
def init_mongodb_connection():
    """Initialize MongoDB connection"""
    try:
        # Get MongoDB connection string from .env file
        connection_string = os.getenv('MONGODB_CONNECTION_STRING')
        
        if not connection_string:
            st.error("❌ MONGODB_CONNECTION_STRING not found in .env file. Please add it to your .env file.")
            return None
        
        # Create MongoDB client with SSL certificate verification
        client = MongoClient(connection_string, tlsCAFile=certifi.where())
        
        # Test connection
        client.admin.command('ping')
        return client
    except Exception as e:
        st.error(f"❌ Error connecting to MongoDB: {str(e)}")
        return None

def load_companies_data():
    """Load companies from MongoDB Companies collection"""
    try:
        client = init_mongodb_connection()
        if client is None:
            return pd.DataFrame()
        
        # Get database and collection names
        db_name = 'VietnamStocks'
        collection_name = 'Companies'
        
        # Get database and collection
        db = client.get_database(db_name)
        collection = db.get_collection(collection_name)
        
        # Query all companies
        companies_cursor = collection.find({})
        companies_list = list(companies_cursor)
        
        if not companies_list:
            st.warning(f"No companies found in MongoDB database '{db_name}', collection '{collection_name}'.")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(companies_list)
        
        # Remove MongoDB ObjectId if present
        if '_id' in df.columns:
            df = df.drop('_id', axis=1)
        
        return df
        
    except Exception as e:
        st.error(f"❌ Error loading companies data from MongoDB: {str(e)}")
        return pd.DataFrame()

def load_projects_data():
    """Load real estate projects from MongoDB database"""
    try:
        client = init_mongodb_connection()
        if client is None:
            return pd.DataFrame()
        
        # Get database and collection names - using VietnamStocks database
        db_name = 'VietnamStocks'
        collection_name = 'RealEstateProjects'
        
        # Get database and collection
        db = client.get_database(db_name)
        collection = db.get_collection(collection_name)
        
        # Query all projects
        projects_cursor = collection.find({})
        projects_list = list(projects_cursor)
        
        if not projects_list:
            st.warning(f"No projects found in MongoDB database '{db_name}', collection '{collection_name}'.")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df_projects = pd.DataFrame(projects_list)
        
        # Remove MongoDB ObjectId if present
        if '_id' in df_projects.columns:
            df_projects = df_projects.drop('_id', axis=1)
        
        # Load companies data and merge
        df_companies = load_companies_data()
        if not df_companies.empty:
            # Merge projects with company information on company_ticker
            df_merged = df_projects.merge(
                df_companies[['ticker', 'company_name', 'sector']], 
                left_on='company_ticker', 
                right_on='ticker', 
                how='left'
            )
            # Drop the duplicate ticker column
            if 'ticker' in df_merged.columns:
                df_merged = df_merged.drop('ticker', axis=1)
            
            # Handle date conversion for last_updated if it exists
            if 'last_updated' in df_merged.columns:
                df_merged['last_updated'] = pd.to_datetime(df_merged['last_updated'], errors='coerce')
            
            return df_merged
        else:
            # Handle date conversion for last_updated if it exists
            if 'last_updated' in df_projects.columns:
                df_projects['last_updated'] = pd.to_datetime(df_projects['last_updated'], errors='coerce')
            return df_projects
        
    except Exception as e:
        st.error(f"❌ Error loading projects data from MongoDB: {str(e)}")
        return pd.DataFrame()

def format_vnd_display(value):
    """Format VND values for display"""
    if pd.isna(value) or value == 0:
        return "N/A"
    
    if value >= 1_000_000_000:
        return f"{value/1_000_000_000:,.0f}"
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

def update_project_rnav(project_id, rnav_value):
    """Update RNAV value for a project in MongoDB"""
    try:
        client = init_mongodb_connection()
        if client is None:
            return False
        
        # Get database and collection names - using VietnamStocks database
        db_name = 'VietnamStocks'
        collection_name = 'RealEstateProjects'
        
        db = client.get_database(db_name)
        collection = db.get_collection(collection_name)
        
        # Update the project with new RNAV value and timestamp
        result = collection.update_one(
            {'project_id': project_id},  # Adjust the filter field as needed
            {
                '$set': {
                    'rnav_value': rnav_value,
                    'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }
        )
        
        return result.modified_count > 0
        
    except Exception as e:
        st.error(f"❌ Error updating RNAV in MongoDB: {str(e)}")
        return False

def main():
    st.title("🏢 Real Estate Company Dashboard (MongoDB)")
    
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
            st.stop()
    
    # Load projects data (now includes company info)
    df_projects = load_projects_data()
    
    if df_projects.empty:
        st.warning("No project data available. Please check the MongoDB database.")
        return
    
    # Debug: Show available columns
    with st.sidebar:
        st.subheader("📋 Available Data")
        st.write(f"Total Projects: {len(df_projects)}")
        if 'company_ticker' in df_projects.columns:
            unique_companies = df_projects['company_ticker'].nunique()
            st.write(f"Unique Companies: {unique_companies}")
    
    # Sidebar for company selection
    st.sidebar.header("🔍 Company Selection")
    
    # Get unique companies - handle both cases where company_name might or might not be available
    if 'company_name' in df_projects.columns:
        companies = df_projects[['company_ticker', 'company_name']].dropna().drop_duplicates()
        company_options = [f"{row['company_ticker']} - {row['company_name']}" for _, row in companies.iterrows()]
    else:
        companies = df_projects[['company_ticker']].dropna().drop_duplicates()
        company_options = [row['company_ticker'] for _, row in companies.iterrows()]
    
    selected_company = st.sidebar.selectbox(
        "Select Company:",
        options=["Select a company..."] + company_options,
        index=0
    )
    
    # Add Quarterly Filing dropdown
    st.sidebar.header("📅 Reporting Period")
    quarterly_options = ["2025Q1", "2024Q4", "2024Q3", "2024Q2", "2024Q1"]
    selected_quarter = st.sidebar.selectbox(
        "Quarterly Filing:",
        options=quarterly_options,
        index=0  # Default to 2025Q1
    )
    
    # Display selected quarter info
    st.sidebar.info(f"📊 Selected Period: **{selected_quarter}**")
    
    if selected_company == "Select a company...":
        # Show overview of all companies
        st.header("📊 Company Overview")
        
        # Calculate summary statistics by company including RNAV
        if 'company_name' in df_projects.columns:
            group_cols = ['company_ticker', 'company_name']
        else:
            group_cols = ['company_ticker']
        
        company_summary = df_projects.groupby(group_cols).agg({
            'project_name': 'count',
            'total_units': 'sum',
            'net_sellable_area': 'sum',
            'average_selling_price': 'mean',
            'rnav_value': 'sum'
        }).reset_index()
        
        if 'company_name' in df_projects.columns:
            company_summary.columns = ['Ticker', 'Company Name', 'Total Projects', 'Total Units', 'Total NSA (m²)', 'Avg Price (VND/m²)', 'Total RNAV']
        else:
            company_summary.columns = ['Ticker', 'Total Projects', 'Total Units', 'Total NSA (m²)', 'Avg Price (VND/m²)', 'Total RNAV']
        
        # Sort by Total RNAV descending
        company_summary = company_summary.sort_values('Total RNAV', ascending=False, na_position='last')
        
        # Format the summary table
        for idx, row in company_summary.iterrows():
            if 'company_name' in df_projects.columns:
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                
                with col1:
                    st.metric("Ticker", row['Ticker'])
                with col2:
                    st.metric("Company", row['Company Name'][:15] + "..." if len(str(row['Company Name'])) > 15 else row['Company Name'])
                with col3:
                    st.metric("Projects", f"{int(row['Total Projects'])}")
                with col4:
                    st.metric("Total Units", format_units_display(row['Total Units']))
                with col5:
                    st.metric("Avg Price", format_vnd_display(row['Avg Price (VND/m²)']))
                with col6:
                    st.metric("Total RNAV", format_vnd_display(row['Total RNAV']))
            else:
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    st.metric("Ticker", row['Ticker'])
                with col2:
                    st.metric("Projects", f"{int(row['Total Projects'])}")
                with col3:
                    st.metric("Total Units", format_units_display(row['Total Units']))
                with col4:
                    st.metric("Avg Price", format_vnd_display(row['Avg Price (VND/m²)']))
                with col5:
                    st.metric("Total RNAV", format_vnd_display(row['Total RNAV']))
            
            st.markdown("---")
        
        st.info("👆 Select a company from the sidebar to view detailed project information and individual RNAVs.")
        
    else:
        # Extract ticker from selection
        if " - " in selected_company:
            selected_ticker = selected_company.split(" - ")[0]
        else:
            selected_ticker = selected_company
        
        # Filter projects for selected company
        company_projects = df_projects[df_projects['company_ticker'] == selected_ticker].copy()
        
        if company_projects.empty:
            st.warning(f"No projects found for {selected_company}")
            return
        
        # Display company header
        if 'company_name' in company_projects.columns and pd.notna(company_projects.iloc[0]['company_name']):
            company_name = company_projects.iloc[0]['company_name']
            st.header(f"🏢 {selected_ticker} - {company_name}")
        else:
            st.header(f"🏢 {selected_ticker}")
        
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
            st.metric("Total Portfolio RNAV", format_vnd_display(total_rnav))
        
        st.markdown("---")

        # Get financial data for the selected company and quarter
        # st.write("### 📊 Financial Overview & Valuation")
        
        try:
            financials_df = get_financials_for_company(selected_ticker, selected_quarter)
            
            if financials_df.empty:
                st.warning(f"No financial data available for {selected_ticker} in {selected_quarter}.")
                st.info("Available quarters might be different. Please check the data source.")
            else:
                # st.success(f"✅ Financial data loaded for {selected_ticker} - {selected_quarter}")
                
                # Debug: Show available columns and KeyCodes
                # st.write("**Available Financial Data Columns:**")
                # st.write(list(financials_df.columns))
                
                # if 'Keycode' in financials_df.columns:
                #     st.write("**Available KeyCodes:**")
                #     st.write(sorted(financials_df['Keycode'].unique().tolist()))
                
                # Function to get value by KeyCode
                def get_value_by_keycode(df, keycode, default=0):
                    """Extract value for a specific Keycode"""
                    try:
                        if 'Keycode' in df.columns and 'Value' in df.columns:
                            filtered = df[df['Keycode'] == keycode]
                            if not filtered.empty:
                                value = filtered['Value'].iloc[0]
                                return float(value) if pd.notna(value) else default
                        return default
                    except Exception as e:
                        st.write(f"Error extracting {keycode}: {e}")
                        return default
                
                # Extract financial metrics using KeyCode
                cash_equivalent = get_value_by_keycode(financials_df, 'Cash_Equivalent', 0)
                st_investment = get_value_by_keycode(financials_df, 'Short_Investment', 0)
                st_debt = get_value_by_keycode(financials_df, 'ST_Debt', 0)
                lt_debt = get_value_by_keycode(financials_df, 'LT_Debt', 0)
                outstanding_shares = get_value_by_keycode(financials_df, 'OS', 0)
                
                # Debug: Show extracted values
                # st.write("**Extracted Values:**")
                # st.write(f"Cash_Equivalent: {cash_equivalent}")
                # st.write(f"Short_Investment: {st_investment}")
                # st.write(f"ST_Debt: {st_debt}")
                # st.write(f"LT_Debt: {lt_debt}")
                # st.write(f"OS: {outstanding_shares}")
                
                # Calculate net cash (positive means net cash, negative means net debt)
                net_cash = cash_equivalent + st_investment - st_debt - lt_debt
                
                # Calculate enterprise value and equity value
                enterprise_value = total_rnav  # RNAV represents enterprise value
                equity_value = enterprise_value + net_cash  # Add net cash to get equity value
                
                # Display financial data in formatted columns
                # st.write("#### Financial Data")
                
                # col1, col2, col3 = st.columns(3)
                
                # with col1:
                #     st.metric("Cash & Cash Equivalents", format_vnd_display(cash_equivalent))
                #     st.metric("Short Term Investments", format_vnd_display(st_investment))
                
                # with col2:
                #     st.metric("Short Term Debt", format_vnd_display(st_debt))
                #     st.metric("Long Term Debt", format_vnd_display(lt_debt))
                
                # with col3:
                #     st.metric("Net Cash/(Debt)", format_vnd_display(net_cash))
                #     st.metric("Outstanding Shares (M)", f"{outstanding_shares:,.0f}" if outstanding_shares > 0 else "N/A")

                # st.markdown("---")

                # Valuation summary
                st.write("#### Valuation Summary")
                
                val_col1, val_col2 = st.columns(2)
                
                with val_col1:
                    st.metric("Total Projects RNAV", format_vnd_display(enterprise_value))
                    st.metric("Equity Value", format_vnd_display(equity_value))
                
                with val_col2:
                    st.metric("Net Cash/(Debt)", format_vnd_display(net_cash))
                    if outstanding_shares > 0:
                        rnav_per_share = equity_value / (outstanding_shares)  # Convert shares from millions
                        st.metric("RNAV per Share (VND)", f"{rnav_per_share:,.0f}")
                    else:
                        st.metric("RNAV per Share", "N/A")
                
        except Exception as e:
            st.error(f"❌ Error loading financial data: {str(e)}")
            st.write("**Debug Info:**")
            st.write(f"Selected Ticker: {selected_ticker}")
            st.write(f"Selected Quarter: {selected_quarter}")
        
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
        display_projects['Total Revenue'] = display_projects['total_revenue'].apply(format_vnd_display)
        display_projects['Total PAT'] = display_projects['total_pat'].apply(format_vnd_display)
        display_projects['Last Updated'] = pd.to_datetime(display_projects['last_updated'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # Select columns for display - reordered to show RNAV prominently
        display_cols = [
            'project_name', 'location', 'RNAV', 'Total Revenue', 'Total PAT', 'Units', 'ASP (VND/m²)', 'NSA',
            'construction_start_year', 'revenue_booking_start_year', 'project_completion_year', 'Last Updated'
        ]
        
        # Rename columns for better display
        column_names = {
            'project_name': 'Project Name',
            'location': 'Location',
            'construction_start_year': 'Construction Start Year',
            'revenue_booking_start_year': 'Revenue Booking Start Year',
            'project_completion_year': 'Revenue Booking End Year'
        }
        
        display_table = display_projects[display_cols].rename(columns=column_names)
        
        # Use data editor for interactive table
        st.data_editor(
            display_table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Project Name": st.column_config.TextColumn("Project Name", width="medium"),
                "RNAV": st.column_config.TextColumn("RNAV", width="medium"),
                "Total Revenue": st.column_config.TextColumn("Total Revenue", width="small"),
                "Total PAT": st.column_config.TextColumn("Total PAT", width="small"),
                "Units": st.column_config.TextColumn("Units", width="small"),
                "ASP (VND/m²)": st.column_config.TextColumn("ASP", width="small"),
                "NSA": st.column_config.TextColumn("NSA", width="small"),
                "Construction Start Year": st.column_config.NumberColumn("Construction Start", width="small"),
                "Revenue Booking Start Year": st.column_config.NumberColumn("Revenue Booking Start Year", width="small"),
                "Revenue Booking End Year": st.column_config.NumberColumn("Revenue Booking End Year", width="small"),
                "Last Updated": st.column_config.TextColumn("Updated", width="small")
            },
            disabled=True
        )
        
        st.markdown("---")
        
        # Revenue Summary Table
        st.subheader("📈 Revenue Summary by Year")
        
        # Calculate revenue summary for each project
        if not company_projects.empty:
            # Get the range of years from all projects
            all_years = set()
            for _, project in company_projects.iterrows():
                if (pd.notna(project.get('revenue_booking_start_year')) and 
                    pd.notna(project.get('project_completion_year'))):
                    start_year = int(project['revenue_booking_start_year'])
                    end_year = int(project['project_completion_year'])
                    all_years.update(range(start_year, end_year + 1))
            
            if all_years:
                # Sort years
                year_columns = sorted(list(all_years))
                
                # Create revenue summary table
                revenue_summary_data = []
                
                for _, project in company_projects.iterrows():
                    row_data = {'Project Name': project['project_name']}
                    
                    # Get total revenue for this project
                    total_revenue = 0
                    if pd.notna(project.get('total_revenue')):
                        total_revenue = project['total_revenue']
                    
                    # Calculate annual revenue distribution
                    project_years = []
                    if (pd.notna(project.get('revenue_booking_start_year')) and 
                        pd.notna(project.get('project_completion_year'))):
                        start_year = int(project['revenue_booking_start_year'])
                        end_year = int(project['project_completion_year'])
                        project_years = list(range(start_year, end_year + 1))
                    
                    # Distribute revenue equally across booking years
                    for year in year_columns:
                        if year in project_years and total_revenue > 0:
                            # Equal distribution across revenue booking period
                            annual_revenue = total_revenue / len(project_years)
                            row_data[str(year)] = annual_revenue
                        else:
                            row_data[str(year)] = 0
                    
                    revenue_summary_data.append(row_data)
                
                # Create DataFrame
                revenue_summary_df = pd.DataFrame(revenue_summary_data)
                
                # Add sum row
                sum_row = {'Project Name': 'TOTAL'}
                for year in year_columns:
                    year_str = str(year)
                    if year_str in revenue_summary_df.columns:
                        sum_row[year_str] = revenue_summary_df[year_str].sum()
                    else:
                        sum_row[year_str] = 0
                
                # Add sum row to dataframe
                revenue_summary_df = pd.concat([revenue_summary_df, pd.DataFrame([sum_row])], ignore_index=True)
                
                # Format revenue values for display
                display_revenue_summary_df = revenue_summary_df.copy()
                for year in year_columns:
                    year_str = str(year)
                    if year_str in display_revenue_summary_df.columns:
                        display_revenue_summary_df[year_str] = display_revenue_summary_df[year_str].apply(
                            lambda x: format_vnd_display(x) if x > 0 else "-"
                        )
                
                # Display the revenue summary table
                st.data_editor(
                    display_revenue_summary_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Project Name": st.column_config.TextColumn("Project Name", width="large"),
                        **{str(year): st.column_config.TextColumn(str(year), width="medium") for year in year_columns}
                    },
                    disabled=True
                )
                
                # Show total portfolio revenue across all years
                #total_portfolio_revenue = sum(sum_row[str(year)] for year in year_columns if str(year) in sum_row)
                #st.metric("💰 Total Portfolio Revenue (All Years)", format_vnd_display(total_portfolio_revenue))
                
            else:
                st.info("No valid revenue booking timeline data available for revenue summary.")
        
        st.markdown("---")
        # PAT Summary Table
        st.subheader("📈 PAT Summary by Year")

        # Calculate PAT summary for each project
        if not company_projects.empty:
            # Get the range of years from all projects
            all_years = set()
            for _, project in company_projects.iterrows():
                if (pd.notna(project.get('revenue_booking_start_year')) and 
                    pd.notna(project.get('project_completion_year'))):
                    start_year = int(project['revenue_booking_start_year'])
                    end_year = int(project['project_completion_year'])
                    all_years.update(range(start_year, end_year + 1))
            
            if all_years:
                # Sort years
                year_columns = sorted(list(all_years))

                # Create PAT summary table
                pat_summary_data = []

                for _, project in company_projects.iterrows():
                    row_data = {'Project Name': project['project_name']}

                    # Get total PAT for this project
                    total_pat = 0
                    if pd.notna(project.get('total_pat')):
                        total_pat = project['total_pat']

                    # Calculate annual PAT distribution
                    project_years = []
                    if (pd.notna(project.get('revenue_booking_start_year')) and 
                        pd.notna(project.get('project_completion_year'))):
                        start_year = int(project['revenue_booking_start_year'])
                        end_year = int(project['project_completion_year'])
                        project_years = list(range(start_year, end_year + 1))

                    # Distribute PAT equally across booking years
                    for year in year_columns:
                        if year in project_years and total_pat > 0:
                            # Equal distribution across PAT booking period
                            annual_pat = total_pat / len(project_years)
                            row_data[str(year)] = annual_pat
                        else:
                            row_data[str(year)] = 0

                    pat_summary_data.append(row_data)

                # Create DataFrame
                pat_summary_df = pd.DataFrame(pat_summary_data)

                # Add sum row
                sum_row = {'Project Name': 'TOTAL'}
                for year in year_columns:
                    year_str = str(year)
                    if year_str in pat_summary_df.columns:
                        sum_row[year_str] = pat_summary_df[year_str].sum()
                    else:
                        sum_row[year_str] = 0
                
                # Add sum row to dataframe
                pat_summary_df = pd.concat([pat_summary_df, pd.DataFrame([sum_row])], ignore_index=True)

                # Format PAT values for display
                display_pat_summary_df = pat_summary_df.copy()
                for year in year_columns:
                    year_str = str(year)
                    if year_str in display_pat_summary_df.columns:
                        display_pat_summary_df[year_str] = display_pat_summary_df[year_str].apply(
                            lambda x: format_vnd_display(x) if x > 0 else "-"
                        )

                # Display the PAT summary table
                st.data_editor(
                    display_pat_summary_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Project Name": st.column_config.TextColumn("Project Name", width="large"),
                        **{str(year): st.column_config.TextColumn(str(year), width="medium") for year in year_columns}
                    },
                    disabled=True
                )

                # Show total portfolio PAT across all years
                #total_portfolio_pat = sum(sum_row[str(year)] for year in year_columns if str(year) in sum_row)
                #st.metric("💰 Total Portfolio PAT (All Years)", format_vnd_display(total_portfolio_pat))

            else:
                st.info("No valid revenue booking timeline data available for revenue summary.")
        
        st.markdown("---")

        # Stacked Column Chart for Revenue by Project and Year
        st.subheader("📊 Revenue by Year - Project Contribution Breakdown")
        
        # Calculate data for the stacked chart
        if not company_projects.empty:
            # Get the range of years from all projects
            chart_years = set()
            for _, project in company_projects.iterrows():
                if (pd.notna(project.get('revenue_booking_start_year')) and 
                    pd.notna(project.get('project_completion_year'))):
                    start_year = int(project['revenue_booking_start_year'])
                    end_year = int(project['project_completion_year'])
                    chart_years.update(range(start_year, end_year + 1))
            
            if chart_years:
                # Sort years
                sorted_years = sorted(list(chart_years))
                
                # Create data structure for stacked chart
                chart_data = {}
                project_names = []
                
                # Initialize data structure
                for _, project in company_projects.iterrows():
                    project_name = project['project_name']
                    project_names.append(project_name)
                    chart_data[project_name] = {year: 0 for year in sorted_years}
                
                # Calculate revenue contribution for each project by year
                for _, project in company_projects.iterrows():
                    project_name = project['project_name']
                    
                    # Get total revenue for this project
                    total_revenue = project.get('total_revenue', 0) if pd.notna(project.get('total_revenue')) else 0
                    
                    # Calculate project years
                    project_years = []
                    if (pd.notna(project.get('revenue_booking_start_year')) and 
                        pd.notna(project.get('project_completion_year'))):
                        start_year = int(project['revenue_booking_start_year'])
                        end_year = int(project['project_completion_year'])
                        project_years = list(range(start_year, end_year + 1))
                    
                    # Distribute revenue equally across project years
                    if project_years and total_revenue > 0:
                        annual_revenue = total_revenue / len(project_years)
                        
                        for year in project_years:
                            if year in chart_data[project_name]:
                                chart_data[project_name][year] = annual_revenue / 1_000_000_000  # Convert to billions
                
                # Create the stacked bar chart using Plotly
                import plotly.graph_objects as go
                import plotly.colors as colors
                
                fig = go.Figure()
                
                # Generate colors for each project
                color_palette = colors.qualitative.Set3[:len(project_names)]
                if len(project_names) > len(color_palette):
                    color_palette = color_palette * (len(project_names) // len(color_palette) + 1)
                
                # Add a trace for each project
                for i, project_name in enumerate(project_names):
                    y_values = [chart_data[project_name][year] for year in sorted_years]
                    
                    # Only add trace if project has non-zero values
                    if any(val > 0 for val in y_values):
                        fig.add_trace(go.Bar(
                            x=sorted_years,
                            y=y_values,
                            name=project_name[:20] + "..." if len(project_name) > 20 else project_name,  # Truncate long names
                            marker_color=color_palette[i],
                            text=[f'{val:.1f}B' if val > 0 else '' for val in y_values],
                            textposition='inside',
                            textfont=dict(size=10)
                        ))
                
                # Update layout
                fig.update_layout(
                    title=f'{selected_ticker} - Revenue Breakdown by Project and Year',
                    xaxis_title='Year',
                    yaxis_title='Revenue (Billions VND)',
                    barmode='stack',
                    height=600,
                    showlegend=True,
                    legend=dict(
                        orientation="v",
                        yanchor="top",
                        y=1,
                        xanchor="left",
                        x=1.02
                    ),
                    xaxis=dict(
                        tickmode='linear',
                        tick0=min(sorted_years),
                        dtick=1
                    ),
                    margin=dict(r=200)  # Add right margin for legend
                )
                
                # Display the chart
                st.plotly_chart(fig, use_container_width=True)
                
            else:
                st.info("No valid timeline data available for chart visualization.")
        
        st.markdown("---")
        
        # Stacked Column Chart for PAT by Project and Year
        st.subheader("📊 PAT by Year - Project Contribution Breakdown")
        
        # Calculate data for the PAT stacked chart
        if not company_projects.empty:
            # Get the range of years from all projects
            chart_years = set()
            for _, project in company_projects.iterrows():
                if (pd.notna(project.get('revenue_booking_start_year')) and 
                    pd.notna(project.get('project_completion_year'))):
                    start_year = int(project['revenue_booking_start_year'])
                    end_year = int(project['project_completion_year'])
                    chart_years.update(range(start_year, end_year + 1))
            
            if chart_years:
                # Sort years
                sorted_years = sorted(list(chart_years))
                
                # Create data structure for PAT stacked chart
                pat_chart_data = {}
                project_names = []
                
                # Initialize data structure
                for _, project in company_projects.iterrows():
                    project_name = project['project_name']
                    project_names.append(project_name)
                    pat_chart_data[project_name] = {year: 0 for year in sorted_years}
                
                # Calculate PAT contribution for each project by year
                for _, project in company_projects.iterrows():
                    project_name = project['project_name']
                    
                    # Get total PAT for this project
                    total_pat = project.get('total_pat', 0) if pd.notna(project.get('total_pat')) else 0
                    
                    # Calculate project years
                    project_years = []
                    if (pd.notna(project.get('revenue_booking_start_year')) and 
                        pd.notna(project.get('project_completion_year'))):
                        start_year = int(project['revenue_booking_start_year'])
                        end_year = int(project['project_completion_year'])
                        project_years = list(range(start_year, end_year + 1))
                    
                    # Distribute PAT equally across project years
                    if project_years and total_pat > 0:
                        annual_pat = total_pat / len(project_years)
                        
                        for year in project_years:
                            if year in pat_chart_data[project_name]:
                                pat_chart_data[project_name][year] = annual_pat / 1_000_000_000  # Convert to billions
                
                # Create the PAT stacked bar chart using Plotly
                import plotly.graph_objects as go
                import plotly.colors as colors
                
                pat_fig = go.Figure()
                
                # Generate colors for each project (using different palette for distinction)
                color_palette = colors.qualitative.Pastel[:len(project_names)]
                if len(project_names) > len(color_palette):
                    color_palette = color_palette * (len(project_names) // len(color_palette) + 1)
                
                # Add a trace for each project
                for i, project_name in enumerate(project_names):
                    y_values = [pat_chart_data[project_name][year] for year in sorted_years]
                    
                    # Only add trace if project has non-zero values
                    if any(val > 0 for val in y_values):
                        pat_fig.add_trace(go.Bar(
                            x=sorted_years,
                            y=y_values,
                            name=project_name[:20] + "..." if len(project_name) > 20 else project_name,  # Truncate long names
                            marker_color=color_palette[i],
                            text=[f'{val:.1f}B' if val > 0 else '' for val in y_values],
                            textposition='inside',
                            textfont=dict(size=10)
                        ))
                
                # Update layout for PAT chart
                pat_fig.update_layout(
                    title=f'{selected_ticker} - PAT Breakdown by Project and Year',
                    xaxis_title='Year',
                    yaxis_title='PAT (Billions VND)',
                    barmode='stack',
                    height=600,
                    showlegend=True,
                    legend=dict(
                        orientation="v",
                        yanchor="top",
                        y=1,
                        xanchor="left",
                        x=1.02
                    ),
                    xaxis=dict(
                        tickmode='linear',
                        tick0=min(sorted_years),
                        dtick=1
                    ),
                    margin=dict(r=200)  # Add right margin for legend
                )
                
                # Display the PAT chart
                st.plotly_chart(pat_fig, use_container_width=True)
                
                                
            else:
                st.info("No valid timeline data available for PAT chart visualization.")
        
        st.markdown("---")

if __name__ == "__main__":
    main()
