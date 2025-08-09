# 📄 PDF Extraction Guide - AI Agent

## ✅ Current Configuration

- **Model**: Claude 3.5 Sonnet (most advanced)
- **Input**: PDF files only
- **Focus**: Vietnamese financial statements

## 🚀 Quick Start

```bash
streamlit run pages/Real_Estate_Financial_Model_AI_Agent.py
```

1. Go to **"🤖 AI Project Discovery"** tab
2. Upload your PDF financial statement
3. Enter company name and ticker
4. Click **"🔍 Extract Projects with Claude"**

## 📋 Handling Different PDF Types

### Text-Based PDFs ✅
- Automatically extracted
- Shows success message with character count
- Proceeds directly to Claude analysis

### Scanned/Image-Based PDFs 📸
When the PDF is scanned (like your DXG file), you'll see:

1. **Manual Input Tab** - Paste text directly
2. **OCR Tools Tab** - Links to conversion tools
3. **Tips Tab** - Guidance on formatting

## 📝 Manual Input Format

When pasting text manually, use this format:

```
HÀNG TỒN KHO / INVENTORY
Đơn vị: Triệu VNĐ

Bất động sản đang phát triển:
- Dự án Gem Riverside: 2,500,000
  Địa điểm: Quận 2, TP.HCM
  Diện tích: 6.7 ha
  Tổng số căn: 3,175 căn
  
- Dự án Opal Boulevard: 1,500,000
  Địa điểm: Dĩ An, Bình Dương
  Tổng số căn: 2,156 căn
  
- Dự án Gem Sky World: 3,200,000
  Địa điểm: Long Thành, Đồng Nai
  Quy mô: 92 ha
  Tổng số căn: 4,500 căn

Bất động sản hoàn thành:
- Lux Star: 450,000
- St. Moritz: 680,000

Tổng cộng: 11,050,000
```

## 🔧 OCR Options for Scanned PDFs

### Free Options:
1. **Google Drive** (Best)
   - Upload PDF → Right-click → Open with Google Docs
   - Automatic OCR conversion
   - Copy text to manual input

2. **Online Tools**
   - [SmallPDF](https://smallpdf.com/pdf-to-word)
   - [ILovePDF](https://www.ilovepdf.com/pdf_to_word)
   - [PDF.io](https://pdf.io/pdf2txt/)

3. **Adobe Acrobat**
   - [Online converter](https://www.adobe.com/acrobat/online/pdf-to-word.html)

## 🎯 What Claude Looks For

### Key Sections:
- **Hàng tồn kho** (Inventory)
- **Bất động sản đang phát triển** (Properties under development)
- **Bất động sản hoàn thành** (Completed properties)
- **Dự án tương lai** (Future projects)

### Project Information:
- Project name (Tên dự án)
- Book value in VND (Giá trị sổ sách)
- Location (Địa điểm)
- Total units (Tổng số căn)
- Land area (Diện tích)
- Development stage (Giai đoạn)

## 📊 Expected Output

Claude will extract:
```json
{
  "projects_in_inventory": [
    {
      "project_name": "Gem Riverside",
      "book_value_vnd": 2500000000000,
      "location": "District 2, Ho Chi Minh City",
      "total_units": 3175,
      "stage": "under_construction"
    }
  ],
  "future_projects": [...],
  "total_inventory_value": 11050000000000
}
```

## ⚡ Tips for Success

1. **Include the entire inventory section** when pasting manually
2. **Keep number formatting** (use millions VND as shown in statements)
3. **Include project details** like location and units if available
4. **Separate projects clearly** with line breaks or dashes

## 🔍 Workflow After Extraction

1. **Review extracted projects** in the summary table
2. **Click "Enrich with Perplexity"** to get market data
3. **Save to MongoDB** to store in database
4. **View in Project Pipeline** tab for editing

## ❓ Troubleshooting

### "Failed to extract text from document"
- PDF is scanned → Use manual input or OCR
- PDF is corrupted → Try re-downloading
- PDF is password-protected → Remove protection first

### "No projects found"
- Check text format matches examples above
- Ensure inventory section is included
- Verify values are in VND (millions/billions)

### "Claude extraction failed"
- Check API key in .env file
- Verify internet connection
- Try with smaller text sample

## 📞 Support

The system is configured to:
- Use Claude 3.5 Sonnet (most advanced model)
- Handle Vietnamese and English text
- Extract from complex financial statements
- Provide manual fallback for scanned PDFs

For scanned PDFs like your DXG file, **manual input with proper formatting** is the recommended approach.