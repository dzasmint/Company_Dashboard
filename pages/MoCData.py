import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="MoC Data Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Ministry of Construction Data Dashboard")
st.markdown("---")

# MongoDB connection
@st.cache_resource
def get_mongodb_client():
    """Get MongoDB client with connection pooling"""
    connection_string = os.getenv('MONGODB_CONNECTION_STRING')
    if not connection_string:
        st.error("Error: MONGODB_CONNECTION_STRING not found in environment variables")
        return None
    return MongoClient(connection_string)

# Load data from MongoDB
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_transaction_volume():
    """Load transaction volume data from MongoDB"""
    client = get_mongodb_client()
    if not client:
        return pd.DataFrame()
    
    db = client['MoCDB']
    collection = db['transaction_volume']
    
    # Get all documents and convert to DataFrame
    data = list(collection.find({}, {'_id': 0}))
    if data:
        df = pd.DataFrame(data)
        # Pivot data for easier visualization
        pivot_df = df.pivot_table(
            index='quarter',
            columns='metric_type',
            values='value',
            aggfunc='first'
        )
        return pivot_df
    return pd.DataFrame()

@st.cache_data(ttl=300)
def load_credit_outstanding():
    """Load credit outstanding data from MongoDB"""
    client = get_mongodb_client()
    if not client:
        return pd.DataFrame()
    
    db = client['MoCDB']
    collection = db['credit_outstanding']
    
    data = list(collection.find({}, {'_id': 0}))
    if data:
        df = pd.DataFrame(data)
        # Pivot data for easier visualization
        pivot_df = df.pivot_table(
            index='quarter',
            columns='credit_type',
            values='value',
            aggfunc='first'
        )
        return pivot_df
    return pd.DataFrame()

@st.cache_data(ttl=300)
def load_inventory():
    """Load inventory data from MongoDB"""
    client = get_mongodb_client()
    if not client:
        return pd.DataFrame()
    
    db = client['MoCDB']
    collection = db['inventory']
    
    data = list(collection.find({}, {'_id': 0}))
    if data:
        df = pd.DataFrame(data)
        # Pivot data for easier visualization
        pivot_df = df.pivot_table(
            index='quarter',
            columns='inventory_type',
            values='value',
            aggfunc='first'
        )
        return pivot_df
    return pd.DataFrame()

@st.cache_data(ttl=300)
def load_infrastructure_projects():
    """Load infrastructure projects data from MongoDB"""
    client = get_mongodb_client()
    if not client:
        return pd.DataFrame()
    
    db = client['MoCDB']
    collection = db['infrastructure_projects']
    
    data = list(collection.find({}, {'_id': 0}))
    if data:
        return pd.DataFrame(data)
    return pd.DataFrame()

@st.cache_data(ttl=300)
def get_latest_data_summary():
    """Get summary of latest data from all collections"""
    client = get_mongodb_client()
    if not client:
        return {}
    
    db = client['MoCDB']
    summary = {}
    
    # Get latest transaction volume
    trans_coll = db['transaction_volume']
    latest_trans = trans_coll.find_one(
        {'metric_type': 'total'},
        sort=[('date', -1)]
    )
    if latest_trans:
        summary['latest_transaction'] = {
            'value': latest_trans.get('value'),
            'quarter': latest_trans.get('quarter')
        }
    
    # Get latest credit outstanding
    credit_coll = db['credit_outstanding']
    latest_credit = credit_coll.find_one(
        {'credit_type': 'total'},
        sort=[('date', -1)]
    )
    if latest_credit:
        summary['latest_credit'] = {
            'value': latest_credit.get('value'),
            'quarter': latest_credit.get('quarter')
        }
    
    # Get latest inventory
    inv_coll = db['inventory']
    latest_inv = inv_coll.find_one(
        {'inventory_type': 'total'},
        sort=[('date', -1)]
    )
    if latest_inv:
        summary['latest_inventory'] = {
            'value': latest_inv.get('value'),
            'quarter': latest_inv.get('quarter')
        }
    
    return summary

# Check MongoDB connection
client = get_mongodb_client()
if not client:
    st.error("⚠️ Cannot connect to MongoDB. Please check your connection string.")
    st.stop()

# Data Overview
st.header("📈 Data Overview")
col1, col2, col3, col4 = st.columns(4)

# Get collection counts
db = client['MoCDB']
with col1:
    trans_count = db['transaction_volume'].count_documents({})
    st.metric("Transaction Records", trans_count)
with col2:
    credit_count = db['credit_outstanding'].count_documents({})
    st.metric("Credit Records", credit_count)
with col3:
    inv_count = db['inventory'].count_documents({})
    st.metric("Inventory Records", inv_count)
with col4:
    proj_count = db['infrastructure_projects'].count_documents({})
    st.metric("Project Records", proj_count)

# Display latest data summary
st.header("📊 Latest Data Summary")
summary = get_latest_data_summary()

col1, col2, col3 = st.columns(3)
with col1:
    if 'latest_transaction' in summary:
        data = summary['latest_transaction']
        st.metric(
            f"Total Transactions ({data['quarter']})",
            f"{data['value']:,.0f}" if data['value'] else "N/A"
        )
with col2:
    if 'latest_credit' in summary:
        data = summary['latest_credit']
        st.metric(
            f"Total Credit Outstanding ({data['quarter']})",
            f"{data['value']:,.0f} VND bn" if data['value'] else "N/A"
        )
with col3:
    if 'latest_inventory' in summary:
        data = summary['latest_inventory']
        st.metric(
            f"Total Inventory ({data['quarter']})",
            f"{data['value']:,.0f}" if data['value'] else "N/A"
        )

# Interactive Visualizations
st.header("📈 Interactive Visualizations")

# Create tabs for different visualizations
tab1, tab2, tab3, tab4 = st.tabs(["Transaction Trends", "Credit Outstanding", "Inventory", "Infrastructure Projects"])

with tab1:
    st.subheader("Real Estate Transaction Volume Trends")
    trans_df = load_transaction_volume()
    
    if not trans_df.empty:
        # Create line chart
        fig = go.Figure()
        
        for col in trans_df.columns:
            if col == 'apartment':
                name = 'Apartments & Individual Houses'
            elif col == 'land':
                name = 'Land Plots'
            elif col == 'total':
                name = 'Total Transactions'
            else:
                name = col
            
            fig.add_trace(go.Scatter(
                x=trans_df.index,
                y=trans_df[col],
                mode='lines+markers',
                name=name,
                connectgaps=False
            ))
        
        fig.update_layout(
            title="Real Estate Transaction Volume by Type",
            xaxis_title="Quarter",
            yaxis_title="Units",
            height=500,
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Show raw data
        with st.expander("View Transaction Data"):
            st.dataframe(trans_df, use_container_width=True)
    else:
        st.info("No transaction data available")

with tab2:
    st.subheader("Credit Outstanding by Project Type")
    credit_df = load_credit_outstanding()
    
    if not credit_df.empty:
        # Select specific credit types to display
        main_types = ['urban_development', 'office', 'industrial', 'tourism', 'hotel', 'total']
        display_cols = [col for col in credit_df.columns if col in main_types]
        
        if display_cols:
            fig = go.Figure()
            
            type_names = {
                'urban_development': 'Urban Development',
                'office': 'Office Buildings',
                'industrial': 'Industrial Zones',
                'tourism': 'Tourism & Resorts',
                'hotel': 'Hotels & Restaurants',
                'construction_repair': 'Construction & Repair',
                'land_rights': 'Land Rights',
                'total': 'Total Credit Outstanding',
                'other': 'Other'
            }
            
            for col in display_cols:
                fig.add_trace(go.Scatter(
                    x=credit_df.index,
                    y=credit_df[col],
                    mode='lines+markers',
                    name=type_names.get(col, col),
                    connectgaps=False
                ))
            
            fig.update_layout(
                title="Credit Outstanding Trends by Type",
                xaxis_title="Quarter",
                yaxis_title="VND Billion",
                height=500,
                hovermode='x unified',
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.02
                )
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Show raw data
        with st.expander("View Credit Data"):
            st.dataframe(credit_df, use_container_width=True)
    else:
        st.info("No credit data available")

with tab3:
    st.subheader("Real Estate Inventory Trends")
    inv_df = load_inventory()
    
    if not inv_df.empty:
        # Create stacked area chart
        fig = go.Figure()
        
        inv_names = {
            'apartment': 'Apartments',
            'individual_house': 'Individual Houses',
            'land': 'Land Plots',
            'total': 'Total Inventory'
        }
        
        # Add traces for each inventory type
        for col in inv_df.columns:
            if col != 'total':  # Exclude total from stacked chart
                fig.add_trace(go.Scatter(
                    x=inv_df.index,
                    y=inv_df[col],
                    mode='lines',
                    name=inv_names.get(col, col),
                    stackgroup='one',
                    fillcolor=None
                ))
        
        # Add total as a separate line
        if 'total' in inv_df.columns:
            fig.add_trace(go.Scatter(
                x=inv_df.index,
                y=inv_df['total'],
                mode='lines+markers',
                name='Total',
                line=dict(width=3, dash='dash'),
            ))
        
        fig.update_layout(
            title="Real Estate Inventory by Type",
            xaxis_title="Quarter",
            yaxis_title="Units",
            height=500,
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Show raw data
        with st.expander("View Inventory Data"):
            st.dataframe(inv_df, use_container_width=True)
    else:
        st.info("No inventory data available")

with tab4:
    st.subheader("Infrastructure Projects Status")
    proj_df = load_infrastructure_projects()
    
    if not proj_df.empty:
        # Filter for project count data
        count_df = proj_df[proj_df['metric_type'] == 'project_count']
        
        if not count_df.empty:
            # Create grouped bar chart
            fig = go.Figure()
            
            status_names = {
                'completed': 'Completed',
                'under_construction': 'Under Construction',
                'newly_licensed': 'Newly Licensed',
                'total': 'Total Projects'
            }
            
            for status in count_df['status'].unique():
                status_data = count_df[count_df['status'] == status]
                fig.add_trace(go.Bar(
                    x=status_data['quarter'],
                    y=status_data['value'],
                    name=status_names.get(status, status)
                ))
            
            fig.update_layout(
                title="Infrastructure Projects by Status",
                xaxis_title="Quarter",
                yaxis_title="Number of Projects",
                height=500,
                barmode='group',
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Show project scale data
        scale_df = proj_df[proj_df['metric_type'] == 'project_scale']
        if not scale_df.empty:
            st.subheader("Project Scale (Units)")
            
            fig2 = go.Figure()
            for status in scale_df['status'].unique():
                status_data = scale_df[scale_df['status'] == status]
                fig2.add_trace(go.Scatter(
                    x=status_data['quarter'],
                    y=status_data['value'],
                    mode='lines+markers',
                    name=status_names.get(status, status)
                ))
            
            fig2.update_layout(
                title="Project Scale by Status",
                xaxis_title="Quarter",
                yaxis_title="Units",
                height=400,
                hovermode='x unified'
            )
            st.plotly_chart(fig2, use_container_width=True)
        
        # Show raw data
        with st.expander("View Project Data"):
            st.dataframe(proj_df, use_container_width=True)
    else:
        st.info("No project data available")

# Data Management Section
st.header("🔧 Data Management")
col1, col2 = st.columns(2)

with col1:
    if st.button("🔄 Refresh Data from MongoDB"):
        # Clear cache
        st.cache_data.clear()
        st.success("✅ Data cache cleared. Page will refresh with latest data.")
        st.rerun()

with col2:
    if st.button("📥 Re-upload CSV to MongoDB"):
        with st.spinner("Uploading data to MongoDB..."):
            # Import and run the upload function
            try:
                from upload_moc_to_mongodb import upload_moc_data_to_mongodb
                upload_moc_data_to_mongodb()
                st.success("✅ Data uploaded successfully to MongoDB!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error uploading data: {str(e)}")

# Footer
st.markdown("---")
st.caption("Data source: Ministry of Construction (MoC) - Vietnam | Stored in MongoDB")