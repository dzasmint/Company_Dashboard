#%%
import pandas as pd
import streamlit as st
import numpy as np
from dotenv import load_dotenv
import os
import re
import datetime
import requests
import sys

# Add the parent directory to sys.path to import from utils
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import database utilities
try:
    from utils.project_database import (
        save_project_data, load_project_data, get_all_project_names,
        load_projects_database, get_companies_from_database, 
        get_projects_for_company, get_project_data_from_database
    )
    DATABASE_AVAILABLE = True
except ImportError as e:
    st.error(f"Failed to import database functions: {str(e)}")
    st.info("Make sure the utils/project_database.py file exists and is properly configured.")
    DATABASE_AVAILABLE = False
    
    # Create mock functions if import fails
    def save_project_data(project_data, project_name, rnav_value=None):
        return {"success": False, "message": "Database not available"}
    
    def load_project_data(project_name):
        return {"success": False, "message": "Database not available"}
    
    def get_all_project_names():
        return []
    
    def load_projects_database():
        return pd.DataFrame()
    
    def get_companies_from_database():
        return []
    
    def get_projects_for_company(company_ticker):
        return []
    
    def get_project_data_from_database(company_ticker, project_name):
        return None


# Load .env file (for local development)
load_dotenv()

# Read API key from environment
perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")

if not perplexity_api_key:
    st.warning(
        "⚠️ PERPLEXITY_API_KEY environment variable is not set.\n\n"
        "**For local development:**\n"
        "1. Create a file named `.env` in your project root directory\n"
        "2. Add this line: `PERPLEXITY_API_KEY=your_perplexity_api_key_here`\n\n"
        "**For Streamlit Cloud deployment:**\n"
        "1. Go to your app settings in Streamlit Cloud\n"
        "2. Add PERPLEXITY_API_KEY as a secret in the 'Secrets' section\n\n"
        "⚡ You can still use the calculator without Perplexity integration!"
    )
    perplexity_api_key = None  # Allow app to continue without API key

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

def get_project_basic_info_perplexity(project_name: str, api_key: str, model: str = "sonar-pro"):
    """
    Query Perplexity API for basic real estate project info using the project name.
    
    Args:
        project_name (str): Name of the real estate project.
        api_key (str): Your Perplexity API key.
        model (str): The model to use. Default is "sonar-pro".
    
    Returns:
        dict: Parsed JSON response from Perplexity API with the info or error details.
    """
    if not api_key:
        raise ValueError("API key must be provided.")
    if not project_name:
        raise ValueError("Project name must be provided.")

    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Enhanced system prompt for Vietnamese real estate analysis
    system_prompt = (
        "You are a Vietnamese real estate market expert with extensive knowledge of property development projects, "
        "pricing structures, and market conditions across Vietnam's major cities. You have access to current market data "
        "and can make intelligent estimates based on location, project type, and comparable developments in the area."
    )
    
    # Comprehensive user message with detailed instructions
    user_message = f"""Please analyze the Vietnamese real estate project named '{project_name}' and provide comprehensive information.

**SEARCH STRATEGY:**
1. First, search for direct information about '{project_name}'
2. If exact data is not available, analyze similar projects in the same area/district
3. Use comparable projects from the same developer if available
4. Apply Vietnamese real estate market standards and regional pricing patterns

**REQUIRED INFORMATION TO EXTRACT/ESTIMATE:**

**1. PROJECT BASIC INFO:**
- Full project name and alternative names
- Developer/owner company
- Exact location (district, city, address if available)
- Project type (apartment, villa, mixed-use, etc.)
- Current status (planning, under construction, completed, selling)
- Launch year and completion timeline

**2. PROJECT SCALE & SPECIFICATIONS:**
- Total number of units (apartments, villas, townhouses)
- Average unit size in m² (break down by unit type if mixed)
- Net Sellable Area (NSA) in m² total
- Gross Floor Area (GFA) in m² total
- Land area in m² (site area)
- Number of buildings/blocks/phases

**3. PRICING INFORMATION:**
- Current average selling price per m² (VND/m²)
- Price range if available (min-max per m²)
- Recent pricing trends or changes
- Price per unit (if available, specify unit type and size)

**4. CONSTRUCTION & DEVELOPMENT COSTS:**
- Estimated construction cost per m² (based on project type and location)
- Land cost per m² (based on area land values)
- Development timeline and phases

**ESTIMATION GUIDELINES WHEN EXACT DATA IS NOT AVAILABLE:**

**For TOTAL UNITS:** 
- High-rise apartments: 20-40 units per floor, 20-50 floors typical
- Mid-rise apartments: 4-8 units per floor, 5-15 floors typical  
- Villa/townhouse projects: Based on land area ÷ typical plot size (150-300m² per unit)
- Mixed-use: Estimate based on GFA and typical unit sizes

**For AVERAGE UNIT SIZE:**
- Ho Chi Minh City apartments: 60-120m² (luxury: 80-150m²)
- Hanoi apartments: 65-110m² (luxury: 90-140m²)
- Secondary cities: 70-130m² (more spacious)
- Villas/townhouses: 150-400m² (premium: 200-500m²)

**For SELLING PRICE PER M²:**
- Research recent transactions in the same district/area
- Consider project positioning (affordable, mid-range, luxury, ultra-luxury)
- Account for location premiums (central vs suburban)
- Use comparable projects' pricing as baseline

**For GROSS FLOOR AREA (GFA):**
- Calculate: Total units × Average unit size × Efficiency factor (1.3-1.5 for apartments, 1.1-1.3 for villas)
- Include common areas, corridors, amenities, parking

**For LAND AREA:**
- Urban apartments: GFA/Land ratio typically 3-8 (higher in central areas)
- Suburban/villa projects: GFA/Land ratio typically 0.3-1.5
- Check local zoning regulations and typical plot ratios

**For CONSTRUCTION COST PER M²:**
- Basic apartments: 15-25 million VND/m²
- Mid-range apartments: 20-35 million VND/m²  
- Luxury apartments: 30-50 million VND/m²
- Ultra-luxury/premium: 45-80+ million VND/m²
- Villas: 25-60 million VND/m² (depending on finishes)

**For LAND COST PER M²:**
- Research recent land auction prices in the area
- Use government published land price frameworks
- Consider location premiums and development rights

**RESPONSE FORMAT (PROVIDE EXACT NUMBERS ONLY):**

Info: [Detailed project description including developer, location, type, status, and any relevant background information]

Total Units: [NUMBER ONLY - no commas or text]
Average Unit Size: [NUMBER ONLY - in m²] 
Average Selling Price: [NUMBER ONLY - VND per m²]
Gross Floor Area: [NUMBER ONLY - total m²]
Construction Cost per sqm: [NUMBER ONLY - VND per m² for construction]
Land Area: [NUMBER ONLY - total land area in m²]
Land Cost per sqm: [NUMBER ONLY - VND per m² for land]

Sources: [List your sources - web results, comparable projects, or "Market analysis based on area comps"]
Confidence: [High/Medium/Low - based on data availability]

Analysis Method: [Explain how you derived each number - "Found exact data" OR "Estimated based on [comparable projects/area standards/project type]"]

Unit Size Analysis: [Explain your unit size calculation: mix of unit types, size distribution, etc.]

Pricing Analysis: [Explain your pricing calculation: recent comps, location factors, premium/discount factors]

Construction Cost Analysis: [Explain cost estimates: project type, quality level, location factors]

Land Cost Analysis: [Explain land cost estimates: area benchmarks, zoning, development intensity]

**IMPORTANT REQUIREMENTS:**
- Always provide numerical estimates even if exact data is not available
- Clearly distinguish between confirmed data and estimates
- Use 2024-2025 Vietnamese market conditions
- Consider inflation and recent market trends
- Be specific about your estimation methodology
- For mixed-use projects, provide weighted averages
- Account for project phasing if applicable

**LOCATION-SPECIFIC CONSIDERATIONS:**
- Ho Chi Minh City: Higher density, premium pricing in central districts
- Hanoi: Government influence, established vs new urban areas  
- Da Nang: Resort/tourism factors, beachfront premiums
- Secondary cities: Lower costs, larger units, emerging markets

Please provide all requested information with your best professional estimates where exact data is not available."""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 2000,  # Increased for comprehensive response
        "temperature": 0.2,
        "top_p": 0.9,
        "stream": False
    }

    # Debug: Log the request payload
    print(f"🔍 DEBUG: Sending request to Perplexity API")
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    print(f"Payload: {payload}")

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        # Debug: Log response status
        print(f"🔍 DEBUG: Response status code: {response.status_code}")
        print(f"🔍 DEBUG: Response headers: {dict(response.headers)}")
        
        response.raise_for_status()
        data = response.json()

        # Debug: Log successful response structure
        print(f"🔍 DEBUG: Successful response keys: {data.keys() if isinstance(data, dict) else 'Not a dict'}")

        # The response usually contains choices with message content
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        else:
            return {"error": "Unexpected API response format", "response": data}

    except requests.exceptions.RequestException as e:
        # Enhanced error handling to show more details
        error_details = {
            "error": f"Perplexity API request failed: {str(e)}",
            "status_code": getattr(e.response, 'status_code', None),
            "request_url": url,
            "request_payload": payload,  # Include the payload that was sent
            "request_headers": {k: v for k, v in headers.items() if k != "Authorization"}  # Exclude API key
        }
        
        # Try to get response text for more details
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_details["response_text"] = e.response.text
                error_details["response_headers"] = dict(e.response.headers)
                
                # Try to parse JSON error response
                if e.response.headers.get('content-type', '').startswith('application/json'):
                    error_details["response_json"] = e.response.json()
            except Exception as parse_error:
                error_details["parse_error"] = str(parse_error)
        
        # Debug: Print detailed error information
        print(f"🚨 DEBUG: API Error Details:")
        for key, value in error_details.items():
            if key != "request_payload":  # Don't print payload twice
                print(f"  {key}: {value}")
        
        return error_details

# ...existing code...

def parse_perplexity_response(response_text):
    """
    Parse Perplexity response to extract structured data fields.
    
    Args:
        response_text (str): Raw response text from Perplexity
        
    Returns:
        dict: Parsed data with extracted fields
    """
    if not response_text or not isinstance(response_text, str):
        return {}
    
    # Enhanced regex patterns for extraction
    patterns = {
        "basic_info": [
            r"Info:\s*(.*?)(?=Total Units:|Average Unit Size:|$)",
            r"Project Info:\s*(.*?)(?=Total Units:|Average Unit Size:|$)",
            r"Description:\s*(.*?)(?=Total Units:|Average Unit Size:|$)"
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
        "asp": [
            r"Average Selling Price:\s*([0-9,\.]+)",
            r"Selling Price:\s*([0-9,\.]+)",
            r"Price per sqm:\s*([0-9,\.]+)",
            r"ASP:\s*([0-9,\.]+)"
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
            r"Sources:\s*(.*?)(?=Confidence:|Analysis Method:|$)",
            r"Source:\s*(.*?)(?=Confidence:|Analysis Method:|$)"
        ],
        "confidence": [
            r"Confidence:\s*(.*?)(?=Analysis Method:|\n|$)",
            r"Confidence Level:\s*(.*?)(?=Analysis Method:|\n|$)"
        ],
        "analysis_method": [
            r"Analysis Method:\s*(.*?)(?=Unit Size Analysis:|\n|$)",
            r"Method:\s*(.*?)(?=Unit Size Analysis:|\n|$)"
        ]
    }
    
    result = {}
    
    # Try multiple patterns for each field
    for key, pattern_list in patterns.items():
        found = False
        for pattern in pattern_list:
            m = re.search(pattern, response_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if m:
                value = m.group(1).strip()
                
                # Clean up numeric values
                if key not in ["basic_info", "sources", "confidence", "analysis_method"] and value:
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
    
    return result

def main():
    st.title("Real Estate RNAV Calculator - Perplexity Edition")

    # Show database status
    if DATABASE_AVAILABLE:
        st.success("✅ Database functions loaded successfully!")
    else:
        st.warning("⚠️ Database functions not available. Some features may be limited.")

    # Get current calendar year automatically
    current_calendar_year = datetime.datetime.now().year

    # Check for pre-loaded project data from dashboard
    preload_data = st.session_state.get('preload_project_data', None)
    preload_name = st.session_state.get('preload_project_name', None)

    # Load projects database only if available
    if DATABASE_AVAILABLE:
        df_projects = load_projects_database()
    else:
        df_projects = pd.DataFrame()
    
    # Project selection interface
    st.header("📋 Project Selection")
    
    if df_projects.empty:
        if DATABASE_AVAILABLE:
            st.warning("No projects found in database. You can still enter project details manually below.")
        else:
            st.info("Database not available. Enter project details manually below.")
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
    
    # Add Save/Load section only if database is available
    if DATABASE_AVAILABLE:
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
    else:
        st.sidebar.info("💾 Database functions not available. Save/Load features disabled.")

    # Add button to get project info from Perplexity
    if "project_info" not in st.session_state:
        st.session_state["project_info"] = {}
    if "project_info_raw" not in st.session_state:
        st.session_state["project_info_raw"] = ""
    if "show_raw_response" not in st.session_state:
        st.session_state["show_raw_response"] = False
    
    # Only show Perplexity button if API key is available
    if perplexity_api_key:
        if st.button("🔍 Search Project Info (Perplexity AI)"):
            with st.spinner("Searching for project information using Perplexity..."):
                info = get_project_basic_info_perplexity(project_name, perplexity_api_key)
                
                # Parse the response if it's a string (successful response)
                if isinstance(info, str):
                    parsed_info = parse_perplexity_response(info)
                    st.session_state["project_info"] = parsed_info
                    st.session_state["project_info_raw"] = info
                    
                    st.success("✅ Perplexity search completed successfully!")
                    
                    # Display parsed information in structured table format
                    if parsed_info:
                        st.subheader("🤖 AI-Extracted Project Information")
                        
                        # Show basic project info if available
                        if parsed_info.get("basic_info"):
                            st.info(f"**Project Description:** {parsed_info['basic_info']}")
                        
                        # Create structured table for comparison
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.markdown("**📊 Project Scale**")
                            if parsed_info.get("total_units"):
                                st.metric("Total Units (AI)", f"{format_number_with_commas(parsed_info['total_units'])}")
                            else:
                                st.metric("Total Units (AI)", "Not found")
                                
                            if parsed_info.get("average_unit_size"):
                                st.metric("Avg Unit Size (AI)", f"{format_number_with_commas(parsed_info['average_unit_size'])} m²")
                            else:
                                st.metric("Avg Unit Size (AI)", "Not found")
                                
                            if parsed_info.get("gfa"):
                                st.metric("GFA (AI)", f"{format_number_with_commas(parsed_info['gfa'])} m²")
                            else:
                                st.metric("GFA (AI)", "Not found")
                        
                        with col2:
                            st.markdown("**💰 Pricing Information**")
                            if parsed_info.get("asp"):
                                asp_millions = float(parsed_info['asp']) / 1_000_000 if parsed_info['asp'] else 0
                                st.metric("ASP (AI)", f"{asp_millions:.0f}M VND/m²")
                            else:
                                st.metric("ASP (AI)", "Not found")
                                
                            if parsed_info.get("construction_cost_per_sqm"):
                                const_millions = float(parsed_info['construction_cost_per_sqm']) / 1_000_000 if parsed_info['construction_cost_per_sqm'] else 0
                                st.metric("Construction Cost (AI)", f"{const_millions:.0f}M VND/m²")
                            else:
                                st.metric("Construction Cost (AI)", "Not found")
                                
                            if parsed_info.get("land_cost_per_sqm"):
                                land_millions = float(parsed_info['land_cost_per_sqm']) / 1_000_000 if parsed_info['land_cost_per_sqm'] else 0
                                st.metric("Land Cost (AI)", f"{land_millions:.0f}M VND/m²")
                            else:
                                st.metric("Land Cost (AI)", "Not found")
                        
                        with col3:
                            st.markdown("**🏗️ Development Info**")
                            if parsed_info.get("land_area"):
                                st.metric("Land Area (AI)", f"{format_number_with_commas(parsed_info['land_area'])} m²")
                            else:
                                st.metric("Land Area (AI)", "Not found")
                                
                            if parsed_info.get("confidence"):
                                confidence_color = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(parsed_info['confidence'], "⚪")
                                st.metric("Confidence", f"{confidence_color} {parsed_info['confidence']}")
                            else:
                                st.metric("Confidence", "Not specified")
                        
                        # Show sources and analysis method
                        if parsed_info.get("sources") or parsed_info.get("analysis_method"):
                            with st.expander("📋 Analysis Details", expanded=False):
                                if parsed_info.get("sources"):
                                    st.markdown(f"**Sources:** {parsed_info['sources']}")
                                if parsed_info.get("analysis_method"):
                                    st.markdown(f"**Analysis Method:** {parsed_info['analysis_method']}")
                        
                        # Comparison with database data if available
                        if selected_project_data:
                            st.markdown("---")
                            st.subheader("📊 Database vs AI Comparison")
                            
                            # Create comparison table
                            comparison_data = []
                            
                            fields_to_compare = [
                                ("Total Units", "total_units", "total_units"),
                                ("Average Unit Size (m²)", "average_unit_size", "average_unit_size"),
                                ("ASP (VND/m²)", "average_selling_price", "asp"),
                                ("GFA (m²)", "gross_floor_area", "gfa"),
                                ("Construction Cost (VND/m²)", "construction_cost_per_sqm", "construction_cost_per_sqm"),
                                ("Land Area (m²)", "land_area", "land_area"),
                                ("Land Cost (VND/m²)", "land_cost_per_sqm", "land_cost_per_sqm")
                            ]
                            
                            for field_name, db_key, ai_key in fields_to_compare:
                                db_value = selected_project_data.get(db_key, "N/A")
                                ai_value = parsed_info.get(ai_key, "N/A")
                                
                                # Format values for display
                                if db_value != "N/A" and isinstance(db_value, (int, float)):
                                    db_display = format_number_with_commas(str(int(db_value)))
                                else:
                                    db_display = str(db_value)
                                    
                                if ai_value != "N/A" and ai_value:
                                    try:
                                        ai_display = format_number_with_commas(str(int(float(ai_value))))
                                    except (ValueError, TypeError):
                                        ai_display = str(ai_value)
                                else:
                                    ai_display = "Not found"
                                
                                # Calculate difference if both values are numeric
                                difference = "N/A"
                                if (db_value != "N/A" and ai_value != "N/A" and ai_value and 
                                    isinstance(db_value, (int, float))):
                                    try:
                                        ai_numeric = float(ai_value)
                                        diff_pct = ((ai_numeric - db_value) / db_value) * 100
                                        difference = f"{diff_pct:+.1f}%"
                                    except (ValueError, TypeError, ZeroDivisionError):
                                        difference = "N/A"
                                
                                comparison_data.append({
                                    "Field": field_name,
                                    "Database": db_display,
                                    "AI Extract": ai_display,
                                    "Difference": difference
                                })
                            
                            comparison_df = pd.DataFrame(comparison_data)
                            st.dataframe(comparison_df, use_container_width=True)
                    
                elif isinstance(info, dict) and "error" in info:
                    st.session_state["project_info"] = {}
                    st.session_state["project_info_raw"] = str(info)
                    
                    st.error(f"❌ Error: {info['error']}")
                    
                    # Show detailed debugging information
                    with st.expander("🔍 Debug Information (Click to expand)"):
                        st.json(info)
                        
                    # Show specific guidance for 400 errors
                    if info.get("status_code") == 400:
                        st.warning("""
                        **400 Bad Request Error - Possible causes:**
                        - Invalid API key format
                        - Unsupported model name
                        - Request payload format issues
                        - Missing required parameters
                        
                        Check the debug information above for the exact request sent to Perplexity.
                        """)
        
        # Show current Perplexity status
        st.success("✅ Perplexity API is configured and ready to use!")
    else:
        st.info("💡 Set up your Perplexity API key to use AI-powered project information search.")

    project_info = st.session_state.get("project_info", {})
    project_info_raw = st.session_state.get("project_info_raw", "")

    # Ensure project_info is always a dict
    if not isinstance(project_info, dict):
        project_info = {}

    # Toggle button for raw AI response
    if project_info_raw or (isinstance(project_info, dict) and "raw_content" in project_info):
        if st.button("🔍 Show/Hide Raw Perplexity Response"):
            st.session_state["show_raw_response"] = not st.session_state["show_raw_response"]
        
        # Show raw response from Perplexity only if toggled on
        if st.session_state["show_raw_response"]:
            st.markdown("**Raw Perplexity Response:**")
            if project_info_raw:
                st.code(project_info_raw, language="markdown")
            elif isinstance(project_info, dict) and "raw_content" in project_info:
                st.code(project_info["raw_content"], language="markdown")

    # Show basic info if available
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

    # Add Save Project button only if database is available
    if DATABASE_AVAILABLE:
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
                    year_value = df_pnl.iloc[row_index]["Year"];
                    
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


# Ensure main function is called when the script runs
if __name__ == "__main__":
    main()
else:
    # For Streamlit, also call main when imported as a module
    main()

