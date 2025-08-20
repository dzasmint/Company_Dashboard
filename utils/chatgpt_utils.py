import streamlit as st
import openai
from openai import OpenAI
import json
from typing import Dict, List, Any, Optional
import pandas as pd
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def analyze_financial_statements(
    pnl_data: pd.DataFrame,
    balance_sheet_data: pd.DataFrame, 
    cash_flow_data: pd.DataFrame,
    company_name: str,
    api_key: Optional[str] = None,
    use_gpt4: bool = False
) -> Dict[str, Any]:
    """
    Analyze consolidated financial statements using ChatGPT.
    
    Args:
        pnl_data: P&L statement DataFrame
        balance_sheet_data: Balance sheet DataFrame
        cash_flow_data: Cash flow statement DataFrame
        company_name: Name of the company being analyzed
        api_key: OpenAI API key (optional, will use env var if not provided)
    
    Returns:
        Dictionary containing analysis results
    """
    
    # Get API key
    if not api_key:
        api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        return {
            'error': 'OpenAI API key not found. Please set OPENAI_API_KEY in your environment variables or .env file.'
        }
    
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)
        
        # Prepare data for analysis
        pnl_json = pnl_data.to_json(orient='records')
        bs_json = balance_sheet_data.to_json(orient='records')
        cf_json = cash_flow_data.to_json(orient='records')
        
        # Create comprehensive prompt
        system_prompt = """You are an expert financial analyst specializing in Vietnamese companies and real estate sector analysis. 
        You provide comprehensive, professional investment analysis based on financial statements. Your analysis should be 
        thorough yet concise, highlighting key metrics, trends, and investment considerations."""
        
        user_prompt = f"""Please analyze the following consolidated financial statements for {company_name} and provide a comprehensive investment analysis.

**P&L Statement (Billion VND):**
{pnl_json}

**Balance Sheet (Billion VND):**
{bs_json}

**Cash Flow Statement (Billion VND):**
{cf_json}

Please provide your analysis in the following sections:

## 1. PROFITABILITY & REVENUE GROWTH ANALYSIS
- Revenue growth trends and composition (real estate vs other segments)
- Gross margin evolution and drivers
- EBITDA margin trends
- Net profit margin analysis
- ROE and ROA calculations where applicable
- Compare historical performance with forecast

## 2. FINANCIAL HEALTH ASSESSMENT
- Debt levels and leverage ratios (Debt/Equity, Net Debt/EBITDA)
- Interest coverage ratio
- Working capital analysis
- Asset quality and inventory turnover
- Customer prepayment trends (important for real estate)

## 3. CASH FLOW QUALITY
- Operating cash flow trends vs net income
- Free cash flow generation
- Cash conversion cycle
- Capital efficiency (CAPEX as % of revenue)
- Cash collection efficiency from presales

## 4. KEY STRENGTHS
- List 3-5 major competitive advantages or positive factors
- Focus on sustainable competitive advantages
- Highlight any improving trends

## 5. RED FLAGS & RISKS
- List 3-5 major concerns or risk factors
- Include both company-specific and industry risks
- Note any deteriorating metrics

## 6. INVESTMENT RECOMMENDATION
- Overall assessment (BUY/HOLD/SELL)
- Target valuation metrics (P/E, P/B ratios if possible)
- Key catalysts for the investment thesis
- Time horizon for the recommendation

## 7. KEY METRICS SUMMARY
Provide a table with key financial ratios for the latest year and forecast:
- Revenue Growth %
- Gross Margin %
- EBITDA Margin %
- Net Margin %
- Debt/Equity Ratio
- Interest Coverage
- ROE %

Please be specific with numbers and provide concrete insights rather than generic observations. Focus on what makes this company unique in the Vietnamese market context."""

        # Choose model based on parameter
        if use_gpt4:
            # Use GPT-4 directly
            response = client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2500
            )
            model_used = "gpt-4-turbo-preview"
        else:
            # Try GPT-5 first
            # Note: GPT-5 only supports default temperature (1)
            response = client.chat.completions.create(
                model="gpt-5",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=2500
            )
            model_used = "gpt-5"
        
        # Extract analysis with error checking
        if response and response.choices and len(response.choices) > 0:
            analysis_text = response.choices[0].message.content
            
            # Check if content is empty
            if not analysis_text or analysis_text.strip() == "":
                # Fallback to GPT-4 if GPT-5 returns empty response
                print("GPT-5 returned empty response, falling back to GPT-4...")
                response = client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2500
                )
                analysis_text = response.choices[0].message.content
                model_used = "gpt-4-turbo-preview (fallback from GPT-5)"
            else:
                model_used = "gpt-5"
        else:
            return {
                'error': 'No response received from OpenAI API'
            }
        
        return {
            'success': True,
            'analysis': analysis_text,
            'model': model_used,
            'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
    except Exception as e:
        return {
            'error': f'Error during analysis: {str(e)}'
        }

def format_dataframe_for_chatgpt(df: pd.DataFrame, max_rows: int = 50) -> str:
    """
    Format a DataFrame for ChatGPT analysis, limiting size if needed.
    
    Args:
        df: DataFrame to format
        max_rows: Maximum number of rows to include
    
    Returns:
        Formatted string representation of the DataFrame
    """
    # Limit rows if needed
    if len(df) > max_rows:
        df_subset = df.head(max_rows)
        footer = f"\n... ({len(df) - max_rows} more rows)"
    else:
        df_subset = df
        footer = ""
    
    # Convert to string with nice formatting
    result = df_subset.to_string(index=False)
    result += footer
    
    return result

def test_openai_connection(api_key: Optional[str] = None) -> bool:
    """
    Test OpenAI API connection.
    
    Args:
        api_key: OpenAI API key (optional, will use env var if not provided)
    
    Returns:
        True if connection successful, False otherwise
    """
    if not api_key:
        api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        return False
    
    try:
        client = OpenAI(api_key=api_key)
        # Simple test call with GPT-5
        response = client.chat.completions.create(
            model="gpt-5",
            messages=[{"role": "user", "content": "Say 'test successful'"}],
            max_completion_tokens=10
        )
        return True
    except:
        return False