# Quarterly Earnings Prompt Template Guide

## ✅ Custom Prompt Template Integration

The system now uses your custom prompt files:
1. **Management presentations:** `quarterly_earnings_management_presentation_prompt.txt`
2. **Sell-side reports:** `quarterly_earnings_sell_side_report_prompt.txt`
3. **User commentary:** Uses inline prompt (can be templated if needed)

---

## 🔄 Template Variable Replacement

### For Management Presentations:

| Template Variable | Populated From | Example Value | Description |
|-------------------|----------------|---------------|-------------|
| `{{COMPANY_NAME}}` | Function parameter | `"Vinhomes JSC"` | Full company name |
| `{{TICKER}}` | Function parameter | `"VHM"` | Stock ticker symbol |
| `{{QUARTER}}` | Function parameter | `"2Q25"` | Quarter being analyzed |
| `{{COMPARISON_QUARTERS_JSON}}` | Auto-calculated | `["1Q25","2Q24"]` | QoQ and YoY comparison quarters |
| `{{FISCAL_HALF}}` | Auto-calculated | `"1H25"` | Fiscal half-year (1H or 2H) |
| `{{TARGET_CCY}}` | Hardcoded | `"VND"` | Target currency (Vietnamese Dong) |
| `{{TARGET_UNITS}}` | Hardcoded | `"bn"` | Units (billions) |
| `{{ACCOUNTING_BASIS}}` | Hardcoded | `"VAS"` | Default accounting standard |

### For Sell-Side Reports:

| Template Variable | Populated From | Example Value | Description |
|-------------------|----------------|---------------|-------------|
| `{{COMPANY_NAME}}` | Function parameter | `"Vinhomes JSC"` | Full company name |
| `{{TICKER}}` | Function parameter | `"VHM"` | Stock ticker symbol |
| `{{QUARTER}}` | Function parameter | `"2Q25"` | Quarter being analyzed |
| `{{COMPARISON_QUARTERS_JSON}}` | Auto-calculated | `["1Q25","2Q24"]` | QoQ and YoY comparison quarters |
| `{{FISCAL_HALF}}` | Auto-calculated | `"1H25"` | Fiscal half-year (1H or 2H) |
| `{{SELL_SIDE_FIRM}}` | Function parameter | `"VCBS"` | **Analyst firm name** |
| `{{TARGET_CCY}}` | Hardcoded | `"VND"` | Target currency (Vietnamese Dong) |
| `{{TARGET_UNITS}}` | Hardcoded | `"bn"` | Units (billions) |
| `{{ACCOUNTING_BASIS}}` | Hardcoded | `"VAS"` | Default accounting standard |

---

## 🧮 Auto-Calculation Logic

### 1. **Comparison Quarters**
Automatically calculates QoQ (Quarter-over-Quarter) and YoY (Year-over-Year) comparison periods:

**Examples:**
```
Input: "2Q25"
Output: ["1Q25", "2Q24"]
Explanation: Previous quarter (1Q25) and same quarter last year (2Q24)

Input: "1Q25"
Output: ["4Q24", "1Q24"]
Explanation: Previous quarter wraps to Q4 of previous year

Input: "3Q25"
Output: ["2Q25", "3Q24"]
Explanation: Previous quarter (2Q25) and same quarter last year (3Q24)
```

### 2. **Fiscal Half**
Automatically determines which half of the fiscal year:

**Logic:**
- Q1, Q2 → `1H` (First Half)
- Q3, Q4 → `2H` (Second Half)

**Examples:**
```
"1Q25" → "1H25"
"2Q25" → "1H25"
"3Q25" → "2H25"
"4Q25" → "2H25"
```

---

## 📝 How It Works

### Step-by-Step Process:

1. **Load Template**
   ```python
   prompt_template = _load_management_prompt()
   # Loads: utils/quarterly_earnings_management_presentation_prompt.txt
   ```

2. **Parse Quarter Input**
   ```python
   quarter = "2Q25"
   quarter_num = 2      # First character
   year_short = "25"    # Last 2 characters
   year_full = 2025     # Convert to full year
   ```

3. **Calculate Comparisons**
   ```python
   qoq_quarter = "1Q25"  # Previous quarter
   yoy_quarter = "2Q24"  # Same quarter last year
   comparison_quarters = ["1Q25", "2Q24"]
   ```

4. **Calculate Fiscal Half**
   ```python
   fiscal_half = "1H25"  # (quarter_num + 1) // 2 = (2+1)//2 = 1
   ```

5. **Replace All Variables**
   ```python
   prompt = prompt_template.replace("{{COMPANY_NAME}}", "Vinhomes JSC")
   prompt = prompt.replace("{{TICKER}}", "VHM")
   prompt = prompt.replace("{{QUARTER}}", "2Q25")
   prompt = prompt.replace("{{COMPARISON_QUARTERS_JSON}}", '["1Q25","2Q24"]')
   prompt = prompt.replace("{{FISCAL_HALF}}", "1H25")
   prompt = prompt.replace("{{TARGET_CCY}}", "VND")
   prompt = prompt.replace("{{TARGET_UNITS}}", "bn")
   prompt = prompt.replace("{{ACCOUNTING_BASIS}}", "VAS")
   ```

6. **Append Schema & Document**
   ```python
   full_prompt = f"{prompt}\n\nJSON SCHEMA:\n{schema_json}\n\nDOCUMENT TEXT:\n{document_text}"
   ```

7. **Send to ChatGPT**
   - Model: `gpt-4o`
   - Temperature: `0.1` (low for accuracy)
   - Response format: `json_object`

---

## 🎯 Example Output

### For Management Presentation:
```python
extract_from_earnings_presentation(
    document_text="<PDF text content>",
    company_name="Vinhomes JSC",
    ticker="VHM",
    quarter="2Q25"
)
```

### For Sell-Side Report:
```python
extract_from_sellside_report(
    document_text="<PDF text content>",
    company_name="Vinhomes JSC",
    ticker="VHM",
    quarter="2Q25",
    analyst_firm="VCBS"
)
```

### Variables Populated for Sell-Side:
```
COMPANY_NAME: "Vinhomes JSC"
TICKER: "VHM"
QUARTER: "2Q25"
COMPARISON_QUARTERS_JSON: ["1Q25","2Q24"]
FISCAL_HALF: "1H25"
SELL_SIDE_FIRM: "VCBS"
TARGET_CCY: "VND"
TARGET_UNITS: "bn"
ACCOUNTING_BASIS: "VAS"
```

### Resulting Sell-Side Prompt (first part):
```
You are a meticulous financial data extractor. Read ONE sell-side earnings 
report (PDF or text) and output ONE JSON object that conforms EXACTLY 
to the provided schema.

PARAMETERS (inject from your pipeline)
- company = "Vinhomes JSC"
- ticker = "VHM"
- quarter = "2Q25"
- comparison_quarters = ["1Q25","2Q24"]
- fiscal_year_half = "1H25"
- sell_side_publisher = "VCBS"
- target_currency = "VND"
- target_units = "bn"
- default_accounting_basis = "VAS"

[... rest of your sell-side prompt template ...]
```

---

## 🔧 Customization

### To Modify Template Variables:

**Location:** `utils/quarterly_earnings_management_presentation_prompt.txt`

1. **Add new placeholder:** Use format `{{VARIABLE_NAME}}`
2. **Update extractor code:** Add replacement in `extract_from_earnings_presentation()` method
3. **Pass value:** Either from parameters or calculate it

### To Change Default Values:

Edit these lines in `quarterly_earnings_extractor.py`:
```python
prompt = prompt.replace("{{TARGET_CCY}}", "VND")      # Change "VND" to other currency
prompt = prompt.replace("{{TARGET_UNITS}}", "bn")     # Change "bn" to "mn" (millions)
prompt = prompt.replace("{{ACCOUNTING_BASIS}}", "VAS") # Change to "IFRS" if needed
```

---

## ✅ Verification

To verify the template is being used correctly:

1. **Check file exists:**
   ```
   utils/quarterly_earnings_management_presentation_prompt.txt
   ```

2. **Upload a test document** and check the extraction

3. **Look for indicators** in extracted data:
   - `source.file_type = "management"`
   - `currency = "VND"`
   - `units = "bn"`
   - `accounting_basis = "VAS"`
   - Comparison quarters populated in period section

---

## 🎉 Benefits

✅ **Centralized Prompt Management** - Edit one file, affects all extractions
✅ **Consistent Instructions** - Same rules applied every time
✅ **Easy Customization** - Modify prompt without touching code
✅ **Auto-Calculation** - Smart quarter comparisons and fiscal half detection
✅ **Zero Hallucination Focus** - Strict "only extract what's present" rules

Your custom prompt template is now fully integrated! 🚀

