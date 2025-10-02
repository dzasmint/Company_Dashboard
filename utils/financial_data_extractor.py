"""
Financial Data Extractor for Quarterly Earnings Analysis

Extracts quarterly financial data from FA_processed.parquet with:
- Current quarter + 2 comparison quarters (QoQ, YoY)
- All 43 financial metrics structured by category
- Pre-calculated percentage changes
- Data validation and error handling
"""

import pandas as pd
import os
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
import streamlit as st


class FinancialDataExtractor:
    """Extracts and structures quarterly financial data from parquet files"""
    
    # Mapping from parquet KEYCODE to our JSON schema fields
    KEYCODE_MAPPING = {
        # Income Statement
        'Net_Revenue': 'net_revenue',
        'COGS': 'cogs',
        'Gross_Profit': 'gross_profit',
        'Gross_Margin': 'gross_margin_pct',
        'GA_Expense': 'ga_expense',
        'Selling_Expense': 'selling_expense',
        'Dep_Expense': 'dep_expense',
        'EBIT': 'ebit',
        'EBIT_Margin': 'ebit_margin_pct',
        'EBITDA': 'ebitda',
        'EBITDA_Margin': 'ebitda_margin_pct',
        'Financial_Income': 'financial_income',
        'Financial_Expense': 'financial_expense',
        'Interest_Expense': 'interest_expense',
        'PBT': 'pbt',
        'Tax': 'tax',
        'Eff_Tax_Rate': 'eff_tax_rate_pct',
        'NPAT': 'npat',
        'NPAT_Margin': 'npat_margin_pct',
        'Minority_Interest_In_Earning': 'minority_interest_in_earning',
        'NPATMI': 'npatmi',
        
        # Balance Sheet
        'Total_Asset': 'total_assets',
        'Cash': 'cash',
        'Cash_Equivalent': 'cash_equivalent',
        'Short_Investment': 'short_investment',
        'Account_Receivable': 'account_receivable',
        'Inventory': 'inventory',
        'Tangible_Fixed_Asset': 'tangible_fixed_asset',
        'Total_Liabilities': 'total_liabilities',
        'Account_Payable': 'account_payable',
        'Advance_From_Custmers': 'advance_from_customers',
        'ST_Debt': 'st_debt',
        'LT_Debt': 'lt_debt',
        'TOTAL_Equity': 'total_equity',
        'Retain_Earning': 'retain_earning',
        'Minority_Interest': 'minority_interest',
        
        # Cash Flow
        'Operating_CF': 'operating_cf',
        'Inv_CF': 'inv_cf',
        'Capex': 'capex',
        'Fin_CF': 'fin_cf',
        'FCF': 'fcf',
        
        # Other
        'OS': 'outstanding_shares',
        'Invested_Capital': 'invested_capital'
    }
    
    # Category mapping
    INCOME_STATEMENT_FIELDS = [
        'net_revenue', 'cogs', 'gross_profit', 'gross_margin_pct',
        'ga_expense', 'selling_expense', 'dep_expense',
        'ebit', 'ebit_margin_pct', 'ebitda', 'ebitda_margin_pct',
        'financial_income', 'financial_expense', 'interest_expense',
        'pbt', 'tax', 'eff_tax_rate_pct',
        'npat', 'npat_margin_pct', 'minority_interest_in_earning', 'npatmi'
    ]
    
    BALANCE_SHEET_FIELDS = [
        'total_assets', 'cash', 'cash_equivalent', 'short_investment',
        'account_receivable', 'inventory', 'tangible_fixed_asset',
        'total_liabilities', 'account_payable', 'advance_from_customers',
        'st_debt', 'lt_debt', 'total_equity', 'retain_earning', 'minority_interest'
    ]
    
    CASH_FLOW_FIELDS = [
        'operating_cf', 'inv_cf', 'capex', 'fin_cf', 'fcf'
    ]
    
    OTHER_FIELDS = [
        'outstanding_shares', 'invested_capital'
    ]
    
    # Fields where percentages should be multiplied by 100
    PERCENTAGE_FIELDS = [
        'gross_margin_pct', 'ebit_margin_pct', 'ebitda_margin_pct',
        'npat_margin_pct', 'eff_tax_rate_pct'
    ]
    
    def __init__(self, parquet_path: str = None):
        """Initialize extractor with path to FA_processed.parquet"""
        if parquet_path is None:
            # Default path relative to project root
            parquet_path = os.path.join(os.getcwd(), 'data', 'FA_processed.parquet')
        
        self.parquet_path = parquet_path
        self._data = None
    
    def _load_data(self) -> pd.DataFrame:
        """Load parquet file (cached)"""
        if self._data is None:
            if not os.path.exists(self.parquet_path):
                raise FileNotFoundError(f"FA_processed.parquet not found at: {self.parquet_path}")
            self._data = pd.read_parquet(self.parquet_path)
        return self._data
    
    def _calculate_comparison_quarters(self, quarter: str) -> Tuple[str, str]:
        """
        Calculate QoQ and YoY comparison quarters
        
        Args:
            quarter: e.g., "2Q25"
            
        Returns:
            (qoq_quarter, yoy_quarter) e.g., ("1Q25", "2Q24")
        """
        # Parse quarter
        q_num = int(quarter[0])  # 1, 2, 3, 4
        year = int("20" + quarter[2:])  # e.g., 2025
        
        # Calculate QoQ (previous quarter)
        if q_num == 1:
            qoq_q = 4
            qoq_year = year - 1
        else:
            qoq_q = q_num - 1
            qoq_year = year
        
        qoq_quarter = f"{qoq_q}Q{str(qoq_year)[2:]}"
        
        # Calculate YoY (same quarter, previous year)
        yoy_quarter = f"{q_num}Q{str(year - 1)[2:]}"
        
        return qoq_quarter, yoy_quarter
    
    def _convert_quarter_format(self, quarter: str) -> str:
        """
        Convert quarter format from "2Q25" to "2025Q2" (parquet format)
        
        Args:
            quarter: e.g., "2Q25"
            
        Returns:
            e.g., "2025Q2"
        """
        q_num = quarter[0]  # "2"
        year = "20" + quarter[2:]  # "2025"
        return f"{year}Q{q_num}"
    
    def validate_data_availability(self, ticker: str, quarter: str) -> Dict[str, Any]:
        """
        Validate that data is available for the requested ticker and quarter
        
        Args:
            ticker: Stock ticker (e.g., "VHM")
            quarter: Quarter string (e.g., "2Q25")
            
        Returns:
            Dictionary with validation results:
            {
                "valid": bool,
                "message": str,
                "available_quarters": list,
                "missing_quarters": list
            }
        """
        try:
            df = self._load_data()
            
            # Check if ticker exists
            ticker_data = df[df['TICKER'] == ticker.upper()]
            if ticker_data.empty:
                available_tickers = sorted(df['TICKER'].unique())
                return {
                    "valid": False,
                    "message": f"Ticker '{ticker}' not found in database. Available tickers: {', '.join(available_tickers[:10])}...",
                    "available_quarters": [],
                    "missing_quarters": [quarter]
                }
            
            # Calculate comparison quarters
            qoq_quarter, yoy_quarter = self._calculate_comparison_quarters(quarter)
            
            # Convert to parquet format
            current_pq = self._convert_quarter_format(quarter)
            qoq_pq = self._convert_quarter_format(qoq_quarter)
            yoy_pq = self._convert_quarter_format(yoy_quarter)
            
            # Check which quarters are available
            available_quarters_pq = set(ticker_data['DATE'].unique())
            
            missing = []
            if current_pq not in available_quarters_pq:
                missing.append(f"{quarter} (current)")
            if qoq_pq not in available_quarters_pq:
                missing.append(f"{qoq_quarter} (QoQ comparison)")
            if yoy_pq not in available_quarters_pq:
                missing.append(f"{yoy_quarter} (YoY comparison)")
            
            if missing:
                available = sorted([q for q in available_quarters_pq], reverse=True)[:10]
                return {
                    "valid": False,
                    "message": f"Missing data for: {', '.join(missing)}. Available quarters for {ticker}: {', '.join(available)}",
                    "available_quarters": available,
                    "missing_quarters": missing
                }
            
            return {
                "valid": True,
                "message": "All required quarters available",
                "available_quarters": [current_pq, qoq_pq, yoy_pq],
                "missing_quarters": []
            }
            
        except Exception as e:
            return {
                "valid": False,
                "message": f"Error validating data: {str(e)}",
                "available_quarters": [],
                "missing_quarters": [quarter]
            }
    
    def _extract_quarter_data(self, df: pd.DataFrame, ticker: str, quarter_pq: str) -> Dict[str, Any]:
        """
        Extract all metrics for a single quarter
        
        Args:
            df: DataFrame with ticker data
            ticker: Stock ticker
            quarter_pq: Quarter in parquet format (e.g., "2025Q2")
            
        Returns:
            Dictionary with all metrics organized by category
        """
        # Filter for this quarter
        quarter_data = df[df['DATE'] == quarter_pq].set_index('KEYCODE')
        
        # Initialize result structure
        result = {
            "income_statement": {},
            "balance_sheet": {},
            "cash_flow": {},
            "other_metrics": {}
        }
        
        # Extract each metric
        for keycode, field_name in self.KEYCODE_MAPPING.items():
            if keycode in quarter_data.index:
                value = quarter_data.loc[keycode, 'VALUE']
                
                # Convert to billions and round
                if pd.notna(value):
                    if field_name in self.PERCENTAGE_FIELDS:
                        # Percentages: multiply by 100 and round to 1 decimal
                        value = round(value * 100, 1)
                    else:
                        # Monetary values: convert to billions and round to 2 decimals
                        value = round(value / 1e9, 2)
                else:
                    value = None
                
                # Assign to correct category
                if field_name in self.INCOME_STATEMENT_FIELDS:
                    result["income_statement"][field_name] = value
                elif field_name in self.BALANCE_SHEET_FIELDS:
                    result["balance_sheet"][field_name] = value
                elif field_name in self.CASH_FLOW_FIELDS:
                    result["cash_flow"][field_name] = value
                elif field_name in self.OTHER_FIELDS:
                    result["other_metrics"][field_name] = value
        
        return result
    
    def _calculate_percentage_change(self, current: float, previous: float) -> Optional[float]:
        """Calculate percentage change, handling edge cases"""
        if current is None or previous is None or previous == 0:
            return None
        return round(((current - previous) / abs(previous)) * 100, 1)
    
    def _calculate_changes(self, current: Dict, qoq: Dict, yoy: Dict) -> Dict[str, Any]:
        """
        Calculate QoQ and YoY percentage changes for key metrics
        
        Args:
            current: Current quarter data
            qoq: QoQ comparison quarter data
            yoy: YoY comparison quarter data
            
        Returns:
            Dictionary with calculated changes
        """
        result = {
            "qoq": {},
            "yoy": {}
        }
        
        # Key metrics to calculate changes for
        key_metrics = [
            ('income_statement', 'net_revenue', 'net_revenue_pct'),
            ('income_statement', 'gross_profit', 'gross_profit_pct'),
            ('income_statement', 'ebit', 'ebit_pct'),
            ('income_statement', 'ebitda', 'ebitda_pct'),
            ('income_statement', 'npat', 'npat_pct'),
            ('income_statement', 'npatmi', 'npatmi_pct'),
            ('balance_sheet', 'total_assets', 'total_assets_pct'),
            ('balance_sheet', 'cash', 'cash_pct'),
            ('balance_sheet', 'inventory', 'inventory_pct'),
            ('balance_sheet', 'st_debt', 'st_debt_pct'),
            ('balance_sheet', 'lt_debt', 'lt_debt_pct'),
            ('balance_sheet', 'total_equity', 'total_equity_pct'),
        ]
        
        for category, metric, change_name in key_metrics:
            current_val = current.get(category, {}).get(metric)
            qoq_val = qoq.get(category, {}).get(metric)
            yoy_val = yoy.get(category, {}).get(metric)
            
            result["qoq"][change_name] = self._calculate_percentage_change(current_val, qoq_val)
            result["yoy"][change_name] = self._calculate_percentage_change(current_val, yoy_val)
        
        return result
    
    def extract_quarterly_data(self, ticker: str, quarter: str) -> Dict[str, Any]:
        """
        Extract complete financial data for a quarter with comparisons
        
        Args:
            ticker: Stock ticker (e.g., "VHM")
            quarter: Quarter string (e.g., "2Q25")
            
        Returns:
            Structured financial data matching the JSON schema
        """
        # Validate first
        validation = self.validate_data_availability(ticker, quarter)
        if not validation["valid"]:
            return {
                "error": validation["message"],
                "validation": validation
            }
        
        # Load data
        df = self._load_data()
        ticker_data = df[df['TICKER'] == ticker.upper()]
        
        # Calculate comparison quarters
        qoq_quarter, yoy_quarter = self._calculate_comparison_quarters(quarter)
        
        # Convert to parquet format
        current_pq = self._convert_quarter_format(quarter)
        qoq_pq = self._convert_quarter_format(qoq_quarter)
        yoy_pq = self._convert_quarter_format(yoy_quarter)
        
        # Extract data for all three quarters
        current_data = self._extract_quarter_data(ticker_data, ticker, current_pq)
        qoq_data = self._extract_quarter_data(ticker_data, ticker, qoq_pq)
        yoy_data = self._extract_quarter_data(ticker_data, ticker, yoy_pq)
        
        # Calculate percentage changes
        changes = self._calculate_changes(current_data, qoq_data, yoy_data)
        
        # Structure result
        result = {
            "data_source": "internal_database",
            "extraction_date": datetime.now().isoformat(),
            "current_quarter": {
                "quarter": quarter,
                **current_data
            },
            "qoq_comparison": {
                "quarter": qoq_quarter,
                **qoq_data
            },
            "yoy_comparison": {
                "quarter": yoy_quarter,
                **yoy_data
            },
            "calculated_changes": changes
        }
        
        return result


