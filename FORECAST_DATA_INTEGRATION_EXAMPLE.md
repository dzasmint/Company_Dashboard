# Forecast Data Integration - VHM Example

## Expected JSON Output for VHM 2Q25

Based on the `forecast_data_extractor.py` logic, here's what the system will extract from MongoDB CompanyForecast collection:

```json
{
  "company": "Vinhomes JSC",
  "ticker": "VHM",
  "period": {
    "quarter": "2Q25",
    "comparison_quarters": [],
    "fiscal_year_half": "1H",
    "as_of_date": null
  },
  "source": {
    "file_name": "forecast_data_VHM_2Q25.json",
    "file_type": "forecast_data",
    "publisher": "Internal Forecast Model",
    "publish_date": "2025-10-04T...",
    "version_note": "Automated extraction from MongoDB CompanyForecast"
  },
  "currency": "VND",
  "units": "bn",
  
  "forecast_data": {
    "data_source": "mongodb_forecast",
    "extraction_date": "2025-10-04T...",
    
    "fy_forecast": {
      "year": 2025,
      "revenue_fy": 45000.00,
      "npatmi_fy": 12000.00,
      "ebitda_fy": 20000.00,
      "gross_profit_fy": 25000.00
    },
    
    "ytd_progress": {
      "quarter": "2Q25",
      "quarter_num": 2,
      "expected_progress_pct": 50.0,
      
      "revenue_ytd_actual": 22000.00,
      "revenue_fy_forecast": 45000.00,
      "revenue_achievement_pct": 48.9,
      "revenue_status": "on_track",
      
      "npatmi_ytd_actual": 5800.00,
      "npatmi_fy_forecast": 12000.00,
      "npatmi_achievement_pct": 48.3,
      "npatmi_status": "on_track",
      
      "remaining_quarters": 2,
      "remaining_revenue_implied": 23000.00,
      "remaining_npatmi_implied": 6200.00
    },
    
    "valuation_metrics": {
      "current_price": 55000,
      "rnav_per_share": 62000,
      "rnav_upside_pct": 12.7,
      "rnav_discount_pct": -11.3,
      
      "trailing_pe": 15.5,
      "current_year_pe": 12.3,
      "next_year_pe": 10.8,
      "mean_pe": 14.2,
      
      "trailing_pb": 1.2,
      "current_year_pb": 1.1,
      "next_year_pb": 1.0,
      "mean_pb": 1.3
    }
  }
}
```

---

## How the Data is Calculated

### **1. FY Forecast Extraction**
From MongoDB `CompanyForecast.forecast_data['2025'].pnl`:
- `revenue_fy`: 45,000 bn VND
- `npatmi_fy`: 12,000 bn VND
- `ebitda_fy`: 20,000 bn VND
- `gross_profit_fy`: 25,000 bn VND

### **2. YTD Progress Calculation**

For Q2 2025 (quarter_num = 2):

**YTD Actuals:**
- Sum Q1 2025 + Q2 2025 from `financial_data`
- `revenue_ytd_actual` = Q1 revenue + Q2 revenue
- `npatmi_ytd_actual` = Q1 NPATMI + Q2 NPATMI

**Achievement %:**
```python
revenue_achievement_pct = (22,000 / 45,000) * 100 = 48.9%
npatmi_achievement_pct = (5,800 / 12,000) * 100 = 48.3%
```

**Expected Progress:**
```python
expected_progress_pct = (2 / 4) * 100 = 50%  # Q2 = 50% of year
```

**Status Determination:**
```python
if achievement >= expected + 5%:  status = "ahead"
elif achievement <= expected - 5%:  status = "behind"
else:  status = "on_track"

# For VHM:
48.9% is within 45-55% range → "on_track"
48.3% is within 45-55% range → "on_track"
```

**Remaining Targets:**
```python
remaining_quarters = 4 - 2 = 2  # Q3 and Q4 left
remaining_revenue_implied = 45,000 - 22,000 = 23,000 bn
remaining_npatmi_implied = 12,000 - 5,800 = 6,200 bn
```

### **3. Valuation Metrics Extraction**

From MongoDB `CompanyForecast.valuation_data`:

**RNAV Metrics:**
```python
current_price = 55,000 VND
rnav_per_share = 62,000 VND

rnav_upside_pct = ((62,000 / 55,000) - 1) * 100 = 12.7%
rnav_discount_pct = ((55,000 / 62,000) - 1) * 100 = -11.3%
```

**Trading Multiples:**
- `trailing_PE`: 15.5x
- `2025F_PE`: 12.3x
- `2026F_PE`: 10.8x
- `mean_PE`: 14.2x
- `trailing_PB`: 1.2x
- `2025F_PB`: 1.1x
- `2026F_PB`: 1.0x
- `mean_PB`: 1.3x

---

## How It Appears in the Report

### **Slide 7 (Guidance & Outlook):**

```markdown
**FY Forecast Progress:**
- FY 2025 targets: Revenue 45,000 bn, NPATMI 12,000 bn
- YTD actual: Revenue 22,000 bn (48.9% of FY), NPATMI 5,800 bn (48.3% of FY)
- Status: On track (expected 50% at Q2)
- Remaining 2 quarters need: 23,000 bn revenue, 6,200 bn NPATMI to hit FY target
```

### **Slide 8 (Valuation):**

```markdown
**Our Valuation:**
- Current price: 55,000 VND
- RNAV per share: 62,000 VND
- Upside to RNAV: 12.7%

**Trading Multiples:**
- Trailing P/E: 15.5x
- 2025F P/E: 12.3x (vs mean 14.2x - trading at 13% discount to historical)
- 2026F P/E: 10.8x
- Trailing P/B: 1.2x, 2025F P/B: 1.1x
```

---

## Data Flow

```
1. User clicks "Generate Report" for VHM 2Q25
   ↓
2. System loads from MongoDB: CompanyForecast.find({"ticker": "VHM"})
   ↓
3. Extracts forecast_data['2025'] for FY targets
   ↓
4. Sums Q1 + Q2 actuals from financial_data for YTD
   ↓
5. Calculates: 22,000 / 45,000 = 48.9% achievement
   ↓
6. Determines status: 48.9% vs 50% expected = "on_track"
   ↓
7. Calculates remaining: 45,000 - 22,000 = 23,000 bn needed
   ↓
8. Extracts valuation_data: RNAV, P/E, P/B
   ↓
9. ChatGPT receives forecast_data in INPUT DATA
   ↓
10. Report shows FY progress and valuation! ✅
```

---

## Testing Within Streamlit

To see the actual data for VHM:

1. Go to Quarterly Earnings tab
2. Select VHM from sidebar
3. Select 2Q25
4. Click "Generate Report"
5. System will automatically:
   - Load VHM forecast from MongoDB
   - Calculate YTD from Q1+Q2 actuals
   - Extract RNAV and multiples
   - Show progress message
6. Report will include Slides 7 & 8 with forecast data

The integration is complete and ready to test! 🎯

