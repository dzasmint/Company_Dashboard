# 📖 How to Use AI Agent for Project Discovery

## 🚨 Current Issue: PDF Extraction

The DXG PDF file is **scanned/image-based** and cannot be directly processed. Here are your options:

## ✅ Option 1: Use the Sample Excel File (IMMEDIATE SOLUTION)

I've created a working Excel file with sample DXG data:

```bash
# 1. Start the application
streamlit run pages/Real_Estate_Financial_Model_AI_Agent.py

# 2. Navigate to "AI Project Discovery" tab

# 3. Upload this file:
data/DXG_Sample_Projects.xlsx

# 4. Enter company details:
Company Name: Dat Xanh Group
Stock Ticker: DXG

# 5. Click "Extract Projects with Claude"
```

**This will work immediately!** The Excel file contains:
- 7 real estate projects with full details
- Financial summary
- Future pipeline projects

## 📝 Option 2: Manual Text Input (For PDF Files)

When you upload the scanned PDF, you'll see:
1. An error message explaining the PDF is scanned
2. A text area for manual input

**Steps:**
1. Copy the inventory section from your financial statement
2. Paste it in the text area that appears
3. Use this format:

```
HÀNG TỒN KHO / INVENTORY

Bất động sản đang phát triển:
- Dự án Gem Riverside: 2,500,000 triệu VNĐ
  Địa điểm: Quận 2, TP.HCM
  Tổng số căn: 3,175
  
- Dự án Opal Boulevard: 1,500,000 triệu VNĐ
  Địa điểm: Dĩ An, Bình Dương
  Tổng số căn: 2,156

- Dự án Gem Sky World: 3,200,000 triệu VNĐ
  Địa điểm: Long Thành, Đồng Nai
  Tổng số căn: 4,500
```

## 🔄 Option 3: Convert PDF to Text First

### Using Google Drive (Free)
1. Upload PDF to Google Drive
2. Right-click → Open with → Google Docs
3. Google will OCR the PDF automatically
4. Copy the text and paste in the manual input area

### Using Online Tools
- [SmallPDF OCR](https://smallpdf.com/pdf-to-word)
- [ILovePDF OCR](https://www.ilovepdf.com/pdf_to_word)
- [Adobe Online OCR](https://www.adobe.com/acrobat/online/pdf-to-word.html)

## 📊 Option 4: Get Excel Version (Best Solution)

Download Excel financial statements from:
- **Company IR Page**: [DXG Investor Relations](https://www.datxanh.vn/quan-he-co-dong)
- **VietstockFinance**: [DXG Financials](https://finance.vietstock.vn/DXG)
- **CafeF**: [DXG Reports](https://cafef.vn/dxg)
- **SSI/HSC/VCSC**: Research platforms (if you have access)

## 🎯 Quick Test Instructions

### Test with Sample Excel (Works Now!)
```python
# File to upload: data/DXG_Sample_Projects.xlsx
# Company Name: Dat Xanh Group  
# Stock Ticker: DXG
```

### Expected Results
- **7 projects extracted** from inventory
- **4 future projects** identified
- Total inventory value: 11.05T VND
- Projects include: Gem Riverside, Opal Boulevard, Gem Sky World, etc.

## ⚡ Quick Commands

```bash
# Run the app
streamlit run pages/Real_Estate_Financial_Model_AI_Agent.py

# Test with sample data
# Upload: data/DXG_Sample_Projects.xlsx
# This file is guaranteed to work!
```

## 🛠️ Troubleshooting

### "Failed to extract text from document"
- **Cause**: PDF is scanned/image-based
- **Solution**: Use Excel file or manual input

### "Claude extraction failed"
- **Cause**: API key issue or text format problem
- **Solution**: Check ANTHROPIC_API_KEY in .env file

### "No projects found"
- **Cause**: Text format doesn't match expected structure
- **Solution**: Use the format examples provided above

## 📞 Need Help?

1. **Use the sample Excel file first** - it's guaranteed to work
2. **Check the AI_AGENT_README.md** for detailed documentation
3. **Review test results** in the terminal output

---

**Remember**: The Excel format (`data/DXG_Sample_Projects.xlsx`) works perfectly and is the recommended approach!