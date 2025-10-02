# 🔢 Financial Data Integration - Quick Visual Guide

## 📊 **What We Have**

**FA_processed.parquet contains 43 financial metrics:**

### Income Statement (21 metrics)
- Net_Revenue, COGS, Gross_Profit, Gross_Margin
- GA_Expense, Selling_Expense, Dep_Expense
- EBIT, EBIT_Margin, EBITDA, EBITDA_Margin
- Financial_Income, Financial_Expense, Interest_Expense
- PBT, Tax, Eff_Tax_Rate
- NPAT, NPAT_Margin, Minority_Interest_In_Earning, NPATMI

### Balance Sheet (15 metrics)
- Total_Asset, Cash, Cash_Equivalent, Short_Investment
- Account_Receivable, Inventory, Tangible_Fixed_Asset
- Total_Liabilities, Account_Payable, Advance_From_Custmers
- ST_Debt, LT_Debt
- TOTAL_Equity, Retain_Earning, Minority_Interest

### Cash Flow (5 metrics)
- Operating_CF, Inv_CF, Fin_CF, Capex, FCF

### Other (2 metrics)
- OS (Outstanding Shares), Invested_Capital

---

## 🎯 **Proposed Schema Structure**

### **Option B (RECOMMENDED):** Current + 2 Comparisons

```json
{
  "financial_data": {
    "data_source": "internal_database",
    "extraction_date": "2025-10-01",
    
    // CURRENT QUARTER
    "current_quarter": {
      "quarter": "2Q25",
      "income_statement": {
        "net_revenue": 19022.22,      // in billions VND
        "cogs": -14498.38,
        "gross_profit": 4523.84,
        "gross_margin_pct": 23.8,
        "ebit": 2976.65,
        "ebit_margin_pct": 15.6,
        "ebitda": 3500.12,
        "ebitda_margin_pct": 18.4,
        "npat": 8348.17,
        "npat_margin_pct": 43.9,
        "npatmi": 7553.45
      },
      "balance_sheet": {
        "total_assets": 658041.9,
        "cash": 15000.5,
        "inventory": 80135.51,
        "st_debt": 30000.0,
        "lt_debt": 44093.26,
        "total_equity": 230736.0
      },
      "cash_flow": {
        "operating_cf": 49823.19,
        "capex": 842.60,
        "fcf": 48980.59
      }
    },
    
    // PREVIOUS QUARTER (for QoQ)
    "qoq_comparison": {
      "quarter": "1Q25",
      "income_statement": {...},
      "balance_sheet": {...},
      "cash_flow": {...}
    },
    
    // PREVIOUS YEAR SAME QUARTER (for YoY)
    "yoy_comparison": {
      "quarter": "2Q24",
      "income_statement": {...},
      "balance_sheet": {...},
      "cash_flow": {...}
    },
    
    // PRE-CALCULATED CHANGES
    "calculated_changes": {
      "qoq": {
        "net_revenue_pct": 12.5,      // 2Q25 vs 1Q25
        "gross_profit_pct": 8.3,
        "npat_pct": 8.2,
        "npatmi_pct": 7.8,
        "inventory_pct": 5.2,
        "total_equity_pct": 3.1
      },
      "yoy": {
        "net_revenue_pct": 23.8,      // 2Q25 vs 2Q24
        "gross_profit_pct": 18.5,
        "npat_pct": 15.5,
        "npatmi_pct": 14.2,
        "inventory_pct": -8.3,
        "total_equity_pct": 12.4
      }
    }
  }
}
```

---

## 🎨 **User Experience**

### **Current Workflow** (Before)
```
1. Upload management presentation  → Manual file upload
2. Upload sell-side report        → Manual file upload
3. Add buy-side commentary        → Manual text input
4. Generate report                → ChatGPT uses 3 sources
```

### **New Workflow** (After)
```
1. Process financial data         → ✨ ONE CLICK! (automated)
2. Upload management presentation → Manual file upload
3. Upload sell-side report        → Manual file upload
4. Add buy-side commentary        → Manual text input
5. Generate report                → ChatGPT uses 4 sources (with complete financial data!)
```

---

## 💡 **Example Use Case**

### **Scenario: VHM 2Q25 Analysis**

**What user does:**
1. Select: Ticker = VHM, Quarter = 2Q25
2. Click: "🔢 Process Financial Data"
3. Wait 2-3 seconds

**What happens:**
```
✓ Extracting data for VHM 2Q25...
✓ Loading comparison quarters (1Q25, 2Q24)...
✓ Calculating QoQ and YoY changes...
✓ Saving to MongoDB...
✅ Financial data processed successfully!
```

**What gets saved:**
- Complete P&L, Balance Sheet, Cash Flow for 2Q25
- Same for 1Q25 and 2Q24
- All percentage changes calculated
- Stored as separate document in MongoDB

**What report generator sees:**
```
FINANCIAL DATA (from internal database):

2Q25 Results:
- Revenue: 19,022 bn VND (+12.5% QoQ, +23.8% YoY)
- NPATMI: 7,553 bn VND (+7.8% QoQ, +14.2% YoY)
- Gross margin: 23.8% (+0.5pp QoQ)
- Operating cash flow: 49,823 bn VND

Balance Sheet:
- Total assets: 658,042 bn VND
- Net debt: 59,093 bn VND
- Inventory: 80,136 bn VND (-8.3% YoY)

MANAGEMENT COMMENTARY:
"Strong quarter driven by product mix..."

SELL-SIDE VIEW:
"Beat expectations, upgrade to BUY..."

BUY-SIDE THESIS:
"Undervalued, RNAV upside..."
```

---

## ⚖️ **Three Options Compared**

| Feature | Option A<br/>Current Only | Option B<br/>Current + 2 | Option C<br/>Full History |
|---------|-------------|--------------|---------------|
| **Document Size** | ~50 KB | ~150 KB | ~500 KB |
| **QoQ Comparison** | ❌ Need query | ✅ Built-in | ✅ Built-in |
| **YoY Comparison** | ❌ Need query | ✅ Built-in | ✅ Built-in |
| **Trend Analysis** | ❌ | ❌ | ✅ |
| **Report Complexity** | High | Low | Low |
| **Storage** | Minimal | Moderate | High |
| **My Recommendation** | ❌ | ✅ ⭐ | ❌ |

**Why Option B?**
- Contains exactly what quarterly reports need (current + 2 comparisons)
- Pre-calculated changes = simpler report generation
- Reasonable document size
- No redundant data

---

## 🔄 **Integration Flow**

```
┌─────────────────────────────────────────────────────────────┐
│  User selects: VHM, 2Q25, Document Type = "Financial Data" │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │  Click "Process Financial   │
        │        Data" Button         │
        └─────────────┬───────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │  FinancialDataExtractor     │
        │  - Calculate comparisons    │
        │  - Load FA_processed.parquet│
        │  - Filter for VHM           │
        │  - Extract 3 quarters       │
        │  - Calculate changes        │
        │  - Structure to JSON        │
        └─────────────┬───────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │  QuarterlyEarningsManager   │
        │  - Create metadata          │
        │  - Prepare document         │
        └─────────────┬───────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │  Save to MongoDB            │
        │  Collection:                │
        │  QuarterlyEarningsData      │
        │  - ticker: VHM              │
        │  - quarter: 2Q25            │
        │  - source.file_type:        │
        │    "financial_data"         │
        └─────────────┬───────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │  Display in UI              │
        │  ✅ Show in document list   │
        │  ✅ Allow review            │
        │  ✅ Include in report gen   │
        └─────────────────────────────┘
```

---

## ✅ **Benefits Summary**

### **For Users:**
- ⚡ **Fast:** One click vs manual data entry
- ✅ **Accurate:** No transcription errors
- 🔄 **Consistent:** Same source for all analyses
- 📊 **Complete:** All 43 metrics captured

### **For Reports:**
- 🎯 **Data-driven:** Hard numbers to support analysis
- 🔍 **Verification:** Cross-check management claims
- 📈 **Context:** See trends (QoQ, YoY)
- 💡 **Insights:** ChatGPT can spot anomalies

### **For System:**
- 🏗️ **Structured:** Clean JSON schema
- 🔗 **Integrated:** Works with existing workflow
- 💾 **Stored:** MongoDB for future reference
- 🔧 **Maintainable:** Single source of truth

---

## ❓ **Quick Decision Guide**

**Answer these 4 questions:**

1. **Data scope?**
   - [ ] A: Current quarter only
   - [ ] B: Current + 2 comparisons ⭐ **(recommended)**
   - [ ] C: Full historical

2. **Behavior?**
   - [ ] Automatic (always extract)
   - [ ] Manual (user clicks button) ⭐ **(recommended)**

3. **Allow both financial_data AND management presentation?**
   - [ ] Yes ⭐ **(recommended - provides both numbers & context)**
   - [ ] No (exclusive)

4. **Unit conversion?**
   - [ ] Store raw (e.g., 19022220000000)
   - [ ] Convert to billions (e.g., 19022.22) ⭐ **(recommended - matches schema)**

---

## 🚀 **Ready to Implement?**

Just confirm your choices and I'll start building! 🛠️

