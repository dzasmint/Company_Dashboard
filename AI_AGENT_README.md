# 🤖 Real Estate Financial Model - AI Agent Edition

## ✅ Setup Complete

Your AI-powered Real Estate Financial Model is fully configured and tested!

### 🔑 API Keys Configured
- ✅ **Claude AI (Anthropic)**: Connected and working
- ✅ **Perplexity AI**: Connected and working  
- ✅ **MongoDB**: Connected to your database

## 📊 Working with Financial Statements

### Issue with PDF Files
The DXG PDF (`DXG_Baocaotaichinh_2024_Kiemtoan_Hopnhat_29042025160213.pdf`) is a **scanned/image-based PDF** that requires OCR to extract text. This is common with Vietnamese financial statements.

### ✅ Solution: Use Excel Format

I've created a **sample Excel file** with DXG project data that works perfectly:
- **File**: `data/DXG_Sample_Projects.xlsx`
- **Contents**: 
  - 7 current real estate projects with full details
  - Financial summary data
  - 4 future pipeline projects

## 🚀 How to Use

### 1. Start the Application
```bash
streamlit run pages/Real_Estate_Financial_Model_AI_Agent.py
```

### 2. Go to AI Project Discovery Tab
Navigate to the **"🤖 AI Project Discovery"** tab in the application

### 3. Upload Financial Statement
Two options:

#### Option A: Excel File (Recommended) ✅
- Upload `data/DXG_Sample_Projects.xlsx` or any Excel financial statement
- Click **"🔍 Extract Projects with Claude"**
- Works immediately!

#### Option B: PDF File
- If PDF is scanned/image-based, you'll see a warning
- Options provided:
  1. Convert PDF using OCR tools (Google Drive, online OCR)
  2. Manually paste text in the provided text area
  3. Download Excel version from company IR page

### 4. Enrich with Market Data
- Click **"🌐 Enrich with Perplexity"** to get additional project details
- Perplexity will research:
  - Project locations and specifications
  - Current market prices
  - Development timelines
  - Sales status

### 5. Save to Database
- Click **"💾 Save to Database"** to store projects in MongoDB
- System tracks:
  - New projects
  - Updated projects
  - Version history

## 📁 File Locations

### Core Files
- **Main App**: `pages/Real_Estate_Financial_Model_AI_Agent.py`
- **Claude Extractor**: `utils/claude_project_extractor.py`
- **Perplexity Research**: `utils/perplexity_utils.py` (class `PerplexityProjectResearcher`)
- **Pipeline Manager**: `utils/project_pipeline_manager.py`
- **MongoDB Helper**: `utils/mongodb_utils.py` (class `MongoDBHelper`)

### Test Data
- **Sample Excel**: `data/DXG_Sample_Projects.xlsx` (working test file)
- **PDF File**: `data/DXG_Baocaotaichinh_2024_Kiemtoan_Hopnhat_29042025160213.pdf` (requires OCR)

## 🔧 Handling Different File Types

### Excel Files (.xlsx, .xls) ✅
- **Status**: Fully supported
- **Extraction**: Automatic, works perfectly
- **Recommendation**: Preferred format

### PDF Files
- **Text-based PDFs**: Supported
- **Scanned/Image PDFs**: Requires OCR or manual input
- **Alternative**: System provides manual text input option

## 💡 Tips for Best Results

### 1. Getting Financial Statements
**Excel Format Sources**:
- Company investor relations pages
- SSI, HSC, VCSC research platforms
- VietstockFinance.vn
- CafeF.vn

### 2. For Scanned PDFs
**OCR Options**:
- **Google Drive**: Upload PDF → Right-click → Open with Google Docs
- **Online Tools**: smallpdf.com, ilovepdf.com
- **Adobe Acrobat**: If available

### 3. Manual Input Format
When pasting text manually, use this format:
```
HÀNG TỒN KHO / INVENTORY
Bất động sản đang phát triển:
- Dự án Gem Riverside: 2,500,000 triệu VNĐ
  Địa điểm: Quận 2, TP.HCM
  Số căn: 3,175 căn
  
- Dự án Opal Boulevard: 1,500,000 triệu VNĐ
  Địa điểm: Dĩ An, Bình Dương
  Số căn: 2,156 căn
```

## 🎯 Features

### AI-Powered Extraction
- Automatically identifies real estate projects from financial statements
- Extracts book values, locations, and project details
- Distinguishes between current inventory and future pipeline

### Market Research Integration
- Enriches project data with current market information
- Finds additional projects not in financial statements
- Estimates missing parameters using market comparables

### Data Management
- Saves to MongoDB with version tracking
- Compares new data with existing records
- Maintains audit trail of all discoveries

## 📈 Workflow Summary

1. **Upload** → Financial statement (Excel preferred)
2. **Extract** → Claude AI analyzes and extracts projects
3. **Enrich** → Perplexity researches additional details
4. **Review** → Check extracted and enriched data
5. **Save** → Store in MongoDB with tracking

## ✨ Ready to Use!

The system is fully operational. Use the sample Excel file to test the complete workflow, then apply it to real financial statements in Excel format for best results.

---

*For issues or questions, check the test results above or run the test scripts provided.*