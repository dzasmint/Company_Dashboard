import streamlit as st
import pandas as pd
from typing import List, Dict, Any

from utils.mongodb_utils import (
    init_mongodb_connection,
    load_companies_data,
    load_company_forecast,
)
from tabs.enhanced_ai_assistant import EnhancedAIToolSystem


class SectorDashboardTab:
    """Sector-level dashboard with comparable table across tickers - Generic Implementation"""

    # Generic metric configuration - defines how each metric should be handled
    METRIC_CONFIG = {
        # Base metrics (no year required) - from get_valuation_analysis
        'current_price': {
            'category': 'base',
            'source': 'get_valuation_analysis',
            'field': 'current_price',
            'display_name': 'Current Price',
            'data_path': 'result["data"]["current_price"]'
        },
        'rnav_per_share': {
            'category': 'base',
            'source': 'get_valuation_analysis',
            'field': 'rnav_per_share',
            'display_name': 'RNAV per share',
            'data_path': 'result["data"]["rnav_per_share"]'
        },
        'total_project_rnav': {
            'category': 'base',
            'source': 'get_valuation_analysis',
            'field': 'total_rnav',
            'display_name': 'Total Project RNAV',
            'data_path': 'result["data"]["total_rnav"]'
        },
        
        # Historical metrics (year required)
        'revenue': {
            'category': 'historical',
            'source': 'get_historical_annual_financials',
            'field': 'Net_Revenue',
            'display_name': 'Revenue',
            'data_path': 'entry["Net_Revenue"] or entry["VALUE"]',
            'fallback_source': 'get_financial_forecasts',
            'fallback_field': 'net_revenue',
            'fallback_path': 'result["forecast_data"][year]["pnl"]["net_revenue"]'
        },
        'npatmi': {
            'category': 'historical',
            'source': 'get_historical_annual_financials',
            'field': 'NPATMI',
            'display_name': 'NPATMI',
            'data_path': 'entry["NPATMI"] or entry["VALUE"]',
            'fallback_source': 'get_financial_forecasts',
            'fallback_field': 'npatmi',
            'fallback_path': 'result["forecast_data"][year]["pnl"]["npatmi"]'
        },
        'total_assets': {
            'category': 'historical',
            'source': 'get_historical_annual_financials',
            'field': 'Total_Asset',
            'display_name': 'Total Assets',
            'data_path': 'entry["Total_Asset"] or entry["VALUE"]',
            'fallback_source': 'get_financial_forecasts',
            'fallback_field': 'total_assets',
            'fallback_path': 'result["forecast_data"][year]["balance_sheet"]["total_assets"]'
        },
        'total_equity': {
            'category': 'historical',
            'source': 'get_historical_annual_financials',
            'field': 'TOTAL_Equity',
            'display_name': 'Total Equity',
            'data_path': 'entry["TOTAL_Equity"] or entry["VALUE"]',
            'fallback_source': 'get_financial_forecasts',
            'fallback_field': 'total_equity',
            'fallback_path': 'result["forecast_data"][year]["balance_sheet"]["total_equity"]'
        },
        'total_debt': {
            'category': 'historical',
            'source': 'get_historical_annual_financials',
            'field': 'Total_Debt',
            'display_name': 'Total Debt',
            'data_path': 'entry["Total_Debt"] or entry["VALUE"]',
            'fallback_source': 'get_financial_forecasts',
            'fallback_field': 'total_debt',
            'fallback_path': 'result["forecast_data"][year]["balance_sheet"]["total_debt"]'
        },
        'cash_and_equivalents': {
            'category': 'historical',
            'source': 'get_historical_annual_financials',
            'field': 'Cash_Equivalent',
            'display_name': 'Cash & Equivalents',
            'data_path': 'entry["Cash_Equivalent"] or entry["VALUE"]',
            'fallback_source': 'get_financial_forecasts',
            'fallback_field': 'cash_and_equivalents',
            'fallback_path': 'result["forecast_data"][year]["balance_sheet"]["cash_and_equivalents"]'
        },
        'inventory': {
            'category': 'historical',
            'source': 'get_historical_annual_financials',
            'field': 'Inventory',
            'display_name': 'Inventory',
            'data_path': 'entry["Inventory"] or entry["VALUE"]',
            'fallback_source': 'get_financial_forecasts',
            'fallback_field': 'inventory',
            'fallback_path': 'result["forecast_data"][year]["balance_sheet"]["inventory"]'
        },
        'account_receivable': {
            'category': 'historical',
            'source': 'get_historical_annual_financials',
            'field': 'Account_Receivable',
            'display_name': 'Account Receivable',
            'data_path': 'entry["Account_Receivable"] or entry["VALUE"]',
            'fallback_source': 'get_financial_forecasts',
            'fallback_field': 'account_receivable',
            'fallback_path': 'result["forecast_data"][year]["balance_sheet"]["account_receivable"]'
        },
        'account_payable': {
            'category': 'historical',
            'source': 'get_historical_annual_financials',
            'field': 'Account_Payable',
            'display_name': 'Account Payable',
            'data_path': 'entry["Account_Payable"] or entry["VALUE"]',
            'fallback_source': 'get_financial_forecasts',
            'fallback_field': 'account_payable',
            'fallback_path': 'result["forecast_data"][year]["balance_sheet"]["account_payable"]'
        },
        'customer_prepayment': {
            'category': 'historical',
            'source': 'get_historical_annual_financials',
            'field': 'Advance_From_Custmers',
            'display_name': 'Customer Prepayment',
            'data_path': 'entry["Advance_From_Custmers"] or entry["VALUE"]',
            'fallback_source': 'get_financial_forecasts',
            'fallback_field': 'customer_prepayment',
            'fallback_path': 'result["forecast_data"][year]["balance_sheet"]["customer_prepayment"]'
        },
        
        # Ratio metrics (year required)
        'net_debt_to_equity': {
            'category': 'ratio',
            'source': 'calculate_balance_sheet_ratios',
            'field': 'net_debt_to_equity',
            'display_name': 'Net Debt/Equity',
            'data_path': 'result["data"]["data"][year]["ratios"]["net_debt_to_equity"]'
        },
        'assets_to_equity': {
            'category': 'ratio',
            'source': 'calculate_balance_sheet_ratios',
            'field': 'assets_to_equity',
            'display_name': 'Assets/Equity',
            'data_path': 'result["data"]["data"][year]["ratios"]["assets_to_equity"]'
        },
        'assets_to_liabilities': {
            'category': 'ratio',
            'source': 'calculate_balance_sheet_ratios',
            'field': 'liabilities_to_assets',
            'display_name': 'Assets/Liabilities',
            'data_path': 'result["data"]["data"][year]["ratios"]["liabilities_to_assets"]',
            'transform': 'invert'  # 1 / value
        },
    }

    # Metric aliases for parsing user input
    METRIC_ALIASES = {
        # Revenue aliases
        'revenue': 'revenue', 'net_revenue': 'revenue', 'sales': 'revenue',
        # Profit aliases
        'npatmi': 'npatmi', 'npat': 'npatmi', 'net_profit': 'npatmi', 'profit': 'npatmi', 'earnings': 'npatmi',
        # Asset aliases
        'total_assets': 'total_assets', 'assets': 'total_assets',
        'total_equity': 'total_equity', 'equity': 'total_equity',
        'total_debt': 'total_debt', 'debt': 'total_debt',
        'cash': 'cash_and_equivalents', 'cash_and_equivalents': 'cash_and_equivalents',
        'inventory': 'inventory',
        'account_receivable': 'account_receivable', 'accounts_receivable': 'account_receivable', 'receivables': 'account_receivable',
        'account_payable': 'account_payable', 'accounts_payable': 'account_payable', 'payables': 'account_payable',
        'customer_prepayment': 'customer_prepayment', 'advance_from_customers': 'customer_prepayment', 'prepayments': 'customer_prepayment',
        # Ratio aliases
        'net_debt_to_equity': 'net_debt_to_equity', 'debt_to_equity': 'net_debt_to_equity', 'net_debt_equity_ratio': 'net_debt_to_equity',
        'assets_to_liabilities': 'assets_to_liabilities', 'asset_liability_ratio': 'assets_to_liabilities',
        'assets_to_equity': 'assets_to_equity', 'asset_equity_ratio': 'assets_to_equity', 'equity_multiplier': 'assets_to_equity',
    }

    def __init__(self, parent=None):
        self.parent = parent

    def _is_base_metric(self, metric_name: str) -> bool:
        """Check if a metric is a base metric (no year required)"""
        # Check if it's a display name for a base metric
        for metric_key, config in self.METRIC_CONFIG.items():
            if config['category'] == 'base' and config['display_name'] == metric_name:
                return True
        return False

    def _get_metric_key_from_display_name(self, display_name: str) -> str:
        """Get metric key from display name"""
        for metric_key, config in self.METRIC_CONFIG.items():
            if config['display_name'] == display_name:
                return metric_key
        return display_name

    def _parse_selected_metrics(self, all_selected: List[str]) -> Dict[str, any]:
        """Parse selected metrics into a generic structure"""
        parsed_metrics = {
            'base_metrics': [],
            'dynamic_metrics': {}  # metric_key -> {year: ['absolute', 'yoy']}
        }
        
        for item in all_selected:
            # Check if it's a base metric by display name
            if self._is_base_metric(item):
                parsed_metrics['base_metrics'].append(item)
                continue
            
            # Parse different formats:
            # 1. "metric year" (absolute value)
            # 2. "metric year YoY" (YoY growth)
            parts = item.lower().split()
            
            if len(parts) == 2:
                # Format: "metric year" (absolute value)
                metric_name = parts[0]
                canonical_metric = self.METRIC_ALIASES.get(metric_name, metric_name)
                
                try:
                    year = int(parts[1])
                    
                    if canonical_metric in self.METRIC_CONFIG:
                        if canonical_metric not in parsed_metrics['dynamic_metrics']:
                            parsed_metrics['dynamic_metrics'][canonical_metric] = {}
                        if year not in parsed_metrics['dynamic_metrics'][canonical_metric]:
                            parsed_metrics['dynamic_metrics'][canonical_metric][year] = []
                        if 'absolute' not in parsed_metrics['dynamic_metrics'][canonical_metric][year]:
                            parsed_metrics['dynamic_metrics'][canonical_metric][year].append('absolute')
                    else:
                        # Unknown metric, treat as base metric
                        if item not in parsed_metrics['base_metrics']:
                            parsed_metrics['base_metrics'].append(item)
                except ValueError:
                    # Invalid year, treat as base metric
                    if item not in parsed_metrics['base_metrics']:
                        parsed_metrics['base_metrics'].append(item)
                        
            elif len(parts) == 3 and parts[2] == 'yoy':
                # Format: "metric year YoY" (YoY growth)
                metric_name = parts[0]
                canonical_metric = self.METRIC_ALIASES.get(metric_name, metric_name)
                
                try:
                    year = int(parts[1])
                    
                    if canonical_metric in self.METRIC_CONFIG:
                        if canonical_metric not in parsed_metrics['dynamic_metrics']:
                            parsed_metrics['dynamic_metrics'][canonical_metric] = {}
                        if year not in parsed_metrics['dynamic_metrics'][canonical_metric]:
                            parsed_metrics['dynamic_metrics'][canonical_metric][year] = []
                        if 'yoy' not in parsed_metrics['dynamic_metrics'][canonical_metric][year]:
                            parsed_metrics['dynamic_metrics'][canonical_metric][year].append('yoy')
                    else:
                        # Unknown metric, treat as base metric
                        if item not in parsed_metrics['base_metrics']:
                            parsed_metrics['base_metrics'].append(item)
                except ValueError:
                    # Invalid year, treat as base metric
                    if item not in parsed_metrics['base_metrics']:
                        parsed_metrics['base_metrics'].append(item)
            else:
                # Invalid format, treat as base metric
                if item not in parsed_metrics['base_metrics']:
                    parsed_metrics['base_metrics'].append(item)
        
        return parsed_metrics

    def _compute_base_metrics(self, tickers: List[str], base_metrics: List[str], tool_system: EnhancedAIToolSystem) -> pd.DataFrame:
        """Compute base metrics (no year required)"""
        rows = []
        
        for ticker in tickers:
            row = {"Ticker": ticker}
            
            for metric_display_name in base_metrics:
                metric_key = self._get_metric_key_from_display_name(metric_display_name)
                config = self.METRIC_CONFIG.get(metric_key)
                
                if config and config['category'] == 'base':
                    try:
                        # Call the get_valuation_analysis function
                        result = tool_system.execute_tool(
                            'get_valuation_analysis',
                            {'ticker': ticker}
                        )
                        
                        if result.get('status') == 'success':
                            # Data is in result['data'], not at top level
                            data = result.get('data', {})
                            value = data.get(config['field'])
                            row[metric_display_name] = value
                        else:
                            row[metric_display_name] = None
                    except Exception:
                        row[metric_display_name] = None
                else:
                    row[metric_display_name] = None
            
            rows.append(row)
        
        return pd.DataFrame(rows)

    def _compute_dynamic_metrics(self, tickers: List[str], dynamic_metrics: Dict[str, Dict[int, List[str]]], tool_system: EnhancedAIToolSystem) -> pd.DataFrame:
        """Compute dynamic metrics (year required) with support for YoY growth"""
        rows = []
        
        for ticker in tickers:
            row = {"Ticker": ticker}
            
            for metric_key, year_configs in dynamic_metrics.items():
                config = self.METRIC_CONFIG.get(metric_key)
                if not config:
                    continue
                
                for year, metric_types in year_configs.items():
                    for metric_type in metric_types:
                        if metric_type == 'yoy':
                            # For YoY growth, we need current year and previous year data
                            col_name = f"{config['display_name']} ({year}) YoY %"
                            
                            try:
                                # Get current year and previous year data
                                current_value = self._get_metric_value(ticker, metric_key, year, config, tool_system)
                                previous_value = self._get_metric_value(ticker, metric_key, year - 1, config, tool_system)
                                
                                # Calculate YoY growth percentage
                                if current_value is not None and previous_value is not None and previous_value != 0:
                                    yoy_growth = ((current_value - previous_value) / abs(previous_value)) * 100
                                    row[col_name] = round(yoy_growth, 2)
                                else:
                                    row[col_name] = None
                            except Exception:
                                row[col_name] = None
                        elif metric_type == 'absolute':
                            # Absolute value
                            col_name = f"{config['display_name']} ({year})"
                            value = self._get_metric_value(ticker, metric_key, year, config, tool_system)
                            row[col_name] = value
            
            rows.append(row)
        
        return pd.DataFrame(rows)

    def _get_metric_value(self, ticker: str, metric_key: str, year: int, config: Dict[str, Any], tool_system: EnhancedAIToolSystem) -> Any:
        """Get a single metric value using the generic approach"""
        try:
            if config['category'] == 'historical':
                return self._get_historical_metric_value(ticker, metric_key, year, config, tool_system)
            elif config['category'] == 'ratio':
                return self._get_ratio_metric_value(ticker, metric_key, year, config, tool_system)
            else:
                return None
        except Exception:
            return None

    def _get_historical_metric_value(self, ticker: str, metric_key: str, year: int, config: Dict[str, Any], tool_system: EnhancedAIToolSystem) -> Any:
        """Get historical metric value with fallback to forecast"""
        # Try historical first
        try:
            result = tool_system.execute_tool(
                'get_historical_annual_financials',
                {
                    'tickers': [ticker],
                    'metrics': [config['field']],
                    'years': [year],
                    'unit': 'billions'
                }
            )
            
            if result.get('status') == 'success' and result.get('data'):
                for entry in result['data']:
                    e_ticker = str(entry.get('TICKER', '')).upper()
                    try:
                        e_year = int(entry.get('DATE')) if entry.get('DATE') is not None else None
                    except Exception:
                        e_year = None
                    if e_year != year or (e_ticker and e_ticker != str(ticker).upper()):
                        continue

                    # Check for metric in pivoted format
                    if config['field'] in entry and entry.get(config['field']) is not None:
                        return float(entry.get(config['field']))
                    # Check for metric in non-pivoted format
                    elif entry.get('KEYCODE') == config['field'] and entry.get('VALUE') is not None:
                        return float(entry.get('VALUE'))
        except Exception:
            pass
        
        # Try forecast fallback if available
        if 'fallback_source' in config:
            try:
                fc_result = tool_system.execute_tool(
                    config['fallback_source'],
                    {
                        'ticker': ticker,
                        'years': [str(year)],
                        'statement_type': 'balance_sheet' if 'balance_sheet' in config['fallback_path'] else 'pnl',
                        'fields': [config['fallback_field']]
                    }
                )
                if fc_result.get('status') == 'success':
                    forecast_data = fc_result.get('forecast_data', {})
                    year_data = forecast_data.get(str(year), {})
                    
                    if 'balance_sheet' in config['fallback_path']:
                        bs = year_data.get('balance_sheet', {})
                        value = bs.get(config['fallback_field'])
                    else:
                        pnl = year_data.get('pnl', {})
                        value = pnl.get(config['fallback_field'])
                    
                    if value is not None:
                        return float(value)
            except Exception:
                pass
        
        return None

    def _get_ratio_metric_value(self, ticker: str, metric_key: str, year: int, config: Dict[str, Any], tool_system: EnhancedAIToolSystem) -> Any:
        """Get ratio metric value"""
        try:
            result = tool_system.execute_tool(
                'calculate_balance_sheet_ratios',
                {
                    'ticker': ticker,
                    'year_start': year,
                    'year_end': year,
                    'period_type': 'annual',
                    'ratios': [config['field']]
                }
            )
            
            if result.get('status') == 'success':
                # Extract data from the nested structure
                outer_data = result.get('data', {})
                inner_data = outer_data.get('data', {})
                year_data = inner_data.get(int(year), {})
                ratios_data = year_data.get('ratios', {})
                
                if config['field'] in ratios_data:
                    calculated_ratio = ratios_data[config['field']]
                    
                    if calculated_ratio is not None:
                        # Apply transformation if needed
                        if config.get('transform') == 'invert' and calculated_ratio != 0:
                            return 1 / calculated_ratio
                        else:
                            return calculated_ratio
        except Exception:
            pass
        
        return None

    def _compute_metrics_for_tickers_generic(self, tickers: List[str], parsed_metrics: Dict[str, Any], tool_system: EnhancedAIToolSystem) -> pd.DataFrame:
        """Compute all metrics using the generic approach"""
        # Compute base metrics
        base_df = self._compute_base_metrics(tickers, parsed_metrics['base_metrics'], tool_system)
        
        # Compute dynamic metrics
        dynamic_df = self._compute_dynamic_metrics(tickers, parsed_metrics['dynamic_metrics'], tool_system)
        
        # Merge the results
        if not base_df.empty and not dynamic_df.empty:
            result_df = base_df.merge(dynamic_df, on='Ticker', how='outer')
        elif not base_df.empty:
            result_df = base_df
        elif not dynamic_df.empty:
            result_df = dynamic_df
        else:
            result_df = pd.DataFrame({'Ticker': tickers})
        
        return result_df

    def _format_dataframe_for_display(self, df: pd.DataFrame) -> pd.DataFrame:
        """Format numerical columns with thousand separators, except percentage columns"""
        if df.empty:
            return df
        
        df_formatted = df.copy()
        
        # Format numerical columns with thousand separators
        for col in df_formatted.columns:
            if col not in ['Ticker', 'Company Name']:
                # Skip percentage columns (contain '%' or 'YoY')
                if '%' not in col and 'YoY' not in col:
                    try:
                        # Check if column contains numerical data
                        numeric_mask = pd.to_numeric(df_formatted[col], errors='coerce').notna()
                        if numeric_mask.any():
                            df_formatted[col] = df_formatted[col].apply(
                                lambda x: f"{x:,.0f}" if pd.notna(x) and isinstance(x, (int, float)) and not isinstance(x, bool) else x
                            )
                    except Exception:
                        # If formatting fails, keep original values
                        pass
        
        return df_formatted

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

        # Initialize session state for metric selections
        if 'selected_metrics' not in st.session_state:
            st.session_state.selected_metrics = []

        # Add new metric section
        st.subheader("➕ Add New Metric")

        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            # Generate available metrics dynamically from METRIC_CONFIG
            available_metrics = []
            
            # Add base metrics (no year required)
            for metric_key, config in self.METRIC_CONFIG.items():
                if config['category'] == 'base':
                    available_metrics.append(config['display_name'])
            
            # Add dynamic metrics (year required)
            for metric_key, config in self.METRIC_CONFIG.items():
                if config['category'] in ['historical', 'ratio']:
                    available_metrics.append(metric_key)
            
            selected_metric = st.selectbox(
                "Select Metric",
                options=available_metrics,
                help="Choose the financial metric you want to add. Most metrics require year selection."
            )

        with col2:
            # Year selection dropdown - disable only for base metrics
            is_base_metric = self._is_base_metric(selected_metric)
            year_options = [str(year) for year in sorted(all_years)]
            selected_year = st.selectbox(
                "Select Year",
                options=year_options,
                help="Choose the year for the selected metric" if not is_base_metric else "Not needed for base metrics",
                disabled=is_base_metric
            )

        with col3:
            # Type selection dropdown - disable only for base metrics
            type_options = ["Absolute Value", "YoY Growth"]
            selected_type = st.selectbox(
                "Type",
                options=type_options,
                help="Choose absolute value or YoY growth" if not is_base_metric else "Not needed for base metrics",
                disabled=is_base_metric
            )

        # New row for buttons
        col_btn1, col_btn2 = st.columns([1, 1])
        
        with col_btn1:
            # Add metric button
            if st.button("Add Metric", type="primary", use_container_width=True):
                # For base metrics, don't include year or type
                if is_base_metric:
                    new_metric = selected_metric
                else:
                    # Include type in the metric name for dynamic metrics
                    if selected_type == "YoY Growth":
                        new_metric = f"{selected_metric} {selected_year} YoY"
                    else:
                        new_metric = f"{selected_metric} {selected_year}"

                # Check if already exists
                if new_metric not in st.session_state.selected_metrics:
                    st.session_state.selected_metrics.append(new_metric)
                    st.success(f"✅ Added: {new_metric}")
                    st.rerun()  # Refresh to show the new selection
                else:
                    st.warning(f"⚠️ Already selected: {new_metric}")

        with col_btn2:
            # Clear all button
            if st.button("Clear All", type="secondary", use_container_width=True):
                st.session_state.selected_metrics = []
                st.info("🗑️ Cleared all selections")
                st.rerun()

        st.markdown("---")

        # Metric selection with year support
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

        # Parse selected metrics using generic approach
        parsed_metrics = self._parse_selected_metrics(all_selected)

        # Build the comparable table
        df_display = base_df.copy()
        has_metrics = any(parsed_metrics.values())
        
        if has_metrics:
            df_metrics = self._compute_metrics_for_tickers_generic(
                df_display['Ticker'].tolist(),
                parsed_metrics,
                tool_system
            )
            
            if not df_metrics.empty:
                df_display = df_display.merge(df_metrics, left_on='Ticker', right_on='Ticker', how='left')
                # Reorder columns: Ticker, Company Name, then all metrics
                col_order = ['Ticker', 'Company Name'] + [col for col in df_metrics.columns if col != 'Ticker']
                existing = [c for c in col_order if c in df_display.columns]
                df_display = df_display[existing]
                
                # Format the dataframe for display
                df_display = self._format_dataframe_for_display(df_display)

            st.dataframe(df_display, use_container_width=True)
        else:
            st.info("No metrics selected. Use the selector above to choose metrics.")

        # Sector Charts Section
        st.markdown("---")
        st.subheader("📊 Sector Charts")
        
        # Load P/E and P/B data
        pe_pb_data = self._load_pe_pb_data()
        
        if not pe_pb_data.empty:
            # Get available tickers from companies collection (same as comparable table)
            df_companies = load_companies_data()
            company_tickers = df_companies['ticker'].tolist() if not df_companies.empty else []
            
            # Filter P/E and P/B data to only include companies from the collection
            pe_pb_data_filtered = pe_pb_data[pe_pb_data['TICKER'].isin(company_tickers)]
            
            if not pe_pb_data_filtered.empty:
                # Get available tickers from the filtered data
                available_tickers = sorted(pe_pb_data_filtered['TICKER'].unique())
                
                # Ticker selector for charts
                col_chart1, col_chart2 = st.columns([1, 1])
                
                with col_chart1:
                    st.markdown("**Ticker Selection for Charts:**")
                selected_chart_tickers = st.multiselect(
                    "Select tickers to display in charts",
                    options=available_tickers,
                    default=[],  # Show no tickers by default, only average/median lines
                    key="chart_ticker_selector",
                    help="Select which tickers to show in the P/E and P/B charts below. Charts will always show sector average and median lines."
                )
            
                # Always create charts (with average/median lines), tickers are optional
                col_pe, col_pb = st.columns([1, 1])
                
                with col_pe:
                    st.markdown("**Trailing P/E Chart**")
                    pe_chart = self._create_pe_chart(pe_pb_data_filtered, selected_chart_tickers)
                    st.plotly_chart(pe_chart, use_container_width=True)
                
                with col_pb:
                    st.markdown("**Trailing P/B Chart**")
                    pb_chart = self._create_pb_chart(pe_pb_data_filtered, selected_chart_tickers)
                    st.plotly_chart(pb_chart, use_container_width=True)
                
                # Add scatter charts section
                st.markdown("---")
                st.subheader("📈 Scatter Analysis")
                
                # Create scatter charts
                col_scatter1, col_scatter2 = st.columns([1, 1])
                
                with col_scatter1:
                    st.markdown("**P/B vs P/E Analysis**")
                    
                    pb_pe_scatter = self._create_pb_pe_scatter()
                    st.plotly_chart(pb_pe_scatter, use_container_width=True)
                
                with col_scatter2:
                    st.markdown("**Land Bank vs Market Cap**")
                    landbank_scatter = self._create_landbank_scatter()
                    st.plotly_chart(landbank_scatter, use_container_width=True)
                
                # Add range charts section
                st.markdown("---")
                st.subheader("📊 P/E & P/B Range Analysis")
                
                # Create range charts
                col_range1, col_range2 = st.columns([1, 1])
                
                with col_range1:
                    st.markdown("**P/E Range by Ticker**")
                    pe_range_chart = self._create_pe_range_chart(pe_pb_data_filtered)
                    st.plotly_chart(pe_range_chart, use_container_width=True)
                
                with col_range2:
                    st.markdown("**P/B Range by Ticker**")
                    pb_range_chart = self._create_pb_range_chart(pe_pb_data_filtered)
                    st.plotly_chart(pb_range_chart, use_container_width=True)
            else:
                st.warning("No P/E and P/B data available for companies in the collection.")
        else:
            st.warning("No P/E and P/B data available. Please check if Val_processed.csv exists and contains data.")
    
    def _load_pe_pb_data(self) -> pd.DataFrame:
        """Load P/E and P/B data from Val_processed.csv"""
        try:
            import os
            file_path = 'data/Val_processed.csv'
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                # Convert TRADE_DATE to datetime
                df['TRADE_DATE'] = pd.to_datetime(df['TRADE_DATE'])
                # Filter out rows with NaN values for P/E and P/B
                df = df.dropna(subset=['P/E', 'P/B'], how='all')
                return df
            else:
                return pd.DataFrame()
        except Exception as e:
            st.error(f"Error loading P/E and P/B data: {str(e)}")
            return pd.DataFrame()
    
    def _create_pe_chart(self, data: pd.DataFrame, selected_tickers: List[str]) -> any:
        """Create trailing P/E chart"""
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            
            # Check if we have any data at all
            if data.empty:
                return go.Figure().add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5)
            
            # Filter data for selected tickers (for individual ticker lines)
            if selected_tickers:
                filtered_data = data[data['TICKER'].isin(selected_tickers)].copy()
            else:
                filtered_data = pd.DataFrame()  # Empty for individual ticker lines
            
            # Create the chart
            fig = go.Figure()
            
            # Add a line for each selected ticker (if any)
            if selected_tickers:
                for ticker in selected_tickers:
                    ticker_data = filtered_data[filtered_data['TICKER'] == ticker].sort_values('TRADE_DATE')
                    
                    if not ticker_data.empty:
                        fig.add_trace(go.Scatter(
                            x=ticker_data['TRADE_DATE'],
                            y=ticker_data['P/E'],
                            mode='lines+markers',
                            name=ticker,
                            line=dict(width=2),
                            marker=dict(size=4),
                            hovertemplate=f'<b>{ticker}</b><br>' +
                                        'Date: %{x}<br>' +
                                        'P/E: %{y:.2f}<br>' +
                                        '<extra></extra>'
                        ))
            
            # Always add Simple Average P/E line (based on all companies in collection)
            avg_pe_data = self._calculate_average_pe(data, None)  # None means all tickers
            if not avg_pe_data.empty:
                fig.add_trace(go.Scatter(
                    x=avg_pe_data['TRADE_DATE'],
                    y=avg_pe_data['AVG_PE'],
                    mode='lines',
                    name='Simple Average P/E',
                    line=dict(width=3, color='red', dash='dash'),
                    hovertemplate='<b>Simple Average P/E</b><br>' +
                                'Date: %{x}<br>' +
                                'Average P/E: %{y:.2f}<br>' +
                                '<extra></extra>'
                ))
            
            # Always add Median P/E line (based on all companies in collection)
            median_pe_data = self._calculate_median_pe(data, None)  # None means all tickers
            if not median_pe_data.empty:
                fig.add_trace(go.Scatter(
                    x=median_pe_data['TRADE_DATE'],
                    y=median_pe_data['MEDIAN_PE'],
                    mode='lines',
                    name='Median P/E',
                    line=dict(width=3, color='blue', dash='dot'),
                    hovertemplate='<b>Median P/E</b><br>' +
                                'Date: %{x}<br>' +
                                'Median P/E: %{y:.2f}<br>' +
                                '<extra></extra>'
                ))
            
            # Update layout
            fig.update_layout(
                title="Trailing P/E Ratio Over Time",
                xaxis_title="Date",
                yaxis_title="P/E Ratio",
                hovermode='x unified',
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.02
                ),
                height=400,
                margin=dict(r=100)
            )
            
            # Add horizontal line at P/E = 1 (fair value reference)
            fig.add_hline(y=1, line_dash="dash", line_color="gray", 
                         annotation_text="P/E = 1", annotation_position="bottom right")
            
            return fig
            
        except Exception as e:
            print(f"Error creating P/E chart: {str(e)}")  # Debug print
            st.error(f"Error creating P/E chart: {str(e)}")
            return go.Figure().add_annotation(text="Error creating chart", xref="paper", yref="paper", x=0.5, y=0.5)
    
    def _create_pb_chart(self, data: pd.DataFrame, selected_tickers: List[str]) -> any:
        """Create trailing P/B chart"""
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            
            # Check if we have any data at all
            if data.empty:
                return go.Figure().add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5)
            
            # Filter data for selected tickers (for individual ticker lines)
            if selected_tickers:
                filtered_data = data[data['TICKER'].isin(selected_tickers)].copy()
            else:
                filtered_data = pd.DataFrame()  # Empty for individual ticker lines
            
            # Create the chart
            fig = go.Figure()
            
            # Add a line for each selected ticker (if any)
            if selected_tickers:
                for ticker in selected_tickers:
                    ticker_data = filtered_data[filtered_data['TICKER'] == ticker].sort_values('TRADE_DATE')
                    
                    if not ticker_data.empty:
                        fig.add_trace(go.Scatter(
                            x=ticker_data['TRADE_DATE'],
                            y=ticker_data['P/B'],
                            mode='lines+markers',
                            name=ticker,
                            line=dict(width=2),
                            marker=dict(size=4),
                            hovertemplate=f'<b>{ticker}</b><br>' +
                                        'Date: %{x}<br>' +
                                        'P/B: %{y:.2f}<br>' +
                                        '<extra></extra>'
                        ))
            
            # Always add Simple Average P/B line (based on all companies in collection)
            avg_pb_data = self._calculate_average_pb(data, None)  # None means all tickers
            if not avg_pb_data.empty:
                fig.add_trace(go.Scatter(
                    x=avg_pb_data['TRADE_DATE'],
                    y=avg_pb_data['AVG_PB'],
                    mode='lines',
                    name='Simple Average P/B',
                    line=dict(width=3, color='red', dash='dash'),
                    hovertemplate='<b>Simple Average P/B</b><br>' +
                                'Date: %{x}<br>' +
                                'Average P/B: %{y:.2f}<br>' +
                                '<extra></extra>'
                ))
            
            # Always add Median P/B line (based on all companies in collection)
            median_pb_data = self._calculate_median_pb(data, None)  # None means all tickers
            if not median_pb_data.empty:
                fig.add_trace(go.Scatter(
                    x=median_pb_data['TRADE_DATE'],
                    y=median_pb_data['MEDIAN_PB'],
                    mode='lines',
                    name='Median P/B',
                    line=dict(width=3, color='blue', dash='dot'),
                    hovertemplate='<b>Median P/B</b><br>' +
                                'Date: %{x}<br>' +
                                'Median P/B: %{y:.2f}<br>' +
                                '<extra></extra>'
                ))
            
            # Update layout
            fig.update_layout(
                title="Trailing P/B Ratio Over Time",
                xaxis_title="Date",
                yaxis_title="P/B Ratio",
                hovermode='x unified',
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.02
                ),
                height=400,
                margin=dict(r=100)
            )
            
            # Add horizontal line at P/B = 1 (book value reference)
            fig.add_hline(y=1, line_dash="dash", line_color="gray", 
                         annotation_text="P/B = 1", annotation_position="bottom right")
            
            return fig
            
        except Exception as e:
            print(f"Error creating P/B chart: {str(e)}")  # Debug print
            st.error(f"Error creating P/B chart: {str(e)}")
            return go.Figure().add_annotation(text="Error creating chart", xref="paper", yref="paper", x=0.5, y=0.5)
    
    def _calculate_average_pe(self, data: pd.DataFrame, selected_tickers: List[str] = None) -> pd.DataFrame:
        """Calculate simple average P/E for selected tickers by date. If selected_tickers is None, use all tickers."""
        try:
            # Filter data for selected tickers (or use all if None)
            if selected_tickers is not None:
                filtered_data = data[data['TICKER'].isin(selected_tickers)].copy()
            else:
                filtered_data = data.copy()
            
            if filtered_data.empty:
                return pd.DataFrame()
            
            # Group by date and calculate average P/E
            avg_data = filtered_data.groupby('TRADE_DATE')['P/E'].mean().reset_index()
            avg_data.columns = ['TRADE_DATE', 'AVG_PE']
            
            # Remove rows where average is NaN
            avg_data = avg_data.dropna()
            
            return avg_data.sort_values('TRADE_DATE')
            
        except Exception:
            return pd.DataFrame()
    
    def _calculate_median_pe(self, data: pd.DataFrame, selected_tickers: List[str] = None) -> pd.DataFrame:
        """Calculate median P/E for selected tickers by date. If selected_tickers is None, use all tickers."""
        try:
            # Filter data for selected tickers (or use all if None)
            if selected_tickers is not None:
                filtered_data = data[data['TICKER'].isin(selected_tickers)].copy()
            else:
                filtered_data = data.copy()
            
            if filtered_data.empty:
                return pd.DataFrame()
            
            # Group by date and calculate median P/E
            median_data = filtered_data.groupby('TRADE_DATE')['P/E'].median().reset_index()
            median_data.columns = ['TRADE_DATE', 'MEDIAN_PE']
            
            # Remove rows where median is NaN
            median_data = median_data.dropna()
            
            return median_data.sort_values('TRADE_DATE')
            
        except Exception:
            return pd.DataFrame()
    
    def _calculate_average_pb(self, data: pd.DataFrame, selected_tickers: List[str] = None) -> pd.DataFrame:
        """Calculate simple average P/B for selected tickers by date. If selected_tickers is None, use all tickers."""
        try:
            # Filter data for selected tickers (or use all if None)
            if selected_tickers is not None:
                filtered_data = data[data['TICKER'].isin(selected_tickers)].copy()
            else:
                filtered_data = data.copy()
            
            if filtered_data.empty:
                return pd.DataFrame()
            
            # Group by date and calculate average P/B
            avg_data = filtered_data.groupby('TRADE_DATE')['P/B'].mean().reset_index()
            avg_data.columns = ['TRADE_DATE', 'AVG_PB']
            
            # Remove rows where average is NaN
            avg_data = avg_data.dropna()
            
            return avg_data.sort_values('TRADE_DATE')
            
        except Exception:
            return pd.DataFrame()
    
    def _calculate_median_pb(self, data: pd.DataFrame, selected_tickers: List[str] = None) -> pd.DataFrame:
        """Calculate median P/B for selected tickers by date. If selected_tickers is None, use all tickers."""
        try:
            # Filter data for selected tickers (or use all if None)
            if selected_tickers is not None:
                filtered_data = data[data['TICKER'].isin(selected_tickers)].copy()
            else:
                filtered_data = data.copy()
            
            if filtered_data.empty:
                return pd.DataFrame()
            
            # Group by date and calculate median P/B
            median_data = filtered_data.groupby('TRADE_DATE')['P/B'].median().reset_index()
            median_data.columns = ['TRADE_DATE', 'MEDIAN_PB']
            
            # Remove rows where median is NaN
            median_data = median_data.dropna()
            
            return median_data.sort_values('TRADE_DATE')
            
        except Exception:
            return pd.DataFrame()
    
    def _create_pb_pe_scatter(self) -> any:
        """Create P/B vs P/E scatter chart with RNAV bubble size using trailing multiples"""
        try:
            import plotly.graph_objects as go
            
            # Get trailing multiples and RNAV data for companies
            scatter_data = self._get_trailing_valuation_data()
            
            if scatter_data.empty:
                return go.Figure().add_annotation(
                    text="No trailing valuation data available", 
                    xref="paper", yref="paper", x=0.5, y=0.5
                )
            
            # Handle NaN values - filter out rows where both P/E and P/B are NaN
            # Keep rows where at least one multiple is available
            scatter_data = scatter_data.dropna(subset=['P/E', 'P/B'], how='all')
            
            # Create scatter plot
            fig = go.Figure()
            
            # Add scatter points
            fig.add_trace(go.Scatter(
                x=scatter_data['P/B'],
                y=scatter_data['P/E'],
                mode='markers+text',
                text=scatter_data['TICKER'],
                textposition='top center',
                marker=dict(
                    size=scatter_data['RNAV_Size'],
                    sizemode='diameter',
                    sizemin=8,
                    color=scatter_data['P/E'].fillna(0),  # Handle NaN values for color mapping
                    colorscale='Viridis',
                    colorbar=dict(title="P/E Ratio"),
                    line=dict(width=2, color='white'),
                    opacity=0.8
                ),
                hovertemplate='<b>%{text}</b><br>' +
                            'P/B: %{x:.2f}<br>' +
                            'P/E: %{y:.2f}<br>' +
                            'Total RNAV: %{customdata[0]:.0f} VND tn<br>' +
                            '<extra></extra>',
                customdata=scatter_data[['Total_RNAV']].values
            ))
            
            # Update layout
            fig.update_layout(
                title="P/B vs P/E Analysis - Trailing Multiples (Bubble Size = Total RNAV)",
                xaxis_title="Trailing P/B Ratio",
                yaxis_title="Trailing P/E Ratio",
                height=400,
                showlegend=False
            )
            
            # Add reference lines
            fig.add_vline(x=1, line_dash="dash", line_color="gray", 
                         annotation_text="P/B = 1", annotation_position="top")
            fig.add_hline(y=1, line_dash="dash", line_color="gray", 
                         annotation_text="P/E = 1", annotation_position="right")
            
            return fig
            
        except Exception as e:
            print(f"Error creating P/B vs P/E scatter chart: {str(e)}")
            return go.Figure().add_annotation(text="Error creating chart", xref="paper", yref="paper", x=0.5, y=0.5)
    
    def _create_landbank_scatter(self) -> any:
        """Create Land Bank vs Market Cap scatter chart"""
        try:
            import plotly.graph_objects as go
            
            # Get land bank and market cap data
            scatter_data = self._get_landbank_marketcap_data()
            
            if scatter_data.empty:
                return go.Figure().add_annotation(text="No land bank data available", xref="paper", yref="paper", x=0.5, y=0.5)
            
            # Create scatter plot
            fig = go.Figure()
            
            # Add scatter points
            fig.add_trace(go.Scatter(
                x=scatter_data['Land_Bank_HA'],
                y=scatter_data['Market_Cap_TN'],
                mode='markers+text',
                text=scatter_data['Ticker'],
                textposition='top center',
                marker=dict(
                    size=15,
                    color=scatter_data['Market_Cap_TN'],
                    colorscale='Blues',
                    colorbar=dict(title="Market Cap (VND tn)"),
                    line=dict(width=2, color='white'),
                    opacity=0.8
                ),
                hovertemplate='<b>%{text}</b><br>' +
                            'Land Bank: %{x:.1f} ha<br>' +
                            'Market Cap: %{y:.1f} VND tn<br>' +
                            '<extra></extra>'
            ))
            
            # Update layout
            fig.update_layout(
                title="Land Bank vs Market Cap",
                xaxis_title="Total Land Bank (ha)",
                yaxis_title="Market Cap (VND tn)",
                height=400,
                showlegend=False
            )
            
            return fig
            
        except Exception as e:
            print(f"Error creating Land Bank vs Market Cap scatter chart: {str(e)}")
            return go.Figure().add_annotation(text="Error creating chart", xref="paper", yref="paper", x=0.5, y=0.5)
    
    def _get_trailing_valuation_data(self) -> pd.DataFrame:
        """Get trailing P/B, P/E, and RNAV data for scatter chart using RNAV breakdown"""
        try:
            from utils.mongodb_utils import load_companies_data
            from tabs.enhanced_ai_assistant import EnhancedAIToolSystem
            
            # Get companies from collection
            df_companies = load_companies_data()
            if df_companies.empty:
                return pd.DataFrame()
            
            company_tickers = df_companies['ticker'].tolist()
            tool_system = EnhancedAIToolSystem()
            
            # Get trailing multiples and RNAV data from valuation analysis
            valuation_data = []
            successful_tickers = []
            failed_tickers = []
            
            # First, try to get data from valuation analysis (includes RNAV)
            for ticker in company_tickers:
                try:
                    result = tool_system.execute_tool('get_valuation_analysis', {'ticker': ticker})
                    if result.get('status') == 'success':
                        data = result.get('data', {})
                        trailing_pe = data.get('trailing_pe')
                        trailing_pb = data.get('trailing_pb')
                        total_rnav = data.get('total_rnav', 0)
                        
                        # Include if at least one multiple is available
                        if trailing_pe is not None or trailing_pb is not None:
                            # Handle RNAV - use 0 if None or 0, convert to tn
                            rnav_tn = (total_rnav / 1000) if total_rnav and total_rnav > 0 else 0
                            
                            valuation_data.append({
                                'TICKER': ticker,
                                'P/E': trailing_pe,
                                'P/B': trailing_pb,
                                'Total_RNAV': rnav_tn
                            })
                            successful_tickers.append(ticker)
                        else:
                            failed_tickers.append(ticker)
                    else:
                        failed_tickers.append(ticker)
                except Exception as e:
                    failed_tickers.append(ticker)
                    continue
            
            # For tickers without valuation data, try to get trailing multiples from PE/PB data
            if failed_tickers:
                pe_pb_data = self._load_pe_pb_data()
                
                for ticker in failed_tickers:
                    try:
                        # Get latest trailing data for this ticker
                        ticker_data = pe_pb_data[pe_pb_data['TICKER'] == ticker]
                        if not ticker_data.empty:
                            # Get the most recent data
                            latest_data = ticker_data.sort_values('TRADE_DATE').iloc[-1]
                            trailing_pe = latest_data.get('P/E')
                            trailing_pb = latest_data.get('P/B')
                            
                            # Include if at least one multiple is available
                            if trailing_pe is not None or trailing_pb is not None:
                                valuation_data.append({
                                    'TICKER': ticker,
                                    'P/E': trailing_pe,
                                    'P/B': trailing_pb,
                                    'Total_RNAV': 0  # No RNAV data available
                                })
                                successful_tickers.append(ticker)
                    except Exception as e:
                        continue
            
            scatter_data = pd.DataFrame(valuation_data)
            
            if scatter_data.empty:
                return pd.DataFrame()
            
            # Clean data - filter out rows where both P/E and P/B are NaN
            # Keep all tickers with at least one trailing multiple, regardless of RNAV
            scatter_data = scatter_data.dropna(subset=['P/E', 'P/B'], how='all')
            
            # Normalize RNAV for bubble size (scale between 8-60)
            if not scatter_data.empty:
                # Separate tickers with and without RNAV
                has_rnav = scatter_data['Total_RNAV'] > 0
                no_rnav = scatter_data['Total_RNAV'] == 0
                
                # Set minimum size for tickers without RNAV
                scatter_data.loc[no_rnav, 'RNAV_Size'] = 8  # Smallest size for zero RNAV
                
                # Scale sizes for tickers with RNAV
                if has_rnav.any():
                    rnav_data = scatter_data[has_rnav]
                    if len(rnav_data) > 1 and rnav_data['Total_RNAV'].max() > rnav_data['Total_RNAV'].min():
                        min_rnav = rnav_data['Total_RNAV'].min()
                        max_rnav = rnav_data['Total_RNAV'].max()
                        # Scale from 15 to 60 based on RNAV value
                        scatter_data.loc[has_rnav, 'RNAV_Size'] = 15 + (scatter_data.loc[has_rnav, 'Total_RNAV'] - min_rnav) / (max_rnav - min_rnav) * 45
                    else:
                        scatter_data.loc[has_rnav, 'RNAV_Size'] = 30  # Default size for single RNAV ticker
                else:
                    # All tickers have no RNAV
                    scatter_data['RNAV_Size'] = 8
            
            return scatter_data[['TICKER', 'P/E', 'P/B', 'Total_RNAV', 'RNAV_Size']]
            
        except Exception as e:
            print(f"Error getting trailing valuation data: {str(e)}")
            return pd.DataFrame()
    
    def _get_landbank_marketcap_data(self) -> pd.DataFrame:
        """Get land bank and market cap data for scatter chart"""
        try:
            from utils.mongodb_utils import load_companies_data, load_projects_data
            from tabs.enhanced_ai_assistant import EnhancedAIToolSystem
            
            # Get companies from collection
            df_companies = load_companies_data()
            if df_companies.empty:
                return pd.DataFrame()
            
            company_tickers = df_companies['ticker'].tolist()
            tool_system = EnhancedAIToolSystem()
            
            # Get projects data for land bank information
            projects_data = load_projects_data()
            
            # Get land bank and market cap data
            scatter_data = []
            
            for ticker in company_tickers:
                try:
                    # Get valuation data for current price
                    result = tool_system.execute_tool('get_valuation_analysis', {'ticker': ticker})
                    current_price = 0
                    if result.get('status') == 'success':
                        data = result.get('data', {})
                        current_price = data.get('current_price', 0)
                    
                    # Get shares outstanding from financial statements
                    shares_result = tool_system.execute_tool('get_historical_annual_financials', {
                        'tickers': [ticker],
                        'metrics': ['OS'],  # Outstanding Shares
                        'years': [2024, 2023, 2022],  # Try recent years
                        'unit': 'millions'
                    })
                    
                    shares_outstanding = 0
                    if shares_result.get('status') == 'success':
                        shares_data = shares_result.get('data', [])
                        if shares_data:
                            # Get the most recent shares outstanding data
                            latest_shares = max(shares_data, key=lambda x: x.get('DATE', 0))
                            # The data is already in actual shares, not millions
                            shares_outstanding = latest_shares.get('VALUE', 0)
                    
                    # Calculate market cap
                    if current_price > 0 and shares_outstanding > 0:
                        market_cap = current_price * shares_outstanding / 1000000000000  # Convert to VND tn
                    else:
                        market_cap = 0  # No valid data
                    
                    # Get land bank data from projects - sum all project land areas for this company
                    company_projects = projects_data[projects_data['company_ticker'] == ticker]
                    if not company_projects.empty and 'land_area' in company_projects.columns:
                        # Sum up all land areas for the company's projects (convert from sqm to hectares)
                        land_bank_sqm = company_projects['land_area'].fillna(0).sum()
                        land_bank_ha = land_bank_sqm / 10000  # Convert from sqm to hectares
                    else:
                        # Fallback to placeholder if no project data
                        land_bank_ha = 0  # No land bank data available
                    
                    # Always add the company to the results, even if market cap is 0
                    scatter_data.append({
                        'Ticker': ticker,
                        'Land_Bank_HA': land_bank_ha,
                        'Market_Cap_TN': market_cap
                    })
                except Exception:
                    continue
            
            return pd.DataFrame(scatter_data)
            
        except Exception as e:
            print(f"Error getting land bank and market cap data: {str(e)}")
            return pd.DataFrame()
    
    def _create_pe_range_chart(self, data: pd.DataFrame) -> any:
        """Create P/E range chart showing min, max, and current P/E for each ticker"""
        try:
            import plotly.graph_objects as go
            
            if data.empty:
                return go.Figure().add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5)
            
            # Calculate min, max, and current P/E for each ticker
            pe_stats = []
            
            for ticker in data['TICKER'].unique():
                ticker_data = data[data['TICKER'] == ticker]['P/E'].dropna()
                
                if not ticker_data.empty:
                    min_pe = ticker_data.min()
                    max_pe = ticker_data.max()
                    current_pe = ticker_data.iloc[-1]  # Most recent value
                    
                    pe_stats.append({
                        'Ticker': ticker,
                        'Min_PE': min_pe,
                        'Max_PE': max_pe,
                        'Current_PE': current_pe
                    })
            
            if not pe_stats:
                return go.Figure().add_annotation(text="No P/E data available", xref="paper", yref="paper", x=0.5, y=0.5)
            
            pe_df = pd.DataFrame(pe_stats)
            
            # Cap displayable P/E values at 50, but preserve original values for hover
            pe_df['Max_PE_Display'] = pe_df['Max_PE'].clip(upper=50)
            pe_df['Min_PE_Display'] = pe_df['Min_PE'].clip(upper=50)
            pe_df['Current_PE_Display'] = pe_df['Current_PE'].clip(upper=50)
            
            # Create the chart
            fig = go.Figure()
            
            # Add range bars (min to max) - use display values but show original in hover
            fig.add_trace(go.Scatter(
                x=pe_df['Ticker'],
                y=pe_df['Max_PE_Display'],
                mode='markers',
                marker=dict(size=8, color='lightblue', symbol='triangle-up'),
                name='Max P/E',
                hovertemplate='<b>%{x}</b><br>Max P/E: %{customdata:.2f}<extra></extra>',
                customdata=pe_df['Max_PE']
            ))
            
            fig.add_trace(go.Scatter(
                x=pe_df['Ticker'],
                y=pe_df['Min_PE_Display'],
                mode='markers',
                marker=dict(size=8, color='lightcoral', symbol='triangle-down'),
                name='Min P/E',
                hovertemplate='<b>%{x}</b><br>Min P/E: %{customdata:.2f}<extra></extra>',
                customdata=pe_df['Min_PE']
            ))
            
            # Add current P/E as larger markers
            fig.add_trace(go.Scatter(
                x=pe_df['Ticker'],
                y=pe_df['Current_PE_Display'],
                mode='markers',
                marker=dict(size=12, color='darkblue', symbol='circle'),
                name='Current P/E',
                hovertemplate='<b>%{x}</b><br>Current P/E: %{customdata:.2f}<extra></extra>',
                customdata=pe_df['Current_PE']
            ))
            
            # Add vertical lines connecting min and max (use display values)
            for _, row in pe_df.iterrows():
                fig.add_trace(go.Scatter(
                    x=[row['Ticker'], row['Ticker']],
                    y=[row['Min_PE_Display'], row['Max_PE_Display']],
                    mode='lines',
                    line=dict(color='gray', width=2),
                    showlegend=False,
                    hoverinfo='skip'
                ))
            
            # Update layout
            fig.update_layout(
                title="P/E Range Analysis by Ticker (Max P/E capped at 50 for display)",
                xaxis_title="Ticker",
                yaxis_title="P/E Ratio",
                yaxis=dict(range=[0, 55]),  # Set y-axis range to accommodate capped values
                hovermode='closest',
                height=400,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            return fig
            
        except Exception as e:
            print(f"Error creating P/E range chart: {str(e)}")
            st.error(f"Error creating P/E range chart: {str(e)}")
            return go.Figure().add_annotation(text="Error creating chart", xref="paper", yref="paper", x=0.5, y=0.5)
    
    def _create_pb_range_chart(self, data: pd.DataFrame) -> any:
        """Create P/B range chart showing min, max, and current P/B for each ticker"""
        try:
            import plotly.graph_objects as go
            
            if data.empty:
                return go.Figure().add_annotation(text="No data available", xref="paper", yref="paper", x=0.5, y=0.5)
            
            # Calculate min, max, and current P/B for each ticker
            pb_stats = []
            
            for ticker in data['TICKER'].unique():
                ticker_data = data[data['TICKER'] == ticker]['P/B'].dropna()
                
                if not ticker_data.empty:
                    min_pb = ticker_data.min()
                    max_pb = ticker_data.max()
                    current_pb = ticker_data.iloc[-1]  # Most recent value
                    
                    pb_stats.append({
                        'Ticker': ticker,
                        'Min_PB': min_pb,
                        'Max_PB': max_pb,
                        'Current_PB': current_pb
                    })
            
            if not pb_stats:
                return go.Figure().add_annotation(text="No P/B data available", xref="paper", yref="paper", x=0.5, y=0.5)
            
            pb_df = pd.DataFrame(pb_stats)
            
            # Create the chart
            fig = go.Figure()
            
            # Add range bars (min to max)
            fig.add_trace(go.Scatter(
                x=pb_df['Ticker'],
                y=pb_df['Max_PB'],
                mode='markers',
                marker=dict(size=8, color='lightgreen', symbol='triangle-up'),
                name='Max P/B',
                hovertemplate='<b>%{x}</b><br>Max P/B: %{y:.2f}<extra></extra>'
            ))
            
            fig.add_trace(go.Scatter(
                x=pb_df['Ticker'],
                y=pb_df['Min_PB'],
                mode='markers',
                marker=dict(size=8, color='lightcoral', symbol='triangle-down'),
                name='Min P/B',
                hovertemplate='<b>%{x}</b><br>Min P/B: %{y:.2f}<extra></extra>'
            ))
            
            # Add current P/B as larger markers
            fig.add_trace(go.Scatter(
                x=pb_df['Ticker'],
                y=pb_df['Current_PB'],
                mode='markers',
                marker=dict(size=12, color='darkgreen', symbol='circle'),
                name='Current P/B',
                hovertemplate='<b>%{x}</b><br>Current P/B: %{y:.2f}<extra></extra>'
            ))
            
            # Add vertical lines connecting min and max
            for _, row in pb_df.iterrows():
                fig.add_trace(go.Scatter(
                    x=[row['Ticker'], row['Ticker']],
                    y=[row['Min_PB'], row['Max_PB']],
                    mode='lines',
                    line=dict(color='gray', width=2),
                    showlegend=False,
                    hoverinfo='skip'
                ))
            
            # Update layout
            fig.update_layout(
                title="P/B Range Analysis by Ticker",
                xaxis_title="Ticker",
                yaxis_title="P/B Ratio",
                hovermode='closest',
                height=400,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            
            # Add horizontal line at P/B = 1 (book value reference)
            fig.add_hline(y=1, line_dash="dash", line_color="gray", 
                         annotation_text="P/B = 1", annotation_position="bottom right")
            
            return fig
            
        except Exception as e:
            print(f"Error creating P/B range chart: {str(e)}")
            st.error(f"Error creating P/B range chart: {str(e)}")
            return go.Figure().add_annotation(text="Error creating chart", xref="paper", yref="paper", x=0.5, y=0.5)
