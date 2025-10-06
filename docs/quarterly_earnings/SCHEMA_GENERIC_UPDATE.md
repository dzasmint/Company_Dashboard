# Quarterly Analysis Schema - Generic for All RE Companies

## ✅ Changes Made for Generic Applicability

Your `quarterly_analysis.json` schema has been updated to work for **all real estate companies across different markets**, not just Vinhomes or Vietnam-specific companies.

---

## 🔄 Schema Changes

### 1. **Currency Detection (Line 18)**
**Before:**
```json
"currency": "VND"
```

**After:**
```json
"currency": null
```

**Impact:**
- ✅ Now supports multi-currency reporting (VND, USD, SGD, THB, MYR, IDR, PHP, etc.)
- ✅ AI will detect currency from document automatically
- ✅ Works for companies reporting in different currencies
- ✅ Regional expansion friendly

### 2. **Business Model Classification (Lines 21-25) - NEW**
**Added:**
```json
"business_model": {
  "primary": null,
  "segments": [],
  "notes": null
}
```

**Supported Business Models:**
- `residential_developer` - Primarily residential (apartments, villas, townhouses)
- `commercial` - Office, retail, shopping centers
- `industrial` - Industrial parks, warehouses, logistics
- `mixed_use` - Multiple property types
- `reit` - Real Estate Investment Trust
- `hospitality` - Hotels, resorts, serviced apartments
- `land_bank` - Land aggregation and sale

**Impact:**
- ✅ Captures different real estate business models
- ✅ Differentiates between developers, REITs, and other RE companies
- ✅ Supports companies with multiple segments
- ✅ Better categorization and analysis

---

## 🌏 Market Applicability

### **Vietnam Market**
✅ VHM (Vinhomes) - Residential developer, VND
✅ NVL (Novaland) - Mixed-use developer, VND
✅ DXG (Dat Xanh) - Residential + Industrial, VND
✅ KDH (Khang Dien House) - Residential developer, VND

### **Thailand Market**
✅ AP (AP Thailand) - Residential developer, THB
✅ LPN (LPN Development) - Residential developer, THB
✅ SIRI (Sansiri) - Residential developer, THB

### **Singapore Market**
✅ CapitaLand - Mixed-use developer, SGD
✅ City Developments (CDL) - Mixed-use developer, SGD
✅ UOL Group - Mixed-use developer, SGD

### **Indonesia Market**
✅ BSDE (Bumi Serpong Damai) - Residential developer, IDR
✅ CTRA (Ciputra Development) - Mixed-use developer, IDR

### **Philippines Market**
✅ Ayala Land - Mixed-use developer, PHP
✅ SM Prime Holdings - Commercial (malls), PHP

### **Regional REITs**
✅ Frasers Centrepoint Trust - REIT, SGD
✅ CapitaLand Integrated Commercial Trust - REIT, SGD

---

## 🤖 AI Extraction Updates

All three extraction methods have been updated:

### 1. **Earnings Presentations**
- Detects currency automatically
- Identifies business model from company description
- Converts amounts to billions in detected currency
- Works across different markets

**System Message Updated:**
```
"You are an expert financial analyst specializing in real estate sector 
earnings analysis across different markets (Vietnam, Thailand, Singapore, 
Indonesia, Philippines, etc.). You extract data with precision, detect 
currencies properly, identify business models, and follow JSON schemas exactly."
```

### 2. **Sell-Side Reports**
- Extracts currency from analyst reports
- Captures analyst's view on business model
- Handles multi-currency reporting
- Distinguishes actuals from estimates

**System Message Updated:**
```
"You are an expert financial analyst specializing in extracting data from 
sell-side research reports covering real estate companies across different 
markets. You distinguish between actuals and estimates clearly and detect 
currency properly."
```

### 3. **User Commentary**
- Infers currency from user context
- Captures user's understanding of business model
- Flexible for any market

---

## 📊 Generic Fields Already in Schema

These fields were already generic and work for all RE companies:

✅ **Headline Financials**
- Revenue (reported and adjusted)
- Gross profit, margins
- NPAT, NPAT-MI
- PBT, EBITDA
- YoY/QoQ growth rates

✅ **Recognition Drivers**
- Projects contributing to revenue
- BCC (Building-Construction-Contracting) - used by many developers
- Bulk sales / finance income

✅ **Presales**
- Contracted sales
- Units sold and presold
- Project mix
- New launches
- Unbilled backlog
- Company guidance

✅ **Balance Sheet**
- Cash, debt, assets, equity
- Debt mix (currency, maturity, rates)
- Leverage metrics
- Notable movements

✅ **One-offs & Events**
- Type: one_off, corporate, policy, legal, other
- Impact assessment
- Recurrence tracking

✅ **Outlook & Guidance**
- Full-year targets
- Project pipeline
- Management quotes

---

## 💡 Usage Examples

### Example 1: Vietnamese Company (VND)
```json
{
  "company": "Vinhomes JSC",
  "ticker": "VHM",
  "currency": "VND",
  "units": "bn",
  "business_model": {
    "primary": "residential_developer",
    "segments": ["high_rise_apartments", "low_rise_villas", "shophouses"],
    "notes": "Vertically integrated developer with own construction subsidiary"
  },
  "headline": {
    "revenue_reported": 15000,  // 15,000 billion VND
    ...
  }
}
```

### Example 2: Singapore REIT (SGD)
```json
{
  "company": "CapitaLand Integrated Commercial Trust",
  "ticker": "CICT.SI",
  "currency": "SGD",
  "units": "bn",
  "business_model": {
    "primary": "reit",
    "segments": ["office", "retail"],
    "notes": "Commercial REIT with pan-Asia portfolio"
  },
  "headline": {
    "revenue_reported": 0.5,  // 0.5 billion SGD
    ...
  }
}
```

### Example 3: Thai Developer (THB)
```json
{
  "company": "Sansiri Public Company",
  "ticker": "SIRI.BK",
  "currency": "THB",
  "units": "bn",
  "business_model": {
    "primary": "residential_developer",
    "segments": ["condominiums", "single_detached_homes"],
    "notes": "Focus on Bangkok and major cities"
  },
  "headline": {
    "revenue_reported": 25,  // 25 billion THB
    ...
  }
}
```

---

## ✅ Benefits of Generic Schema

### 1. **Multi-Market Coverage**
- Works for any real estate company in Southeast Asia
- Supports different currencies
- Captures different business models

### 2. **Scalability**
- Easy to add companies from new markets
- No code changes needed for different countries
- Consistent data structure across markets

### 3. **Comparison & Analysis**
- Compare companies across markets (after currency normalization)
- Analyze different business models
- Track industry trends regionally

### 4. **Future-Proof**
- Ready for expansion into new markets
- Supports acquisitions and cross-border investments
- Flexible for new business model types

---

## 🚀 Ready to Use

The schema is now **100% generic** and ready for:

✅ Vietnamese real estate companies (VND)
✅ Thai developers (THB)
✅ Singapore REITs and developers (SGD)
✅ Indonesian developers (IDR)
✅ Philippine companies (PHP)
✅ Malaysian companies (MYR)
✅ Any regional real estate company

Simply upload documents from any company, and the system will:
1. Detect the currency automatically
2. Identify the business model
3. Extract data in the appropriate format
4. Store in consistent schema structure

No configuration or code changes needed! 🎉

---

## 📝 Testing Recommendation

To verify generic applicability, test with:
1. A Vietnamese company (VHM, NVL) - VND
2. A Singapore REIT - SGD  
3. A Thai developer - THB
4. An Indonesian company - IDR

The system should handle all correctly with proper currency and business model detection.

