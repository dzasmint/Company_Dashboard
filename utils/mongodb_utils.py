#%%

import streamlit as st
import os
import pandas as pd
import certifi
from pymongo import MongoClient
import datetime
from dotenv import load_dotenv
from pathlib import Path
import sys

# Load environment variables at module import
load_dotenv()

# Add parent directory to path for config imports
sys.path.append(str(Path(__file__).parent.parent))
from config.constants import MONGODB_COLLECTIONS, REAL_ESTATE_CONFIG, FINANCIAL_CONFIG


@st.cache_resource
def init_mongodb_connection():
    """Initialize MongoDB connection with graceful error handling"""
    try:
        # Load environment variables again in case they weren't loaded
        load_dotenv()
        
        # Get MongoDB connection string from .env file
        connection_string = os.getenv('MONGODB_CONNECTION_STRING')
        
        if not connection_string:
            st.error("❌ MONGODB_CONNECTION_STRING not found in .env file. Please add it to your .env file.")
            return None
        
        # Create MongoDB client with SSL certificate verification and increased timeout settings
        client = MongoClient(
            connection_string, 
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=30000,  # 30 second timeout (increased from 5s)
            connectTimeoutMS=30000,          # 30 second connection timeout (increased from 10s)
            socketTimeoutMS=30000            # 30 second socket timeout (increased from 10s)
        )
        
        # Test connection
        client.admin.command('ping')
        return client
    except Exception as e:
        error_msg = str(e)
        
        # Provide more specific error messages based on the error type
        if "timed out" in error_msg.lower():
            st.error("❌ **MongoDB Connection Timeout**")
            st.warning("""
            **Possible causes:**
            1. **IP not whitelisted**: Check MongoDB Atlas Network Access settings
            2. **Network/Firewall blocking**: Corporate firewall may be blocking MongoDB ports (27017)
            3. **Internet connectivity issues**: Check your internet connection
            
            **To fix:**
            - Go to MongoDB Atlas → Network Access → Add your current IP address
            - Or add 0.0.0.0/0 to allow all IPs (less secure, only for development)
            """)
        elif "authentication failed" in error_msg.lower():
            st.error("❌ **MongoDB Authentication Failed**")
            st.warning("Check your username and password in the connection string")
        else:
            st.error(f"❌ Error connecting to MongoDB: {error_msg}")
        
        return None

def load_companies_data():
    """Load companies from MongoDB Companies collection"""
    try:
        client = init_mongodb_connection()
        if client is None:
            # Return empty DataFrame when MongoDB is not available
            return pd.DataFrame()
        
        # Get database and collection names
        db_name = 'VietnamStocks'
        collection_name = MONGODB_COLLECTIONS['companies']
        
        # Get database and collection
        db = client.get_database(db_name)
        collection = db.get_collection(collection_name)
        
        # Query all companies
        companies_cursor = collection.find({})
        companies_list = list(companies_cursor)
        
        if not companies_list:
            #st.write(f"🔍 DEBUG: No companies found in MongoDB database '{db_name}', collection '{collection_name}'.")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(companies_list)
        
        # Remove MongoDB ObjectId if present
        if '_id' in df.columns:
            df = df.drop('_id', axis=1)
        
        #st.write(f"🔍 DEBUG: Loaded {len(df)} companies from MongoDB")
        return df
        
    except Exception as e:
        # Don't show error for connection issues - already handled in init_mongodb_connection
        if "timed out" not in str(e).lower():
            st.error(f"❌ Error loading companies data from MongoDB: {str(e)}")
        return pd.DataFrame()

def load_projects_data():
    """Load real estate projects from MongoDB database"""
    try:
        client = init_mongodb_connection()
        if client is None:
            # Return empty DataFrame when MongoDB is not available
            return pd.DataFrame()
        
        # Get database and collection names - using VietnamStocks database
        db_name = 'VietnamStocks'
        collection_name = MONGODB_COLLECTIONS['real_estate_projects']
        
        # Get database and collection
        db = client.get_database(db_name)
        collection = db.get_collection(collection_name)
        
        # Query all projects
        projects_cursor = collection.find({})
        projects_list = list(projects_cursor)
        
        if not projects_list:
            #st.write(f"🔍 DEBUG: No projects found in MongoDB database '{db_name}', collection '{collection_name}'.")
            return pd.DataFrame()
        
        # Convert to DataFrame
        df_projects = pd.DataFrame(projects_list)
        
        # Remove MongoDB ObjectId if present
        if '_id' in df_projects.columns:
            df_projects = df_projects.drop('_id', axis=1)
        
        #st.write(f"🔍 DEBUG: Loaded {len(df_projects)} projects from MongoDB")
        #st.write(f"🔍 DEBUG: Project columns: {list(df_projects.columns)}")
        
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
            
            #st.write(f"🔍 DEBUG: Merged dataframe shape: {df_merged.shape}")
            return df_merged
        else:
            # Handle date conversion for last_updated if it exists
            if 'last_updated' in df_projects.columns:
                df_projects['last_updated'] = pd.to_datetime(df_projects['last_updated'], errors='coerce')
            return df_projects
        
    except Exception as e:
        st.error(f"❌ Error loading projects data from MongoDB: {str(e)}")
        return pd.DataFrame()

def get_companies_list():
    """Get formatted list of companies for selectbox"""
    df_companies = load_companies_data()
    if df_companies.empty:
        return []
    
    # Format as "TICKER - Company Name"
    companies_list = []
    for _, row in df_companies.iterrows():
        ticker = row.get('ticker', '')
        name = row.get('company_name', '')
        if ticker and name:
            companies_list.append(f"{ticker} - {name}")
    
    return sorted(companies_list)

def get_projects_for_company(company_ticker):
    """Get projects for a specific company"""
    df_projects = load_projects_data()
    if df_projects.empty:
        return []
    
    # Filter projects by company ticker
    company_projects = df_projects[df_projects['company_ticker'] == company_ticker]
    if company_projects.empty:
        return []
    
    return sorted(company_projects['project_name'].tolist())

def get_financials_for_company(company_ticker, selected_quarter):
    """Get financial data for a specific company from CompanyFinancials collection"""
    try:
        client = init_mongodb_connection()
        if client is None:
            return pd.DataFrame()
        
        # Get database and collection names
        db_name = 'VietnamStocks'
        collection_name = 'CompanyFinancials'
        
        # Get database and collection
        db = client.get_database(db_name)
        collection = db.get_collection(collection_name)
        
        # Query financials for specific company ticker and Type = "P"
        query = {"Ticker": company_ticker, "Type": "P"}
        financials_cursor = collection.find(query)
        
        financials_list = list(financials_cursor)
        
        if not financials_list:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df_financials = pd.DataFrame(financials_list)
        
        # Remove MongoDB ObjectId if present
        if '_id' in df_financials.columns:
            df_financials = df_financials.drop('_id', axis=1)
        
        # Handle date conversion for Date column if it exists
        # Date format is like "2025Q1", "2025Q2", etc.
        
        # Filter by selected quarter if specified
        if selected_quarter and selected_quarter != "All" and 'Date' in df_financials.columns:
            df_financials = df_financials[df_financials['Date'] == selected_quarter]
        
        return df_financials
        
    except Exception as e:
        st.error(f"❌ Error loading financial data for {company_ticker} from MongoDB: {str(e)}")
        return pd.DataFrame()

def get_project_data(company_ticker, project_name):
    """Get specific project data"""
    df_projects = load_projects_data()
    if df_projects.empty:
        return None
    
    # Find the specific project
    project_data = df_projects[
        (df_projects['company_ticker'] == company_ticker) & 
        (df_projects['project_name'] == project_name)
    ]
    
    if project_data.empty:
        return None
    
    return project_data.iloc[0].to_dict()

def save_project_to_mongodb(project_data, project_name, rnav_value=None):
    """Save project data to MongoDB"""
    try:
        client = init_mongodb_connection()
        if client is None:
            return {"success": False, "message": "Failed to connect to MongoDB"}
        
        # Get database and collection
        db_name = 'VietnamStocks'
        collection_name = MONGODB_COLLECTIONS['real_estate_projects']
        
        db = client.get_database(db_name)
        collection = db.get_collection(collection_name)
        
        # Prepare document including location and new financial fields
        document = {
            "project_name": project_name,
            "company_ticker": project_data.get('company_ticker', 'MANUAL'),
            "company_name": project_data.get('company_name', 'Manual Entry'),
            "location": project_data.get('location', ''),  # Include location field
            "project_ownership": project_data.get('project_ownership', 1.0),  # New field for project ownership
            "total_units": project_data.get('total_units', 0),
            "net_sellable_area": project_data.get('total_units', 0) * project_data.get('average_unit_size', 0),
            "average_unit_size": project_data.get('average_unit_size', 0),
            "average_selling_price": project_data.get('average_selling_price', 0),
            "price_increment_factor": project_data.get('price_increment_factor', 0.0),  # New field for price increment factor
            "gross_floor_area": project_data.get('gross_floor_area', 0),
            "land_area": project_data.get('land_area', 0),
            "construction_cost_per_sqm": project_data.get('construction_cost_per_sqm', 0),
            "land_cost_per_sqm": project_data.get('land_cost_per_sqm', 0),
            "construction_start_year": project_data.get('construction_start_year', 2025),
            "sale_start_year": project_data.get('sale_start_year', 2025),
            "land_payment_year": project_data.get('land_payment_year', 2025),
            "construction_years": project_data.get('construction_years', 3),
            "sales_years": project_data.get('sales_years', 3),
            "revenue_booking_start_year": project_data.get('revenue_booking_start_year', 2025),
            "project_completion_year": project_data.get('project_completion_year', 2028),
            "sga_percentage": project_data.get('sga_percentage', FINANCIAL_CONFIG['default_sga']),
            "wacc_rate": project_data.get('wacc_rate', FINANCIAL_CONFIG['default_wacc']),
            "cost_of_debt": project_data.get('cost_of_debt', 0.08),  # New field for cost of debt
            "rnav_value": rnav_value,
            # Add new financial fields
            "total_revenue": project_data.get('total_revenue', 0),
            "total_pat": project_data.get('total_pat', 0),
            "total_pbt": project_data.get('total_pbt', 0),
            "total_construction_cost": project_data.get('total_construction_cost', 0),
            "total_land_cost": project_data.get('total_land_cost', 0),
            "total_sga_cost": project_data.get('total_sga_cost', 0),
            "last_updated": datetime.datetime.now(),
            "created_date": datetime.datetime.now()
        }
        
        # Check if project exists
        existing = collection.find_one({
            "project_name": project_name,
            "company_ticker": document["company_ticker"]
        })
        
        if existing:
            # Update existing document but preserve created_date and location if not provided
            document["created_date"] = existing.get("created_date", datetime.datetime.now())
            # Preserve existing location if new one is empty
            if not document["location"] and existing.get("location"):
                document["location"] = existing["location"]
            result = collection.replace_one(
                {"_id": existing["_id"]}, 
                document
            )
            action = "updated"
            message = f"✅ Project '{project_name}' updated successfully in MongoDB"
        else:
            # Insert new document
            result = collection.insert_one(document)
            action = "saved"
            message = f"✅ Project '{project_name}' saved successfully to MongoDB"
        
        return {"success": True, "message": message, "action": action}
        
    except Exception as e:
        return {"success": False, "message": f"Error saving to MongoDB: {str(e)}"}

def delete_project_from_mongodb(company_ticker, project_name):
    """Delete a project from MongoDB database"""
    try:
        client = init_mongodb_connection()
        if client is None:
            return {"success": False, "message": "Failed to connect to MongoDB"}
        
        # Get database and collection
        db_name = 'VietnamStocks'
        collection_name = 'RealEstateProjects'
        
        db = client.get_database(db_name)
        collection = db.get_collection(collection_name)
        
        # Check if project exists before deletion
        existing_project = collection.find_one({
            "project_name": project_name,
            "company_ticker": company_ticker
        })
        
        if not existing_project:
            return {
                "success": False, 
                "message": f"Project '{project_name}' not found for company '{company_ticker}'"
            }
        
        # Delete the project
        result = collection.delete_one({
            "project_name": project_name,
            "company_ticker": company_ticker
        })
        
        if result.deleted_count == 1:
            return {
                "success": True, 
                "message": f"Project '{project_name}' successfully deleted from company '{company_ticker}'"
            }
        else:
            return {
                "success": False, 
                "message": f"Failed to delete project '{project_name}' - no documents were deleted"
            }
        
    except Exception as e:
        return {
            "success": False, 
            "message": f"Error deleting project from MongoDB: {str(e)}"
        }

# %%
