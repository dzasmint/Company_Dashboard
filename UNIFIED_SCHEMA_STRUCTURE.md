# ✅ Unified JSON Schema Structure for Quarterly Earnings

## 🎯 Overview

All quarterly earnings documents (management presentations, sell-side reports, buy-side commentary, and financial data) now follow **one consistent JSON schema** defined in `utils/quarterly_analysis.json`.

This ensures:
- **Consistency**: All data follows the same structure regardless of source
- **Easy aggregation**: Multiple sources can be merged and compared
- **Simplified reporting**: Report generation works with a single schema
- **Type safety**: Clear data structure for all operations

---

## 📋 Schema Structure

### **Top-Level Fields (Common to All Document Types)**

All documents have these top-level fields:

```json
{
  "company": "Vinhomes JSC",
  "ticker": "VHM",
  "period": {
    "quarter": "2Q25",
    "comparison_quarters": ["1Q25", "2Q24"],
    "fiscal_year_half": "1H|2H",
    "as_of_date": "2025-07-15"
  },
  "source": {
    "file_name": "earnings_VHM_2Q25.pdf",
    "file_type": "management|sell_side|buy_side|financial_data",
    "publisher": "Vinhomes|Vietcap|User Commentary|Internal Database",
    "publish_date": "2025-07-20",
    "pages_covered": "1-45",
    "version_note": "Original extraction"
  },
  "currency": "VND",
  "units": "bn",
  "accounting_basis": "VAS|IFRS|USGAAP|Unknown"
}
```

### **Data Sections**

All documents include these sections (populated based on document type):

```json
{
  "headline": { /* P&L metrics */ },
  "recognition_drivers": { /* Project contributions */ },
  "presales": { /* Sales pipeline */ },
  "balance_sheet": { /* Assets, debt, equity */ },
  "one_offs_and_events": [ /* Special items */ ],
  "outlook_and_guidance": { /* Forward-looking */ },
  
  "management_commentary": { /* Populated if source.file_type = "management" */ },
  "sell_side_commentary": { /* Populated if source.file_type = "sell_side" */ },
  "buy_side_commentary": { /* Populated if source.file_type = "buy_side" */ },
  "financial_data": { /* Populated if source.file_type = "financial_data" */ },
  
  "methodology": { /* Extraction metadata */ }
}
```

---

## 🔄 Document Type Differences

### **1. Management Presentations** (`source.file_type = "management"`)

**What's Populated:**
- ✅ `headline` - Reported financial metrics
- ✅ `recognition_drivers` - Project-level revenue details
- ✅ `presales` - Contracted sales, new launches
- ✅ `balance_sheet` - Debt, equity, leverage
- ✅ `outlook_and_guidance` - FY targets and guidance
- ✅ `management_commentary` - **Primary section**
  - `outlook_summary`
  - `guidance_update`
  - `strategic_priorities`
  - `catalysts_and_risks`

**What's Empty:**
- ❌ `sell_side_commentary`
- ❌ `buy_side_commentary`
- ❌ `financial_data`

**Example:**
```json
{
  "source": {
    "file_type": "management",
    "publisher": "Vinhomes"
  },
  "headline": {
    "revenue_reported": 15000,
    "npATMI": 5800,
    "npATMI_yoy_pct": 25.5
  },
  "management_commentary": {
    "outlook_summary": "Strong H2 pipeline with multiple launches planned",
    "guidance_update": {
      "adjusted_revenue_target_fy": 45000,
      "guidance_change": "maintain"
    }
  }
}
```

---

### **2. Sell-Side Reports** (`source.file_type = "sell_side"`)

**What's Populated:**
- ✅ `headline` - May include actuals or estimates
- ✅ `presales` - Sales performance commentary
- ✅ `balance_sheet` - Leverage analysis
- ✅ `sell_side_commentary` - **Primary section**
  - `analyst_view_summary`
  - `result_vs_expectation` (beat/miss)
  - `guidance_reaction`
  - `forecast_changes`
  - `rating_target` (TP, rating)
  - `model_changes`
  - `catalysts_and_risks`

**What's Empty:**
- ❌ `management_commentary`
- ❌ `buy_side_commentary`
- ❌ `financial_data`

**Example:**
```json
{
  "source": {
    "file_type": "sell_side",
    "publisher": "Vietcap Securities"
  },
  "headline": {
    "revenue_reported": 15000,
    "npATMI": 5800
  },
  "sell_side_commentary": {
    "analyst_view_summary": "Strong quarter driven by project handovers",
    "result_vs_expectation": {
      "label": "beat",
      "basis": "sell_side_forecast"
    },
    "rating_target": {
      "rating_current": "BUY",
      "target_price_current": 68000,
      "valuation_method": "DCF + RNAV"
    }
  }
}
```

---

### **3. Buy-Side Commentary** (`source.file_type = "buy_side"`)

**What's Populated:**
- ✅ `buy_side_commentary` - **Primary section**
  - `raw_bullets` - Original analyst notes
  - `classified_points` - Categorized observations
  - `valuation_analysis` - RNAV, target price
  - `key_takeaways_summary`

**What's Empty:**
- ❌ `management_commentary`
- ❌ `sell_side_commentary`
- ❌ `financial_data`
- ⚠️ Other sections may be sparsely populated (qualitative only)

**Example:**
```json
{
  "source": {
    "file_type": "buy_side",
    "publisher": "User Commentary"
  },
  "buy_side_commentary": {
    "raw_bullets": [
      "Strong presales momentum in HCMC",
      "Leverage improving ahead of schedule"
    ],
    "classified_points": [
      {
        "category": "presales",
        "content": "Strong presales momentum in HCMC",
        "sentiment": "positive",
        "confidence_pct": 85
      }
    ],
    "valuation_analysis": {
      "rnav_per_share": 62000,
      "target_price": 65000,
      "upside_downside_pct": 18.5
    }
  }
}
```

---

### **4. Financial Data** (`source.file_type = "financial_data"`)

**What's Populated:**
- ✅ `financial_data` - **Primary section**
  - `current_quarter` - All 43 financial metrics
    - `income_statement` (21 metrics)
    - `balance_sheet` (15 metrics)
    - `cash_flow` (5 metrics)
    - `other_metrics` (2 metrics)
  - `qoq_comparison` - Previous quarter data
  - `yoy_comparison` - Same quarter last year data
  - `calculated_changes` - Pre-calculated % changes

**What's Empty:**
- ❌ `management_commentary`
- ❌ `sell_side_commentary`
- ❌ `buy_side_commentary`
- ❌ Most other sections (headline, presales, etc.)

**Example:**
```json
{
  "source": {
    "file_type": "financial_data",
    "publisher": "Internal Database"
  },
  "financial_data": {
    "data_source": "internal_database",
    "extraction_date": "2025-10-02T10:30:00",
    "current_quarter": {
      "quarter": "2Q25",
      "income_statement": {
        "net_revenue": 15234.56,
        "gross_profit": 8901.23,
        "gross_margin_pct": 58.4,
        "ebitda": 7234.56,
        "ebitda_margin_pct": 47.5,
        "npat": 5678.90,
        "npatmi": 5612.34
      },
      "balance_sheet": {
        "total_assets": 185000.00,
        "cash": 12345.67,
        "cash_equivalent": 3456.78,
        "st_debt": 15000.00,
        "lt_debt": 45000.00,
        "total_equity": 98000.00
      }
    },
    "qoq_comparison": {
      "quarter": "1Q25",
      "income_statement": { /* Previous quarter data */ }
    },
    "yoy_comparison": {
      "quarter": "2Q24",
      "income_statement": { /* Last year data */ }
    },
    "calculated_changes": {
      "qoq": {
        "net_revenue_pct": 8.5,
        "npatmi_pct": 12.3,
        "total_equity_pct": 3.2
      },
      "yoy": {
        "net_revenue_pct": 25.8,
        "npatmi_pct": 35.6,
        "total_equity_pct": 15.4
      }
    }
  }
}
```

---

## 💾 MongoDB Storage

### **Collection: `QuarterlyEarningsData`**

Each document is stored separately with:

```json
{
  "_id": ObjectId("..."),
  "document_id": "doc_12345",  // Links to QuarterlyEarningsDocuments
  "ticker": "VHM",
  "company_name": "Vinhomes JSC",
  "quarter": "2Q25",
  "year": 2025,
  "quarter_num": 2,
  "upload_date": ISODate("2025-10-02T..."),
  "last_updated": ISODate("2025-10-02T..."),
  
  // Complete unified schema
  "company": "Vinhomes JSC",
  "ticker": "VHM",
  "period": { /* ... */ },
  "source": { /* ... */ },
  "currency": "VND",
  "units": "bn",
  "accounting_basis": "VAS",
  "headline": { /* ... */ },
  "presales": { /* ... */ },
  "balance_sheet": { /* ... */ },
  "management_commentary": { /* ... */ },
  "sell_side_commentary": { /* ... */ },
  "buy_side_commentary": { /* ... */ },
  "financial_data": { /* ... */ },
  "methodology": { /* ... */ }
}
```

### **Key Points:**
- Each uploaded document creates a **separate MongoDB document**
- Multiple sources for the same quarter coexist (no merging at storage)
- Query by `(ticker, quarter)` returns **array of all sources**
- Report generation combines all sources intelligently

---

## 🔍 Querying Data

### **Get All Data for a Quarter:**
```python
data = mongo_helper.get_quarterly_earnings_data("VHM", "2Q25")
# Returns: [management_doc, sellside_doc, buyside_doc, financial_data_doc]
```

### **Filter by Source Type:**
```python
financial_data = [d for d in data if d['source']['file_type'] == 'financial_data']
management = [d for d in data if d['source']['file_type'] == 'management']
```

### **Extract Financial Metrics:**
```python
if doc['source']['file_type'] == 'financial_data':
    revenue = doc['financial_data']['current_quarter']['income_statement']['net_revenue']
    qoq_change = doc['financial_data']['calculated_changes']['qoq']['net_revenue_pct']
```

---

## 📊 Report Generation

The report generator receives **all documents** for a quarter and:

1. **Identifies document types** by `source.file_type`
2. **Prioritizes financial_data** for reported numbers
3. **Uses management_commentary** for official guidance
4. **Uses sell_side_commentary** for consensus view
5. **Uses buy_side_commentary** for our internal view
6. **Cross-checks** claims against financial_data actuals

**Priority Hierarchy:**
1. **Buy-side commentary** = primary narrative
2. **Financial data** = ground truth for numbers
3. **Management** = strategic context
4. **Sell-side** = market consensus

---

## ✅ Benefits of Unified Schema

### **1. Consistency**
- All documents follow the same structure
- Easy to understand and maintain
- Type-safe operations

### **2. Flexibility**
- Each document type populates relevant sections
- Empty sections don't cause errors
- Can mix and match sources

### **3. Scalability**
- Easy to add new document types
- New fields can be added to schema
- Backward compatible

### **4. Intelligent Merging**
- Report generator knows which sections to use
- Can compare across sources
- Handles conflicts gracefully

### **5. Data Integrity**
- Financial data serves as ground truth
- Can verify management/sell-side claims
- Audit trail through source metadata

---

## 🔧 Implementation Files

| File | Purpose |
|------|---------|
| `utils/quarterly_analysis.json` | **Master schema definition** |
| `utils/financial_data_extractor.py` | Extracts financial data in unified format |
| `utils/quarterly_earnings_extractor.py` | Extracts management/sell-side/buy-side |
| `utils/quarterly_earnings_manager.py` | Orchestrates all extractions |
| `utils/quarterly_report_generator.py` | Generates reports from unified schema |
| `utils/mongodb_utils.py` | Stores/retrieves unified documents |

---

## 📝 Usage Examples

### **Example 1: Upload Management Presentation**
1. User uploads PDF
2. `QuarterlyEarningsExtractor.extract_from_earnings_presentation()`
3. Returns data with `source.file_type = "management"`
4. `management_commentary` section populated
5. Saved to MongoDB

### **Example 2: Process Financial Data**
1. User clicks "Process Financial Data"
2. `FinancialDataExtractor.extract_quarterly_data()`
3. Returns data with `source.file_type = "financial_data"`
4. `financial_data` section populated with 3 quarters
5. Saved to MongoDB

### **Example 3: Generate Report**
1. User requests report for VHM 2Q25
2. System queries MongoDB for all documents
3. Gets 4 documents: management, sell-side, buy-side, financial_data
4. Report generator combines all sources
5. Produces PowerPoint-ready markdown

---

## 🎯 Key Takeaways

✅ **One schema** for all document types  
✅ **Source type** identified by `source.file_type`  
✅ **Each type** populates its primary section  
✅ **Empty sections** are valid and expected  
✅ **Financial data** provides ground truth  
✅ **MongoDB** stores each source separately  
✅ **Reports** intelligently merge all sources  

This unified structure ensures **consistency**, **flexibility**, and **data integrity** across the entire quarterly earnings workflow.

