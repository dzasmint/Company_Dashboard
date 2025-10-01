# Quarterly Earnings Analysis - User Guide

## 🎯 Overview

The Quarterly Earnings Analysis tab (within Real Estate Financial Model) allows you to upload, analyze, and summarize quarterly earnings documents using AI-powered extraction and report generation.

## 📍 How to Access

1. Open the **Real Estate Financial Model** page
2. Select a company from the sidebar
3. Navigate to the **Quarterly Earnings** tab in the sidebar navigation

## 📁 File Structure

### Data Organization
Files are automatically organized in the following structure:
```
data/
├── {TICKER}/                      # e.g., VHM, NVL, DXG
│   ├── {QUARTER}/                 # e.g., 1Q25, 2Q25, 3Q25, 4Q25
│   │   ├── RawReports/           # Original uploaded files
│   │   │   ├── earnings_presentation_VHM_2Q25.pdf
│   │   │   ├── sellside_report_VCBS_VHM_2Q25.pdf
│   │   │   └── user_notes_2Q25.txt
│   │   └── Summaries/            # Generated summary reports
│   │       └── earnings_summary_2Q25.txt
```

## 🗄️ MongoDB Collections

### 1. QuarterlyEarningsDocuments
Stores metadata about uploaded documents:
- File information (name, path, size)
- Processing status
- Upload date and user
- Document type and source

### 2. QuarterlyEarningsData
Stores structured extracted data:
- Financial metrics (revenue, profit, margins)
- Operational metrics (units sold, ASP)
- Project highlights and new launches
- Land bank changes
- Management outlook and guidance
- Balance sheet highlights
- Analyst insights (for sell-side reports)
- User notes (for commentary)

### 3. QuarterlySummaries
Stores generated summary reports:
- Full summary text
- Structured sections
- Generation metadata
- File paths for downloads
- Cache validity status

## 🚀 How to Use

### Step 1: Upload Documents

1. Navigate to the **"Upload Documents"** tab
2. Select the company from the dropdown
3. Choose the quarter and year
4. Select document type:
   - **Earnings Presentation**: Company's official quarterly results
   - **Sell-Side Report**: Analyst research reports (requires firm name)
   - **User Commentary**: Your notes and observations
5. Upload the file (PDF, Excel, Word, or Text)
6. Click **"Upload and Analyze Document"**

The system will:
- Save the file to the organized folder structure
- Extract text from the document
- Send to ChatGPT for structured data extraction
- Display extracted data for review

### Step 2: Review AI Analysis

1. Go to the **"AI Analysis"** tab
2. Review the extracted data in expandable sections
3. (Optional) Edit the JSON if corrections are needed
4. Click **"Save to MongoDB"** to store the data

### Step 3: Generate Summary Report

1. Go to the **"Summary Reports"** tab
2. Select company and quarter
3. Click **"Generate Summary Report"**
4. Review the comprehensive summary
5. Download as TXT or Markdown

The summary includes:
- Executive Summary
- Financial Performance
- Operational Highlights
- Project Updates
- New Project Launches
- Land Bank & Expansion
- Management Outlook & Guidance
- Analyst Views & Market Sentiment
- Key Takeaways

### Step 4: Document Management

Use the **"Document Management"** tab to:
- View all documents for a quarter
- Check processing status
- Delete documents if needed
- Re-analyze documents (coming soon)

## 📊 Key Features

✅ **Multi-document Support**: Upload multiple documents for the same quarter (earnings + analyst reports + notes)
✅ **Smart Data Aggregation**: Combines insights from all sources
✅ **AI-Powered Extraction**: Uses GPT-4o for accurate data extraction
✅ **Intelligent Caching**: Cached summaries regenerate only when new documents are added
✅ **Organized Storage**: Automatic folder structure by ticker and quarter
✅ **Flexible Exports**: Download summaries as TXT or Markdown

## 🎨 Document Type Details

### Earnings Presentation
Extracts:
- Revenue, profit, margins with YoY/QoQ growth
- EPS and book value per share
- Units sold, ASP, contracted sales
- Project-level performance
- New launches
- Land acquisitions
- Management guidance
- Balance sheet highlights

### Sell-Side Report
Extracts:
- Analyst recommendation (BUY/HOLD/SELL)
- Target price
- Key positive points
- Concerns and risks
- Catalysts
- Valuation metrics (PE, PB, EV/EBITDA)
- Financial forecasts

### User Commentary
Extracts:
- Categorized notes (management tone, strategic insight, market observation)
- Importance level (high/medium/low)
- Sentiment (positive/neutral/negative)
- Important quotes
- Action items

## 💡 Tips

1. **Upload Multiple Sources**: For best results, upload the company's earnings presentation + sell-side reports + your own notes
2. **Review Before Saving**: Always review extracted data before saving to MongoDB
3. **Force Regenerate**: Use the "Force regenerate" option if you want to update the summary after editing data
4. **Consistent Naming**: The system automatically handles file naming, but you can identify documents by upload date

## 🔧 Technical Details

### AI Models Used
- **GPT-4o**: For data extraction and summary generation
- **Temperature 0.1**: For extraction (high accuracy)
- **Temperature 0.3**: For summary generation (balanced creativity)
- **JSON Mode**: Enforces structured output for reliable parsing

### Supported File Types
- PDF (text-based or OCR)
- Excel (.xlsx, .xls)
- Word (.docx)
- Text (.txt, .md)

### Error Handling
- Failed text extraction: Shows error with manual input option
- Failed AI extraction: Retries or allows manual input
- Missing data: Uses null values, doesn't break workflow
- Cache invalidation: Automatic when new documents added

## 📝 Example Workflow

```
1. Upload Q2 2025 VHM earnings presentation
   → AI extracts financial and operational data
   → Review and save to MongoDB

2. Upload Q2 2025 VCBS research report on VHM
   → AI extracts analyst insights
   → Review and save to MongoDB

3. Upload your commentary about Q2 2025 VHM results
   → AI extracts and categorizes your notes
   → Review and save to MongoDB

4. Generate Q2 2025 VHM summary report
   → AI combines all 3 sources
   → Creates comprehensive summary
   → Download and share
```

## 🛠️ Future Enhancements

- Multi-quarter comparison charts
- Email notifications when reports are ready
- Batch upload for multiple files
- Enhanced editing interface
- PDF export with charts
- Integration with RNAV Calculator
- Automatic earnings calendar tracking
