"""
Common imports for Company Dashboard
Centralizes frequently used imports across modules
"""

# Standard library
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

# Third party - Data processing
import pandas as pd
import numpy as np

# Third party - Visualization  
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# Third party - Web framework
import streamlit as st

# Third party - Database & APIs
import requests
from pymongo import MongoClient
import certifi

# Third party - Configuration
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Commonly used Streamlit configurations
STREAMLIT_CONFIG = {
    'page_config': {
        'page_title': 'Company Financial Dashboard',
        'layout': 'wide',
        'initial_sidebar_state': 'expanded'
    },
    'chart_config': {
        'use_container_width': True,
        'config': {'displayModeBar': False}
    }
}

# Common pandas display options
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', 50)

# Add project root to path for absolute imports
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def setup_page(title: str = "Company Dashboard", layout: str = "wide") -> None:
    """Setup standard Streamlit page configuration"""
    st.set_page_config(
        page_title=title,
        layout=layout,
        initial_sidebar_state="expanded"
    )

def display_error(error_msg: str, error_type: str = "Error") -> None:
    """Standardized error display"""
    st.error(f"❌ {error_type}: {error_msg}")

def display_success(success_msg: str) -> None:
    """Standardized success display"""
    st.success(f"✅ {success_msg}")

def display_info(info_msg: str) -> None:
    """Standardized info display"""
    st.info(f"ℹ️ {info_msg}")

def display_warning(warning_msg: str) -> None:
    """Standardized warning display"""
    st.warning(f"⚠️ {warning_msg}")

def format_currency_vnd(value: float, unit: str = "billion") -> str:
    """Format Vietnamese currency values"""
    if pd.isna(value) or value == 0:
        return "0"
    
    if unit == "billion":
        return f"{value/1e9:,.1f}B VND"
    elif unit == "million":
        return f"{value/1e6:,.1f}M VND" 
    elif unit == "thousand":
        return f"{value/1e3:,.1f}K VND"
    else:
        return f"{value:,.0f} VND"

def format_percentage(value: float, decimals: int = 2) -> str:
    """Format percentage values"""
    if pd.isna(value):
        return "N/A"
    return f"{value:.{decimals}f}%"

# Export commonly used objects
__all__ = [
    # Standard library
    'os', 'sys', 'Path', 'datetime', 'Dict', 'List', 'Optional', 'Tuple', 'Union',
    
    # Data processing
    'pd', 'np',
    
    # Visualization
    'go', 'px', 'make_subplots',
    
    # Web framework  
    'st',
    
    # Database & APIs
    'requests', 'MongoClient', 'certifi',
    
    # Configuration
    'load_dotenv',
    
    # Utilities
    'setup_page', 'display_error', 'display_success', 'display_info', 'display_warning',
    'format_currency_vnd', 'format_percentage', 'STREAMLIT_CONFIG', 'PROJECT_ROOT'
]