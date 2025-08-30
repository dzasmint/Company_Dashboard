#%%
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# Import refactored utilities
from core.data_loader import data_loader
from core.plot_factory import plot_factory
from config.constants import FINANCIAL_CATEGORIES, FINANCIAL_CONFIG

#%% Data preparation
@st.cache_data
def load_all_data():
    """Load all required data with caching"""
    return {
        'financial': data_loader.load_financial_statements(),
        'valuation': data_loader.load_valuation_data(),
        # 'market_cap': data_loader.load_market_cap_data(),  # File not available
        'bank': data_loader.load_bank_supplement_data()
    }

# Load data
data = load_all_data()
df = data['financial']
val = data['valuation'] 
# mcap = data['market_cap']  # Not available
bank = data['bank']

#%% Refactored table creation functions
def create_fs_table_main(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Create main financial statement table using standardized approach"""
    sections = ['IS', 'MARGIN']
    combined_table = pd.DataFrame()
    
    for section_name in sections:
        section_metrics = FINANCIAL_CATEGORIES.get(section_name, [])
        if section_metrics:
            section_table = data_loader.pivot_financial_data(df, ticker)
            section_filtered = section_table.loc[
                section_table.index.intersection(section_metrics)
            ]
            combined_table = pd.concat([combined_table, section_filtered])
    
    # Format as billions
    if not combined_table.empty:
        numeric_columns = combined_table.select_dtypes(include=['number']).columns
        combined_table[numeric_columns] = combined_table[numeric_columns] / 1e9
        combined_table = combined_table.round(2)
    
    return combined_table

def create_bs_table(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Create balance sheet table"""
    return plot_factory.create_table_chart(df, ticker, FINANCIAL_CATEGORIES['BS'])

def create_cf_table(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Create cash flow table"""  
    return plot_factory.create_table_chart(df, ticker, FINANCIAL_CATEGORIES['CF'])

#%% Refactored plotting functions using PlotFactory
def create_FA_plots(df: pd.DataFrame, ticker: str) -> go.Figure:
    """Create financial analysis plots using plot factory"""
    plot_config = {
        'cols': 2,
        'rows': 2, 
        'plot_cols': ['Net_Revenue', 'Gross_Profit', 'EBIT', 'NPATMI'],
        'subplot_titles': ['Net Revenue', 'Gross Profit', 'EBIT', 'NPATMI'],
        'chart_type': 'mixed',
        'show_ma': True,
        'title': 'Income Statement Overview'
    }
    return plot_factory.create_financial_plots(df, ticker, plot_config)

def create_gr_plots(df: pd.DataFrame, ticker: str) -> go.Figure:
    """Create growth rate plots"""
    # Filter for growth data
    df_temp = df.copy()
    df_ticker = df_temp[(df_temp.TICKER == ticker) & (df_temp.KEYCODE.isin(FINANCIAL_CATEGORIES['IS']))]
    df_ticker = df_ticker.pivot(index='DATE', columns='KEYCODE', values='YoY') * 100
    
    plot_config = {
        'cols': 2,
        'rows': 2,
        'plot_cols': ['Net_Revenue', 'Gross_Profit', 'EBIT', 'NPATMI'],
        'subplot_titles': ['Revenue Growth (%)', 'Gross Profit Growth (%)', 'EBIT Growth (%)', 'NPATMI Growth (%)'],
        'chart_type': 'mixed',
        'show_ma': True,
        'title': 'Growth Rate Analysis'
    }
    
    # Create custom figure for growth rates (percentage data)
    fig = go.Figure()
    colors = ['royalblue', 'darkorange', 'green', 'gray']
    
    for idx, col in enumerate(plot_config['plot_cols']):
        if col in df_ticker.columns:
            fig.add_trace(go.Bar(
                x=df_ticker.index,
                y=df_ticker[col],
                name=f'{col} Growth',
                marker_color=colors[idx % len(colors)]
            ))
    
    fig.update_layout(
        title_text=f"{ticker} - {plot_config['title']}",
        height=600,
        width=1200,
        template="plotly_white",
        yaxis_title="Growth Rate (%)",
        xaxis_title="Date"
    )
    
    return fig

def create_margin_plots(df: pd.DataFrame, ticker: str) -> go.Figure:
    """Create margin analysis plots"""
    plot_config = {
        'cols': 2,
        'rows': 2,
        'plot_cols': ['Gross_Margin', 'EBIT_Margin', 'EBITDA_Margin', 'NPAT_Margin'],
        'subplot_titles': ['Gross Margin (%)', 'EBIT Margin (%)', 'EBITDA Margin (%)', 'Net Margin (%)'],
        'chart_type': 'line',
        'show_ma': True,
        'title': 'Profitability Margins'
    }
    return plot_factory.create_financial_plots(df, ticker, plot_config)

def create_bank_plots(df: pd.DataFrame, ticker: str) -> go.Figure:
    """Create bank-specific plots"""
    plot_config = {
        'cols': 2,
        'rows': 2,
        'plot_cols': ['NIM', 'CIR', 'ROE', 'ROA'],
        'subplot_titles': ['Net Interest Margin (%)', 'Cost-Income Ratio (%)', 'ROE (%)', 'ROA (%)'],
        'chart_type': 'mixed',
        'show_ma': True,
        'title': 'Banking Metrics'
    }
    return plot_factory.create_financial_plots(df, ticker, plot_config)

#%% Main Streamlit Application
def main():
    st.set_page_config(page_title="Company Financial Dashboard", layout="wide")
    st.title("📊 Company Financial Dashboard")
    st.sidebar.title("Dashboard Controls")
    
    # Get available tickers
    tickers = data_loader.get_available_tickers(df)
    
    if not tickers:
        st.error("No ticker data found!")
        return
    
    # Ticker selection
    selected_ticker = st.sidebar.selectbox("Select Company Ticker", tickers)
    
    if not selected_ticker:
        st.warning("Please select a ticker to begin analysis")
        return
    
    # Main dashboard layout
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.header(f"Financial Analysis: {selected_ticker}")
        
        # Financial plots tabs - use key parameter for state persistence
        tab1, tab2, tab3, tab4 = st.tabs(["Income Statement", "Growth Rates", "Margins", "Banking Metrics"])
        
        with tab1:
            try:
                fig_fa = create_FA_plots(df, selected_ticker)
                st.plotly_chart(fig_fa, use_container_width=True)
            except Exception as e:
                st.error(f"Error creating income statement plots: {str(e)}")
        
        with tab2:
            try:
                fig_gr = create_gr_plots(df, selected_ticker)
                st.plotly_chart(fig_gr, use_container_width=True)
            except Exception as e:
                st.error(f"Error creating growth plots: {str(e)}")
        
        with tab3:
            try:
                fig_margin = create_margin_plots(df, selected_ticker)
                st.plotly_chart(fig_margin, use_container_width=True)
            except Exception as e:
                st.error(f"Error creating margin plots: {str(e)}")
        
        with tab4:
            if not bank.empty:
                try:
                    fig_bank = create_bank_plots(bank, selected_ticker)
                    st.plotly_chart(fig_bank, use_container_width=True)
                except Exception as e:
                    st.error(f"Error creating bank plots: {str(e)}")
            else:
                st.info("No banking data available")
    
    with col2:
        st.header("Financial Tables")
        
        # Financial statement tables
        try:
            fs_table = create_fs_table_main(df, selected_ticker)
            if not fs_table.empty:
                st.subheader("Income Statement (Bn VND)")
                st.dataframe(fs_table, use_container_width=True)
            else:
                st.info("No financial statement data available")
        except Exception as e:
            st.error(f"Error creating financial statement table: {str(e)}")
        
        try:
            bs_table = create_bs_table(df, selected_ticker)
            if not bs_table.empty:
                st.subheader("Balance Sheet (Bn VND)")
                st.dataframe(bs_table, use_container_width=True)
        except Exception as e:
            st.error(f"Error creating balance sheet table: {str(e)}")
        
        try:
            cf_table = create_cf_table(df, selected_ticker)
            if not cf_table.empty:
                st.subheader("Cash Flow (Bn VND)")
                st.dataframe(cf_table, use_container_width=True)
        except Exception as e:
            st.error(f"Error creating cash flow table: {str(e)}")
    
    # Footer
    st.markdown("---")
    st.markdown("*Data updated: " + str(datetime.now().strftime("%Y-%m-%d %H:%M")) + "*")

if __name__ == "__main__":
    main()