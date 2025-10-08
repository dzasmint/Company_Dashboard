# Database Schema Reference Guide
**Dragon Capital Financial Data Pipeline**

## Overview
This document provides a comprehensive reference for all database tables created and maintained by the financial data pipeline. Tables are organized by functional area with detailed schema information, relationships, and data characteristics.

---

## Table of Contents
1. [Financial Statement Tables](#financial-statement-tables)
2. [Market Data Tables](#market-data-tables)
3. [Banking Analytics Tables](#banking-analytics-tables)
4. [Reference Data Tables](#reference-data-tables)
5. [Table Relationships](#table-relationships)
6. [Data Update Patterns](#data-update-patterns)

---

## Financial Statement Tables

### FA_Quarterly
**Purpose**: Quarterly financial statement data for all listed companies
**Update Frequency**: Weekly
**Data Range**: 2016 - Present
**Row Count**: ~500,000+

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | NVARCHAR(50) | NO | Stock symbol (3 letters) | 'VNM' |
| **KEYCODE** | NVARCHAR(50) | NO | Financial metric identifier | 'Net_Revenue' |
| **DATE** | NVARCHAR(50) | NO | Quarter in YYYYQX format | '2024Q3' |
| VALUE | FLOAT | YES | Metric value in VND | 15234567890.0 |
| YEAR | BIGINT | YES | Extracted year for filtering | 2024 |
| YoY | FLOAT | YES | Year-over-year growth rate | 0.085 (8.5%) |

**Primary Key**: TICKER + KEYCODE + DATE
**Common KEYCODE Values**:
- Income Statement: Net_Revenue, COGS, Gross_Profit, EBIT, EBITDA, NPAT, NPATMI
- Balance Sheet: Total_Asset, Total_Liabilities, TOTAL_Equity, Cash, ST_Debt, LT_Debt
- Cash Flow: Operating_CF, Inv_CF, Fin_CF, FCF, Capex
- Margins: Gross_Margin, EBIT_Margin, EBITDA_Margin, NPAT_Margin

---

### FA_Annual
**Purpose**: Annual financial statement data
**Update Frequency**: Weekly
**Data Range**: 2016 - Present
**Row Count**: ~125,000+

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | NVARCHAR(50) | NO | Stock symbol | 'VNM' |
| **KEYCODE** | NVARCHAR(50) | NO | Financial metric identifier | 'Net_Revenue' |
| **DATE** | NVARCHAR(50) | NO | Year as string | '2024' |
| VALUE | FLOAT | YES | Annual metric value in VND | 61234567890.0 |
| YEAR | BIGINT | YES | Year as integer | 2024 |
| YoY | FLOAT | YES | Year-over-year growth | 0.092 |

**Primary Key**: TICKER + KEYCODE + DATE
**Note**: Contains same KEYCODE values as FA_Quarterly but with annual aggregations

---

## Market Data Tables

### Market_Data
**Purpose**: Comprehensive daily market data including OHLC prices, valuation multiples, and EV/EBITDA
**Update Frequency**: Daily
**Data Range**: 2018 - Present
**Row Count**: ~1,400,000+

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | VARCHAR(10) | NO | Stock symbol (extracted from PRIMARYSECID) | 'VNM' |
| **TRADE_DATE** | DATE | NO | Trading date | '2024-09-23' |
| PE | FLOAT | YES | Price-to-Earnings ratio | 18.5 |
| PB | FLOAT | YES | Price-to-Book ratio | 3.2 |
| PS | FLOAT | YES | Price-to-Sales ratio | 2.8 |
| PX_OPEN | FLOAT | YES | Opening price | 67500 |
| PX_HIGH | FLOAT | YES | Daily high price | 68200 |
| PX_LOW | FLOAT | YES | Daily low price | 67000 |
| PX_LAST | FLOAT | YES | Closing/Last price | 67800 |
| MKT_CAP | FLOAT | YES | Market capitalization | 145678.5 |
| EV_EBITDA | FLOAT | YES | Enterprise Value/EBITDA ratio | 12.3 |
| UPDATE_TIMESTAMP | DATETIME | YES | Last update timestamp | '2024-09-23 18:30:00' |

**Primary Key**: TICKER + TRADE_DATE
**Data Sources**:
- Bloomberg (SIL.S_BBG_DATA_DWH_ADJUSTED): PE, PB, PS, PX_OPEN, PX_HIGH, PX_LOW, PX_LAST, MKT_CAP
- IRIS (SIL.W_F_IRIS_CALCULATE): EV_EBITDA
**Data Quality Notes**:
- PX_ prefix used for price columns to avoid SQL reserved keywords
- NULL values indicate data not available or not calculable
- Price relationships validated: PX_HIGH >= PX_LAST >= PX_LOW
- Extreme valuation ratios capped (PE < 1000, PB < 100, PS < 100)
- Updated via standalone valuation_ohlc_extractor script

---

### MarketCap
**Purpose**: Latest market capitalization snapshot
**Update Frequency**: Daily
**Data Range**: Current snapshot only
**Row Count**: ~1,700 (all listed stocks)

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | NVARCHAR(50) | NO | Stock symbol | 'VNM' |
| CUR_MKT_CAP | FLOAT | YES | Market cap in billions VND | 145678.5 |
| **TRADE_DATE** | DATETIME | YES | Date of snapshot | '2024-09-23' |

**Primary Key**: TICKER + TRADE_DATE
**Note**: Only contains latest values, historical data in separate archive

---

### MarketIndex
**Purpose**: Stock market index historical data (HOSE)
**Update Frequency**: Daily
**Data Range**: 2016 - Present
**Row Count**: ~2,000+

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **COMGROUPCODE** | NVARCHAR(50) | NO | Index identifier | 'VNINDEX' |
| **TRADINGDATE** | DATETIME | NO | Trading date | '2024-09-23' |
| INDEXVALUE | FLOAT | YES | Closing index value | 1285.67 |
| PRIORINDEXVALUE | FLOAT | YES | Previous day's close | 1278.45 |
| HIGHEST | FLOAT | YES | Intraday high | 1290.12 |
| LOWEST | FLOAT | YES | Intraday low | 1275.30 |
| TOTALSHARE | BIGINT | YES | Total shares traded | 567890123 |
| TOTALVALUE | FLOAT | YES | Total value traded (VND) | 12345678901234 |
| FOREIGNBUYVOLUME | BIGINT | YES | Foreign buying volume | 12345678 |
| FOREIGNSELLVOLUME | BIGINT | YES | Foreign selling volume | 11234567 |

**Primary Key**: COMGROUPCODE + TRADINGDATE

---

## Banking Analytics Tables

### BankingMetrics
**Purpose**: Comprehensive banking metrics including 26 calculated ratios (CA.1-CA.26)
**Update Frequency**: Quarterly with annual aggregates
**Data Range**: 2017 - Present (including forecast years)
**Row Count**: ~10,000+ (actual + forecast)

**Key Columns**:
| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | NVARCHAR(20) | NO | Bank ticker or tier aggregate | 'VCB' or 'SOCB' |
| **YEARREPORT** | INT | NO | Reporting year | 2024 |
| **LENGTHREPORT** | INT | NO | 1-4 for Q1-Q4, 5 for annual | 3 |
| **ACTUAL** | BIT | NO | True=Historical, False=Forecast | 1 |
| DATE | DATE | YES | End date of period | '2024-09-30' |
| DATE_STRING | NVARCHAR(20) | YES | Formatted period | '2024-Q3' or '2024' |
| BANK_TYPE | NVARCHAR(20) | YES | Bank classification | 'SOCB', 'Private_1' |
| PERIOD_TYPE | NVARCHAR(10) | YES | 'Q' for quarterly, 'Y' for annual | 'Q' |

**Financial Metrics** (Human-readable column names):
| Column Name | Description | Typical Range |
|-------------|-------------|---------------|
| TOI | Total Operating Income | 1000-50000 bn VND |
| PBT | Profit Before Tax | 500-30000 bn VND |
| Net Interest Income | Interest revenue net of expense | 500-30000 bn VND |
| OPEX | Operating Expenses | -500 to -20000 bn VND |
| PPOP | Pre-Provision Operating Profit | 500-25000 bn VND |
| Provision expense | Credit provision expense | -100 to -10000 bn VND |
| NPATMI | Net Profit After Tax Minority Interest | 300-20000 bn VND |
| Fees Income | Non-interest fee income | 100-5000 bn VND |
| Net Profit | Net profit after all expenses | 300-20000 bn VND |
| Loan | Total customer loans | 10000-1500000 bn VND |
| Deposit | Total customer deposits | 10000-1500000 bn VND |
| Total Assets | Balance sheet total assets | 50000-2000000 bn VND |
| Total Equity | Total shareholders' equity | 5000-150000 bn VND |
| Provision on Balance Sheet | Accumulated provisions (negative) | -1000 to -50000 bn VND |
| Write-off | Loan write-offs (Nt.220) | 0-5000 bn VND |

**Calculated Banking Ratios** (Human-readable column names):
| Column Name | CA Code | Description | Formula | Typical Range |
|-------------|---------|-------------|---------|---------------|
| LDR | CA.1 | Loan-to-Deposit Ratio | Loan/Deposit | 70-100% |
| CASA | CA.2 | Current/Savings Account ratio | (Nt.121+124+125)/Deposit | 15-40% |
| NPL | CA.3 | Non-Performing Loan ratio | (Nt.68+69+70)/Loan | 0.5-3% |
| ABS NPL | CA.4 | Absolute NPL amount | Nt.68+69+70 | 100-50000 bn VND |
| GROUP 2 | CA.5 | Group 2 loans ratio | Nt.67/Loan | 0.5-2% |
| CIR | CA.6 | Cost-to-Income Ratio | -OPEX/TOI | 30-60% |
| NPL Coverage ratio | CA.7 | Provision coverage of NPL | -Provision/(Nt.68+69+70) | 50-200% |
| Total Credit Balance | CA.8 | Total credit exposure | BS.13+BS.16+Nt.97+Nt.112 | 15000-2000000 bn VND |
| Provision/ Total Loan | CA.9 | Provision to loan ratio | -Provision/Loan | 1-3% |
| Leverage Multiple | CA.10 | Assets to equity ratio | Total Assets/Total Equity | 8-15x |
| Interest Earnings Asset | CA.11 | Interest-earning assets | Sum of earning assets | 40000-1800000 bn VND |
| Interest Bearing Liabilities | CA.12 | Interest-bearing liabilities | Sum of costing liabilities | 35000-1700000 bn VND |
| NIM | CA.13 | Net Interest Margin | NII/Avg(IEA) annualized | 2-5% |
| Customer loans | CA.14 | Total customer lending | BS.13+BS.16 | 10000-1500000 bn VND |
| Loan yield | CA.15 | Average loan interest rate | Interest income/Avg(Loans) | 6-10% |
| ROA | CA.16 | Return on Assets | Net Profit/Avg(Assets) | 0.5-2% |
| ROE | CA.17 | Return on Equity | NPATMI/Avg(Equity) | 10-25% |
| Deposit balance | CA.18 | Interbank deposits | BS.3+BS.5+BS.6 | 1000-100000 bn VND |
| Deposit yield | CA.19 | Average deposit cost | Interest expense/Avg(Deposits) | 3-6% |
| Fees/ Total asset | CA.20 | Fee income efficiency | Fees Income/Avg(Assets) | 0.5-2% |
| Individual % | CA.21 | Retail loans percentage | Nt.89/BS.12 | 20-60% |
| NPL Formation Amount | CA.22 | New NPL in period | (NPL-Write-off)-NPL_prev | -1000 to 5000 bn VND |
| New NPL | CA.23 | NPL formation rate | CA.22/Loan_prev | -1% to 2% |
| Group 2 Formation | CA.24 | New Group 2 loans | (G2+NPL_form)-G2_prev | -500 to 2000 bn VND |
| New G2 | CA.25 | Group 2 formation rate | CA.24/Loan_prev | -0.5% to 1% |
| Overdue_loan | CA.26 | Total overdue loans ratio | NPL + GROUP 2 | 1-5% |

**Primary Key**: TICKER + YEARREPORT + LENGTHREPORT + ACTUAL

**Special TICKER Values for Aggregates**:
- 'SOCB': State-owned commercial banks aggregate
- 'Private_1': Tier 1 private banks
- 'Private_2': Tier 2 private banks
- 'Private_3': Tier 3 private banks
- 'Sector': Entire banking sector

---

### Banking_Comments
**Purpose**: Qualitative commentary and analysis notes for banks
**Update Frequency**: Quarterly (manual)
**Data Range**: As available
**Row Count**: Variable

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| **TICKER** | NVARCHAR(50) | NO | Bank ticker | 'VCB' |
| SECTOR | NVARCHAR(50) | YES | Banking sector/type | 'SOCB' |
| **DATE** | NVARCHAR(50) | NO | Quarter in YYYYQX format | '2024Q3' |
| COMMENT | NVARCHAR(MAX) | YES | Analysis text | 'Strong credit growth...' |

**Primary Key**: TICKER + DATE

---

## Reference Data Tables

### Sector_Map
**Purpose**: Master reference for ticker classification and index membership
**Update Frequency**: As needed
**Data Range**: All listed tickers
**Row Count**: 433

| Column | Data Type | Nullable | Description | Example |
|--------|-----------|----------|-------------|---------|
| OrganCode | NVARCHAR(20) | YES | Organization code | 'VNMILK' |
| **Ticker** | NVARCHAR(10) | NO | Stock ticker | 'VNM' |
| ExportClassification | NVARCHAR(10) | YES | Export flag | 'Export' |
| Sector | NVARCHAR(20) | NO | Primary sector | 'Consumer' |
| L1 | NVARCHAR(30) | NO | Level 1 industry | 'Consumer Staples' |
| L2 | NVARCHAR(25) | NO | Level 2 industry | 'Food & Beverage' |
| L3 | NVARCHAR(25) | YES | Level 3 sub-industry | 'Dairy' |
| VNI | NVARCHAR(1) | YES | VN30 Index member | 'Y' or NULL |

**Primary Key**: Ticker

**Sector Distribution**:
- Consumer: ~100 tickers
- Industrial: ~150 tickers
- Service: ~80 tickers
- Financial: ~40 tickers
- Resources: ~60 tickers

**VNI Membership**: 37 tickers marked with 'Y'

---

## Table Relationships

### Primary Relationships
```
FA_Quarterly/FA_Annual
    ↓ [TICKER]
Sector_Map ← [TICKER] → MarketCap
    ↓ [TICKER]           ↓ [TICKER]
Valuation ← [TICKER] → BankingMetrics
                         ↓ [TICKER]
                    Banking_Comments
```

### Key Relationships
1. **TICKER** is the universal join key across all tables
2. **DATE** formats vary by table:
   - Financial: 'YYYYQX' or 'YYYY'
   - Banking: YEARREPORT + LENGTHREPORT
   - Market: DATETIME
3. **Sector_Map** provides classification for all tickers
4. **BankingMetrics** includes both individual banks and aggregates

---

## Data Update Patterns

### Daily Updates
- **MarketCap**: Full replacement with latest snapshot
- **Valuation**: Incremental addition of new trading day
- **MarketIndex**: Incremental addition of new trading day

### Weekly Updates
- **FA_Quarterly**: Incremental update for reporting companies
- **FA_Annual**: Incremental update (mainly during annual reporting season)

### Quarterly Updates
- **BankingMetrics**: Full refresh with new quarter data
- **Banking_Comments**: Manual updates as analysis completed

### Annual Updates
- **BankingMetrics (Forecast)**: Forecast data refresh with ACTUAL=0
- Updates when new analyst projections available
- Processed through equation solver for complex formulas

### On-Demand Updates
- **Sector_Map**: When new listings or reclassifications occur
- **Forecast Data**: Can be updated as new projections become available

---

## Query Examples

### 1. Get latest financials for a ticker
```sql
SELECT KEYCODE, VALUE, YoY
FROM FA_Quarterly
WHERE TICKER = 'VNM'
  AND DATE = (SELECT MAX(DATE) FROM FA_Quarterly WHERE TICKER = 'VNM')
ORDER BY KEYCODE
```

### 2. Banking peer comparison
```sql
SELECT TICKER, BANK_TYPE,
       [LDR] as LoanDeposit,
       [NPL] as NPL_Ratio,
       [ROE] as ReturnEquity
FROM BankingMetrics
WHERE YEARREPORT = 2024 AND LENGTHREPORT = 2
  AND TICKER IN ('VCB', 'CTG', 'BID', 'TCB', 'MBB')
ORDER BY [ROE] DESC
```

### 3. Sector performance overview
```sql
SELECT s.Sector,
       COUNT(DISTINCT m.TICKER) as StockCount,
       AVG(m.CUR_MKT_CAP) as AvgMarketCap
FROM Sector_Map s
JOIN MarketCap m ON s.Ticker = m.TICKER
GROUP BY s.Sector
ORDER BY AvgMarketCap DESC
```

### 4. VN30 Index members valuation
```sql
SELECT s.Ticker, s.L1, v.[P/E], v.[P/B], v.[EV/EBITDA]
FROM Sector_Map s
JOIN Valuation v ON s.Ticker = v.TICKER
WHERE s.VNI = 'Y'
  AND v.TRADE_DATE = (SELECT MAX(TRADE_DATE) FROM Valuation)
ORDER BY v.[P/E]
```

---

## Data Quality Notes

### Common Data Patterns
- **NULL handling**: NULL values indicate data not available or not applicable
- **YoY calculations**: First year/quarter will have NULL YoY values
- **Banking aggregates**: TICKER values like 'SOCB' represent tier aggregates
- **Date formats**: Inconsistent across tables - use appropriate conversion

### Data Validation Rules
- All TICKER values should exist in Sector_Map
- Financial metrics should have consistent KEYCODEs
- Banking metrics CA.1-CA.26 follow specific calculation rules
- Ratios bounded by business logic (e.g., NPL typically < 5%)

### Known Limitations
- Historical data starts from 2016 (2017 for banking)
- Some companies may have incomplete quarterly data
- Banking metrics require auxiliary Excel files for full calculations
- Market data updated with 1-day lag

---

## Forecast Data Integration

### Overview
The BankingMetrics table supports both historical and forecast data, distinguished by the ACTUAL column:
- **ACTUAL = 1 (True)**: Historical data from actual financial statements
- **ACTUAL = 0 (False)**: Forecast data from analyst projections

### Forecast Data Source
Forecast data originates from `SIL.W_F_IRIS_FORECAST` table with the following characteristics:
- **Annual Only**: Forecast data has LENGTHREPORT = 5
- **Date Range**: Typically current year and next year (e.g., 2025-2026)
- **KEYCODE Mapping**: Uses IRIS_KEYCODE.csv to map human-readable codes to banking formulas

### Equation Solving
Forecast data often contains high-level metrics that require equation solving:

| Forecast KEYCODE | Formula | Resolution |
|------------------|---------|------------|
| Customer_loan | BS.13+BS.16 | Solver derives BS.16 if BS.13 known |
| CASA | (Nt.121+Nt.124+Nt.125)/Deposit | Complex calculation |
| LDR | Loan/Deposit | Derives Loan if Deposit known |

The pipeline includes an equation solver that:
1. Parses formulas with operations (+, -, *, /)
2. Builds systems of equations from available data
3. Iteratively solves for unknown banking metrics
4. Converts results to standard BS.XX, IS.XX format

### Query Examples with Forecast Data

#### Compare Actual vs Forecast
```sql
SELECT TICKER, YEARREPORT,
       CASE WHEN ACTUAL = 1 THEN 'Historical' ELSE 'Forecast' END as DataType,
       [ROA] as ROA, [ROE] as ROE, [NPL] as NPL_Ratio
FROM BankingMetrics
WHERE TICKER = 'VCB'
  AND YEARREPORT IN (2024, 2025)
ORDER BY YEARREPORT, ACTUAL DESC
```

#### Forecast Trend Analysis
```sql
SELECT TICKER, YEARREPORT,
       [Net Interest Income] as NII,
       [Loan] as TotalLoans,
       [LDR] as LoanDepositRatio
FROM BankingMetrics
WHERE ACTUAL = 0  -- Forecast only
  AND TICKER IN ('VCB', 'CTG', 'TCB')
ORDER BY TICKER, YEARREPORT
```

---

## Contact & Support
For questions about data definitions, calculations, or access:
- Pipeline Documentation: `.docs/` directory
- Column Mappings: `unified_pipeline/column_mappings.py`
- Banking Calculations: `unified_pipeline/banking_functions.py`

Last Updated: September 2024