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

    # Metric aliases for parsing user input
    METRIC_ALIASES = {
        'revenue': 'revenue',
        'net_revenue': 'revenue',
        'sales': 'revenue',
        'npatmi': 'npatmi',
        'npat': 'npatmi',
        'net_profit': 'npatmi',
        'profit': 'npatmi',
        'earnings': 'npatmi',
        # Balance Sheet aliases
        'total_assets': 'total_assets',
        'assets': 'total_assets',
        'total_equity': 'total_equity',
        'equity': 'total_equity',
        'total_debt': 'total_debt',
        'debt': 'total_debt',
        'cash': 'cash_and_equivalents',
        'cash_and_equivalents': 'cash_and_equivalents',
        'inventory': 'inventory',
        'account_receivable': 'account_receivable',
        'accounts_receivable': 'account_receivable',
        'receivables': 'account_receivable',
        'account_payable': 'account_payable',
        'accounts_payable': 'account_payable',
        'payables': 'account_payable',
        'customer_prepayment': 'customer_prepayment',
        'advance_from_customers': 'customer_prepayment',
        'prepayments': 'customer_prepayment',
        # Balance Sheet Ratios
        'net_debt_to_equity': 'net_debt_to_equity',
        'debt_to_equity': 'net_debt_to_equity',
        'net_debt_equity_ratio': 'net_debt_to_equity',
        'assets_to_liabilities': 'assets_to_liabilities',
        'asset_liability_ratio': 'assets_to_liabilities',
        'assets_to_equity': 'assets_to_equity',
        'asset_equity_ratio': 'assets_to_equity',
        'equity_multiplier': 'assets_to_equity',
    }

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

        # Create dynamic metric options with years (removed - not used in current implementation)
        # dynamic_metric_options = []
        # for metric in self.ORDERED_METRICS:
        #     dynamic_metric_options.append(metric)
        #     for year in all_years:
        #         dynamic_metric_options.append(f"{metric.lower()} {year}")

        # Initialize session state for metric selections
        if 'selected_metrics' not in st.session_state:
            st.session_state.selected_metrics = self.ORDERED_METRICS.copy()

        # Add new metric section (moved to top)
        st.subheader("➕ Add New Metric")

        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            # Metric selection dropdown - separate base metrics from dynamic metrics
            available_metrics = [
                # Base metrics (no year needed)
                "Current Price", "RNAV per share", "Total Project RNAV",
                # Dynamic P&L metrics (require year)
                "revenue", "npatmi",
                # Dynamic Balance Sheet metrics (require year)
                "total_assets", "total_equity", "total_debt", 
                "cash_and_equivalents", "inventory", "account_receivable", 
                "account_payable", "customer_prepayment",
                # Dynamic Balance Sheet Ratios (require year)
                "net_debt_to_equity", "assets_to_liabilities", "assets_to_equity"
            ]
            selected_metric = st.selectbox(
                "Select Metric",
                options=available_metrics,
                help="Choose the financial metric you want to add. Balance sheet, P&L metrics, and ratios require year selection."
            )

        with col2:
            # Year selection dropdown - disable only for base metrics (Current Price, RNAV per share, Total Project RNAV)
            is_base_metric = selected_metric in ["Current Price", "RNAV per share", "Total Project RNAV"]
            year_options = [str(year) for year in sorted(all_years)]
            selected_year = st.selectbox(
                "Select Year",
                options=year_options,
                help="Choose the year for the selected metric" if not is_base_metric else "Not needed for base metrics",
                disabled=is_base_metric
            )

        with col3:
            # Add metric button
            if st.button("Add Metric", type="primary", use_container_width=True):
                # For base metrics, don't include year
                if is_base_metric:
                    new_metric = selected_metric
                else:
                    new_metric = f"{selected_metric} {selected_year}"

                # Check if already exists
                if new_metric not in st.session_state.selected_metrics:
                    st.session_state.selected_metrics.append(new_metric)
                    st.success(f"✅ Added: {new_metric}")
                    st.rerun()  # Refresh to show the new selection
                else:
                    st.warning(f"⚠️ Already selected: {new_metric}")

            # Clear all button
            if st.button("Clear All", type="secondary", use_container_width=True):
                st.session_state.selected_metrics = []
                st.info("🗑️ Cleared all selections")
                st.rerun()

        st.markdown("---")

        # Metric selection with year support (moved below)
        selected_metrics_input = st.multiselect(
            "Selected metrics",
            options=st.session_state.selected_metrics,
            default=st.session_state.selected_metrics,
            help="Your selected metrics. Remove items by unchecking them.",
            key="metric_selector"
        )

        # Update session state when user makes changes
        st.session_state.selected_metrics = selected_metrics_input

        # Use session state selections for processing
        all_selected = st.session_state.selected_metrics.copy()


        # Parse selected metrics to separate base metrics from year-specific ones
        selected_metrics = []
        revenue_years = []
        npatmi_years = []
        balance_sheet_metrics = {}
        balance_sheet_ratios = {}
        # Initialize balance sheet metric years
        for bs_metric in ['total_assets', 'total_equity', 'total_debt', 'cash_and_equivalents', 
                         'inventory', 'account_receivable', 'account_payable', 'customer_prepayment']:
            balance_sheet_metrics[bs_metric] = []
        # Initialize balance sheet ratio years
        for bs_ratio in ['net_debt_to_equity', 'assets_to_liabilities', 'assets_to_equity']:
            balance_sheet_ratios[bs_ratio] = []

        for item in all_selected:
            if item in self.ORDERED_METRICS:
                # Base metric
                selected_metrics.append(item)
            else:
                # Check if it's a base metric that was added without year
                if item in ["Current Price", "RNAV per share", "Total Project RNAV"]:
                    selected_metrics.append(item)
                else:
                    # Parse "metric year" format
                    parts = item.lower().split()
                    if len(parts) == 2:
                        metric_name = parts[0]
                        # Use aliases for more flexible input
                        canonical_metric = self.METRIC_ALIASES.get(metric_name, metric_name)

                        try:
                            year = int(parts[1])
                            if canonical_metric in ['revenue']:
                                if year not in revenue_years:
                                    revenue_years.append(year)
                            elif canonical_metric in ['npatmi']:
                                if year not in npatmi_years:
                                    npatmi_years.append(year)
                            elif canonical_metric in balance_sheet_metrics:
                                if year not in balance_sheet_metrics[canonical_metric]:
                                    balance_sheet_metrics[canonical_metric].append(year)
                            elif canonical_metric in balance_sheet_ratios:
                                if year not in balance_sheet_ratios[canonical_metric]:
                                    balance_sheet_ratios[canonical_metric].append(year)
                            else:
                                # Unknown metric, treat as base metric
                                if item not in selected_metrics:
                                    selected_metrics.append(item)
                        except ValueError:
                            # Invalid year, treat as base metric
                            if item not in selected_metrics:
                                selected_metrics.append(item)
                    else:
                        # Invalid format, treat as base metric
                        if item not in selected_metrics:
                            selected_metrics.append(item)

        # Build the comparable table
        df_display = base_df.copy()
        has_metrics = (selected_metrics or revenue_years or npatmi_years or 
                      any(years for years in balance_sheet_metrics.values()) or
                      any(years for years in balance_sheet_ratios.values()))
        
        if has_metrics:
            df_metrics = self._compute_metrics_for_tickers(
                df_display['Ticker'].tolist(),
                selected_metrics,
                revenue_years,
                npatmi_years,
                balance_sheet_metrics,
                balance_sheet_ratios,
                tool_system
            )
            if not df_metrics.empty:
                df_display = df_display.merge(df_metrics, left_on='Ticker', right_on='Ticker', how='left')
                # Reorder columns: Ticker, Company Name, then selected metrics in chosen order
                dynamic_cols = ([f"Revenue ({y})" for y in revenue_years] + 
                               [f"NPATMI ({y})" for y in npatmi_years])
                
                # Add balance sheet dynamic columns
                bs_display_names = {
                    'total_assets': 'Total Assets',
                    'total_equity': 'Total Equity', 
                    'total_debt': 'Total Debt',
                    'cash_and_equivalents': 'Cash & Equivalents',
                    'inventory': 'Inventory',
                    'account_receivable': 'Account Receivable',
                    'account_payable': 'Account Payable',
                    'customer_prepayment': 'Customer Prepayment'
                }
                
                for bs_metric, years in balance_sheet_metrics.items():
                    display_name = bs_display_names.get(bs_metric, bs_metric.replace('_', ' ').title())
                    for year in sorted(years):
                        dynamic_cols.append(f"{display_name} ({year})")
                
                # Add balance sheet ratio dynamic columns
                bs_ratio_display_names = {
                    'net_debt_to_equity': 'Net Debt/Equity',
                    'assets_to_liabilities': 'Assets/Liabilities', 
                    'assets_to_equity': 'Assets/Equity'
                }
                
                for bs_ratio, years in balance_sheet_ratios.items():
                    display_name = bs_ratio_display_names.get(bs_ratio, bs_ratio.replace('_', ' ').title())
                    for year in sorted(years):
                        dynamic_cols.append(f"{display_name} ({year})")
                
                col_order = ['Ticker', 'Company Name'] + selected_metrics + dynamic_cols
                existing = [c for c in col_order if c in df_display.columns]
                df_display = df_display[existing]

            st.dataframe(df_display, use_container_width=True)
        else:
            st.info("No metrics selected. Use the selector above to choose metrics.")

    def _compute_metrics_for_tickers(self, tickers: List[str], metrics: List[str], revenue_years: List[int], npatmi_years: List[int], balance_sheet_metrics: Dict[str, List[int]], balance_sheet_ratios: Dict[str, List[int]], tool_system: EnhancedAIToolSystem) -> pd.DataFrame:
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
                        # Handle both pivoted and non-pivoted formats
                        for entry in hist_res['data']:
                            # Ensure year and ticker match
                            e_ticker = str(entry.get('TICKER', '')).upper()
                            try:
                                e_year = int(entry.get('DATE')) if entry.get('DATE') is not None else None
                            except Exception:
                                e_year = None
                            if e_year != int(year) or (e_ticker and e_ticker != str(ticker).upper()):
                                continue

                            # Check for Net_Revenue in pivoted format (when no metrics specified)
                            if 'Net_Revenue' in entry and entry.get('Net_Revenue') is not None:
                                value = float(entry.get('Net_Revenue'))
                                break
                            # Check for Net_Revenue in non-pivoted format (when metrics specified)
                            elif entry.get('KEYCODE') == 'Net_Revenue' and entry.get('VALUE') is not None:
                                value = float(entry.get('VALUE'))
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
                        # Handle both pivoted and non-pivoted formats
                        for entry in hist_res['data']:
                            e_ticker = str(entry.get('TICKER', '')).upper()
                            try:
                                e_year = int(entry.get('DATE')) if entry.get('DATE') is not None else None
                            except Exception:
                                e_year = None
                            if e_year != int(year) or (e_ticker and e_ticker != str(ticker).upper()):
                                continue

                            # Check for NPATMI in pivoted format (when no metrics specified)
                            if 'NPATMI' in entry and entry.get('NPATMI') is not None:
                                value = float(entry.get('NPATMI'))
                                break
                            # Check for NPATMI in non-pivoted format (when metrics specified)
                            elif entry.get('KEYCODE') == 'NPATMI' and entry.get('VALUE') is not None:
                                value = float(entry.get('VALUE'))
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

            # Balance Sheet metrics by selected years
            bs_keycode_mapping = {
                'total_assets': 'Total_Asset',
                'total_equity': 'TOTAL_Equity', 
                'total_debt': 'Total_Debt',
                'cash_and_equivalents': 'Cash_Equivalent',
                'inventory': 'Inventory',
                'account_receivable': 'Account_Receivable',
                'account_payable': 'Account_Payable',
                'customer_prepayment': 'Advance_From_Custmers'  # Note: typo in original KEYCODE
            }
            
            bs_display_names = {
                'total_assets': 'Total Assets',
                'total_equity': 'Total Equity', 
                'total_debt': 'Total Debt',
                'cash_and_equivalents': 'Cash & Equivalents',
                'inventory': 'Inventory',
                'account_receivable': 'Account Receivable',
                'account_payable': 'Account Payable',
                'customer_prepayment': 'Customer Prepayment'
            }
            
            for bs_metric, years in balance_sheet_metrics.items():
                keycode = bs_keycode_mapping.get(bs_metric)
                display_name = bs_display_names.get(bs_metric, bs_metric.replace('_', ' ').title())
                
                if not keycode or not years:
                    continue
                    
                for year in years:
                    col = f"{display_name} ({year})"
                    value = None
                    
                    # Try historical annual first
                    try:
                        hist_res = tool_system.execute_tool(
                            'get_historical_annual_financials',
                            {
                                'tickers': [ticker],
                                'metrics': [keycode],
                                'years': [int(year)],
                                'unit': 'billions'
                            }
                        )
                        if hist_res.get('status') == 'success' and hist_res.get('data'):
                            # Handle both pivoted and non-pivoted formats
                            for entry in hist_res['data']:
                                e_ticker = str(entry.get('TICKER', '')).upper()
                                try:
                                    e_year = int(entry.get('DATE')) if entry.get('DATE') is not None else None
                                except Exception:
                                    e_year = None
                                if e_year != int(year) or (e_ticker and e_ticker != str(ticker).upper()):
                                    continue

                                # Check for metric in pivoted format
                                if keycode in entry and entry.get(keycode) is not None:
                                    value = float(entry.get(keycode))
                                    break
                                # Check for metric in non-pivoted format
                                elif entry.get('KEYCODE') == keycode and entry.get('VALUE') is not None:
                                    value = float(entry.get('VALUE'))
                                    break
                    except Exception:
                        pass
                    
                    # If not found, try forecast
                    if value is None:
                        try:
                            # Map to forecast field names
                            forecast_field_mapping = {
                                'total_assets': 'total_assets',
                                'total_equity': 'total_equity',
                                'total_debt': 'total_debt', 
                                'cash_and_equivalents': 'cash_and_equivalents',
                                'inventory': 'inventory',
                                'account_receivable': 'account_receivable',
                                'account_payable': 'account_payable',
                                'customer_prepayment': 'customer_prepayment'
                            }
                            
                            forecast_field = forecast_field_mapping.get(bs_metric)
                            if forecast_field:
                                fc_res = tool_system.execute_tool(
                                    'get_financial_forecasts',
                                    {
                                        'ticker': ticker,
                                        'years': [str(year)],
                                        'statement_type': 'balance_sheet',
                                        'fields': [forecast_field]
                                    }
                                )
                                if fc_res.get('status') == 'success':
                                    forecast_data = fc_res.get('forecast_data', {})
                                    year_data = forecast_data.get(str(year), {})
                                    bs = year_data.get('balance_sheet', {})
                                    # The value is already in billions from get_financial_forecasts
                                    bs_value = bs.get(forecast_field)
                                    if bs_value is not None:
                                        value = float(bs_value)
                        except Exception:
                            pass
                    
                    match[col] = value

            # Balance Sheet Ratios by selected years - using existing calculate_balance_sheet_ratios function
            bs_ratio_display_names = {
                'net_debt_to_equity': 'Net Debt/Equity',
                'assets_to_liabilities': 'Assets/Liabilities', 
                'assets_to_equity': 'Assets/Equity'
            }
            
            for bs_ratio, years in balance_sheet_ratios.items():
                display_name = bs_ratio_display_names.get(bs_ratio, bs_ratio.replace('_', ' ').title())
                
                if not years:
                    continue
                    
                for year in years:
                    col = f"{display_name} ({year})"
                    ratio_value = None
                    
                    # Use the existing calculate_balance_sheet_ratios function
                    try:
                        # Map our ratio names to the function's ratio names
                        ratio_mapping = {
                            'net_debt_to_equity': 'net_debt_to_equity',
                            'assets_to_equity': 'assets_to_equity',
                            'assets_to_liabilities': 'liabilities_to_assets'  # We'll invert this
                        }
                        
                        function_ratio_name = ratio_mapping.get(bs_ratio)
                        if function_ratio_name:
                            # Call the calculate_balance_sheet_ratios function
                            ratio_res = tool_system.execute_tool(
                                'calculate_balance_sheet_ratios',
                                {
                                    'ticker': ticker,
                                    'year_start': int(year),
                                    'year_end': int(year),
                                    'period_type': 'annual',
                                    'ratios': [function_ratio_name]
                                }
                            )
                            
                            if ratio_res.get('status') == 'success':
                                # Extract data from the nested structure
                                # Structure: result['data']['data'][year_int]['ratios'][ratio_name]
                                outer_data = ratio_res.get('data', {})
                                inner_data = outer_data.get('data', {})
                                year_data = inner_data.get(int(year), {})  # Use int(year), not str(year)
                                ratios_data = year_data.get('ratios', {})
                                
                                if function_ratio_name in ratios_data:
                                    calculated_ratio = ratios_data[function_ratio_name]
                                    
                                    if calculated_ratio is not None:
                                        if bs_ratio == 'assets_to_liabilities':
                                            # Invert liabilities_to_assets to get assets_to_liabilities
                                            if calculated_ratio != 0:
                                                ratio_value = 1 / calculated_ratio
                                        else:
                                            ratio_value = calculated_ratio
                    
                    except Exception:
                        ratio_value = None
                    
                    match[col] = ratio_value

        return pd.DataFrame(rows)
