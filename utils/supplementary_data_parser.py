"""
Supplementary Data Parser for Quarterly Earnings Analysis

Parses Excel/CSV files containing quarterly time series data
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime
import streamlit as st


class SupplementaryDataParser:
    """Parses supplementary data files (Excel/CSV) into structured format"""
    
    def __init__(self):
        """Initialize parser"""
        pass
    
    def _normalize_quarter_format(self, quarter_str: str) -> Optional[str]:
        """
        Normalize quarter format to standard "1Q25" format
        
        Args:
            quarter_str: Quarter string in various formats (1Q22, Q1 2022, 2022Q1, 1Q2022, etc.)
            
        Returns:
            Normalized quarter string or None if invalid
        """
        if pd.isna(quarter_str):
            return None
            
        quarter_str = str(quarter_str).strip().upper()
        
        # Try various formats
        import re
        
        # Format: 1Q22, 2Q23
        match = re.match(r'(\d)Q(\d{2})', quarter_str)
        if match:
            return f"{match.group(1)}Q{match.group(2)}"
        
        # Format: Q1 2022, Q2 2023
        match = re.match(r'Q(\d)\s*(\d{4})', quarter_str)
        if match:
            return f"{match.group(1)}Q{match.group(2)[2:]}"
        
        # Format: 2022Q1
        match = re.match(r'(\d{4})Q(\d)', quarter_str)
        if match:
            return f"{match.group(2)}Q{match.group(1)[2:]}"
        
        # Format: 1Q2022
        match = re.match(r'(\d)Q(\d{4})', quarter_str)
        if match:
            return f"{match.group(1)}Q{match.group(2)[2:]}"
        
        return None
    
    def _calculate_changes(self, current: float, previous: float) -> Optional[float]:
        """Calculate percentage change"""
        if pd.isna(current) or pd.isna(previous) or previous == 0:
            return None
        return round(((current - previous) / abs(previous)) * 100, 1)
    
    def parse_file(self, file_path: str, target_quarter: str) -> Dict[str, Any]:
        """
        Parse supplementary data file
        
        Args:
            file_path: Path to CSV or Excel file
            target_quarter: Target quarter for analysis (e.g., "2Q25")
            
        Returns:
            Structured dictionary matching unified schema
        """
        try:
            # Read file based on extension
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:  # Excel
                df = pd.read_excel(file_path)
            
            # Identify date/quarter column (first column or column named Date/Quarter)
            date_col = df.columns[0]
            for col in df.columns:
                if col.lower() in ['date', 'quarter', 'period', 'q']:
                    date_col = col
                    break
            
            # Check if row 2 contains units (second row after header)
            units_dict = {}
            if len(df) > 0:
                first_row = df.iloc[0]
                # Check if first data row looks like units (contains 'VND', 'bn', 'tn', 'mn', '%', 'units', etc.)
                unit_indicators = ['vnd', 'bn', 'tn', 'mn', '%', 'unit', 'thousand', 'million', 'billion', 'trillion']
                first_row_is_units = any(
                    any(indicator in str(val).lower() for indicator in unit_indicators)
                    for val in first_row.values if pd.notna(val)
                )
                
                if first_row_is_units:
                    # Extract units from first row
                    for col in df.columns:
                        if col != date_col:
                            unit_val = first_row[col]
                            units_dict[col] = str(unit_val).strip() if pd.notna(unit_val) else None
                    # Remove the units row
                    df = df.iloc[1:].reset_index(drop=True)
            
            # Normalize quarter format
            df['normalized_quarter'] = df[date_col].apply(self._normalize_quarter_format)
            df = df[df['normalized_quarter'].notna()]  # Remove invalid dates
            
            # Get metric columns (all except date column)
            metric_cols = [col for col in df.columns if col not in [date_col, 'normalized_quarter']]
            
            # Convert metrics to numeric
            for col in metric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Sort by quarter
            df = df.sort_values('normalized_quarter')
            
            # Build time series dictionary
            time_series = {}
            for col in metric_cols:
                time_series[col] = []
                for _, row in df.iterrows():
                    time_series[col].append({
                        "quarter": row['normalized_quarter'],
                        "value": float(row[col]) if not pd.isna(row[col]) else None
                    })
            
            # Find current quarter data
            current_quarter_row = df[df['normalized_quarter'] == target_quarter]
            current_quarter_values = {}
            qoq_changes = {}
            yoy_changes = {}
            
            if not current_quarter_row.empty:
                current_idx = current_quarter_row.index[0]
                
                # Get current values
                for col in metric_cols:
                    current_val = df.loc[current_idx, col]
                    current_quarter_values[col] = float(current_val) if not pd.isna(current_val) else None
                    
                    # Calculate QoQ change
                    if current_idx > 0:
                        prev_val = df.iloc[current_idx - 1][col]
                        qoq_changes[col] = self._calculate_changes(current_val, prev_val)
                    
                    # Calculate YoY change (4 quarters back)
                    if current_idx >= 4:
                        yoy_val = df.iloc[current_idx - 4][col]
                        yoy_changes[col] = self._calculate_changes(current_val, yoy_val)
            
            # Generate trend summary
            trend_summary = {}
            for col in metric_cols:
                values = df[col].dropna()
                if len(values) >= 2:
                    # Calculate trend
                    recent_4 = values.tail(4)
                    if len(recent_4) >= 2:
                        trend = "increasing" if recent_4.iloc[-1] > recent_4.iloc[0] else "decreasing"
                        avg = round(recent_4.mean(), 2)
                        trend_summary[col] = {
                            "trend": trend,
                            "avg_last_4q": avg,
                            "latest_value": float(values.iloc[-1]),
                            "min_value": float(values.min()),
                            "max_value": float(values.max())
                        }
            
            # Structure result
            result = {
                "data_source": "user_uploaded",
                "file_name": file_path.split('/')[-1],
                "upload_date": datetime.now().isoformat(),
                "time_series": time_series,
                "metrics_included": metric_cols,
                "units": units_dict if units_dict else None,  # Units for each metric
                "quarters_covered": df['normalized_quarter'].tolist(),
                "current_quarter_values": current_quarter_values,
                "qoq_changes": qoq_changes,
                "yoy_changes": yoy_changes,
                "trend_summary": trend_summary
            }
            
            return result
            
        except Exception as e:
            st.error(f"Error parsing supplementary data: {str(e)}")
            return {"error": str(e)}

