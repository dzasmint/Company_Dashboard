#%%
import pandas as pd
import streamlit as st
import numpy as np
from dotenv import load_dotenv
import os
import re
import datetime


# Optional: If openai is not installed, run: pip install openai
import openai

# Google Search API
try:
    from googleapiclient.discovery import build
    GOOGLE_SEARCH_AVAILABLE = True
except ImportError:
    GOOGLE_SEARCH_AVAILABLE = False
    st.warning("Google API client not installed. Install with: pip install google-api-python-client")

# Import utility functions


# print("OPENAI_API_KEY:", os.getenv("OPENAI_API_KEY"))

# Load .env file (for local development)
load_dotenv()

# Read API keys from environment
api_key = os.getenv("OPENAI_API_KEY")
google_api_key = os.getenv("GOOGLE_API_KEY")
google_search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

# Debug: Print API key status (without exposing keys)
# print(f"Google API Key present: {bool(google_api_key)}")
# print(f"Google Search Engine ID present: {bool(google_search_engine_id)}")
# print(f"Google API Client available: {GOOGLE_SEARCH_AVAILABLE}")

if not api_key:
    st.warning(
        "⚠️ OPENAI_API_KEY environment variable is not set.\n\n"
        "**For local development:**\n"
        "1. Create a file named `.env` in your project root directory\n"
        "2. Add this line: `OPENAI_API_KEY=your_openai_api_key_here`\n\n"
        "**For Streamlit Cloud deployment:**\n"
        "1. Go to your app settings in Streamlit Cloud\n"
        "2. Add OPENAI_API_KEY as a secret in the 'Secrets' section\n\n"
        "⚡ You can still use the calculator without ChatGPT integration!"
    )
    api_key = None  # Allow app to continue without API key

# Check Google Search API setup
google_search_enabled = bool(google_api_key and google_search_engine_id and GOOGLE_SEARCH_AVAILABLE)
if not google_search_enabled and api_key:
    st.info(
        "🔍 **Google Search Integration**: Set up Google Custom Search for enhanced web search.\n\n"
        "**Setup Steps:**\n"
        "1. Get Google Custom Search API key from Google Cloud Console\n"
        "2. Create a Custom Search Engine and get the Search Engine ID\n"
        "3. Add to your .env file:\n"
        "   - `GOOGLE_API_KEY=your_google_api_key`\n"
        "   - `GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id`"
    )

#%%
def selling_progress_schedule(
    total_revenue: float,
    current_year: int,
    start_year: int,
    num_years: int,
    complete_year: int
) -> list:
    """
    Distribute total revenue evenly over a given number of years (num_years),
    starting from start_year. Output is aligned from current_year to complete_year.
    Now allows start_year to be before current_year for historical tracking.

    Args:
        total_revenue (float): Total revenue
        current_year (int): Start year of the output array
        start_year (int): Year selling begins (can be < current_year)
        num_years (int): Number of years selling takes
        complete_year (int): Project completion year

    Returns:
        List[float]: Annual revenue array from current_year to complete_year
    """
    if complete_year < start_year:
        raise ValueError("complete_year must be >= start_year")
    if (start_year + num_years - 1) > complete_year:
        raise ValueError("Selling period exceeds project completion year")

    annual_revenue = total_revenue / num_years

    # Build full year list from current_year to complete_year
    full_years = list(range(current_year, complete_year + 1))

    # Create array with revenue in the selling years only
    revenue_by_year = [
        annual_revenue if start_year <= year < start_year + num_years else 0.0
        for year in full_years
    ]

    return revenue_by_year


# 🔄 Example usage:1
# if __name__ == "__main__":
#     nsa = 120_000          # Net sellable area (m²)
#     price = 50_000_000     # VND/m²
#     current_year = 2025
#     start_year = 2026
#     num_years = 3
#     complete_year = 2030

#     result = selling_progress_schedule(nsa * price, current_year, start_year, num_years, complete_year)

#     for i, value in enumerate(result):
#         print(f"{current_year + i}: {value:,.0f} VND")



def land_use_right_payment_schedule_single_year(
    total_payment: float,
    current_year: int,
    payment_year: int,
    complete_year: int
) -> list:
    """
    Generate land use right payment schedule from current_year to complete_year,
    with the entire payment made in payment_year.

    Args:
        land_area (float): Land area in m².
        price_per_m2 (float): Price per m² in VND.
        current_year (int): Base year of the model.
        payment_year (int): Year payment occurs (must be within range).
        complete_year (int): Final year of the project (inclusive).

    Returns:
        List[float]: Annual cash flow array from current_year to complete_year.
    """
    if payment_year > complete_year:
        raise ValueError("payment_year must be earlier than complete_year")

    
    num_years = complete_year - current_year + 1

    payment_array = [0.0] * num_years

    if payment_year < current_year:
        # Payment year is before the current year, so no payment in the schedule
        pass
    else:
        payment_index = payment_year - current_year
        payment_array[payment_index] = total_payment

    return payment_array

# %%
# 🔄 Example usage:
# if __name__ == "__main__":
#     land_area = 560_000              # in m²
#     price_per_m2 = 5_000_000         # 5 million VND/m²
#     current_year = 2025
#     payment_year = 2026
#     complete_year = 2029

#     result = land_use_right_payment_schedule_single_year(
#         land_area * price_per_m2, current_year, payment_year, complete_year
#     )

#     for i, value in enumerate(result):
#         print(f"{current_year + i}: {value:,.0f} VND")


def construction_payment_schedule(
    total_cost: float,
    current_year: int,
    start_year: int,
    num_years: int,
    complete_year: int
) -> list:
    """
    Distribute total construction cost evenly over num_years starting from start_year.
    Output is aligned from current_year to complete_year.
    Now allows start_year to be before current_year for historical tracking.

    Args:
        total_cost (float): Total construction cost
        current_year (int): First year of the output array
        start_year (int): Year construction begins (can be < current_year)
        num_years (int): Number of years construction takes
        complete_year (int): Final year of the project

    Returns:
        List[float]: Construction cost per year aligned from current_year to complete_year
    """
    if complete_year < start_year:
        raise ValueError("complete_year must be >= start_year")
    if (start_year + num_years - 1) > complete_year:
        raise ValueError("Construction period exceeds project completion year")

    annual_cost = total_cost / num_years

    # Create timeline from current_year to complete_year
    full_years = list(range(current_year, complete_year + 1))

    # Allocate cost to construction years
    cost_by_year = [
        annual_cost if start_year <= year < start_year + num_years else 0.0
        for year in full_years
    ]

    return cost_by_year


# 🔄 Example usage:
# if __name__ == "__main__":
#     gfa = 200_000             # m²
#     cost_per_sqm = 20_000_000 # VND/m²
#     current_year = 2025
#     start_year = 2026
#     num_years = 4
#     complete_year = 2030
#     result = construction_payment_schedule(gfa * cost_per_sqm, current_year, start_year, num_years, complete_year)

#     for i, value in enumerate(result):
#         print(f"{current_year + i}: {value:,.0f} VND")



def sga_payment_schedule(
    total_sga: float,
    current_year: int,
    start_year: int,
    num_years: int,
    complete_year: int
) -> list:
    """
    Distribute total SG&A evenly over a given number of years (num_years),
    starting from start_year. Output is aligned from current_year to complete_year.
    Now allows start_year to be before current_year for historical tracking.

    Args:
        total_sga (float): Total SG&A cost
        current_year (int): Start year of the output array
        start_year (int): Year SG&A begins (can be < current_year)
        num_years (int): Number of years SG&A takes
        complete_year (int): Project completion year

    Returns:
        List[float]: Annual SG&A array from current_year to complete_year
    """
    if complete_year < start_year:
        raise ValueError("complete_year must be >= start_year")
    if (start_year + num_years - 1) > complete_year:
        raise ValueError("SG&A period exceeds project completion year")

    annual_sga = total_sga / num_years

    # Build full year list from current_year to complete_year
    full_years = list(range(current_year, complete_year + 1))

    # Create array with SG&A in the active years only
    sga_by_year = [
        annual_sga if start_year <= year < start_year + num_years else 0.0
        for year in full_years
    ]

    return sga_by_year

# %%
def generate_pnl_schedule(
    total_revenue: float,
    total_land_payment: float,
    total_construction_payment: float,
    total_sga: float,
    current_year: int,
    start_booking_year: int,
    end_booking_year: int
) -> pd.DataFrame:
    """
    Generate a simplified P&L schedule from start_booking_year to end_booking_year.
    Shows both historical and future data with proper labeling.

    Args:
        total_revenue (float): Total revenue (VND)
        total_land_payment (float): Total land use cost (VND)
        total_construction_payment (float): Total construction payment (VND)
        total_sga (float): Total SG&A (VND)
        current_year (int): Current year (for historical vs future classification)
        start_booking_year (int): Year revenue booking starts
        end_booking_year (int): Year revenue booking ends

    Returns:
        pd.DataFrame: Year-by-year P&L table from start_booking_year to end_booking_year with totals row
    """
    if end_booking_year < start_booking_year:
        raise ValueError("end_booking_year must be >= start_booking_year")

    # Calculate annual amounts based on total booking period
    total_booking_years = end_booking_year - start_booking_year + 1
    revenue_annual = total_revenue / total_booking_years if total_booking_years > 0 else 0
    land_payment_annual = total_land_payment / total_booking_years if total_booking_years > 0 else 0
    sga_annual = total_sga / total_booking_years if total_booking_years > 0 else 0
    construction_annual = total_construction_payment / total_booking_years if total_booking_years > 0 else 0

    pnl_data = []
    for year in range(start_booking_year, end_booking_year + 1):
        # Determine if this is historical or future
        is_historical = year < current_year
        year_type = "Historical" if is_historical else "Future"
        
        # All years in the booking period have values
        revenue = revenue_annual
        land_cost = land_payment_annual
        sga = sga_annual
        construction = construction_annual
        pbt = revenue + land_cost + sga + construction
        tax = -pbt * 0.2 if pbt > 0 else 0.0
        pat = pbt + tax

        pnl_data.append({
            "Year": year,
            "Type": year_type,
            "Revenue": revenue,
            "Land Payment": land_cost,
            "Construction": construction,
            "SG&A": sga,
            "Profit Before Tax": pbt,
            "Tax Expense (20%)": tax,
            "Profit After Tax": pat
        })

    df = pd.DataFrame(pnl_data)
    
    # Add total rows for historical, future, and overall
    historical_df = df[df["Type"] == "Historical"]
    future_df = df[df["Type"] == "Future"]
    
    # Add subtotals
    if not historical_df.empty:
        historical_total = {
            "Year": "Total (Historical)",
            "Type": "Summary",
            "Revenue": historical_df["Revenue"].sum(),
            "Land Payment": historical_df["Land Payment"].sum(),
            "Construction": historical_df["Construction"].sum(),
            "SG&A": historical_df["SG&A"].sum(),
            "Profit Before Tax": historical_df["Profit Before Tax"].sum(),
            "Tax Expense (20%)": historical_df["Tax Expense (20%)"].sum(),
            "Profit After Tax": historical_df["Profit After Tax"].sum()
        }
        df = pd.concat([df, pd.DataFrame([historical_total])], ignore_index=True)
    
    if not future_df.empty:
        future_total = {
            "Year": "Total (Future)",
            "Type": "Summary",
            "Revenue": future_df["Revenue"].sum(),
            "Land Payment": future_df["Land Payment"].sum(),
            "Construction": future_df["Construction"].sum(),
            "SG&A": future_df["SG&A"].sum(),
            "Profit Before Tax": future_df["Profit Before Tax"].sum(),
            "Tax Expense (20%)": future_df["Tax Expense (20%)"].sum(),
            "Profit After Tax": future_df["Profit After Tax"].sum()
        }
        df = pd.concat([df, pd.DataFrame([future_total])], ignore_index=True)
    
    # Add overall total
    overall_total = {
        "Year": "Total (Overall)",
        "Type": "Summary",
        "Revenue": df[df["Type"] != "Summary"]["Revenue"].sum(),
        "Land Payment": df[df["Type"] != "Summary"]["Land Payment"].sum(),
        "Construction": df[df["Type"] != "Summary"]["Construction"].sum(),
        "SG&A": df[df["Type"] != "Summary"]["SG&A"].sum(),
        "Profit Before Tax": df[df["Type"] != "Summary"]["Profit Before Tax"].sum(),
        "Tax Expense (20%)": df[df["Type"] != "Summary"]["Tax Expense (20%)"].sum(),
        "Profit After Tax": df[df["Type"] != "Summary"]["Profit After Tax"].sum()
    }
    df = pd.concat([df, pd.DataFrame([overall_total])], ignore_index=True)

    return df


# 🔄 Example usage:
# if __name__ == "__main__":
#     df_pnl = generate_pnl_schedule(
#         total_revenue=10_000_000_000_000,      # 10 trillion VND
#         total_land_payment=3_000_000_000_000,  # 3 trillion VND
#         total_sga=1_000_000_000_000,           # 1 trillion VND
#         current_year=2025,
#         start_booking_year=2026,
#         end_booking_year=2030
#     )

#     print("📄 P&L Schedule:")
#     print(df_pnl)

#     print("\n💰 Tax Expense Schedule:")
#     tax_schedule = df_pnl["Tax Expense (20%)"].tolist()
#     print(tax_schedule)
# %%

def RNAV_Calculation(
    selling_progress_schedule: list,
    construction_payment_schedule: list,
    sga_payment_schedule: list,
    tax_expense_schedule: list,
    land_use_right_payment_schedule: list,
    wacc: float,
    current_year: int
) -> pd.DataFrame:
    """
    Calculate RNAV using discounted cash flow method.
    Only includes future cash flows (current year and beyond) for RNAV calculation.

    Args:
        selling_progress_schedule (list of float): Cash inflow per year
        construction_payment_schedule (list of float): Construction cost per year
        sga_payment_schedule (list of float): SG&A cost per year
        tax_expense_schedule (list of float): Tax expense per year
        land_use_right_payment_schedule (list of float): Land use right payments per year
        wacc (float): Discount rate (e.g. 0.12 for 12%)
        current_year (int): Starting year for the analysis

    Returns:
        pd.DataFrame: Year-by-year cash flows and total discounted RNAV
    """
    n = len(selling_progress_schedule)
    # Validate all input lists are of equal length
    all_schedules = [
        construction_payment_schedule,
        sga_payment_schedule,
        tax_expense_schedule,
        land_use_right_payment_schedule
    ]
    if not all(len(lst) == n for lst in all_schedules):
        raise ValueError("All input lists must be of equal length.")

    data = []
    total_rnav = 0.0
    for i in range(n):
        year = current_year + i
        inflow = selling_progress_schedule[i]
        
        # Break down outflow components
        construction_cost = construction_payment_schedule[i]
        sga_cost = sga_payment_schedule[i]
        tax_cost = tax_expense_schedule[i]
        land_cost = land_use_right_payment_schedule[i]
        
        total_outflow = construction_cost + sga_cost + tax_cost + land_cost
        net_cashflow = inflow + total_outflow
        
        # Calculate discount factor (year 0 = current year)
        discount_factor = 1 / ((1 + wacc) ** i)
        discounted_cashflow = net_cashflow * discount_factor
        
        # Only add to RNAV if it's current year or future (i >= 0)
        total_rnav += discounted_cashflow

        # Determine if this is a future cash flow for RNAV
        included_in_rnav = True  # Since we start from current_year, all are included

        data.append({
            "Year": year,
            "Year Index": i,
            "Inflow (Revenue)": inflow,
            "Construction Cost": construction_cost,
            "Land Cost": land_cost,
            "SG&A": sga_cost,
            "Tax": tax_cost,
            "Total Outflow": total_outflow,
            "Net Cash Flow": net_cashflow,
            "Discount Factor": discount_factor,
            "Discounted Cash Flow": discounted_cashflow,
            "Included in RNAV": "Yes" if included_in_rnav else "No"
        })

    df = pd.DataFrame(data)
    
    # Add total row
    total_row = {
        "Year": "Total RNAV",
        "Year Index": np.nan,
        "Inflow (Revenue)": df["Inflow (Revenue)"].sum(),
        "Construction Cost": df["Construction Cost"].sum(),
        "Land Cost": df["Land Cost"].sum(),
        "SG&A": df["SG&A"].sum(),
        "Tax": df["Tax"].sum(),
        "Total Outflow": df["Total Outflow"].sum(),
        "Net Cash Flow": df["Net Cash Flow"].sum(),
        "Discount Factor": np.nan,
        "Discounted Cash Flow": total_rnav,
        "Included in RNAV": "Summary"
    }
    
    df = pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)
    
    return df


# 🔄 Example usage
#%%
# if __name__ == "__main__":
    
#     nsa = 265_295
#     asp = 120_000_000
#     gfa = 300_000
#     construction_cost_per_sqm = 20_000_000
#     land_area = 67_143
#     land_cost_per_sqm = 48_500_000
#     sga_as_percent = 0.08
#     wacc_rate = 0.12

#     current_year = 2025

#     start_year = 2025
#     num_years = 3
#     start_booking_year = 2027
#     complete_year = 2030

#     total_revenue = nsa * asp
#     total_construction_cost = gfa*construction_cost_per_sqm
#     total_land_cost = land_area*land_cost_per_sqm
#     total_sga_cost = total_revenue * sga_as_percent

#     selling_progress = selling_progress_schedule(total_revenue,current_year,start_year,num_years,complete_year)
#     sga_payment = sga_payment_schedule(total_sga_cost,0.08,current_year,start_year,num_years,complete_year)
#     construction_payment = construction_payment_schedule(total_construction_cost,current_year,start_year,num_years,complete_year)
#     land_use_right_payment = land_use_right_payment_schedule_single_year(total_land_cost,current_year,start_year,complete_year)

#     df_pnl = generate_pnl_schedule(total_revenue,total_land_cost,total_construction_cost,total_sga_cost,start_year,start_booking_year, complete_year)

#     tax_expense = df_pnl["Tax Expense (20%)"].tolist()

#     df_rnav = RNAV_Calculation(selling_progress,construction_payment,sga_payment,tax_expense,land_use_right_payment,wacc_rate)

#     print(df_rnav) 

def format_vnd_billions(value: float) -> str:
    """
    Format a VND value into billions with proper formatting.
    
    Args:
        value (float): Raw VND value
        
    Returns:
        str: Formatted string in billions VND (e.g., "31.84 billion VND")
    """
    if value == 0:
        return "0 VND"
    
    # Convert to billions
    billions = value / 1_000_000_000
    
    # Format with appropriate decimal places
    if abs(billions) >= 1000:
        # For very large numbers, show fewer decimals
        return f"{billions:,.0f} billion VND"
    elif abs(billions) >= 100:
        # For hundreds of billions, show 1 decimal
        return f"{billions:,.1f} billion VND"
    elif abs(billions) >= 10:
        # For tens of billions, show 1 decimal
        return f"{billions:,.1f} billion VND"
    elif abs(billions) >= 1:
        # For billions, show 2 decimals
        return f"{billions:,.2f} billion VND"
    else:
        # For less than 1 billion, show in millions
        millions = value / 1_000_000
        if abs(millions) >= 1:
            return f"{millions:,.0f} million VND"
        else:
            # For very small amounts, show in thousands or raw
            if abs(value) >= 1_000:
                thousands = value / 1_000
                return f"{thousands:,.0f} thousand VND"
            else:
                return f"{value:,.0f} VND"


def format_number_with_commas(value: str) -> str:
    """
    Format a numeric string with commas for better readability.
    
    Args:
        value (str): Numeric value as string
        
    Returns:
        str: Formatted number with commas
    """
    if not value or value == "":
        return "none"
    
    try:
        # Convert to float first to handle any decimal points
        num = float(str(value).replace(",", ""))
        # Format with commas
        if num == int(num):
            return f"{int(num):,}"
        else:
            return f"{num:,.2f}"
    except (ValueError, TypeError):
        return str(value)

# ...existing code...

# %%
def get_project_basic_info(project_name: str, openai_api_key: str) -> dict:
    """
    Get project information using Google Search + OpenAI analysis
    This combines real-time web search with AI interpretation
    """
    
    # Step 1: Search Google for current information
    search_results = search_project_online(project_name)
    
    # Step 2: Prepare context from search results
    search_context = ""
    if search_results["status"] == "success" and search_results["results"]:
        search_context = "Here are recent search results about this project:\n\n"
        for i, result in enumerate(search_results["results"][:10], 1):  # Use top 10 results
            search_context += f"{i}. **{result['title']}**\n"
            search_context += f"   Link: {result['link']}\n"
            search_context += f"   Info: {result['snippet']}\n\n"
        search_context += "\nBased on these search results, please extract and analyze the following information:\n"
    else:
        search_context = f"Google Search Status: {search_results['message']}\n"
        search_context += "Please provide analysis based on your training data and Vietnamese market knowledge:\n"
    
    # Step 3: Create enhanced prompt with search context
    prompt = (
        f"Analyze the real estate project '{project_name}' in Vietnam.\n\n"
        f"{search_context}\n"
        f"Please extract and provide the following information:\n\n"
        f"1. Project location, developer, and current status\n"
        f"2. Current selling prices (IMPORTANT: distinguish between price per unit vs price per sqm)\n"
        f"3. Project scale and specifications\n"
        f"4. Market positioning and category\n\n"
        f"CRITICAL PRICING INSTRUCTIONS:\n"
        f"- ALWAYS distinguish between 'price per unit' (giá/căn) and 'price per sqm' (giá/m²)\n"
        f"- Price per unit examples: '2.5 tỷ/căn', '3 billion VND/unit', '1.8 tỷ VND/căn hộ'\n"
        f"- Price per sqm examples: '50 triệu/m²', '80 million VND/m²', '60 triệu VND/m²'\n"
        f"- If you find price per unit AND average unit size, calculate: Price per sqm = Price per unit ÷ Average unit size\n"
        f"- Vietnamese context: 1 tỷ = 1 billion VND, 1 triệu = 1 million VND\n"
        f"- Common unit sizes in Vietnam: 50-120m² for apartments, 100-300m² for villas\n\n"
        f"NET SELLABLE AREA (NSA) CALCULATION INSTRUCTIONS:\n"
        f"- If NSA is directly mentioned, use that value\n"
        f"- If only NUMBER OF UNITS is available:\n"
        f"  1. First, try to find average unit size from the search results or similar projects in the same area\n"
        f"  2. Calculate: NSA = Number of units × Average unit size per unit\n"
        f"  3. If no unit size information available, use these defaults:\n"
        f"     • Apartments/Condos: 80 m² per unit\n"
        f"     • Luxury apartments: 100 m² per unit\n"
        f"     • Villas/Townhouses: 200 m² per unit\n"
        f"     • Mixed-use projects: 85 m² per unit\n"
        f"- Always explain your NSA calculation method\n\n"
        f"CALCULATION EXAMPLES:\n"
        f"- If unit price = 3 tỷ VND and unit size = 75m², then price per sqm = 3,000,000,000 ÷ 75 = 40,000,000 VND/m²\n"
        f"- If unit price = 2.5 billion VND and unit size = 80m², then price per sqm = 2,500,000,000 ÷ 80 = 31,250,000 VND/m²\n"
        f"- If project has 1,500 units and average unit size is 85m², then NSA = 1,500 × 85 = 127,500 m²\n"
        f"- If project has 800 apartment units with no size info, assume 80m²/unit, then NSA = 800 × 80 = 64,000 m²\n\n"
        f"FORMAT YOUR RESPONSE EXACTLY AS FOLLOWS:\n\n"
        f"Info: [Detailed project description with current status, location, and developer]\n"
        f"Average Selling Price: 100000000\n"
        f"Total Units: 1500\n"
        f"Average Unit Size: 80\n"
        f"Gross Floor Area: 300000\n"
        f"Construction Cost per sqm: 20000000\n"
        f"Land Area: 50000\n"
        f"Land Cost per sqm: 50000000\n"
        f"Sources: [List key sources from search results or 'Training data + market estimates']\n"
        f"Confidence: [High/Medium/Low based on available data]\n"
        f"Price Analysis: [Explain your price calculation: 'Found price per sqm directly' OR 'Calculated from unit price X VND ÷ unit size Y m² = Z VND/m²' OR 'Market estimate based on location/type']\n"
        f"Units Analysis: [Explain your units calculation: 'Found total units directly' OR 'Estimated based on project scale and type']\n\n"
        f"IMPORTANT NOTES:\n"
        f"- For 'Average Selling Price', provide ONLY the price per m² in VND (numbers only, no commas/currency)\n"
        f"- For 'Total Units', provide ONLY the number of units (numbers only)\n"
        f"- For 'Average Unit Size', provide ONLY the average size per unit in m² (numbers only)\n"
        f"- If you find unit prices, convert them to price per m² using typical unit sizes for that project type\n"
        f"- If you find NSA but no unit count, estimate units using: Total Units = NSA ÷ Average Unit Size\n"
        f"- Use Vietnamese real estate market standards (2024-2025) for estimates when specific data is not available\n"
        f"- Apartment projects: typical unit size 60-90m², luxury: 80-150m², villa: 150-400m²\n"
        f"- If uncertain about unit size, use conservative estimates: apartments 80m², villas 200m²\n"
        f"- Always prioritize information from the search results over general estimates"
    )
    
    # Step 4: Get OpenAI analysis
    models_to_try = ["gpt-4", "gpt-3.5-turbo", "gpt-4o"]
    
    for model in models_to_try:
        try:
            client = openai.OpenAI(api_key=openai_api_key)
            
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert Vietnamese real estate analyst with deep knowledge of pricing structures. You MUST distinguish between unit prices (giá/căn) and price per sqm (giá/m²). When you find unit prices, calculate the price per sqm by dividing by typical unit sizes. Always explain your pricing calculation method. For numeric fields, provide ONLY numbers without formatting."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1800,  # Increased for more detailed price analysis
                temperature=0.1,  # Very low temperature for consistent formatting
            )
            
            content = response.choices[0].message.content.strip()
            break
            
        except Exception as model_error:
            if model == models_to_try[-1]:
                return {"error": f"All models failed. Last error: {str(model_error)}"}
            continue
    
    # Step 5: Parse the response with improved patterns
    result = {
        "basic_info": "",
        "asp": "",
        "total_units": "",
        "average_unit_size": "",
        "gfa": "",
        "construction_cost_per_sqm": "",
        "land_area": "",
        "land_cost_per_sqm": "",
        "sources": "",
        "confidence": "",
        "price_analysis": "",
        "units_analysis": "",
        "raw_content": content,
        "model_used": model,
        "search_results_count": len(search_results.get("results", [])),
        "search_status": search_results["status"],
        "google_search_used": search_results["status"] == "success"
    }
    
    # Enhanced regex patterns with multiple variations
    patterns = {
        "basic_info": [
            r"Info:\s*(.*?)(?=Average Selling Price:|Total Units:|$)",
            r"Project Info:\s*(.*?)(?=Average Selling Price:|Total Units:|$)",
            r"Description:\s*(.*?)(?=Average Selling Price:|Total Units:|$)"
        ],
        "asp": [
            r"Average Selling Price:\s*([0-9,\.]+)",
            r"Selling Price:\s*([0-9,\.]+)",
            r"Price per sqm:\s*([0-9,\.]+)",
            r"ASP:\s*([0-9,\.]+)"
        ],
        "total_units": [
            r"Total Units:\s*([0-9,\.]+)",
            r"Number of Units:\s*([0-9,\.]+)",
            r"Units:\s*([0-9,\.]+)"
        ],
        "average_unit_size": [
            r"Average Unit Size:\s*([0-9,\.]+)",
            r"Unit Size:\s*([0-9,\.]+)",
            r"Average Size:\s*([0-9,\.]+)"
        ],
        "gfa": [
            r"Gross Floor Area:\s*([0-9,\.]+)",
            r"Floor Area:\s*([0-9,\.]+)",
            r"GFA:\s*([0-9,\.]+)",
            r"Total Floor Area:\s*([0-9,\.]+)"
        ],
        "construction_cost_per_sqm": [
            r"Construction Cost per sqm:\s*([0-9,\.]+)",
            r"Construction Cost:\s*([0-9,\.]+)",
            r"Building Cost per sqm:\s*([0-9,\.]+)"
        ],
        "land_area": [
            r"Land Area:\s*([0-9,\.]+)",
            r"Site Area:\s*([0-9,\.]+)",
            r"Plot Area:\s*([0-9,\.]+)"
        ],
        "land_cost_per_sqm": [
            r"Land Cost per sqm:\s*([0-9,\.]+)",
            r"Land Cost:\s*([0-9,\.]+)",
            r"Land Price per sqm:\s*([0-9,\.]+)"
        ],
        "sources": [
            r"Sources:\s*(.*?)(?=Confidence:|Price Analysis:|$)",
            r"Source:\s*(.*?)(?=Confidence:|Price Analysis:|$)",
            r"References:\s*(.*?)(?=Confidence:|Price Analysis:|$)"
        ],
        "confidence": [
            r"Confidence:\s*(.*?)(?=Price Analysis:|\n|$)",
            r"Reliability:\s*(.*?)(?=Price Analysis:|\n|$)"
        ],
        "price_analysis": [
            r"Price Analysis:\s*(.*?)(?=Units Analysis:|\n|$)",
            r"Pricing Method:\s*(.*?)(?=Units Analysis:|\n|$)",
            r"Price Calculation:\s*(.*?)(?=Units Analysis:|\n|$)"
        ],
        "units_analysis": [
            r"Units Analysis:\s*(.*?)(?=\n|$)",
            r"Unit Calculation:\s*(.*?)(=\n|$)"
        ]
    }
    
    # Try multiple patterns for each field
    for key, pattern_list in patterns.items():
        found = False
        for pattern in pattern_list:
            m = re.search(pattern, content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if m:
                value = m.group(1).strip()
                
                # Clean up numeric values more aggressively
                if key not in ["basic_info", "sources", "confidence", "price_analysis", "units_analysis"] and value:
                    # Remove all non-numeric characters except dots
                    cleaned_value = re.sub(r'[^\d\.]', '', value)
                    # Handle multiple dots (keep only the first one)
                    if cleaned_value.count('.') > 1:
                        parts = cleaned_value.split('.')
                        cleaned_value = parts[0] + '.' + ''.join(parts[1:])
                    # Remove trailing dots
                    cleaned_value = cleaned_value.rstrip('.')
                    value = cleaned_value
                
                result[key] = value
                found = True
                break
        
        # Fallback extraction for numeric fields if patterns fail
        if not found and key not in ["basic_info", "sources", "confidence", "price_analysis", "units_analysis"]:
            # Try to find any number in the vicinity of the field name
            field_names = {
                "asp": ["selling price", "price per sqm", "average price"],
                "total_units": ["total units", "number of units", "units"],
                "average_unit_size": ["unit size", "average size", "size per unit"],
                "gfa": ["floor area", "gross area", "gfa", "total area"],
                "construction_cost_per_sqm": ["construction cost", "building cost"],
                "land_area": ["land area", "site area", "plot area"],
                "land_cost_per_sqm": ["land cost", "land price"]
            }
            
            for field_name in field_names.get(key, []):
                # Look for numbers after field name mentions
                pattern = rf"{field_name}[:\s]*([0-9,\.]+)"
                m = re.search(pattern, content, re.IGNORECASE)
                if m:
                    value = re.sub(r'[^\d\.]', '', m.group(1))
                    if value:
                        result[key] = value
                        break

    # Add debug information for troubleshooting
    result["parsing_debug"] = {
        "content_length": len(content),
        "fields_found": {k: bool(v) for k, v in result.items() if k not in ["raw_content", "parsing_debug"]},
        "sample_content": content[:500] + "..." if len(content) > 500 else content
    }
    
    return result

def search_project_online(project_name: str) -> dict:
    """
    Search for project information online using Google Custom Search API
    Focuses on getting basic info, net sellable area, and average selling price
    """
    if not google_search_enabled:
        return {
            "status": "not_configured", 
            "message": f"Google Search API not configured. API Key: {bool(google_api_key)}, Engine ID: {bool(google_search_engine_id)}, Client Available: {GOOGLE_SEARCH_AVAILABLE}",
            "results": []
        }
    
    try:
        # Build the Google Search service
        service = build("customsearch", "v1", developerKey=google_api_key)
        
        # Enhanced search queries targeting specific Vietnamese real estate websites
        search_queries = [
            # Basic project information from batdongsan.com.vn
            f'site:batdongsan.com.vn "{project_name}" dự án bất động sản thông tin cơ bản chủ đầu tư',
            f'site:batdongsan.com.vn "{project_name}" real estate project basic information developer',
            
            # Basic project information from chotot.com
            f'site:chotot.com "{project_name}" dự án bất động sản thông tin cơ bản chủ đầu tư',
            f'site:chotot.com "{project_name}" real estate project basic information developer',
            
            # Basic project information from nhadat247.com.vn
            f'site:nhadat247.com.vn "{project_name}" dự án bất động sản thông tin cơ bản chủ đầu tư',
            f'site:nhadat247.com.vn "{project_name}" real estate project basic information developer',
            
            # Basic project information from homedy.com
            f'site:homedy.com "{project_name}" dự án bất động sản thông tin cơ bản chủ đầu tư',
            f'site:homedy.com "{project_name}" real estate project basic information developer',
            
            # Basic project information from rever.vn
            f'site:rever.vn "{project_name}" dự án bất động sản thông tin cơ bản chủ đầu tư',
            f'site:rever.vn "{project_name}" real estate project basic information developer',
            
            # Basic project information from onehousing.vn
            f'site:onehousing.vn "{project_name}" dự án bất động sản thông tin cơ bản chủ đầu tư',
            f'site:onehousing.vn "{project_name}" real estate project basic information developer',
            
            # Basic project information from meeyland.com
            f'site:meeyland.com "{project_name}" dự án bất động sản thông tin cơ bản chủ đầu tư',
            f'site:meeyland.com "{project_name}" real estate project basic information developer',
            
            # Net sellable area and project scale queries
            f'site:batdongsan.com.vn "{project_name}" "diện tích" "căn hộ" "tổng số" quy mô',
            f'site:chotot.com "{project_name}" "diện tích" "căn hộ" "tổng số" quy mô',
            f'site:nhadat247.com.vn "{project_name}" "diện tích" "căn hộ" "tổng số" quy mô',
            f'site:homedy.com "{project_name}" "diện tích" "căn hộ" "tổng số" quy mô',
            f'site:rever.vn "{project_name}" "diện tích" "căn hộ" "tổng số" quy mô',
            f'site:onehousing.vn "{project_name}" "diện tích" "căn hộ" "tổng số" quy mô',
            f'site:meeyland.com "{project_name}" "diện tích" "căn hộ" "tổng số" quy mô',
            
            # Average selling price queries
            f'site:batdongsan.com.vn "{project_name}" "giá bán" "triệu/m2" "VND/m2" bảng giá',
            f'site:chotot.com "{project_name}" "giá bán" "triệu/m2" "VND/m2" bảng giá',
            f'site:nhadat247.com.vn "{project_name}" "giá bán" "triệu/m2" "VND/m2" bảng giá',
            f'site:homedy.com "{project_name}" "giá bán" "triệu/m2" "VND/m2" bảng giá',
            f'site:rever.vn "{project_name}" "giá bán" "triệu/m2" "VND/m2" bảng giá',
            f'site:onehousing.vn "{project_name}" "giá bán" "triệu/m2" "VND/m2" bảng giá',
            f'site:meeyland.com "{project_name}" "giá bán" "triệu/m2" "VND/m2" bảng giá',
            
            # Detailed specifications and pricing queries
            f'site:batdongsan.com.vn "{project_name}" thông số kỹ thuật diện tích căn hộ giá cả',
            f'site:chotot.com "{project_name}" thông số kỹ thuật diện tích căn hộ giá cả',
            f'site:nhadat247.com.vn "{project_name}" thông số kỹ thuật diện tích căn hộ giá cả',
            f'site:homedy.com "{project_name}" thông số kỹ thuật diện tích căn hộ giá cả',
            f'site:rever.vn "{project_name}" thông số kỹ thuật diện tích căn hộ giá cả',
            f'site:onehousing.vn "{project_name}" thông số kỹ thuật diện tích căn hộ giá cả',
            f'site:meeyland.com "{project_name}" thông số kỹ thuật diện tích căn hộ giá cả'
        ]
        
        all_results = []
        
        for i, query in enumerate(search_queries):
            try:
                print(f"Executing search query {i+1}/{len(search_queries)}: {query}")
                
                # Execute search with parameters optimized for Vietnamese real estate
                result = service.cse().list(
                    q=query,
                    cx=google_search_engine_id,
                    num=2,  # Reduced to 2 per query since we have more sites now
                    lr='lang_vi|lang_en',  # Vietnamese and English
                    dateRestrict='y3',  # Results from last 3 years for more data
                    safe='medium',
                    gl='vn',  # Search in Vietnam
                    hl='vi',  # Interface language Vietnamese
                    fields='items(title,link,snippet,displayLink,formattedUrl)'
                ).execute()
                
                print(f"Search {i+1} returned {len(result.get('items', []))} results")
                
                # Extract and categorize information
                if 'items' in result:
                    for item in result['items']:
                        # Categorize the result based on content
                        snippet = item.get('snippet', '').lower()
                        title = item.get('title', '').lower()
                        
                        category = "general"
                        if any(keyword in snippet + title for keyword in ['giá', 'price', 'triệu', 'tỷ', 'vnd']):
                            category = "pricing"
                        elif any(keyword in snippet + title for keyword in ['diện tích', 'area', 'm2', 'sqm', 'căn hộ']):
                            category = "area_specs"
                        elif any(keyword in snippet + title for keyword in ['chủ đầu tư', 'developer', 'dự án', 'project']):
                            category = "basic_info"
                        
                        # Determine source website
                        source_site = "unknown"
                        link = item.get('link', '').lower()
                        if 'batdongsan.com' in link:
                            source_site = "batdongsan.com.vn"
                        elif 'chotot.com' in link:
                            source_site = "chotot.com"
                        elif 'nhadat247.com' in link:
                            source_site = "nhadat247.com.vn"
                        elif 'homedy.com' in link:
                            source_site = "homedy.com"
                        elif 'rever.vn' in link:
                            source_site = "rever.vn"
                        elif 'onehousing.vn' in link:
                            source_site = "onehousing.vn"
                        elif 'meeyland.com' in link:
                            source_site = "meeyland.com"
                        
                        all_results.append({
                            'title': item.get('title', ''),
                            'link': item.get('link', ''),
                            'snippet': item.get('snippet', ''),
                            'display_link': item.get('displayLink', ''),
                            'formatted_url': item.get('formattedUrl', ''),
                            'query_used': query,
                            'category': category,
                            'query_index': i + 1,
                            'source_site': source_site
                        })
                        
            except Exception as search_error:
                print(f"Search query {i+1} failed: {str(search_error)}")
                # Continue with next query instead of failing completely
                continue
        
        # Sort results by category priority (pricing and area specs first)
        category_priority = {"pricing": 1, "area_specs": 2, "basic_info": 3, "general": 4}
        all_results.sort(key=lambda x: category_priority.get(x['category'], 5))
        
        print(f"Total search results collected: {len(all_results)}")
        print(f"Results by category: {dict(pd.Series([r['category'] for r in all_results]).value_counts())}")
        
        # Count results by source site
        source_counts = {}
        for result in all_results:
            source = result.get('source_site', 'unknown')
            source_counts[source] = source_counts.get(source, 0) + 1
        
        return {
            "status": "success",
            "message": f"Found {len(all_results)} search results from {len(search_queries)} queries, targeting 7 Vietnamese real estate websites",
            "results": all_results,
            "queries_attempted": len(search_queries),
            "successful_queries": len([r for r in all_results if r]),
            "results_by_category": dict(pd.Series([r['category'] for r in all_results]).value_counts()),
            "results_by_source": source_counts
        }
        
    except Exception as e:
        error_msg = f"Google Search API failed: {str(e)}"
        print(f"Google Search Error: {error_msg}")
        return {
            "status": "error",
            "message": error_msg,
            "results": [],
            "error_type": type(e).__name__
        }


def save_project_data(project_data, project_name, rnav_value=None):
    """Save project data to the CSV database"""
    try:
        csv_path = os.path.join("data", "real_estate_projects.csv")
        
        # Load existing data
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
        else:
            # Create new dataframe with required columns
            columns = ['company_ticker', 'company_name', 'project_name', 'total_units', 
                      'average_selling_price', 'net_sellable_area', 'gross_floor_area', 
                      'land_area', 'construction_cost_per_sqm', 'land_cost_per_sqm',
                      'construction_start_year', 'sale_start_year', 'land_payment_year',
                      'construction_years', 'sales_years', 'revenue_booking_start_year', 
                      'project_completion_year', 'sga_percentage', 'wacc_rate', 'rnav_value',
                      'last_updated']
            df = pd.DataFrame(columns=columns)
        
        # Prepare new row data
        new_row = {
            'company_ticker': project_data.get('company_ticker', 'MANUAL'),
            'company_name': project_data.get('company_name', 'Manual Entry'),
            'project_name': project_name,
            'total_units': project_data['total_units'],
            'average_selling_price': project_data['average_selling_price'],
            'net_sellable_area': project_data['total_units'] * project_data['average_unit_size'],
            'gross_floor_area': project_data['gross_floor_area'],
            'land_area': project_data['land_area'],
            'construction_cost_per_sqm': project_data['construction_cost_per_sqm'],
            'land_cost_per_sqm': project_data['land_cost_per_sqm'],
            'construction_start_year': project_data['construction_start_year'],
            'sale_start_year': project_data['sale_start_year'],
            'land_payment_year': project_data['land_payment_year'],
            'construction_years': project_data['construction_years'],
            'sales_years': project_data['sales_years'],
            'revenue_booking_start_year': project_data['revenue_booking_start_year'],
            'project_completion_year': project_data['project_completion_year'],
            'sga_percentage': project_data['sga_percentage'],
            'wacc_rate': project_data['wacc_rate'],
            'rnav_value': rnav_value,
            'last_updated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Check if project already exists
        existing_index = df[(df['project_name'] == project_name) & 
                           (df['company_ticker'] == new_row['company_ticker'])].index
        
        if len(existing_index) > 0:
            # Update existing project
            for col, value in new_row.items():
                df.loc[existing_index[0], col] = value
            action = "updated"
        else:
            # Add new project
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            action = "saved"
        
        # Save to CSV
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        df.to_csv(csv_path, index=False)
        
        return {"success": True, "message": f"Project {action} successfully!", "action": action}
        
    except Exception as e:
        return {"success": False, "message": f"Error saving project: {str(e)}"}

def load_project_data(project_name):
    """Load project data from the CSV database"""
    try:
        csv_path = os.path.join("data", "real_estate_projects.csv")
        df = pd.read_csv(csv_path)
        
        # Find project
        project_rows = df[df['project_name'] == project_name]
        
        if project_rows.empty:
            return {"success": False, "message": f"Project '{project_name}' not found in database"}
        
        if len(project_rows) > 1:
            # Multiple companies have projects with same name
            st.warning(f"Multiple projects found with name '{project_name}'. Using the first one.")
        
        project_data = project_rows.iloc[0].to_dict()
        
        # Calculate average unit size from NSA and total units
        if project_data['total_units'] > 0:
            project_data['average_unit_size'] = project_data['net_sellable_area'] / project_data['total_units']
        else:
            project_data['average_unit_size'] = 80  # default
        
        return {"success": True, "data": project_data, "message": "Project loaded successfully!"}
        
    except FileNotFoundError:
        return {"success": False, "message": "Project database not found"}
    except Exception as e:
        return {"success": False, "message": f"Error loading project: {str(e)}"}

def get_all_project_names():
    """Get list of all project names from database"""
    try:
        csv_path = os.path.join("data", "real_estate_projects.csv")
        df = pd.read_csv(csv_path)
        return df['project_name'].unique().tolist()
    except:
        return []

def load_projects_database():
    """Load the complete projects database"""
    try:
        csv_path = os.path.join("data", "real_estate_projects.csv")
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            return df
        else:
            st.warning("No project database found. Please ensure 'data/real_estate_projects.csv' exists.")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading project database: {str(e)}")
        return pd.DataFrame()

def get_companies_from_database():
    """Get list of unique companies from database"""
    df = load_projects_database()
    if df.empty:
        return []
    companies = df[['company_ticker', 'company_name']].drop_duplicates()
    return [f"{row['company_ticker']} - {row['company_name']}" for _, row in companies.iterrows()]

def get_projects_for_company(company_ticker):
    """Get projects for a specific company ticker"""
    df = load_projects_database()
    if df.empty:
        return []
    company_projects = df[df['company_ticker'] == company_ticker]
    return company_projects['project_name'].tolist()

def get_project_data_from_database(company_ticker, project_name):
    """Get specific project data from database"""
    df = load_projects_database()
    if df.empty:
        return None
    
    project_data = df[(df['company_ticker'] == company_ticker) & 
                     (df['project_name'] == project_name)]
    
    if project_data.empty:
        return None
    
    data = project_data.iloc[0].to_dict()
    # Calculate average unit size from NSA and total units
    if data['total_units'] > 0:
        data['average_unit_size'] = data['net_sellable_area'] / data['total_units']
    else:
        data['average_unit_size'] = 80  # default
    
    return data

# ...existing code...

def main():
    st.title("Real Estate RNAV Calculator 3.2PM")

    # Get current calendar year automatically
    current_calendar_year = datetime.datetime.now().year

    # Check for pre-loaded project data from dashboard
    preload_data = st.session_state.get('preload_project_data', None)
    preload_name = st.session_state.get('preload_project_name', None)

    # Load projects database
    df_projects = load_projects_database()
    
    # Project selection interface
    st.header("📋 Project Selection")
    
    if df_projects.empty:
        st.warning("No projects found in database. You can still enter project details manually below.")
        project_name = st.text_input("Project Name", value="My Project")
        selected_project_data = None
    else:
        # Company selection
        companies = get_companies_from_database()
        
        # Check if we have preloaded data to set default selection
        default_company_index = 0
        default_project_index = 0
        
        if preload_data and 'company_ticker' in preload_data:
            preload_company = f"{preload_data['company_ticker']} - {preload_data['company_name']}"
            if preload_company in companies:
                default_company_index = companies.index(preload_company) + 1
        
        selected_company = st.selectbox(
            "Select Company:",
            options=["Select a company..."] + companies,
            index=default_company_index
        )
        
        if selected_company == "Select a company...":
            st.info("👆 Please select a company to see available projects")
            project_name = st.text_input("Or enter project name manually:", value="My Project")
            selected_project_data = None
        else:
            # Extract ticker from selection
            company_ticker = selected_company.split(" - ")[0]
            company_name = selected_company.split(" - ")[1]
            
            # Project selection
            projects = get_projects_for_company(company_ticker)
            
            if not projects:
                st.warning(f"No projects found for {selected_company}")
                project_name = st.text_input("Enter new project name:", value="New Project")
                selected_project_data = None
            else:
                # Check if we have preloaded project to set default
                if preload_name and preload_name in projects:
                    default_project_index = projects.index(preload_name) + 1
                
                selected_project = st.selectbox(
                    "Select Project:",
                    options=["Select a project..."] + projects,
                    index=default_project_index
                )
                
                if selected_project == "Select a project...":
                    st.info("👆 Please select a project or enter a new one")
                    project_name = st.text_input("Or enter new project name:", value="New Project")
                    selected_project_data = None
                else:
                    project_name = selected_project
                    selected_project_data = get_project_data_from_database(company_ticker, selected_project)
                    
                    if selected_project_data:
                        st.success(f"✅ Loaded project: {selected_project}")
                        
                        # Show project summary
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total Units", f"{int(selected_project_data['total_units']):,}")
                            st.metric("NSA", f"{int(selected_project_data['net_sellable_area']):,} m²")
                        with col2:
                            st.metric("ASP", f"{int(selected_project_data['average_selling_price']/1_000_000):,}M VND/m²")
                            st.metric("GFA", f"{int(selected_project_data['gross_floor_area']):,} m²")
                        with col3:
                            st.metric("Land Area", f"{int(selected_project_data['land_area']):,} m²")
                            st.metric("Completion", f"{int(selected_project_data['project_completion_year'])}")
                        
                        # Override preload_data with database data
                        preload_data = selected_project_data
                    else:
                        st.error("Error loading project data from database")

    # Add manual entry option
    col1, col2 = st.columns([3, 1])
    with col1:
        pass  # project_name already defined above
    
    # Add Save/Load section
    st.sidebar.header("💾 Save & Load Projects")
    
    # Quick load from database
    if not df_projects.empty:
        st.sidebar.subheader("📂 Quick Load")
        all_projects = df_projects['project_name'].unique().tolist()
        selected_quick_load = st.sidebar.selectbox(
            "Quick load any project:",
            options=["Select project..."] + all_projects,
            index=0
        )
        
        if st.sidebar.button("📂 Quick Load Project"):
            if selected_quick_load != "Select project...":
                # Find the project in database
                project_row = df_projects[df_projects['project_name'] == selected_quick_load].iloc[0]
                quick_load_data = project_row.to_dict()
                
                # Calculate average unit size
                if quick_load_data['total_units'] > 0:
                    quick_load_data['average_unit_size'] = quick_load_data['net_sellable_area'] / quick_load_data['total_units']
                else:
                    quick_load_data['average_unit_size'] = 80
                
                st.session_state['preload_project_data'] = quick_load_data
                st.session_state['preload_project_name'] = selected_quick_load
                st.session_state['manual_mode'] = False
                st.sidebar.success(f"✅ Loaded: {selected_quick_load}")
                st.rerun()

    # Set your OpenAI API key if available
    if api_key:
        openai.api_key = api_key

    # Add button to get project info from ChatGPT
    if "project_info" not in st.session_state:
        st.session_state["project_info"] = {}
    if "project_info_raw" not in st.session_state:
        st.session_state["project_info_raw"] = ""
    if "show_raw_response" not in st.session_state:
        st.session_state["show_raw_response"] = False
    # Add session state for search results debugging
    if "search_results" not in st.session_state:
        st.session_state["search_results"] = {}
    if "show_search_results" not in st.session_state:
        st.session_state["show_search_results"] = False
    
    # Only show ChatGPT button if API key is available
    if api_key:
        if st.button("🔍 Search Project Info (Web Search + AI)"):
            with st.spinner("Searching the web for current project information..."):
                # First, get search results for debugging
                search_results = search_project_online(project_name)
                st.session_state["search_results"] = search_results
                
                # Then get full project info
                info = get_project_basic_info(project_name, api_key)
                st.session_state["project_info"] = info
                
                # Show detailed feedback
                if isinstance(info, dict):
                    if "error" in info:
                        st.error(f"❌ Error: {info['error']}")
                    else:
                        # Show search status with more details
                        search_status = info.get("search_status", "unknown")
                        search_count = info.get("search_results_count", 0)
                        google_used = info.get("google_search_used", False)
                        
                        if google_used:
                            st.success(f"✅ Google Search performed successfully! Found {search_count} results. Model: {info.get('model_used', 'unknown')}")
                        else:
                            st.warning(f"⚠️ Google Search not available ({search_status}). Used model: {info.get('model_used', 'unknown')} with training data only.")
                        
                        if info.get("sources"):
                            st.info(f"📄 Sources found: {info['sources']}")
                    
                    # Save the raw response
                    if "raw_content" in info:
                        st.session_state["project_info_raw"] = info["raw_content"]
                    else:
                        st.session_state["project_info_raw"] = str(info)
        
        # Show current Google Search status
        if google_search_enabled:
            st.success("✅ Google Search is configured and ready to use!")
        else:
            st.info("🔍 **Google Search Integration**: Set up Google Custom Search for enhanced web search.")
    else:
        st.info("💡 Set up your OpenAI API key to use AI-powered project information search.")

    # Debug section for Google Search Results
    search_results = st.session_state.get("search_results", {})
    if search_results:
        # Toggle button for search results debugging
        if st.button("🔍 Show/Hide Google Search Results (Debug)"):
            st.session_state["show_search_results"] = not st.session_state["show_search_results"]
        
        # Show search results if toggled on
        if st.session_state["show_search_results"]:
            st.markdown("---")
            st.markdown("### 🔍 Google Search Results (Debug Information)")
            
            # Show search status and summary
            status = search_results.get("status", "unknown")
            message = search_results.get("message", "No message")
            results = search_results.get("results", [])
            
            # Status overview
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Search Status", status)
            with col2:
                st.metric("Total Results", len(results))
            with col3:
                queries_attempted = search_results.get("queries_attempted", 0)
                st.metric("Queries Attempted", queries_attempted)
            
            # Show message
            if status == "success":
                st.success(f"✅ {message}")
            elif status == "error":
                st.error(f"❌ {message}")
            else:
                st.warning(f"⚠️ {message}")
            
            # Show results by category if available
            if results and "results_by_category" in search_results:
                st.markdown("**Results by Category:**")
                category_data = search_results["results_by_category"]
                for category, count in category_data.items():
                    st.write(f"- **{category.title()}**: {count} results")
            
            # Show individual search results
            if results:
                st.markdown("**Individual Search Results:**")
                
                # Group results by category for better organization
                results_by_category = {}
                for result in results:
                    category = result.get('category', "general")
                    if category not in results_by_category:
                        results_by_category[category] = []
                    results_by_category[category].append(result)
                
                # Display results by category
                for category, category_results in results_by_category.items():
                    with st.expander(f"📁 {category.title()} Results ({len(category_results)} items)", expanded=(category == "pricing")):
                        for i, result in enumerate(category_results, 1):
                            st.markdown(f"**{i}. {result.get('title', 'No title')}**")
                            st.markdown(f"🔗 **Link:** {result.get('link', 'No link')}")
                            st.markdown(f"📝 **Snippet:** {result.get('snippet', 'No snippet')}")
                            st.markdown(f"🔍 **Query used:** `{result.get('query_used', 'Unknown')}`")
                            st.markdown(f"📊 **Category:** {result.get('category', 'general')}")
                            if i < len(category_results):
                                st.markdown("---")
            else:
                st.warning("No search results to display")
            
            st.markdown("---")

    project_info = st.session_state.get("project_info", {})
    project_info_raw = st.session_state.get("project_info_raw", "")

    # Ensure project_info is always a dict
    if not isinstance(project_info, dict):
        project_info = {}

    # Show sources if web search was performed
    if isinstance(project_info, dict) and project_info.get("sources"):
        st.markdown("**🔗 Sources Found:**")
        st.markdown(project_info["sources"])

    # Toggle button for raw AI response
    if project_info_raw or (isinstance(project_info, dict) and "raw_content" in project_info):
        if st.button("🔍 Show/Hide Raw AI Response"):
            st.session_state["show_raw_response"] = not st.session_state["show_raw_response"]
        
        # Show raw response from ChatGPT only if toggled on
        if st.session_state["show_raw_response"]:
            st.markdown("**Raw AI Response:**")
            if project_info_raw:
                st.code(project_info_raw, language="markdown")
            elif isinstance(project_info, dict) and "raw_content" in project_info:
                st.code(project_info["raw_content"], language="markdown")

    # Show image and basic info if available
    if project_info.get("basic_info"):
        st.info(project_info["basic_info"])
    elif project_info.get("error"):
        st.error(project_info["error"])

    # Helper to parse float or fallback to default
    def parse_float(val, default):
        try:
            return float(str(val).replace(",", "").replace(".", "")) if val else default
        except Exception:
            return default

    # Suggestion values from ChatGPT
    total_units_suggest = project_info.get("total_units", "")
    average_unit_size_suggest = project_info.get("average_unit_size", "")
    asp_suggest = project_info.get("asp", "")
    gfa_suggest = project_info.get("gfa", "")
    construction_cost_suggest = project_info.get("construction_cost_per_sqm", "")
    land_area_suggest = project_info.get("land_area", "")
    land_cost_suggest = project_info.get("land_cost_per_sqm", "")

    # Helper function for float parsing with preload and fallback
    def parse_float_with_preload(ai_suggest, preload_value, default):
        try:
            if preload_value is not None:
                return float(preload_value)
            elif ai_suggest:
                return float(str(ai_suggest).replace(",", "").replace(".", ""))
            else:
                return float(default)
        except Exception:
            return float(default)

    # Helper function for int parsing with preload and fallback
    def parse_int_with_preload(ai_suggest, preload_value, default):
        try:
            if preload_value is not None:
                return int(preload_value)
            elif ai_suggest:
                return int(str(ai_suggest).replace(",", "").replace(".", ""))
            else:
                return int(default)
        except Exception:
            return int(default)

    # Create two parallel columns for Project Parameters and Timeline
    param_col, timeline_col = st.columns(2)

    with param_col:
        st.header("Project Parameters")
        
        # Total Units
        total_units = st.number_input(
            "Total Units", 
            value=parse_float_with_preload(
                project_info.get("total_units", ""),
                preload_data.get('total_units') if preload_data else None, 
                2500
            ), 
            key="total_units"
        )
        # Show data source caption
        if preload_data and 'total_units' in preload_data:
            st.caption(f"📊 From database: **{format_number_with_commas(str(int(preload_data['total_units'])))}** units")
        elif project_info.get("total_units"):
            st.caption(f"💡 AI suggestion: **{format_number_with_commas(project_info.get('total_units', ''))}** units")
        else:
            st.caption("💡 Using default value")
        
        # Average Unit Size
        average_unit_size = st.number_input(
            "Average Unit Size (m²)", 
            value=parse_float_with_preload(
                project_info.get("average_unit_size", ""),
                preload_data.get('average_unit_size') if preload_data else None, 
                80
            ), 
            key="average_unit_size"
        )
        if preload_data and 'average_unit_size' in preload_data:
            st.caption(f"📊 From database: **{format_number_with_commas(str(int(preload_data['average_unit_size'])))}** m²")
        elif project_info.get("average_unit_size"):
            st.caption(f"💡 AI suggestion: **{format_number_with_commas(project_info.get('average_unit_size', ''))}** m²")
        else:
            st.caption("💡 Using default value")
        
        # Calculate NSA from units and unit size
        nsa = total_units * average_unit_size
        st.info(f"📊 **Calculated Net Sellable Area:** {format_number_with_commas(str(int(nsa)))} m²")
        
        # Average Selling Price
        asp = st.number_input(
            "Average Selling Price (VND/m²)", 
            value=parse_float_with_preload(
                project_info.get("asp", ""),
                preload_data.get('average_selling_price') if preload_data else None, 
                100_000_000
            ), 
            key="asp"
        )
        if preload_data and 'average_selling_price' in preload_data:
            st.caption(f"📊 From database: **{format_number_with_commas(str(int(preload_data['average_selling_price'])))}** VND/m²")
        elif project_info.get("asp"):
            st.caption(f"💡 AI suggestion: **{format_number_with_commas(project_info.get('asp', ''))}** VND/m²")
        else:
            st.caption("💡 Using default value")
        
        # Gross Floor Area
        gfa = st.number_input(
            "Gross Floor Area (m²)", 
            value=parse_float_with_preload(
                project_info.get("gfa", ""),
                preload_data.get('gross_floor_area') if preload_data else None, 
                300_000
            ), 
            key="gfa"
        )
        if preload_data and 'gross_floor_area' in preload_data:
            st.caption(f"📊 From database: **{format_number_with_commas(str(int(preload_data['gross_floor_area'])))}** m²")
        elif project_info.get("gfa"):
            st.caption(f"💡 AI suggestion: **{format_number_with_commas(project_info.get('gfa', ''))}** m²")
        else:
            st.caption("💡 Using default value")
        
        # Construction Cost per sqm
        construction_cost_per_sqm = st.number_input(
            "Construction Cost per m² (VND)", 
            value=parse_float_with_preload(
                project_info.get("construction_cost_per_sqm", ""),
                preload_data.get('construction_cost_per_sqm') if preload_data else None, 
                20_000_000
            ), 
            
            key="construction_cost_per_sqm"
        )
        if preload_data and 'construction_cost_per_sqm' in preload_data:
            st.caption(f"📊 From database: **{format_number_with_commas(str(int(preload_data['construction_cost_per_sqm'])))}** VND/m²")
        elif project_info.get("construction_cost_per_sqm"):
            st.caption(f"💡 AI suggestion: **{format_number_with_commas(project_info.get('construction_cost_per_sqm', ''))}** VND/m²")
        else:
            st.caption("💡 Using default value")
        
        # Land Area
        land_area = st.number_input(
            "Land Area (m²)", 
            value=parse_float_with_preload(
                project_info.get("land_area", ""),
                preload_data.get('land_area') if preload_data else None, 
                50_000
            ), 
            key="land_area"
        )
        if preload_data and 'land_area' in preload_data:
            st.caption(f"📊 From database: **{format_number_with_commas(str(int(preload_data['land_area'])))}** m²")
        elif project_info.get("land_area"):
            st.caption(f"💡 AI suggestion: **{format_number_with_commas(project_info.get('land_area', ''))}** m²")
        else:
            st.caption("💡 Using default value")
        
        # Land Cost per sqm
        land_cost_per_sqm = st.number_input(
            "Land Cost per m² (VND)", 
            value=parse_float_with_preload(
                project_info.get("land_cost_per_sqm", ""),
                preload_data.get('land_cost_per_sqm') if preload_data else None, 
                50_000_000
            ), 
            key="land_cost_per_sqm"
        )
        if preload_data and 'land_cost_per_sqm' in preload_data:
            st.caption(f"📊 From database: **{format_number_with_commas(str(int(preload_data['land_cost_per_sqm'])))}** VND/m²")
        elif project_info.get("land_cost_per_sqm"):
            st.caption(f"💡 AI suggestion: **{format_number_with_commas(project_info.get('land_cost_per_sqm', ''))}** VND/m²")
        else:
            st.caption("💡 Using default value")

    with timeline_col:
        st.header("Timeline")
        
        # Remove the current year input and use calendar year automatically
        current_year = current_calendar_year
        st.info(f"📅 **Current Year:** {current_year} (automatically set to calendar year)")
        
        start_year = st.number_input(
            "Construction/Sales Start Year", 
            value=parse_int_with_preload("", preload_data.get('construction_start_year') if preload_data else None, current_year),
            min_value=current_year - 10,  # Allow up to 10 years in the past
            max_value=current_year + 20   # Allow up to 20 years in the future
        )
        
        # Show warning if start year is in the past
        if start_year < current_year:
            years_ago = current_year - start_year
            st.warning(f"⚠️ Start year is {years_ago} year(s) in the past. Historical data will be shown but not included in RNAV calculation.")
        
        # Add land payment year input
        land_payment_year = st.number_input(
            "Land Payment Year", 
            value=parse_int_with_preload("", preload_data.get('land_payment_year') if preload_data else None, start_year),
            min_value=current_year - 10,  # Allow up to 10 years in the past
            max_value=current_year + 20   # Allow up to 20 years in the future
        )
        
        # Separate construction and sales duration
        construction_years = st.number_input(
            "Number of Years for Construction", 
            value=parse_int_with_preload("", preload_data.get('construction_years') if preload_data else None, 3), 
            min_value=1
        )
        sales_years = st.number_input(
            "Number of Years for Sales", 
            value=parse_int_with_preload("", preload_data.get('sales_years') if preload_data else None, 3), 
            min_value=1
        )
        
        start_booking_year = st.number_input(
            "Revenue Booking Start Year", 
            value=parse_int_with_preload("", preload_data.get('revenue_booking_start_year') if preload_data else None, max(current_year, start_year + 1)),
            min_value=start_year
        )
        complete_year = st.number_input(
            "Project Completion Year", 
            value=parse_int_with_preload("", preload_data.get('project_completion_year') if preload_data else None, start_year + 5),
            min_value=start_year + 1
        )
        
        # Show timeline summary
        st.markdown("---")
        st.markdown("**📊 Project Timeline Summary:**")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"• Construction: {start_year} - {start_year + construction_years - 1}")
            st.write(f"• Sales: {start_year} - {start_year + sales_years - 1}")
            st.write(f"• Land Payment: {land_payment_year}")
        with col2:
            st.write(f"• Revenue Booking: {start_booking_year} - {complete_year}")
            st.write(f"• Project Duration: {complete_year - start_year + 1} years")
        
        st.markdown("---")
        sga_percent = st.number_input(
            "SG&A as % of Revenue", 
            min_value=0.0, max_value=1.0, 
            value=float(preload_data.get('sga_percentage', 0.08)) if preload_data and 'sga_percentage' in preload_data else 0.08, 
            step=0.01
        )
        wacc_rate = st.number_input(
            "WACC (Discount Rate, e.g. 0.12 for 12%)", 
            min_value=0.0, max_value=1.0, 
            value=float(preload_data.get('wacc_rate', 0.12)) if preload_data and 'wacc_rate' in preload_data else 0.12, 
            step=0.01
        )

    # Add Save Project button with improved logic
    st.sidebar.markdown("---")
    if st.sidebar.button("💾 Save Current Project", type="primary"):
        # Calculate RNAV value before saving
        try:
            # Calculate totals
            total_revenue = nsa * asp
            total_construction_cost = -gfa * construction_cost_per_sqm
            total_land_cost = -land_area * land_cost_per_sqm
            total_sga_cost = -total_revenue * sga_percent

            # Generate schedules
            selling_progress = selling_progress_schedule(
                total_revenue/(10**9), int(current_year), int(start_year), int(sales_years), int(complete_year)
            )
            sga_payment = sga_payment_schedule(
                total_sga_cost/(10**9), int(current_year), int(start_year), int(sales_years), int(complete_year)
            )
            construction_payment = construction_payment_schedule(
                total_construction_cost/(10**9), int(current_year), int(start_year), int(construction_years), int(complete_year)
            )
            land_use_right_payment = land_use_right_payment_schedule_single_year(
                total_land_cost/(10**9), int(current_year), int(land_payment_year), int(complete_year)
            )

            df_pnl = generate_pnl_schedule(
                total_revenue/(10**9), total_land_cost/(10**9), total_construction_cost/(10**9), total_sga_cost/(10**9),
                int(current_year), int(start_booking_year), int(complete_year)
            )
            
            # Create tax expense schedule
            num_years = int(complete_year) - int(current_year) + 1
            tax_expense = []
            for year in range(int(current_year), int(complete_year) + 1):
                year_data = df_pnl[df_pnl["Year"] == year]
                if not year_data.empty and year_data["Type"].iloc[0] != "Summary":
                    tax_value = year_data["Tax Expense (20%)"].iloc[0]
                else:
                    tax_value = 0.0
                tax_expense.append(tax_value)

            # Calculate RNAV
            df_rnav = RNAV_Calculation(
                selling_progress, construction_payment, sga_payment, tax_expense, land_use_right_payment, wacc_rate, int(current_year)
            )

            # Get RNAV value
            total_row = df_rnav[df_rnav["Year"] == "Total RNAV"]
            if not total_row.empty:
                rnav_value = total_row["Discounted Cash Flow"].iloc[0] * (10**9)
            else:
                rnav_value = df_rnav.loc[df_rnav.index[-1], 'Discounted Cash Flow'] * (10**9)

        except Exception as e:
            st.sidebar.error(f"Error calculating RNAV: {str(e)}")
            rnav_value = None

        # Determine company info
        if selected_project_data:
            # Use existing company info from selected project
            company_ticker = selected_project_data.get('company_ticker', 'MANUAL')
            company_name = selected_project_data.get('company_name', 'Manual Entry')
        elif preload_data:
            # Use preload company info
            company_ticker = preload_data.get('company_ticker', 'MANUAL')
            company_name = preload_data.get('company_name', 'Manual Entry')
        else:
            # Default for manual entries
            company_ticker = 'MANUAL'
            company_name = 'Manual Entry'
        
        # Collect current project data
        current_project_data = {
            'company_ticker': company_ticker,
            'company_name': company_name,
            'total_units': total_units,
            'average_unit_size': average_unit_size,
            'average_selling_price': asp,
            'gross_floor_area': gfa,
            'land_area': land_area,
            'construction_cost_per_sqm': construction_cost_per_sqm,
            'land_cost_per_sqm': land_cost_per_sqm,
            'construction_start_year': start_year,
            'sale_start_year': start_year,
            'land_payment_year': land_payment_year,
            'construction_years': construction_years,
            'sales_years': sales_years,
            'revenue_booking_start_year': start_booking_year,
            'project_completion_year': complete_year,
            'sga_percentage': sga_percent,
            'wacc_rate': wacc_rate
        }
        
        save_result = save_project_data(current_project_data, project_name, rnav_value)
        if save_result["success"]:
            if rnav_value is not None:
                st.sidebar.success(f"{save_result['message']}\n💰 RNAV: {format_vnd_billions(rnav_value)}")
            else:
                st.sidebar.success(save_result["message"])
            if save_result["action"] == "saved":
                st.sidebar.info("💡 Project added to database. Refresh to see in dropdown.")
                # Refresh the database after save
                st.rerun()
        else:
            st.sidebar.error(save_result["message"])

    # Clear preload data after first use (but not for database selections)
    if preload_data and not selected_project_data:
        if 'clear_preload' not in st.session_state:
            st.session_state['clear_preload'] = True
        else:
            if st.session_state['clear_preload']:
                st.session_state.pop('preload_project_data', None)
                st.session_state.pop('preload_project_name', None)
                st.session_state['clear_preload'] = False

    # Calculate totals
    total_revenue = nsa * asp
    total_construction_cost = -gfa * construction_cost_per_sqm
    total_land_cost = -land_area * land_cost_per_sqm
    total_sga_cost = -total_revenue * sga_percent
    total_estimated_PBT = total_revenue + total_land_cost + total_construction_cost + total_sga_cost
    total_estimated_PAT = total_estimated_PBT * 0.8  # Assuming 20% tax rate

    st.subheader("Calculated Totals")
    st.write(f"**Total Revenue:** {format_vnd_billions(total_revenue)}")
    st.write(f"**Total Construction Cost:** {format_vnd_billions(total_construction_cost)}")
    st.write(f"**Total Land Cost:** {format_vnd_billions(total_land_cost)}")
    st.write(f"**Total SG&A:** {format_vnd_billions(total_sga_cost)}")
    st.write(f"**Total Estimated PBT:** {format_vnd_billions(total_estimated_PBT)}")
    st.write(f"**Total Estimated PAT:** {format_vnd_billions(total_estimated_PAT)}")

    # Update schedule calculations to use separate construction and sales years
    selling_progress = selling_progress_schedule(
        total_revenue/(10**9), int(current_year), int(start_year), int(sales_years), int(complete_year)
    )
    sga_payment = sga_payment_schedule(
        total_sga_cost/(10**9), int(current_year), int(start_year), int(sales_years), int(complete_year)
    )
    construction_payment = construction_payment_schedule(
        total_construction_cost/(10**9), int(current_year), int(start_year), int(construction_years), int(complete_year)
    )
    land_use_right_payment = land_use_right_payment_schedule_single_year(
        total_land_cost/(10**9), int(current_year), int(land_payment_year), int(complete_year)
    )

    df_pnl = generate_pnl_schedule(
        total_revenue/(10**9), total_land_cost/(10**9), total_construction_cost/(10**9), total_sga_cost/(10**9),
        int(current_year), int(start_booking_year), int(complete_year)
    )
    
    # Create tax expense schedule that matches the time period from current_year to complete_year
    num_years = int(complete_year) - int(current_year) + 1
    
    # Get tax expense for each year from current_year to complete_year
    tax_expense = []
    for year in range(int(current_year), int(complete_year) + 1):
        # Find tax expense for this year in the P&L schedule
        year_data = df_pnl[df_pnl["Year"] == year]
        if not year_data.empty and year_data["Type"].iloc[0] != "Summary":
            tax_value = year_data["Tax Expense (20%)"].iloc[0]
        else:
            # If year not found in P&L (e.g., before booking period), use 0
            tax_value = 0.0
        tax_expense.append(tax_value)
    
    # Verify all schedules have the same length
    schedules_info = {
        "selling_progress": len(selling_progress),
        "construction_payment": len(construction_payment), 
        "sga_payment": len(sga_payment),
        "tax_expense": len(tax_expense),
        "land_use_right_payment": len(land_use_right_payment)
    }
    
    # Debug information (remove in production)
    st.sidebar.write("Schedule lengths:", schedules_info)
    
    # Ensure all schedules have the same length
    expected_length = num_years
    if not all(length == expected_length for length in schedules_info.values()):
        st.error(f"Schedule length mismatch! Expected: {expected_length}, Got: {schedules_info}")
        st.stop()

    st.header(f"Project: {project_name}")

    df_rnav = RNAV_Calculation(
        selling_progress, construction_payment, sga_payment, tax_expense, land_use_right_payment, wacc_rate, int(current_year)
    )

    # Create two parallel columns for P&L Schedule and RNAV Calculation
    pnl_col, rnav_col = st.columns(2)
    
    with pnl_col:
        st.header("P&L Schedule")
        
        # Color-code the dataframe display
        if len(df_pnl) > 0:
            # Create a styled version that highlights historical vs future
            def highlight_historical(row):
                row_index = row.name
                if row_index < len(df_pnl):
                    year_type = df_pnl.iloc[row_index]["Type"]
                    year_value = df_pnl.iloc[row_index]["Year"]
                    
                    if year_type == "Historical":
                        return ['background-color: #ffebee'] * len(row)  # Light red for historical
                    elif year_type == "Future":
                        return ['background-color: #e8f5e8'] * len(row)  # Light green for future
                    elif year_type == "Summary":
                        if "Historical" in str(year_value):
                            return ['background-color: #ffcdd2; font-weight: bold'] * len(row)  # Darker red for historical total
                        elif "Future" in str(year_value):
                            return ['background-color: #c8e6c8; font-weight: bold'] * len(row)  # Darker green for future total
                        else:
                            return ['background-color: #e0e0e0; font-weight: bold'] * len(row)  # Gray for overall total
                return [''] * len(row)
            
            st.dataframe(df_pnl.style.apply(highlight_historical, axis=1))
            
            # Add legend
            st.markdown("""
            **Legend:**
            - 🔴 Light red: Historical data (already occurred)
            - 🟢 Light green: Future projections (for RNAV calculation)
            - **Bold**: Summary totals
            """)
            
            # Show summary statistics
            historical_data = df_pnl[df_pnl["Type"] == "Historical"]
            future_data = df_pnl[df_pnl["Type"] == "Future"]
            
            if not historical_data.empty and not future_data.empty:
                st.markdown("**📊 Period Breakdown:**")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Historical Years", len(historical_data))
                    st.metric("Historical Revenue", f"{historical_data['Revenue'].sum():.1f}B VND")
                with col2:
                    st.metric("Future Years", len(future_data))
                    st.metric("Future Revenue", f"{future_data['Revenue'].sum():.1f}B VND")
            elif not future_data.empty:
                st.info(f"📅 All {len(future_data)} years are in the future (RNAV includes all cash flows)")
            elif not historical_data.empty:
                st.warning(f"📅 All {len(historical_data)} years are historical (RNAV calculation may be limited)")
        else:
            st.dataframe(df_pnl)
    
    with rnav_col:
        st.header("RNAV Calculation")
        st.dataframe(df_rnav)
        
        st.info("💡 **Note:** RNAV calculation only includes cash flows from current year onwards.")

    st.subheader("RNAV (Total Discounted Cash Flow)")
    
    # Get RNAV value from the total row
    try:
        total_row = df_rnav[df_rnav["Year"] == "Total RNAV"]
        if not total_row.empty:
            rnav_value = total_row["Discounted Cash Flow"].iloc[0] * (10**9)
        else:
            # Fallback to old method
            rnav_value = df_rnav.loc[df_rnav.index[-1], 'Discounted Cash Flow'] * (10**9)
    except:
        rnav_value = 0
    
    st.write(f"**{format_vnd_billions(rnav_value)}**")
    
    # Show RNAV history if available
    if selected_project_data and 'rnav_value' in selected_project_data and selected_project_data['rnav_value'] is not None:
        stored_rnav = selected_project_data['rnav_value']
        last_updated = selected_project_data.get('last_updated', 'Unknown')
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Current RNAV", format_vnd_billions(rnav_value))
        with col2:
            st.metric(
                "Stored RNAV", 
                format_vnd_billions(stored_rnav),
                delta=format_vnd_billions(rnav_value - stored_rnav)
            )
        
        st.caption(f"📅 Last stored: {last_updated}")
    
    if start_year < current_year:
        st.info(f"💡 **Note:** Project started {current_year - start_year} years ago. RNAV calculation excludes historical cash flows and only considers future value from {current_year} onwards.")

    st.header("Cash Flow Chart")
    # Filter out the "Total" row and create chart with years on x-axis
    chart_data = df_rnav[~df_rnav["Year"].isin(["Total RNAV"])].copy()
    
    if len(chart_data) > 0:
        # Ensure Year column is integer for clean display
        chart_data["Year"] = chart_data["Year"].astype(int)
        chart_data = chart_data.set_index("Year")[["Net Cash Flow", "Discounted Cash Flow"]]
        
        # Use plotly for better control over x-axis formatting
        import plotly.express as px
        import plotly.graph_objects as go
        
        # Create plotly chart with clean year formatting
        fig = go.Figure()
        
        # Add Net Cash Flow line
        fig.add_trace(go.Scatter(
            x=chart_data.index,
            y=chart_data["Net Cash Flow"],
            mode='lines+markers',
            name='Net Cash Flow',
            line=dict(color='blue')
        ))
        
        # Add Discounted Cash Flow line
        fig.add_trace(go.Scatter(
            x=chart_data.index,
            y=chart_data["Discounted Cash Flow"],
            mode='lines+markers',
            name='Discounted Cash Flow',
            line=dict(color='red')
        ))
        
        # Add vertical line at current year
        fig.add_vline(
            x=current_year, 
            line_dash="dash", 
            line_color="green",
            annotation_text=f"Current Year ({current_year})",
            annotation_position="top"
        )
        
        # Update layout for clean year display
        fig.update_layout(
            title="Cash Flow Analysis",
            xaxis_title="Year",
            yaxis_title="Cash Flow (Billions VND)",
            xaxis=dict(
                tickmode='linear',
                tick0=chart_data.index.min(),
                dtick=1,
                tickformat='d'  # Display as integer without decimals
            ),
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No data available for chart display.")

# ...existing code...

def test_openai_connection(api_key: str, project_name: str = "Test Project"):
    """
    Test function to debug OpenAI API issues
    """
    if not api_key:
        return {"error": "No API key provided"}
    
    try:
        client = openai.OpenAI(api_key=api_key)
        
        # Simple test prompt
        test_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'Hello, API is working!'"}],
            max_tokens=50
        )
        
        return {
            "success": True,
            "test_response": test_response.choices[0].message.content,
            "model": "gpt-3.5-turbo"
        }
        
    except Exception as e:
        return {"error": f"OpenAI API test failed: {str(e)}"}

# Ensure main function is called when the script runs
if __name__ == "__main__":
    main()
else:
    # For Streamlit, also call main when imported as a module
    main()

