# Quarterly Earnings Schema Update

## ✅ Update Complete

The quarterly earnings extraction system has been updated to use your comprehensive **`quarterly_analysis.json`** schema for all document types.

---

## 🎯 What Changed

### 1. **Unified Schema Integration**
- All three document types (earnings presentations, sell-side reports, user commentary) now use the **same unified JSON schema**
- Schema file: `utils/quarterly_analysis.json`
- Schema is loaded at initialization and used for all extractions

### 2. **Updated Extraction Logic**

#### `utils/quarterly_earnings_extractor.py`
- Added `_load_schema()` method to load the JSON schema
- Completely rewrote all three extraction methods:
  - `extract_from_earnings_presentation()`
  - `extract_from_sellside_report()`
  - `extract_from_user_commentary()`
- Each method now:
  - Passes the complete schema to ChatGPT
  - Provides detailed instructions on how to populate each section
  - Ensures consistent data structure across all document types

#### `utils/quarterly_report_generator.py`
- Updated `_prepare_data_for_summary()` to handle the new schema structure
- Now properly aggregates data from the unified schema format:
  - `headline` (financial metrics)
  - `recognition_drivers` (project contributions)
  - `presales` (contracted sales, launches)
  - `balance_sheet` (assets, debt, equity)
  - `one_offs_and_events` (special items)
  - `outlook_and_guidance` (forward-looking statements)

---

## 📊 New Schema Structure

Your `quarterly_analysis.json` schema includes:

### Core Sections:
1. **Company & Period** - Company name, quarter, comparison periods
2. **Source** - File metadata, publisher, version
3. **Currency & Units** - VND, billions
4. **Headline** - P&L metrics (revenue, profit, margins, YoY/QoQ)
5. **Recognition Drivers** - Projects contributing, BCC, bulk sales
6. **Presales** - Contracted sales, units, launches, backlog
7. **Balance Sheet** - Assets, debt, equity, leverage metrics
8. **One-offs & Events** - Non-recurring items, corporate actions
9. **Outlook & Guidance** - FY targets, pipeline, management quotes
10. **Methodology** - Parsing notes, assumptions, confidence

---

## 🔄 Extraction Behavior by Document Type

### Earnings Presentations
- `source.file_type` = "management"
- Extracts actual reported figures
- High confidence scores (80-95%)
- Comprehensive P&L, presales, and balance sheet data

### Sell-Side Reports
- `source.file_type` = "sell_side"
- Extracts both actuals AND analyst estimates
- Notes distinguish actuals from forecasts
- Medium-high confidence (70-85%)
- Includes analyst commentary in outlook section

### User Commentary
- `source.file_type` = "management" or "sell_side" (context-dependent)
- `source.publisher` = "User Commentary"
- Primarily qualitative observations
- Lower confidence (30-60%)
- Focuses on:
  * Sentiment and tone
  * Strategic insights
  * Management observations
  * Concerns and opportunities
- Most quantitative fields remain null
- Rich use of notes fields

---

## 💾 MongoDB Storage

### Collection: `QuarterlyEarningsData`
Each document now follows this structure:
```javascript
{
  ticker: "VHM",
  company_name: "Vinhomes JSC",
  quarter: "2Q25",
  year: 2025,
  quarter_num: 2,
  
  // Follows quarterly_analysis.json schema
  company: "Vinhomes JSC",
  period: {...},
  source: {...},
  currency: "VND",
  units: "bn",
  headline: {...},
  recognition_drivers: {...},
  presales: {...},
  balance_sheet: {...},
  one_offs_and_events: [...],
  outlook_and_guidance: {...},
  methodology: {...}
}
```

---

## 📝 Key Improvements

### 1. **Consistency**
- All data follows the same structure regardless of source
- Easy to aggregate and compare across documents

### 2. **Comprehensiveness**
- Captures much more detail than previous schema:
  - Project-level revenue recognition
  - Presales by project and product mix
  - Debt mix (currency, maturity, rates)
  - Leverage metrics
  - One-off events with impact assessment

### 3. **Real Estate Specific**
- Fields tailored for real estate developers:
  - Contracted sales vs recognized revenue
  - Unbilled backlog
  - BCC contribution
  - Land bank changes
  - Project pipeline

### 4. **Data Quality Tracking**
- `methodology.confidence_pct` - Data quality score
- `methodology.parsing_notes` - Extraction challenges
- `methodology.assumptions` - Assumptions made
- Source tracking for each data point

---

## 🚀 Usage

### No Changes Needed!
The API remains the same. Simply use the tab as before:
1. Upload document
2. Review extracted data (now in new schema format)
3. Save to MongoDB
4. Generate summary reports

### What You'll Notice:
- **More structured data** in the AI Analysis tab
- **Richer detail** especially for presales and projects
- **Better tracking** of data sources and confidence
- **Consistent format** across all document types

---

## 🧪 Testing Recommendations

1. **Test with each document type:**
   - Upload an earnings presentation
   - Upload a sell-side report
   - Add user commentary

2. **Verify schema compliance:**
   - Check that all sections are populated correctly
   - Ensure null values where data is missing
   - Confirm confidence scores are appropriate

3. **Review summary generation:**
   - Generate report combining all three sources
   - Verify data aggregation works correctly
   - Check that sources are properly attributed

---

## 📋 Next Steps (Optional)

If you want to further enhance the system:

1. **Add validation** - Validate extracted JSON against schema
2. **Custom fields** - Add company-specific fields to schema
3. **Data enrichment** - Cross-reference with historical data
4. **Export to Excel** - Create formatted Excel reports with the structured data
5. **Comparison views** - Quarter-over-quarter diff visualization

---

## ✅ Files Modified

1. `utils/quarterly_earnings_extractor.py` - Schema-based extraction
2. `utils/quarterly_report_generator.py` - Schema-aware aggregation
3. `utils/quarterly_analysis.json` - **Your comprehensive schema** (already existed)

No changes to:
- UI components (`tabs/quarterly_earnings.py`)
- MongoDB utils
- Manager orchestration

---

## 🎉 Result

You now have a **professional-grade quarterly earnings extraction system** that:
- Uses a unified, comprehensive schema
- Handles multiple document types consistently
- Captures real estate-specific metrics
- Tracks data quality and sources
- Generates structured, comparable data

Ready to extract quarterly earnings data with precision! 📊
