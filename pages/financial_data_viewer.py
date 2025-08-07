import pandas as pd
import streamlit as st
import os

def load_financial_data(file_path):
    """Load the processed financial data from CSV file"""
    try:
        df = pd.read_csv(file_path)
        return df
    except FileNotFoundError:
        st.error(f"Error: File {file_path} not found.")
        return None
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return None

def get_available_tickers(df):
    """Get list of available tickers from the dataset"""
    return sorted(df['TICKER'].unique().tolist())

def filter_data_by_ticker(df, ticker):
    """Filter data for a specific ticker"""
    return df[df['TICKER'] == ticker]

def categorize_keycode(keycode):
    """Categorize KEYCODE into Income Statement, Balance Sheet, or Cashflow"""
    keycode_upper = keycode.upper()
    
    # Income Statement keywords
    income_keywords = [
        'REVENUE', 'SALES', 'INCOME', 'EBITDA', 'EBIT', 'PROFIT', 'LOSS',
        'EXPENSE', 'COST', 'TAX', 'INTEREST', 'DEPRECIATION', 'AMORTIZATION',
        'OPERATING', 'GROSS', 'NET', 'EARNINGS', 'EPS', 'MARGIN'
    ]
    
    # Balance Sheet keywords
    balance_keywords = [
        'ASSET', 'LIABILITY', 'EQUITY', 'CASH', 'DEBT', 'INVENTORY',
        'RECEIVABLE', 'PAYABLE', 'CAPITAL', 'RETAINED', 'SHAREHOLDER',
        'CURRENT', 'FIXED', 'INTANGIBLE', 'GOODWILL', 'PROPERTY'
    ]
    
    # Cashflow keywords
    cashflow_keywords = [
        'CASHFLOW', 'CASH_FLOW', 'FINANCING', 'INVESTING', 'FREE_CASH',
        'DIVIDEND', 'CAPEX', 'WORKING_CAPITAL', 'SHARE_REPURCHASE'
    ]
    
    # Check for exact matches or contains
    for keyword in income_keywords:
        if keyword in keycode_upper:
            return 'Income Statement'
    
    for keyword in balance_keywords:
        if keyword in keycode_upper:
            return 'Balance Sheet'
    
    for keyword in cashflow_keywords:
        if keyword in keycode_upper:
            return 'Cashflow'
    
    # Default to Income Statement if no match
    return 'Income Statement'

def create_financial_tables_by_type(df):
    """Create separate tables for Income Statement, Balance Sheet, and Cashflow"""
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # Add category column
    df_copy = df.copy()
    df_copy['Category'] = df_copy['KEYCODE'].apply(categorize_keycode)
    
    # Filter by category
    income_data = df_copy[df_copy['Category'] == 'Income Statement']
    balance_data = df_copy[df_copy['Category'] == 'Balance Sheet']
    cashflow_data = df_copy[df_copy['Category'] == 'Cashflow']
    
    # Create pivot tables
    income_table = income_data.pivot_table(
        index='KEYCODE', columns='YEAR', values='VALUE', aggfunc='first'
    ) if not income_data.empty else pd.DataFrame()
    
    balance_table = balance_data.pivot_table(
        index='KEYCODE', columns='YEAR', values='VALUE', aggfunc='first'
    ) if not balance_data.empty else pd.DataFrame()
    
    cashflow_table = cashflow_data.pivot_table(
        index='KEYCODE', columns='YEAR', values='VALUE', aggfunc='first'
    ) if not cashflow_data.empty else pd.DataFrame()
    
    return income_table, balance_table, cashflow_table

def reorder_income_statement_vas(income_table):
    """Reorder Income Statement according to VAS standard"""
    if income_table.empty:
        return income_table
    
    # Define VAS Income Statement order
    vas_order = [
        # Revenue section
        'REVENUE', 'NET_REVENUE', 'TOTAL_REVENUE', 'SALES', 'NET_SALES',
        
        # Cost of goods sold
        'COGS', 'COST_OF_GOODS_SOLD', 'COST_OF_SALES',
        
        # Gross profit
        'GROSS_PROFIT', 'GROSS_INCOME',
        
        # Operating expenses
        'SELLING_EXPENSES', 'ADMINISTRATIVE_EXPENSES', 'OPERATING_EXPENSES',
        
        # Operating profit
        'OPERATING_PROFIT', 'OPERATING_INCOME', 'EBIT',
        
        # Financial income/expenses
        'FINANCIAL_INCOME', 'INTEREST_INCOME',
        'FINANCIAL_EXPENSES', 'INTEREST_EXPENSES',
        
        # Other income/expenses
        'OTHER_INCOME', 'OTHER_EXPENSES',
        
        # Profit before tax
        'PROFIT_BEFORE_TAX', 'INCOME_BEFORE_TAX', 'EBT',
        
        # Tax
        'TAX_EXPENSES', 'INCOME_TAX', 'CORPORATE_TAX',
        
        # Net profit
        'NET_PROFIT', 'NET_INCOME', 'PROFIT_AFTER_TAX',
        
        # Per share metrics
        'EPS', 'BASIC_EPS', 'DILUTED_EPS'
    ]
    
    # Get existing keycodes
    existing_keycodes = income_table.index.tolist()
    
    # Create ordered list
    ordered_keycodes = []
    
    # Add items in VAS order if they exist
    for item in vas_order:
        matching_codes = [code for code in existing_keycodes if item in code.upper()]
        ordered_keycodes.extend(matching_codes)
    
    # Add remaining items that don't match the standard order
    remaining_codes = [code for code in existing_keycodes if code not in ordered_keycodes]
    ordered_keycodes.extend(sorted(remaining_codes))
    
    # Reorder the dataframe
    return income_table.reindex(ordered_keycodes)

def main():
    """Main function to run the financial data viewer"""
    st.title("📊 Financial Data Viewer")
    st.markdown("---")
    
    # Try different possible file locations
    possible_paths = [
        "data/FA_processed.csv",
        "../data/FA_processed.csv",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "FA_processed.csv")
    ]
    
    df = None
    for file_path in possible_paths:
        if os.path.exists(file_path):
            df = load_financial_data(file_path)
            if df is not None:
                break
    
    if df is None:
        st.error("Could not find FA_processed.csv file. Please ensure the file exists in one of these locations:")
        for path in possible_paths:
            st.text(f"- {path}")
        return

    # Check if required columns exist
    required_columns = ['KEYCODE', 'TICKER', 'DATE', 'VALUE', 'YEAR', 'YoY']
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        st.error(f"Missing required columns: {missing_columns}")
        st.error("Please ensure your CSV file has the following columns: KEYCODE, TICKER, DATE, VALUE, YEAR, YoY")
        return

    # Get available tickers
    tickers = get_available_tickers(df)
    
    # Sidebar for ticker selection
    st.sidebar.header("Select Ticker")
    selected_ticker = st.sidebar.selectbox(
        "Choose a ticker symbol:",
        options=tickers,
        index=0
    )
    
    if selected_ticker:
        # Filter data for selected ticker
        ticker_data = filter_data_by_ticker(df, selected_ticker)
        
        if ticker_data.empty:
            st.warning(f"No data available for ticker {selected_ticker}")
            return
        
        # Display header
        st.header(f"Financial Data for {selected_ticker}")
        
        # Show summary information
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Data Points", len(ticker_data))
        with col2:
            st.metric("Years Available", ticker_data['YEAR'].nunique())
        with col3:
            st.metric("Financial Items", ticker_data['KEYCODE'].nunique())
        
        # Create tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs(["Income Statement", "Balance Sheet", "Cashflow", "Raw Data"])
        
        # Create financial tables by type
        income_table, balance_table, cashflow_table = create_financial_tables_by_type(ticker_data)
        
        with tab1:
            st.subheader("Income Statement")
            if not income_table.empty:
                # Reorder according to VAS standard
                ordered_income_table = reorder_income_statement_vas(income_table)
                st.dataframe(ordered_income_table, use_container_width=True)
            else:
                st.info("No income statement data available.")
        
        with tab2:
            st.subheader("Balance Sheet")
            if not balance_table.empty:
                st.dataframe(balance_table, use_container_width=True)
            else:
                st.info("No balance sheet data available.")
        
        with tab3:
            st.subheader("Cashflow Statement")
            if not cashflow_table.empty:
                st.dataframe(cashflow_table, use_container_width=True)
            else:
                st.info("No cashflow data available.")
        
        with tab4:
            st.subheader("Raw Financial Data")
            st.dataframe(ticker_data, use_container_width=True)

if __name__ == "__main__":
    main()