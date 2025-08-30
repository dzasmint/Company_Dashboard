import pandas as pd
import streamlit as st
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from utils.utils import get_data_path
from config.constants import DATA_FILES

class DataLoader:
    """Centralized data loading utility for Company Dashboard"""
    
    def __init__(self):
        self._cached_data = {}
    
    @st.cache_data
    def _load_csv_cached(_self, file_path: str) -> pd.DataFrame:
        """Load CSV with Streamlit caching"""
        return pd.read_csv(file_path)
    
    @st.cache_data  
    def _load_excel_cached(_self, file_path: str, sheet_name: str = None) -> pd.DataFrame:
        """Load Excel with Streamlit caching"""
        if sheet_name:
            return pd.read_excel(file_path, sheet_name=sheet_name)
        return pd.read_excel(file_path)
    
    @st.cache_data
    def _load_parquet_cached(_self, file_path: str) -> pd.DataFrame:
        """Load parquet with Streamlit caching"""
        return pd.read_parquet(file_path)
    
    def load_financial_statements(self) -> pd.DataFrame:
        """Load financial statements data"""
        file_path = get_data_path(DATA_FILES['financial_statements'])
        # Check if it's a parquet file
        if str(file_path).endswith('.parquet'):
            return self._load_parquet_cached(str(file_path))
        else:
            return self._load_csv_cached(str(file_path))
    
    def load_valuation_data(self) -> pd.DataFrame:
        """Load valuation metrics data"""
        file_path = get_data_path(DATA_FILES['valuation'])
        return self._load_csv_cached(str(file_path))
    
    def load_market_cap_data(self) -> pd.DataFrame:
        """Load market cap data"""
        file_path = get_data_path(DATA_FILES['market_cap'])
        return self._load_csv_cached(str(file_path))
    
    def load_bank_quarterly_data(self) -> pd.DataFrame:
        """Load bank quarterly data"""
        file_path = get_data_path(DATA_FILES['bank_quarterly'])
        return self._load_csv_cached(file_path)
    
    def load_bank_supplement_data(self) -> pd.DataFrame:
        """Load bank supplement data"""
        file_path = get_data_path(DATA_FILES['bank_supplement'])
        return self._load_csv_cached(file_path)
    
    def load_classification_data(self, sheet_name: str = None) -> pd.DataFrame:
        """Load classification/sector data"""
        file_path = get_data_path(DATA_FILES['classification'])
        return self._load_excel_cached(file_path, sheet_name)
    
    def load_stock_list(self) -> pd.DataFrame:
        """Load stock list data"""
        file_path = get_data_path(DATA_FILES['stock_list'])
        return self._load_excel_cached(file_path)
    
    def load_bank_keycodes(self) -> pd.DataFrame:
        """Load bank keycodes mapping"""
        file_path = get_data_path(DATA_FILES['bank_keycodes'])
        return self._load_excel_cached(file_path)
    
    def load_real_estate_projects(self) -> pd.DataFrame:
        """Load real estate projects data"""
        file_path = get_data_path(DATA_FILES['real_estate_projects'])
        return self._load_csv_cached(file_path)
    
    def get_ticker_data(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Filter dataframe for specific ticker"""
        df_temp = df.copy()
        return df_temp[df_temp['TICKER'] == ticker]
    
    def pivot_financial_data(self, df: pd.DataFrame, ticker: str) -> pd.DataFrame:
        """Standard pivot operation for financial data"""
        ticker_data = self.get_ticker_data(df, ticker)
        return ticker_data.pivot(index='KEYCODE', columns='DATE', values='VALUE')
    
    def get_available_tickers(self, df: pd.DataFrame) -> list:
        """Get list of available tickers from dataset"""
        if 'TICKER' in df.columns:
            return sorted(df['TICKER'].unique().tolist())
        return []
    
    def get_available_dates(self, df: pd.DataFrame) -> list:
        """Get list of available dates from dataset"""
        if 'DATE' in df.columns:
            return sorted(df['DATE'].unique().tolist())
        return []

# Global instance
data_loader = DataLoader()