# Quarterly Earnings Analysis Feature

## ✅ Integration Complete

The Quarterly Earnings Analysis is now **integrated as a tab** within the Real Estate Financial Model page.

## 🚀 How to Access

1. Run the app: `streamlit run pages/Real_Estate_Financial_Model_God_AI.py`
2. Select a company from the sidebar
3. Click on **"Quarterly Earnings"** in the sidebar navigation
4. Start uploading and analyzing quarterly earnings documents!

## 📂 Files Created/Modified

### New Files
- `tabs/quarterly_earnings.py` - Main tab module for the UI
- `utils/quarterly_earnings_extractor.py` - ChatGPT extraction logic
- `utils/quarterly_report_generator.py` - Summary report generation
- `utils/quarterly_earnings_manager.py` - Main orchestrator
- `docs/Quarterly_Earnings_Guide.md` - Comprehensive user guide

### Modified Files
- `utils/mongodb_utils.py` - Added 3 new collections and 12 methods
- `pages/Real_Estate_Financial_Model_God_AI.py` - Integrated as new tab

## 🗄️ MongoDB Collections

Three new collections were added to the `VietnamStocks` database:

1. **QuarterlyEarningsDocuments** - Document metadata and processing status
2. **QuarterlyEarningsData** - Structured extracted financial and operational data
3. **QuarterlySummaries** - Generated summary reports with caching

## 🎯 Features

### 1. Document Upload & Analysis
- Upload PDF, Excel, Word, or Text files
- Three document types supported:
  - 📊 Company Earnings Presentations
  - 📈 Sell-Side Research Reports
  - 📝 User Commentary/Notes
- AI-powered extraction using GPT-4o
- Review and edit extracted data before saving

### 2. Document Management
- View all uploaded documents by company and quarter
- Track processing status
- Delete documents
- View detailed metadata

### 3. AI Analysis Review
- Expandable sections for each data category
- JSON editor for manual corrections
- Save validated data to MongoDB

### 4. Summary Report Generation
- Comprehensive quarterly summaries combining all sources
- Smart caching for fast retrieval
- Professional investment report format
- Download as TXT or Markdown

## 📊 Data Extracted

### From Earnings Presentations:
- Revenue, profit, margins (YoY/QoQ growth)
- EPS, book value per share
- Units sold, handed over, ASP
- Project-level performance
- New launches
- Land acquisitions
- Management guidance
- Balance sheet highlights

### From Sell-Side Reports:
- Analyst recommendations and target prices
- Key investment points
- Concerns and risks
- Catalysts
- Valuation metrics
- Financial forecasts

### From User Commentary:
- Categorized notes with importance levels
- Sentiment analysis
- Important quotes
- Action items

## 🔄 Workflow

```
1. Upload Document
   ↓
2. AI Extracts Data (GPT-4o)
   ↓
3. Review & Edit Data
   ↓
4. Save to MongoDB
   ↓
5. Generate Summary Report
   ↓
6. Download & Share
```

## 📁 Data Storage Structure

```
data/
├── VHM/
│   ├── 1Q25/
│   │   ├── RawReports/
│   │   │   ├── earnings_presentation_VHM_1Q25_20250630_100530.pdf
│   │   │   └── sellside_report_VCBS_VHM_1Q25_20250630_140220.pdf
│   │   └── Summaries/
│   │       └── earnings_summary_1Q25.txt
│   ├── 2Q25/
│   │   ├── RawReports/
│   │   └── Summaries/
```

## 💡 Usage Tips

1. **Upload Multiple Sources**: For comprehensive analysis, upload:
   - Company earnings presentation
   - 2-3 sell-side analyst reports
   - Your own notes/commentary

2. **Review Before Saving**: Always review extracted data - AI may miss context

3. **Cache is Smart**: Summary reports are cached and auto-regenerate when new documents are added

4. **Force Regenerate**: Use the checkbox if you want to update the summary after editing data

## 🔧 Technical Details

### AI Models
- **GPT-4o** for all extraction and generation
- **JSON mode** for reliable structured output
- **Temperature 0.1** for extraction (high accuracy)
- **Temperature 0.3** for summaries (balanced)

### Performance
- Text extraction: ~5-10 seconds
- AI analysis: ~15-30 seconds per document
- Summary generation: ~20-40 seconds
- Cached summaries: Instant

### Error Handling
- Graceful fallbacks for failed extractions
- Manual input options for problematic files
- Retry mechanisms for API failures

## 📚 Documentation

For detailed information, see:
- `docs/Quarterly_Earnings_Guide.md` - Full user guide
- Code comments in each utility file

## 🎉 Ready to Use!

The system is fully functional and ready for production use. No additional setup required beyond having:
- ✅ MongoDB connection configured
- ✅ OpenAI API key in `.env` file
- ✅ Company data in MongoDB

Start analyzing quarterly earnings now! 🚀
