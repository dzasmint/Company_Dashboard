import streamlit as st
import pandas as pd
from typing import List, Dict

from utils.mongodb_utils import (
    init_mongodb_connection,
    load_companies_data,
    load_company_forecast,
)
from tabs.enhanced_ai_assistant import EnhancedAIToolSystem


class SectorDashboardTab:
    """Sector-level dashboard with comparable table across tickers"""

    # All available metrics and default ordering for display
    ORDERED_METRICS = [
        "Current Price",
        "RNAV per share",
        "Total Project RNAV",
    ]

    def __init__(self, parent=None):
        self.parent = parent

    def render(self):
        st.subheader("Sector Comparable")

        # Ensure MongoDB connection available
        client = init_mongodb_connection()
        if client is None:
            st.error("MongoDB connection required to load Companies list and forecasts.")
            return

        # Load Companies list with ticker and name
        df_companies = load_companies_data()
        if df_companies.empty:
            st.info("No companies found in MongoDB 'VietnamStocks.Companies'.")
            return

        # Standardize columns
        tickers = df_companies.get('ticker')
        names = df_companies.get('company_name') if 'company_name' in df_companies.columns else None

        base_df = pd.DataFrame({
            'Ticker': tickers,
            'Company Name': names if names is not None else [None] * len(tickers)
        })
        base_df = base_df.dropna(subset=['Ticker']).reset_index(drop=True)

        # Metric selection controls (multiselect)
        selected_metrics = st.multiselect(
            "Select metrics",
            options=self.ORDERED_METRICS,
            default=self.ORDERED_METRICS,
            help="Remove metrics to hide columns; order is preserved."
        )

        # Build available years from historical + forecast data
        tool_system = EnhancedAIToolSystem()
        hist_years = []
        try:
            df_hist = tool_system._load_annual_financial_statements()
            if df_hist is not None and not df_hist.empty and 'DATE' in df_hist.columns:
                hist_years = sorted(df_hist['DATE'].dropna().astype(int).unique().tolist())
        except Exception:
            hist_years = []

        forecast_years = set()
        try:
            for ticker in base_df['Ticker'].dropna().unique().tolist():
                doc = load_company_forecast(ticker)
                yrs = doc.get('forecast_years', []) if isinstance(doc, dict) else []
                for y in yrs:
                    try:
                        forecast_years.add(int(y))
                    except Exception:
                        pass
        except Exception:
            pass
        all_years = sorted(set(hist_years).union(forecast_years))

        cols_years = st.columns(2)
        with cols_years[0]:
            revenue_years = st.multiselect(
                "Revenue years",
                options=all_years,
                default=[],
                help="Select any historical or forecast years to add Revenue columns (VND bn)"
            )
        with cols_years[1]:
            npatmi_years = st.multiselect(
                "NPATMI years",
                options=all_years,
                default=[],
                help="Select any historical or forecast years to add NPATMI columns (VND bn)"
            )

        # Build the comparable table
        df_display = base_df.copy()
        if selected_metrics or revenue_years or npatmi_years:
            df_metrics = self._compute_metrics_for_tickers(
                df_display['Ticker'].tolist(),
                selected_metrics,
                revenue_years,
                npatmi_years,
                tool_system
            )
            if not df_metrics.empty:
                df_display = df_display.merge(df_metrics, left_on='Ticker', right_on='Ticker', how='left')
                # Reorder columns: Ticker, Company Name, then selected metrics in chosen order
                dynamic_cols = [f"Revenue ({y})" for y in revenue_years] + [f"NPATMI ({y})" for y in npatmi_years]
                col_order = ['Ticker', 'Company Name'] + selected_metrics + dynamic_cols
                existing = [c for c in col_order if c in df_display.columns]
                df_display = df_display[existing]
        else:
            st.info("No metrics selected. Use the selector above to choose metrics.")

        st.dataframe(df_display, use_container_width=True)

    def _compute_metrics_for_tickers(self, tickers: List[str], metrics: List[str], revenue_years: List[int], npatmi_years: List[int], tool_system: EnhancedAIToolSystem) -> pd.DataFrame:
        """Compute metrics for multiple tickers with improved error handling"""
        rows: List[Dict] = []
        for ticker in tickers:
            row = {"Ticker": ticker}
            forecast_doc = load_company_forecast(ticker)

            # Total Project RNAV from valuation_data.rnav_details item 'SUB-TOTAL RNAV' (already in B VND)
            if "Total Project RNAV" in metrics:
                total_rnav_b = None
                try:
                    vd = forecast_doc.get('valuation_data', {}) if isinstance(forecast_doc, dict) else {}
                    details = vd.get('rnav_details', []) if isinstance(vd, dict) else []
                    subtotal = next((d for d in details if str(d.get('item', '')).strip().upper() == 'SUB-TOTAL RNAV'), None)
                    if subtotal:
                        # Prefer rnav_to_company if available; fallback to rnav_value
                        val = subtotal.get('rnav_to_company')
                        if val is None:
                            val = subtotal.get('rnav_value')
                        if val is not None:
                            # Values in rnav_details are saved in billions VND already
                            total_rnav_b = float(val)
                except Exception:
                    total_rnav_b = None
                row["Total Project RNAV"] = total_rnav_b

            # (Dynamic year-based metrics handled below)

            # Current Price from valuation_data.current_price (VND)
            if "Current Price" in metrics:
                current_price = None
                try:
                    vd = forecast_doc.get('valuation_data', {}) if isinstance(forecast_doc, dict) else {}
                    cp = vd.get('current_price') if isinstance(vd, dict) else None
                    if cp is not None:
                        current_price = float(cp)
                except Exception:
                    current_price = None
                row["Current Price"] = current_price

            # RNAV per share (VND per share) from valuation_data.rnav_per_share
            if "RNAV per share" in metrics:
                rps = None
                try:
                    vd = forecast_doc.get('valuation_data', {}) if isinstance(forecast_doc, dict) else {}
                    val = vd.get('rnav_per_share') if isinstance(vd, dict) else None
                    if val is not None:
                        rps = float(val)
                except Exception:
                    rps = None
                row["RNAV per share"] = rps

            rows.append(row)

        # Now compute dynamic annual metrics using AI tools (billions VND)
        for ticker in tickers:
            # Initialize row if not present
            match = next((r for r in rows if r.get('Ticker') == ticker), None)
            if match is None:
                match = {"Ticker": ticker}
                rows.append(match)

            # Revenue by selected years
            for year in revenue_years:
                col = f"Revenue ({year})"
                value = None
                # Try historical annual first
                try:
                    hist_res = tool_system.execute_tool(
                        'get_historical_annual_financials',
                        {
                            'tickers': [ticker],
                            'metrics': ['Net_Revenue'],
                            'years': [int(year)],
                            'unit': 'billions'
                        }
                    )
                    if hist_res.get('status') == 'success' and hist_res.get('data'):
                        # The data is already pivoted when metrics are specified
                        for entry in hist_res['data']:
                            # Ensure year and ticker match
                            e_ticker = str(entry.get('TICKER', '')).upper()
                            try:
                                e_year = int(entry.get('DATE')) if entry.get('DATE') is not None else None
                            except Exception:
                                e_year = None
                            if e_year != int(year) or (e_ticker and e_ticker != str(ticker).upper()):
                                continue
                            # Check for Net_Revenue in pivoted format
                            if 'Net_Revenue' in entry and entry.get('Net_Revenue') is not None:
                                value = float(entry.get('Net_Revenue'))
                                break
                except Exception:
                    pass
                # If not found, try forecast
                if value is None:
                    try:
                        fc_res = tool_system.execute_tool(
                            'get_financial_forecasts',
                            {
                                'ticker': ticker,
                                'years': [str(year)],
                                'statement_type': 'pnl',
                                'fields': ['net_revenue']
                            }
                        )
                        if fc_res.get('status') == 'success':
                            forecast_data = fc_res.get('forecast_data', {})
                            year_data = forecast_data.get(str(year), {})
                            pnl = year_data.get('pnl', {})
                            # The value is already in billions from get_financial_forecasts
                            nv = pnl.get('net_revenue')
                            if nv is not None:
                                value = float(nv)
                    except Exception:
                        pass
                match[col] = value

            # NPATMI by selected years
            for year in npatmi_years:
                col = f"NPATMI ({year})"
                value = None
                # Try historical annual first
                try:
                    hist_res = tool_system.execute_tool(
                        'get_historical_annual_financials',
                        {
                            'tickers': [ticker],
                            'metrics': ['NPATMI'],
                            'years': [int(year)],
                            'unit': 'billions'
                        }
                    )
                    if hist_res.get('status') == 'success' and hist_res.get('data'):
                        # The data is already pivoted when metrics are specified
                        for entry in hist_res['data']:
                            e_ticker = str(entry.get('TICKER', '')).upper()
                            try:
                                e_year = int(entry.get('DATE')) if entry.get('DATE') is not None else None
                            except Exception:
                                e_year = None
                            if e_year != int(year) or (e_ticker and e_ticker != str(ticker).upper()):
                                continue
                            # Check for NPATMI in pivoted format
                            if 'NPATMI' in entry and entry.get('NPATMI') is not None:
                                value = float(entry.get('NPATMI'))
                                break
                except Exception:
                    pass
                # If not found, try forecast
                if value is None:
                    try:
                        fc_res = tool_system.execute_tool(
                            'get_financial_forecasts',
                            {
                                'ticker': ticker,
                                'years': [str(year)],
                                'statement_type': 'pnl',
                                'fields': ['npatmi']
                            }
                        )
                        if fc_res.get('status') == 'success':
                            forecast_data = fc_res.get('forecast_data', {})
                            year_data = forecast_data.get(str(year), {})
                            pnl = year_data.get('pnl', {})
                            # The value is already in billions from get_financial_forecasts
                            nv = pnl.get('npatmi')
                            if nv is not None:
                                value = float(nv)
                    except Exception:
                        pass
                match[col] = value

        return pd.DataFrame(rows)
