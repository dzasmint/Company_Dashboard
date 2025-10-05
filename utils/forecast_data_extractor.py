"""
Forecast Data Extractor for Quarterly Earnings Analysis

Extracts forecast and valuation data from MongoDB CompanyForecast collection
for integration with quarterly earnings reports
"""

import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime
import streamlit as st
from .mongodb_utils import load_company_forecast


class ForecastDataExtractor:
    """Extracts forecast and valuation data from MongoDB for quarterly analysis"""
    
    def __init__(self):
        """Initialize extractor"""
        pass
    
    def _calculate_ytd_from_quarters(self, quarter: str, quarters_data: list) -> Dict[str, float]:
        """
        Calculate YTD values from quarterly financial data
        
        Args:
            quarter: Target quarter (e.g., "2Q25")
            quarters_data: List of quarterly data documents from financial_data
            
        Returns:
            Dict with YTD revenue and NPATMI
        """
        q_num = int(quarter[0])
        year = 2000 + int(quarter[2:])
        
        # Sum all quarters in current year up to target quarter
        ytd_revenue = 0
        ytd_npatmi = 0
        
        for q in range(1, q_num + 1):
            quarter_key = f"{q}Q{str(year)[2:]}"
            # Find matching quarter in financial data
            for q_data in quarters_data:
                if q_data.get('period', {}).get('quarter') == quarter_key.upper():
                    fin_data = q_data.get('financial_data', {})
                    current_q = fin_data.get('current_quarter', {})
                    income_stmt = current_q.get('income_statement', {})
                    
                    ytd_revenue += income_stmt.get('net_revenue', 0) or 0
                    ytd_npatmi += income_stmt.get('npatmi', 0) or 0
                    break
        
        return {
            "revenue_ytd": ytd_revenue,
            "npatmi_ytd": ytd_npatmi
        }
    
    def extract_forecast_data(self, ticker: str, quarter: str, 
                             company_name: str = None,
                             quarterly_data: list = None) -> Dict[str, Any]:
        """
        Extract forecast and valuation data for quarterly earnings analysis
        
        Args:
            ticker: Stock ticker (e.g., "VHM")
            quarter: Quarter string (e.g., "2Q25")
            company_name: Company name (optional)
            quarterly_data: List of quarterly financial data documents for YTD calculation
            
        Returns:
            Structured forecast data matching unified schema
        """
        try:
            # Load forecast from MongoDB
            forecast_doc = load_company_forecast(ticker)
            
            if not forecast_doc or not forecast_doc.get('forecast_data'):
                return {
                    "error": f"No forecast data found for {ticker} in MongoDB CompanyForecast collection",
                    "available": False
                }
            
            # Parse quarter to get year
            q_num = int(quarter[0])
            year = 2000 + int(quarter[2:])
            year_str = str(year)
            
            # Get forecast for current year
            forecast_data = forecast_doc.get('forecast_data', {})
            current_year_forecast = forecast_data.get(year_str)
            
            if not current_year_forecast:
                available_years = list(forecast_data.keys())
                return {
                    "error": f"No forecast for year {year}. Available years: {', '.join(available_years)}",
                    "available": False
                }
            
            # Extract FY forecast metrics
            # Note: Data is stored in raw VND values, need to convert to billions
            pnl = current_year_forecast.get('pnl', {})
            fy_revenue = pnl.get('net_revenue', 0) / 1e9 if pnl.get('net_revenue') else 0
            fy_npatmi = pnl.get('npatmi', 0) / 1e9 if pnl.get('npatmi') else 0
            fy_ebitda = pnl.get('ebitda', 0) / 1e9 if pnl.get('ebitda') else 0
            fy_gross_profit = pnl.get('gross_profit', 0) / 1e9 if pnl.get('gross_profit') else 0
            
            # Calculate YTD actuals from quarterly data
            ytd_data = {"revenue_ytd": 0, "npatmi_ytd": 0}
            if quarterly_data:
                ytd_data = self._calculate_ytd_from_quarters(quarter, quarterly_data)
            
            ytd_revenue = ytd_data["revenue_ytd"]
            ytd_npatmi = ytd_data["npatmi_ytd"]
            
            # Calculate achievement percentages
            revenue_achievement = (ytd_revenue / fy_revenue * 100) if fy_revenue > 0 else None
            npatmi_achievement = (ytd_npatmi / fy_npatmi * 100) if fy_npatmi > 0 else None
            
            # Expected progress (linear assumption: Q1=25%, Q2=50%, Q3=75%, Q4=100%)
            expected_progress = (q_num / 4) * 100
            
            # Assessment
            if revenue_achievement:
                if revenue_achievement >= expected_progress + 5:
                    revenue_status = "ahead"
                elif revenue_achievement <= expected_progress - 5:
                    revenue_status = "behind"
                else:
                    revenue_status = "on_track"
            else:
                revenue_status = "unknown"
            
            if npatmi_achievement:
                if npatmi_achievement >= expected_progress + 5:
                    npatmi_status = "ahead"
                elif npatmi_achievement <= expected_progress - 5:
                    npatmi_status = "behind"
                else:
                    npatmi_status = "on_track"
            else:
                npatmi_status = "unknown"
            
            # Extract valuation data
            valuation_data_raw = forecast_doc.get('valuation_data', {})
            current_price = valuation_data_raw.get('current_price', 0)
            rnav_per_share = valuation_data_raw.get('rnav_per_share', 0)
            multiples = valuation_data_raw.get('multiples', {})
            
            # Calculate RNAV metrics
            rnav_upside = ((rnav_per_share / current_price - 1) * 100) if current_price > 0 else None
            rnav_discount = ((current_price / rnav_per_share - 1) * 100) if rnav_per_share > 0 else None
            
            # Structure result
            result = {
                "data_source": "mongodb_forecast",
                "extraction_date": datetime.now().isoformat(),
                "fy_forecast": {
                    "year": year,
                    "revenue_fy": round(fy_revenue, 2) if fy_revenue else None,
                    "npatmi_fy": round(fy_npatmi, 2) if fy_npatmi else None,
                    "ebitda_fy": round(fy_ebitda, 2) if fy_ebitda else None,
                    "gross_profit_fy": round(fy_gross_profit, 2) if fy_gross_profit else None
                },
                "ytd_progress": {
                    "quarter": quarter.upper(),
                    "quarter_num": q_num,
                    "expected_progress_pct": expected_progress,
                    "revenue_ytd_actual": round(ytd_revenue, 2) if ytd_revenue else None,
                    "revenue_fy_forecast": round(fy_revenue, 2) if fy_revenue else None,
                    "revenue_achievement_pct": round(revenue_achievement, 1) if revenue_achievement else None,
                    "revenue_status": revenue_status,
                    "npatmi_ytd_actual": round(ytd_npatmi, 2) if ytd_npatmi else None,
                    "npatmi_fy_forecast": round(fy_npatmi, 2) if fy_npatmi else None,
                    "npatmi_achievement_pct": round(npatmi_achievement, 1) if npatmi_achievement else None,
                    "npatmi_status": npatmi_status,
                    "remaining_quarters": 4 - q_num,
                    "remaining_revenue_implied": round(fy_revenue - ytd_revenue, 2) if (fy_revenue and ytd_revenue) else None,
                    "remaining_npatmi_implied": round(fy_npatmi - ytd_npatmi, 2) if (fy_npatmi and ytd_npatmi) else None
                },
                "valuation_metrics": {
                    "current_price": round(current_price, 0) if current_price else None,
                    "rnav_per_share": round(rnav_per_share, 0) if rnav_per_share else None,
                    "rnav_upside_pct": round(rnav_upside, 1) if rnav_upside else None,
                    "rnav_discount_pct": round(rnav_discount, 1) if rnav_discount else None,
                    "trailing_pe": multiples.get('trailing_PE'),
                    "current_year_pe": multiples.get(f'{year}F_PE'),
                    "next_year_pe": multiples.get(f'{year+1}F_PE'),
                    "mean_pe": multiples.get('mean_PE'),
                    "trailing_pb": multiples.get('trailing_PB'),
                    "current_year_pb": multiples.get(f'{year}F_PB'),
                    "next_year_pb": multiples.get(f'{year+1}F_PB'),
                    "mean_pb": multiples.get('mean_PB')
                }
            }
            
            return result
            
        except Exception as e:
            st.error(f"Error extracting forecast data: {str(e)}")
            return {"error": str(e), "available": False}
    
    def structure_for_unified_schema(self, ticker: str, quarter: str, 
                                     company_name: str,
                                     quarterly_data: list = None) -> Dict[str, Any]:
        """
        Extract forecast data and structure in unified quarterly_analysis.json format
        
        Args:
            ticker: Stock ticker
            quarter: Quarter string
            company_name: Company name
            quarterly_data: Quarterly financial data for YTD calculation
            
        Returns:
            Complete document in unified schema format
        """
        # Extract forecast data
        forecast_data = self.extract_forecast_data(ticker, quarter, company_name, quarterly_data)
        
        if "error" in forecast_data:
            return forecast_data
        
        # Parse quarter
        q_num = int(quarter[0])
        year = 2000 + int(quarter[2:])
        
        # Structure in unified schema
        result = {
            "company": company_name,
            "ticker": ticker.upper(),
            "period": {
                "quarter": quarter.upper(),
                "comparison_quarters": [],
                "fiscal_year_half": "1H" if q_num <= 2 else "2H",
                "as_of_date": None
            },
            "source": {
                "file_name": f"forecast_data_{ticker}_{quarter}.json",
                "file_type": "forecast_data",
                "publisher": "Internal Forecast Model",
                "publish_date": datetime.now().isoformat(),
                "pages_covered": None,
                "version_note": "Automated extraction from MongoDB CompanyForecast"
            },
            "currency": "VND",
            "units": "bn",
            "accounting_basis": None,
            
            # Forecast data section
            "forecast_data": forecast_data,
            
            # Empty sections
            "headline": {},
            "recognition_drivers": {},
            "presales": {},
            "balance_sheet": {},
            "one_offs_and_events": [],
            "outlook_and_guidance": {},
            "management_commentary": {},
            "sell_side_commentary": {},
            "buy_side_commentary": {},
            "financial_data": {},
            "supplementary_data": {},
            "methodology": {
                "parsing_notes": "Automated extraction from MongoDB CompanyForecast collection",
                "assumptions": "YTD calculated by summing quarterly actuals. Expected progress assumes linear quarterly distribution (Q2 = 50% of FY).",
                "omissions": None,
                "confidence_pct": 100
            }
        }
        
        return result

