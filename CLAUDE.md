# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Real Estate Financial Model** application built with Streamlit, focusing on comprehensive real estate financial analysis, RNAV calculations, and AI-powered project discovery for the Vietnamese stock market. The main application (`pages/Real_Estate_Financial_Model_God_AI.py`) serves as the primary tool for Dragon Capital's real estate investment analysis workflows, with additional legacy dashboards for company financial analysis and bank sector analytics.

## Essential Commands

### Running the Application
```bash
# Main application - Real Estate Financial Model
streamlit run pages/Real_Estate_Financial_Model_God_AI.py

# Other available specialized pages
streamlit run pages/RNAV_Calculator_MongoDB.py

# Install dependencies
pip install -r requirements.txt
```

### Environment Setup
Required environment variables in `.env`:
```
MONGODB_CONNECTION_STRING="your_mongodb_connection"
OPENAI_API_KEY="your_openai_key" 
PERPLEXITY_API_KEY="your_perplexity_key"
```

### Development Dependencies
For PDF extraction and OCR capabilities, system packages are required (defined in `packages.txt`):
```bash
# Linux/Ubuntu (for deployment)
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-vie poppler-utils
```

## High-Level Architecture

### Core Application Structure
- **Main Application** (`pages/Real_Estate_Financial_Model_God_AI.py`) - Primary real estate financial modeling interface
- **Specialized Pages** (`/pages/`) - Domain-specific dashboards (banking, real estate, sector comparison)  
- **Core Modules** (`/core/`) - Refactored utilities for data loading and plotting
  - `data_loader.py` - Centralized data loading with caching
  - `plot_factory.py` - Standardized plotting functions
  - `common_imports.py` - Consolidated imports and utilities
- **Configuration** (`/config/`) - Centralized constants and settings
  - `constants.py` - Financial metrics, plot settings, file mappings
- **Utilities Layer** (`/utils/`) - Shared business logic and data processing
- **Data Layer** (`/data/`) - Financial datasets and reference files
- **Archive** (`/archive/`) - Disabled/legacy files

### Key Architectural Patterns

**Centralized Data Loading**: Use `DataLoader` class for consistent data access:
```python
from core.data_loader import data_loader
df = data_loader.load_financial_statements()
pivot_data = data_loader.pivot_financial_data(df, ticker)
```

**Standardized Plotting**: Use `PlotFactory` for consistent chart creation:
```python
from core.plot_factory import plot_factory
fig = plot_factory.create_financial_plots(df, ticker, plot_config)
```

**Configuration Management**: All constants centralized in `/config/constants.py`:
```python
from config.constants import PLOTLY_CONFIG, FINANCIAL_CATEGORIES
```

**Multi-Source Data Integration**:
- Parquet/CSV files for historical financial data (via `DataLoader`)
- MongoDB for real estate project data (via enhanced `mongodb_utils.py`)
- SSI API for live Vietnamese stock prices (via `utils/stock_candle.py`)
- AI APIs (Perplexity/OpenAI/Claude) for project information enrichment
- MCP tool system for historical financials (`get_historical_quarterly_financials`, `get_historical_annual_financials`)
- PDF extraction capabilities for earnings reports (OCR via Tesseract)

**Refactored Code Organization**: 
- Eliminated code duplication in plotting functions (reduced from 4 similar functions to 1 factory)
- Centralized configuration reduces magic numbers
- Standardized imports via `common_imports.py`
- Cleaned file structure with archive for disabled files

### Technology Stack
- **Frontend**: Streamlit multi-page application
- **Data Processing**: Pandas/NumPy with financial domain calculations
- **Visualization**: Plotly for interactive charts
- **Database**: MongoDB for persistent storage
- **APIs**: SSI (Vietnamese stocks), Perplexity AI, OpenAI
- **Market Focus**: Vietnamese stock exchange (VND currency, local regulations)

### Critical Business Logic

**Financial Metrics**: Handles Vietnamese market-specific calculations including Income Statement ratios, Balance Sheet analysis, Cash Flow metrics, and Bank-specific indicators (NIM, NPL, Cost of Funds).

**RNAV Calculations**: Complex real estate valuation logic in `utils/RNAV_utils.py` including land value calculations, construction cost analysis, and project completion timeline modeling.

**Vietnamese Market Adaptations**: VND currency formatting (billions/millions), local stock ticker formats, and banking sector regulatory compliance.

### Data Dependencies

**Static Data Sources** (manual updates required):
- `/data/FA_A_processed.parquet` - Annual financial statements (primary)
- `/data/FA_processed.parquet` - Quarterly financial statements
- `/data/Val_processed.csv` - Valuation metrics  
- `/data/MktCap_processed.parquet` - Market capitalization data
- `/data/MoC_Data.csv` - Ministry of Construction real estate projects
- Legacy: `/data/BankSupp_processed.csv` - Banking supplement data
- Legacy: `/data/Classification.xlsx` - Sector classifications

**Dynamic Data Sources**:
- SSI API for real-time stock prices and candlestick data
- MongoDB for real estate project database
- AI APIs for project parameter estimation

### External Service Dependencies

**Critical APIs**: SSI Vietnamese stock data API, MongoDB connection, Perplexity AI for project lookup. The application implements graceful degradation when external services are unavailable, with cached data fallbacks and user-friendly error handling.

## Development Notes

- All financial calculations assume VND currency and Vietnamese accounting standards
- Real estate features require active MongoDB connection
- AI-powered project analysis is optional (degrades gracefully without API keys)
- **Refactored Structure**: Use `Company_Dashboard_Refactored.py` for new development
- **Data Loading**: Always use `data_loader` instance for consistency and caching
- **Plotting**: Use `plot_factory` methods instead of custom plotting functions
- **Configuration**: Reference `config/constants.py` instead of hardcoded values
- **Archive Management**: Disabled/legacy files are moved to `/archive/` directory
- **Specialized Pages**: Additional tools available in `/pages/` for specific use cases

## Coding Guidelines for Claude

When writing code for this repository:

1. Jupyter/Interactive Style:
   - Use `#%%` cell markers for code organization
   - Assume pandas, numpy, and plotly are already imported
   - Write code that can be run cell-by-cell in Jupyter

2. Calculation Focus:
   - Prioritize mathematical correctness and clarity
   - Use vectorized pandas operations
   - Don't add excessive try/except blocks
   - Assume data exists and is in expected format

3. Data Analysis Patterns:
   ```python
   # Good - direct calculation
   df['metric'] = df['revenue'] / df['assets']
   
   # Avoid - over-engineered
   def calculate_metric(df):
       if 'revenue' not in df.columns:
           raise ValueError("Missing revenue column")
       # ... more checks
   ```

4. Variable Naming:
   - Use descriptive names for financial metrics
   - Keep DataFrame names short (df_q, df_a, etc.)
   - Use standard financial abbreviations (ROE, ROA, NPAT)

5. Output Style:
   - Display DataFrames directly without wrapping
   - Use simple print statements for quick checks
   - Format numbers inline with f-strings when needed

## AI Tooling Notes

### Historical Financials
The MCP tool system provides two historical endpoints backed by parquet files:
- `get_historical_quarterly_financials` → `data/FA_processed.parquet`
- `get_historical_annual_financials` → `data/FA_A_processed.parquet`

Key behavior (updated):
- Units: Both tools accept `unit` ('raw' | 'billions', default 'raw'). When `billions`, only monetary metrics are divided by 1e9. Ratios/margins (`EBITDA_Margin`, `EBIT_Margin`, `Gross_Margin`, `NPAT_Margin`, `Eff_Tax_Rate`) and `OS` are not scaled.
- YoY: Results include YoY growth as separate columns with `_YoY` suffix when pivoted (e.g., `Net_Revenue_YoY`). Non‑pivot responses keep the original `YoY` column.
- Metadata: Responses include `units` and `conversion_applied` flags for clarity.

Metric aliases: The tools map common names to KEYCODEs (e.g., `revenue→Net_Revenue`, `ebitda→EBITDA`, `accounts_receivable→Account_Receivable`, `accounts_payable→Account_Payable`, `advance_from_customers→Advance_From_Custmers`, `sga→GA_Expense`). Prefer canonical KEYCODEs for precision.

Balance sheet ratios:
- calculate_balance_sheet_ratios supports aliases: `interest_coverage|icr→ebitda_interest_coverage`, `dte→debt_to_equity`, `nde→net_debt_to_equity`.
- Added ratios: `quick_ratio`, `cash_ratio`, `net_debt` (returns `net_debt_bn`).
- For forecasts, current assets/liabilities are synthesized: cash + AR + inventory (+ ST investment) and AP + customer_prepayment + ST debt.

### Enhanced Project Contribution Analysis
The `analyse_project_contribution_to_forecast` tool has been enhanced to support both P&L and Cash Flow metrics:

**Available Metrics (17 total):**

**P&L Statement (from project_breakdown):**
- `revenue`, `cogs`, `gross_profit`, `sga`, `interest`
- `pbt`, `pat`, `patmi`, `minority_interest`

**Cash Flow Statement (from cash_flow_detail):**
- `presales_inflow`, `land_outflow`, `construction_outflow`
- `interest_outflow`, `sga_outflow`, `tax_outflow`
- `debt_changes`, `net_cash_flow`

**Usage:**
```python
# P&L metric
analyse_project_contribution_to_forecast(ticker="VHM", metric="revenue", year="2025")

# Cash Flow metric
analyse_project_contribution_to_forecast(ticker="VHM", metric="presales_inflow", year="2025")
```

The tool automatically determines the data source (project_breakdown vs cash_flow_detail) based on the requested metric and provides project-level contribution analysis with percentages.

Example (quarterly, in billions):
```python
tools.get_historical_quarterly_financials(
    tickers=["DXG"], years=[2023], metrics=["Net_Revenue","EBITDA"], unit="billions"
)
```

Notes:
- `DATE` uses `YYYYQn` for quarterly and `YYYY` for annual.
- Use `metrics` to reduce payload; otherwise all 40+ KEYCODEs are returned.

# important-instruction-reminders
Do what has been asked; nothing more, nothing less.
NEVER create files unless they're absolutely necessary for achieving your goal.
ALWAYS prefer editing an existing file to creating a new one.
NEVER proactively create documentation files (*.md) or README files. Only create documentation files if explicitly requested by the User.
