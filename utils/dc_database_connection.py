"""
Dragon Capital Database Connection Engine

Connects to Dragon Capital's MSSQL database for financial data access.
Supports FA_Quarterly, FA_Annual, Market_Data, BankingMetrics, and reference tables.

Based on DATABASE_CONNECTION_GUIDE.md and DATABASE_SCHEMA.md
"""

import os
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
import pandas as pd
import urllib.parse
from typing import Dict, List, Any, Optional
from datetime import datetime


class DCDatabaseConnection:
    """Dragon Capital MSSQL Database Connection Manager"""
    
    # Singleton instance
    _instance = None
    
    def __new__(cls):
        """Singleton pattern - reuse single connection"""
        if cls._instance is None:
            cls._instance = super(DCDatabaseConnection, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize database connection"""
        if self._initialized:
            return
        
        self.engine = None
        self.connection_string = None
        self._initialized = True
        
        # Attempt to connect
        self._establish_connection()
    
    def _get_connection_string(self) -> Optional[str]:
        """
        Get connection string from Streamlit secrets or environment variable
        
        Returns:
            Connection string or None if not found
        """
        # Try Streamlit secrets first (production)
        try:
            if hasattr(st, 'secrets') and 'DC_DB_STRING' in st.secrets:
                return st.secrets['DC_DB_STRING']
        except:
            pass
        
        # Try environment variable (local development)
        return os.environ.get('DC_DB_STRING')
    
    def _parse_connection_string(self, conn_str: str) -> Dict[str, str]:
        """
        Parse ODBC-style connection string into components
        
        Args:
            conn_str: Connection string (e.g., "Server=host;Database=db;User Id=user;Password=pass")
            
        Returns:
            Dict with parsed components
        """
        # Check if already a SQLAlchemy URL
        if conn_str.startswith('mssql+'):
            return {'url': conn_str}
        
        # Parse ODBC-style connection string
        params = {}
        parts = conn_str.split(';')
        
        for part in parts:
            if '=' in part:
                key, value = part.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Map common variations to standard keys
                if key in ['Server', 'Data Source']:
                    # Handle tcp: prefix and port
                    value = value.replace('tcp:', '')
                    if ',' in value:
                        host, port = value.rsplit(',', 1)
                        params['host'] = host
                        params['port'] = port
                    else:
                        params['host'] = value
                        params['port'] = '1433'  # Default port
                elif key in ['Database', 'Initial Catalog']:
                    params['database'] = value
                elif key in ['User Id', 'UID', 'User']:
                    params['username'] = value
                elif key in ['Password', 'PWD']:
                    params['password'] = value
        
        return params
    
    def _build_connection_url(self, params: Dict[str, str]) -> str:
        """
        Build SQLAlchemy connection URL from parameters
        
        Args:
            params: Dict with host, database, username, password, port
            
        Returns:
            SQLAlchemy connection URL
        """
        # If already a URL, return as-is
        if 'url' in params:
            return params['url']
        
        # Validate required parameters
        required = ['host', 'database', 'username', 'password']
        missing = [p for p in required if p not in params]
        if missing:
            raise ValueError(f"Missing required connection parameters: {', '.join(missing)}")
        
        # URL encode password to handle special characters
        password_encoded = urllib.parse.quote_plus(params['password'])
        
        # Build connection URL with pymssql driver
        host = params['host']
        port = params.get('port', '1433')
        database = params['database']
        username = params['username']
        
        connection_url = (
            f"mssql+pymssql://{username}:{password_encoded}@{host}:{port}/{database}"
            f"?charset=utf8"
        )
        
        return connection_url
    
    def _establish_connection(self):
        """Establish connection to Dragon Capital database"""
        try:
            # Get connection string
            conn_str = self._get_connection_string()
            
            if not conn_str:
                st.warning("⚠️ Dragon Capital database connection string not found. Set DC_DB_STRING in secrets or environment.")
                return
            
            # Parse connection string
            params = self._parse_connection_string(conn_str)
            
            # Build SQLAlchemy URL
            connection_url = self._build_connection_url(params)
            
            # Create engine with connection pooling
            self.engine = create_engine(
                connection_url,
                poolclass=QueuePool,
                pool_size=5,           # Keep 5 connections alive
                max_overflow=10,       # Allow up to 10 additional connections
                pool_pre_ping=True,    # Test connections before use
                pool_recycle=3600,     # Recycle connections after 1 hour
                echo=False,            # Set to True for SQL debugging
                connect_args={
                    "timeout": 30,     # Connection timeout: 30 seconds
                }
            )
            
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            self.connection_string = conn_str
            st.success("✅ Connected to Dragon Capital database")
            
        except Exception as e:
            st.error(f"❌ Failed to connect to Dragon Capital database: {str(e)}")
            self.engine = None
    
    def is_connected(self) -> bool:
        """Check if database connection is established"""
        return self.engine is not None
    
    def execute_query(self, query: str, params: Dict = None) -> pd.DataFrame:
        """
        Execute SQL query and return results as DataFrame
        
        Args:
            query: SQL query string
            params: Optional query parameters for parameterized queries
            
        Returns:
            DataFrame with query results
        """
        if not self.is_connected():
            st.warning("Database not connected. Cannot execute query.")
            return pd.DataFrame()
        
        try:
            with self.engine.connect() as conn:
                if params:
                    result = conn.execute(text(query), params)
                else:
                    result = conn.execute(text(query))
                
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
                return df
        except Exception as e:
            st.error(f"Error executing query: {str(e)}")
            return pd.DataFrame()
    
    # ========== Dragon Capital Specific Query Methods ==========
    
    def get_quarterly_financials(self, ticker: str, keycodes: List[str] = None, 
                                 start_quarter: str = None, end_quarter: str = None) -> pd.DataFrame:
        """
        Get quarterly financial data from FA_Quarterly table
        
        Args:
            ticker: Stock ticker (e.g., 'VNM')
            keycodes: List of KEYCODEs to retrieve (e.g., ['Net_Revenue', 'NPATMI'])
                     If None, returns all KEYCODEs
            start_quarter: Start quarter in YYYYQX format (e.g., '2024Q1')
            end_quarter: End quarter in YYYYQX format (e.g., '2024Q4')
            
        Returns:
            DataFrame with quarterly financial data
        """
        query = """
            SELECT TICKER, KEYCODE, DATE, VALUE, YEAR, YoY
            FROM FA_Quarterly
            WHERE TICKER = :ticker
        """
        
        params = {'ticker': ticker.upper()}
        
        if keycodes:
            placeholders = ', '.join([f":keycode{i}" for i in range(len(keycodes))])
            query += f" AND KEYCODE IN ({placeholders})"
            for i, kc in enumerate(keycodes):
                params[f'keycode{i}'] = kc
        
        if start_quarter:
            query += " AND DATE >= :start_quarter"
            params['start_quarter'] = start_quarter
        
        if end_quarter:
            query += " AND DATE <= :end_quarter"
            params['end_quarter'] = end_quarter
        
        query += " ORDER BY DATE, KEYCODE"
        
        return self.execute_query(query, params)
    
    def get_annual_financials(self, ticker: str, keycodes: List[str] = None,
                             start_year: int = None, end_year: int = None) -> pd.DataFrame:
        """
        Get annual financial data from FA_Annual table
        
        Args:
            ticker: Stock ticker
            keycodes: List of KEYCODEs to retrieve
            start_year: Start year (e.g., 2020)
            end_year: End year (e.g., 2024)
            
        Returns:
            DataFrame with annual financial data
        """
        query = """
            SELECT TICKER, KEYCODE, DATE, VALUE, YEAR, YoY
            FROM FA_Annual
            WHERE TICKER = :ticker
        """
        
        params = {'ticker': ticker.upper()}
        
        if keycodes:
            placeholders = ', '.join([f":keycode{i}" for i in range(len(keycodes))])
            query += f" AND KEYCODE IN ({placeholders})"
            for i, kc in enumerate(keycodes):
                params[f'keycode{i}'] = kc
        
        if start_year:
            query += " AND YEAR >= :start_year"
            params['start_year'] = start_year
        
        if end_year:
            query += " AND YEAR <= :end_year"
            params['end_year'] = end_year
        
        query += " ORDER BY DATE, KEYCODE"
        
        return self.execute_query(query, params)
    
    def get_market_data(self, ticker: str = None, start_date: str = None, 
                       end_date: str = None) -> pd.DataFrame:
        """
        Get market data from Market_Data table
        
        Args:
            ticker: Stock ticker (optional - if None, returns all tickers)
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format
            
        Returns:
            DataFrame with market data (prices, PE, PB, PS, MKT_CAP, EV_EBITDA)
        """
        query = """
            SELECT TICKER, TRADE_DATE, PE, PB, PS, 
                   PX_OPEN, PX_HIGH, PX_LOW, PX_LAST, 
                   MKT_CAP, EV_EBITDA, UPDATE_TIMESTAMP
            FROM Market_Data
            WHERE 1=1
        """
        
        params = {}
        
        if ticker:
            query += " AND TICKER = :ticker"
            params['ticker'] = ticker.upper()
        
        if start_date:
            query += " AND TRADE_DATE >= :start_date"
            params['start_date'] = start_date
        
        if end_date:
            query += " AND TRADE_DATE <= :end_date"
            params['end_date'] = end_date
        
        query += " ORDER BY TICKER, TRADE_DATE"
        
        return self.execute_query(query, params)
    
    def get_latest_price(self, ticker: str) -> Optional[float]:
        """
        Get latest closing price for a ticker
        
        Args:
            ticker: Stock ticker
            
        Returns:
            Latest closing price or None
        """
        query = """
            SELECT TOP 1 PX_LAST
            FROM Market_Data
            WHERE TICKER = :ticker
            ORDER BY TRADE_DATE DESC
        """
        
        df = self.execute_query(query, {'ticker': ticker.upper()})
        
        if not df.empty and 'PX_LAST' in df.columns:
            return float(df['PX_LAST'].iloc[0])
        return None
    
    def get_banking_metrics(self, ticker: str = None, year: int = None,
                           quarter: int = None, actual_only: bool = True) -> pd.DataFrame:
        """
        Get banking metrics from BankingMetrics table
        
        Args:
            ticker: Bank ticker (or 'SOCB', 'Private_1', etc. for aggregates)
            year: Reporting year
            quarter: Quarter number (1-4), or None for annual (LENGTHREPORT=5)
            actual_only: If True, only return actual data (ACTUAL=1)
            
        Returns:
            DataFrame with banking metrics
        """
        query = "SELECT * FROM BankingMetrics WHERE 1=1"
        params = {}
        
        if ticker:
            query += " AND TICKER = :ticker"
            params['ticker'] = ticker.upper()
        
        if year:
            query += " AND YEARREPORT = :year"
            params['year'] = year
        
        if quarter:
            query += " AND LENGTHREPORT = :quarter"
            params['quarter'] = quarter
        elif quarter == 0:  # Annual data
            query += " AND LENGTHREPORT = 5"
        
        if actual_only:
            query += " AND ACTUAL = 1"
        
        query += " ORDER BY YEARREPORT, LENGTHREPORT, TICKER"
        
        return self.execute_query(query, params)
    
    def get_sector_classification(self, ticker: str = None) -> pd.DataFrame:
        """
        Get sector classification from Sector_Map table
        
        Args:
            ticker: Stock ticker (optional - if None, returns all)
            
        Returns:
            DataFrame with sector classification data
        """
        query = """
            SELECT Ticker, Sector, L1, L2, L3, VNI, OrganCode, ExportClassification
            FROM Sector_Map
        """
        
        params = {}
        
        if ticker:
            query += " WHERE Ticker = :ticker"
            params['ticker'] = ticker.upper()
        else:
            query += " ORDER BY Sector, Ticker"
        
        return self.execute_query(query, params)
    
    def get_vn30_members(self) -> List[str]:
        """
        Get list of VN30 index member tickers
        
        Returns:
            List of tickers in VN30 index
        """
        query = """
            SELECT Ticker
            FROM Sector_Map
            WHERE VNI = 'Y'
            ORDER BY Ticker
        """
        
        df = self.execute_query(query)
        
        if not df.empty and 'Ticker' in df.columns:
            return df['Ticker'].tolist()
        return []
    
    def close(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            self.engine = None


# ========== Singleton Accessor ==========

_db_instance = None

def get_dc_database() -> DCDatabaseConnection:
    """
    Get singleton instance of Dragon Capital database connection
    
    Returns:
        DCDatabaseConnection instance
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = DCDatabaseConnection()
    return _db_instance


# ========== Convenience Functions ==========

def load_quarterly_data(ticker: str, metrics: List[str] = None, 
                       quarters: int = 8) -> pd.DataFrame:
    """
    Load recent quarterly financial data for a ticker
    
    Args:
        ticker: Stock ticker
        metrics: List of metric KEYCODEs (e.g., ['Net_Revenue', 'NPATMI'])
        quarters: Number of recent quarters to load (default: 8 = 2 years)
        
    Returns:
        DataFrame in wide format (quarters as columns)
    """
    db = get_dc_database()
    
    if not db.is_connected():
        return pd.DataFrame()
    
    # Get data
    df = db.get_quarterly_financials(ticker, keycodes=metrics)
    
    if df.empty:
        return df
    
    # Get last N quarters
    quarters_list = sorted(df['DATE'].unique(), reverse=True)[:quarters]
    df = df[df['DATE'].isin(quarters_list)]
    
    # Pivot to wide format
    pivot_df = df.pivot_table(
        index='KEYCODE',
        columns='DATE',
        values='VALUE',
        aggfunc='first'
    )
    
    # Sort columns chronologically
    sorted_cols = sorted(pivot_df.columns, key=lambda x: (int(x[:4]), int(x[5])))
    pivot_df = pivot_df[sorted_cols]
    
    return pivot_df


def load_annual_data(ticker: str, metrics: List[str] = None,
                    years: int = 5) -> pd.DataFrame:
    """
    Load recent annual financial data for a ticker
    
    Args:
        ticker: Stock ticker
        metrics: List of metric KEYCODEs
        years: Number of recent years to load (default: 5)
        
    Returns:
        DataFrame in wide format (years as columns)
    """
    db = get_dc_database()
    
    if not db.is_connected():
        return pd.DataFrame()
    
    # Get data
    df = db.get_annual_financials(ticker, keycodes=metrics)
    
    if df.empty:
        return df
    
    # Get last N years
    years_list = sorted(df['YEAR'].unique(), reverse=True)[:years]
    df = df[df['YEAR'].isin(years_list)]
    
    # Pivot to wide format
    pivot_df = df.pivot_table(
        index='KEYCODE',
        columns='DATE',
        values='VALUE',
        aggfunc='first'
    )
    
    # Sort columns chronologically
    sorted_cols = sorted(pivot_df.columns)
    pivot_df = pivot_df[sorted_cols]
    
    return pivot_df


def get_latest_valuation(ticker: str) -> Dict[str, float]:
    """
    Get latest valuation metrics for a ticker
    
    Args:
        ticker: Stock ticker
        
    Returns:
        Dict with latest PE, PB, PS, price, market cap
    """
    db = get_dc_database()
    
    if not db.is_connected():
        return {}
    
    query = """
        SELECT TOP 1 TICKER, TRADE_DATE, PE, PB, PS, PX_LAST, MKT_CAP, EV_EBITDA
        FROM Market_Data
        WHERE TICKER = :ticker
        ORDER BY TRADE_DATE DESC
    """
    
    df = db.execute_query(query, {'ticker': ticker.upper()})
    
    if df.empty:
        return {}
    
    return {
        'ticker': df['TICKER'].iloc[0],
        'date': df['TRADE_DATE'].iloc[0],
        'price': df['PX_LAST'].iloc[0],
        'pe': df['PE'].iloc[0],
        'pb': df['PB'].iloc[0],
        'ps': df['PS'].iloc[0],
        'market_cap': df['MKT_CAP'].iloc[0],
        'ev_ebitda': df['EV_EBITDA'].iloc[0]
    }

