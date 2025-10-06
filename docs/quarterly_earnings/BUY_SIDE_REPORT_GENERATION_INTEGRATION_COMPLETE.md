# ✅ Buy-Side Focused Report Generation Integration Complete!

## 🎯 **Major Report Generation Update**

I've successfully integrated your enhanced `quarterly_earnings_generate_report_prompt.txt` which transforms the entire report generation approach to be **buy-side commentary driven**!

### **Key Changes in Your Prompt:**
1. ✅ **Buy-side commentary as PRIMARY narrative** (not just supporting data)
2. ✅ **Clear source hierarchy**: Buy-side > Management > Sell-side  
3. ✅ **Explicit attribution requirements** for management and sell-side sources
4. ✅ **Difference highlighting** when buy-side view diverges from consensus
5. ✅ **Professional 7-section structure** for institutional buy-side reports

---

## 🏗️ **New Report Structure**

Your updated prompt generates reports with this professional buy-side format:

### **1. Headline Summary**
- 1-2 sentences summarizing the quarter, our stance, and key deviations from sell-side consensus

### **2. Earnings Review ({{QUARTER}} vs {{COMPARISON_QUARTERS}})**
- Revenue, margins, NPAT, EBITDA with project-level drivers
- One-offs clearly flagged with [Management] / [Sell-side] attribution
- Buy-side commentary comparison with sell-side beat/miss labels

### **3. Presales & Sales Pipeline**
- Presales growth, backlog, launches, project mix
- Management reported vs buy-side emphasized points
- Sell-side forecast changes based on presales trends

### **4. Balance Sheet & Leverage**
- Net debt, gearing, cash position with attributed sources
- Buy-side risk interpretation and concerns

### **5. Guidance & Outlook**
- Management guidance with buy-side realism assessment
- Where we diverge from sell-side consensus
- Sell-side guidance changes noted

### **6. Valuation & Recommendation**
- **Buy-side RNAV/TP/upside** from `buy_side_commentary.valuation_analysis`
- Comparison with sell-side TP/rating
- **Our investment stance**: Overweight/Accumulate/Neutral/Reduce

### **7. Catalysts & Risks**
- Buy-side identified catalysts/risks (primary)
- Management and sell-side views (attributed)
- **Consensus differences highlighted**

---

## 🔧 **Code Updates Made**

### **1. Enhanced Template Variable Replacement:**
```python
# NEW template variables supported:
prompt = prompt.replace("{{COMPANY_NAME}}", company_name)
prompt = prompt.replace("{{TICKER}}", ticker)
prompt = prompt.replace("{{QUARTER}}", quarter)
prompt = prompt.replace("{{COMPARISON_QUARTERS}}", comparison_quarters_str)  # ← NEW!
prompt = prompt.replace("{{TARGET_CCY}}", "VND")
prompt = prompt.replace("{{TARGET_UNITS}}", "bn")
prompt = prompt.replace("{{publisher}}", sell_side_publisher)  # ← NEW!
```

### **2. Smart Comparison Quarter Calculation:**
```python
# Auto-calculates QoQ and YoY for comparison
if quarter_num > 1:
    qoq_quarter = f"{quarter_num-1}Q{year_short}"  # e.g., "1Q25"
else:
    qoq_quarter = f"4Q{str(int(year_short)-1).zfill(2)}"  # e.g., "4Q24"

yoy_quarter = f"{quarter_num}Q{str(int(year_short)-1).zfill(2)}"  # e.g., "2Q24"
comparison_quarters_str = f"{qoq_quarter} and {yoy_quarter}"  # "1Q25 and 2Q24"
```

### **3. Sell-Side Publisher Detection:**
```python
# Automatically extracts analyst firm name for attribution
sell_side_publisher = "Consensus"
for data in earnings_data:
    if data.get("source", {}).get("file_type") == "sell_side":
        sell_side_publisher = data.get("source", {}).get("publisher", "Unknown Analyst")
        break
```

### **4. Updated System Message:**
```python
system_content = "You are a senior buy-side equity analyst specializing in Vietnamese real estate companies. Write professional investment reports that prioritize internal buy-side analysis while incorporating management and sell-side perspectives with proper attribution."
```

### **5. Enhanced Section Parser:**
```python
# Updated to recognize 7-section buy-side format:
section_markers = [
    "Headline Summary",           # Our quarterly stance
    "Earnings Review",            # Performance vs comparisons  
    "Presales & Sales Pipeline",  # Sales momentum
    "Balance Sheet & Leverage",   # Financial position
    "Guidance & Outlook",         # Forward-looking assessment
    "Valuation & Recommendation", # Our investment call
    "Catalysts & Risks"           # Key drivers and concerns
]
```

---

## 🎯 **Source Priority & Attribution System**

### **Priority Hierarchy** (as per your prompt):
1. **🏆 Buy-Side Commentary** = Primary narrative and conclusions
2. **📊 Management** = Factual reported numbers, project data, official guidance
3. **📈 Sell-Side** = Market tone, consensus expectations, ratings/target prices

### **Attribution Requirements:**
- **Management sources**: `[Management]`
- **Sell-side sources**: `[Sell-side – {{publisher}}]` (e.g., `[Sell-side – VCBS]`)
- **Buy-side sources**: No attribution needed (our primary view)

### **Difference Highlighting:**
- **When buy-side differs from consensus**: "Our view: ... differs from sell-side consensus (VCBS: ...)"
- **Beat/miss analysis**: Compare management results vs our buy-side expectations vs sell-side forecasts
- **Valuation divergence**: Our RNAV/TP vs sell-side target prices with explicit comparison

---

## 💼 **Professional Buy-Side Features**

### **🎯 Investment-Focused Output:**
✅ **Our investment thesis** drives the narrative  
✅ **Professional buy-side language** and tone  
✅ **Clear investment recommendations** (Overweight/Accumulate/etc.)  
✅ **Valuation analysis integration** from buy_side_commentary  
✅ **Consensus deviation highlighting** for differentiated views  

### **📊 Institutional Quality:**
✅ **Source attribution** for all non-buy-side information  
✅ **Evidence-based analysis** with management/analyst quotes  
✅ **Vietnamese market context** (VND billions, local projects)  
✅ **Professional section structure** for institutional consumption  

### **🚀 Multi-Perspective Integration:**
✅ **Buy-side primary** - Our investment view leads  
✅ **Management context** - Official numbers and guidance attributed  
✅ **Sell-side comparison** - Market consensus and expectations referenced  
✅ **Differentiated analysis** - Clear where we differ and why  

---

## 📋 **Example Report Flow**

### **Headline Summary:**
*"2Q25 results exceeded our expectations driven by VHM02 presales acceleration. Our Overweight stance differs from sell-side consensus (VCBS: Neutral) given undervalued RNAV discount."*

### **Earnings Review:**
*"Revenue of VND 15.2bn beat our estimate of VND 14.5bn, driven by VHM Grand Park contributions [Management]. This compares favorably to sell-side expectations (VCBS: VND 14.8bn) [Sell-side – VCBS]."*

### **Valuation & Recommendation:**
*"Our RNAV of VND 42,000/share implies 28% upside from current levels, compared to sell-side TP of VND 35,000 [Sell-side – VCBS]. Maintain Overweight on project pipeline acceleration."*

---

## ✅ **System Status: PRODUCTION READY**

### **Complete Integration:**
✅ **Custom prompt template** fully integrated with all variables  
✅ **Buy-side priority system** implemented in data processing  
✅ **Professional 7-section format** with enhanced section parsing  
✅ **Attribution system** for management and sell-side sources  
✅ **Comparison highlighting** for consensus divergence  

### **Multi-Source Support:**
✅ **Management commentary** → Official guidance and strategic priorities  
✅ **Sell-side commentary** → Market consensus and analyst views  
✅ **Buy-side commentary** → **Primary investment narrative** ⭐  
✅ **User commentary** → Additional context and observations  

### **Vietnamese Market Optimization:**
✅ **VND billions** currency formatting  
✅ **Local project references** and Vietnamese market context  
✅ **VAS/IFRS accounting** basis recognition  
✅ **Vietnamese analyst firms** attribution (VCBS, SSI, etc.)  

---

## 🎉 **Next Report Generation Will:**

1. **Load your custom prompt** with buy-side focus
2. **Replace all template variables** (company, quarter, comparison quarters, publisher)
3. **Prioritize buy-side commentary** as the primary narrative
4. **Attribute management and sell-side** sources explicitly
5. **Highlight consensus differences** where buy-side view diverges
6. **Generate professional 7-section reports** suitable for institutional consumption
7. **Include valuation recommendations** with clear investment stance

**Your quarterly earnings system now generates institutional-quality, buy-side focused investment reports that prioritize internal analysis while properly contextualizing management and sell-side perspectives!** 🚀
