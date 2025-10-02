# ✅ Redesigned: Separate Documents Per Source

## 🎯 **Design Change Implemented**

As requested, the system has been redesigned to store **each uploaded file as a separate document** in MongoDB.

---

## 📊 **New System Architecture**

### **Two MongoDB Collections:**

#### **1. QuarterlyEarningsDocuments** (File Tracking)
```
Purpose: Track uploaded files and processing status
Behavior: One document per uploaded file
```

#### **2. QuarterlyEarningsData** (Extracted Data) ⭐ **REDESIGNED**
```
Purpose: Store extracted earnings data
NEW Behavior: One document per uploaded file (no merging)
OLD Behavior: One consolidated document per ticker/quarter (with merging)
```

---

## 🆕 **New Data Model**

### **3 Uploads = 3 Separate Documents:**

```javascript
// Document 1: Management Presentation
{
  "_id": ObjectId("..."),
  "document_id": "doc1",              // ← Links to QuarterlyEarningsDocuments
  "ticker": "VHM",
  "quarter": "2Q25",
  "source": {
    "file_type": "management",
    "file_name": "VHM_2Q25_Management.pdf"
  },
  "headline": {...},
  "presales": {...},
  "balance_sheet": {...},
  "management_commentary": {...},     // ← Only this document has this
  "upload_date": "2025-01-01T10:00:00"
}

// Document 2: Sell-Side Report
{
  "_id": ObjectId("..."),
  "document_id": "doc2",              // ← Links to QuarterlyEarningsDocuments
  "ticker": "VHM",
  "quarter": "2Q25",
  "source": {
    "file_type": "sell_side",
    "file_name": "VHM_2Q25_VCBS.pdf",
    "publisher": "VCBS"
  },
  "headline": {...},
  "presales": {...},
  "sell_side_commentary": {...},      // ← Only this document has this
  "upload_date": "2025-01-01T11:00:00"
}

// Document 3: Buy-Side Commentary
{
  "_id": ObjectId("..."),
  "document_id": "doc3",              // ← Links to QuarterlyEarningsDocuments
  "ticker": "VHM",
  "quarter": "2Q25",
  "source": {
    "file_type": "buy_side"
  },
  "buy_side_commentary": {            // ← Only this document has this
    "raw_bullets": [...],
    "valuation_analysis": {...}
  },
  "upload_date": "2025-01-01T12:00:00"
}
```

---

## 🔧 **Code Changes Made**

### **1. MongoDB Indexes Updated:**

```python
# OLD (with unique constraint):
create_index([("ticker", 1), ("quarter", 1)], unique=True)  # ❌ Only 1 doc allowed

# NEW (without unique constraint):
create_index([("ticker", 1), ("quarter", 1)])  # ✅ Multiple docs allowed
create_index([("ticker", 1), ("quarter", 1), ("source.file_type", 1)])  # ✅ Query by source
create_index([("document_id", 1)])  # ✅ Link to source file
```

### **2. Save Method Simplified:**

```python
# OLD (upsert - overwrites):
def save_quarterly_earnings_data(earnings_data):
    result = quarterly_data_collection.update_one(
        {"ticker": earnings_data["ticker"], "quarter": earnings_data["quarter"]},
        {"$set": earnings_data},
        upsert=True  # ❌ Overwrites existing
    )

# NEW (insert - always new):
def save_quarterly_earnings_data(earnings_data):
    result = quarterly_data_collection.insert_one(earnings_data)  # ✅ Always creates new
    return str(result.inserted_id)
```

### **3. Manager Save Logic Simplified:**

```python
# REMOVED:
- Complex merge logic (_merge_earnings_data method)
- Priority-based merging
- Completeness comparison
- Source document tracking array

# NEW:
- Simple insert for each upload
- Each document is independent
- Links back to source file via document_id
- Clear source.file_type for filtering
```

### **4. Report Generator (Already Handles This):**

```python
# Report generator ALREADY aggregates from multiple documents:
def generate_summary_report(...):
    all_earnings_data = mongo_helper.get_quarterly_earnings_data(ticker, quarter)
    # Returns list of ALL documents for that ticker/quarter
    # Aggregates in _prepare_data_for_summary()
```

✅ **No changes needed!** Report generator already designed to handle multiple documents.

---

## 📋 **Querying the New Structure**

### **Get All Documents for a Quarter:**
```python
# Returns list of all documents (management, sell-side, buy-side)
documents = mongo_helper.get_quarterly_earnings_data("VHM", "2Q25")
# Result: [doc1, doc2, doc3]
```

### **Filter by Source Type:**
```javascript
// Get only management data
db.QuarterlyEarningsData.find({
  "ticker": "VHM",
  "quarter": "2Q25",
  "source.file_type": "management"
})

// Get only sell-side data
db.QuarterlyEarningsData.find({
  "ticker": "VHM",
  "quarter": "2Q25",
  "source.file_type": "sell_side"
})
```

### **Link to Source File:**
```javascript
// Find the original uploaded file
db.QuarterlyEarningsDocuments.findOne({
  "_id": ObjectId(document_id)
})
```

---

## ✅ **Benefits of New Design**

### **1. Data Independence:**
✅ **Each upload is isolated** - no risk of overwriting  
✅ **Full traceability** - each document links to its source file  
✅ **Easy to delete** - remove individual documents without affecting others  

### **2. Simplicity:**
✅ **No merge logic** - simpler code, fewer bugs  
✅ **No priority conflicts** - each source stands alone  
✅ **Clear data model** - one file = one document  

### **3. Flexibility:**
✅ **Upload in any order** - no dependencies  
✅ **Re-upload same source** - creates new version  
✅ **Multiple sell-side reports** - can upload VCBS, SSI, etc. separately  

### **4. Auditability:**
✅ **Full history** - see exactly what was uploaded when  
✅ **Source tracking** - know which file each data point came from  
✅ **Version control** - keep multiple versions if needed  

---

## 🔄 **Report Generation (Unchanged)**

The report generator **already aggregates** from multiple documents:

### **Aggregation Process:**
1. **Query MongoDB** → Get ALL documents for ticker/quarter
2. **Separate by source** → Group by `source.file_type`
3. **Collect commentary** → Each source's commentary preserved
4. **Merge financial data** → Uses priority in report generator (not storage)
5. **Generate report** → Combines all perspectives

### **Priority Applied at Report Time:**
```python
# In _prepare_data_for_summary():
- Management data preferred for financial metrics
- Sell-side used if management not available
- Buy-side used for valuation and investment thesis
- ALL commentary sections preserved
```

---

## 📊 **Example Workflow**

### **Upload Sequence:**

**Step 1: Upload Management Presentation**
```
✅ Creates: 1 document in QuarterlyEarningsDocuments
✅ Creates: 1 document in QuarterlyEarningsData (management data)
🆕 Created separate data document for VHM - 2Q25 (management)
```

**Step 2: Upload Sell-Side Report**
```
✅ Creates: 1 document in QuarterlyEarningsDocuments
✅ Creates: 1 document in QuarterlyEarningsData (sell-side data)
🆕 Created separate data document for VHM - 2Q25 (sell_side)
```

**Step 3: Enter Buy-Side Commentary**
```
✅ Creates: 1 document in QuarterlyEarningsDocuments
✅ Creates: 1 document in QuarterlyEarningsData (buy-side data)
🆕 Created separate data document for VHM - 2Q25 (buy_side)
```

### **Final State:**
```
QuarterlyEarningsDocuments: 3 documents (file tracking)
QuarterlyEarningsData:      3 documents (extracted data) ✅
```

### **Generate Report:**
```
1. Query: Get all documents for VHM - 2Q25
2. Result: [management_doc, sell_side_doc, buy_side_doc]
3. Aggregate: Combine all three in report generator
4. Output: Professional report with all perspectives
```

---

## 🎯 **Key Differences from Old Design**

### **OLD Design (Consolidated):**
```
✅ Advantages:
- One document per quarter
- Pre-merged data
- Simpler queries

❌ Disadvantages:
- Complex merge logic
- Risk of data loss
- Priority conflicts
- Harder to audit
```

### **NEW Design (Separate):**
```
✅ Advantages:
- Each source independent
- No merge conflicts
- Full traceability
- Simple code
- Easy to manage

❌ Disadvantages:
- Multiple documents per quarter
- Aggregation at report time
```

---

## 🎉 **Migration Notes**

### **If You Have Existing Data:**

Your existing consolidated documents will remain in the database. New uploads will create separate documents.

**To clean up (optional):**
```javascript
// Remove old consolidated documents if desired
db.QuarterlyEarningsData.deleteMany({
  "source_documents": { $exists: true }  // Old format had this field
})
```

### **Going Forward:**

✅ Each new upload creates a separate document  
✅ You can have multiple documents for same ticker/quarter  
✅ Report generation aggregates all sources  
✅ Clean, simple, auditable architecture  

---

## 🎊 **System Status: REDESIGNED**

### **What Changed:**
✅ **MongoDB indexes** - Removed unique constraint  
✅ **Save method** - Changed from upsert to insert  
✅ **Manager logic** - Removed merge code  
✅ **Data model** - One document per uploaded file  

### **What Stayed the Same:**
✅ **Report generation** - Already designed for multiple documents  
✅ **UI workflow** - Upload process unchanged  
✅ **JSON schema** - Schema structure unchanged  
✅ **Prompt templates** - Extraction logic unchanged  

### **Result:**
✅ **3 uploads = 3 documents** in QuarterlyEarningsData  
✅ **Each document independent** and traceable  
✅ **Report generator aggregates** all sources  
✅ **Simpler, cleaner architecture**  

**Your system now stores each uploaded file as a separate, independent document in MongoDB!** 🚀

