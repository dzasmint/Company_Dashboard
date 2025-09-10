import streamlit as st
import pandas as pd
from typing import List, Dict

from utils.mongodb_utils import (
    init_mongodb_connection,
    load_companies_data,
    load_company_forecast,
)


class SectorDashboardTab:
    """Sector-level dashboard with comparable table across tickers"""

    # All available metrics and default ordering for display
    ORDERED_METRICS = [
        "Current Price",
        "RNAV per share",
        "Total Project RNAV",
        "2026E Revenue",
        "2026E NPATMI",
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

        # Build the comparable table
        df_display = base_df.copy()
        if selected_metrics:
            df_metrics = self._compute_metrics_for_tickers(df_display['Ticker'].tolist(), selected_metrics)
            if not df_metrics.empty:
                df_display = df_display.merge(df_metrics, left_on='Ticker', right_on='Ticker', how='left')
                # Reorder columns: Ticker, Company Name, then selected metrics in chosen order
                col_order = ['Ticker', 'Company Name'] + selected_metrics
                existing = [c for c in col_order if c in df_display.columns]
                df_display = df_display[existing]
        else:
            st.info("No metrics selected. Use the selector above to choose metrics.")

        st.dataframe(df_display, use_container_width=True)

    def _compute_metrics_for_tickers(self, tickers: List[str], metrics: List[str]) -> pd.DataFrame:
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

            # 2026E metrics from forecast_data['2026'].pnl
            if any(m.startswith("2026E") for m in metrics):
                pnl_2026 = {}
                try:
                    fd = forecast_doc.get('forecast_data', {}) if isinstance(forecast_doc, dict) else {}
                    pnl_2026 = (fd.get('2026', {}) or {}).get('pnl', {})
                except Exception:
                    pnl_2026 = {}

                if "2026E Revenue" in metrics:
                    val = pnl_2026.get('net_revenue')
                    row["2026E Revenue"] = (float(val) / 1e9) if val is not None else None

                if "2026E NPATMI" in metrics:
                    val = pnl_2026.get('npatmi')
                    row["2026E NPATMI"] = (float(val) / 1e9) if val is not None else None

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

        return pd.DataFrame(rows)
