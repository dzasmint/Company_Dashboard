# ⚠️ CRITICAL: MongoDB Index Issue Found!

## 🔍 **Root Cause Identified**

You're seeing only 1 document because MongoDB **still has the old unique index** that prevents multiple documents with the same `(ticker, quarter)` combination!

### **What's Happening:**

1. ✅ **Code is correct** - Using `insert_one` (not upsert)
2. ❌ **MongoDB has old unique index** - Prevents duplicate (ticker, quarter)
3. ❌ **Second insert fails silently** - Or gets rejected by MongoDB

### **The Problem:**

When I updated the Python code to remove `unique=True`:
```python
# OLD CODE (created unique index):
create_index([("ticker", 1), ("quarter", 1)], unique=True)

# NEW CODE (no unique constraint):
create_index([("ticker", 1), ("quarter", 1)])
```

**BUT:** The old unique index **already exists in MongoDB** and changing Python code doesn't remove it!

---

## 🔧 **SOLUTION: Run the Fix Script**

I've created a script to fix the MongoDB indexes. Run it once:

### **Step 1: Run the Fix Script**

```bash
python fix_mongodb_indexes.py
```

**What it does:**
1. Connects to your MongoDB
2. Lists current indexes (shows the problematic unique index)
3. Drops the old `ticker_1_quarter_1` unique index
4. Creates new indexes without unique constraint
5. Verifies the fix

**Expected Output:**
```
============================================================
MongoDB Index Fix for QuarterlyEarningsData Collection
============================================================

📊 Current indexes:
  - _id_: {'_id': 1}
  - ticker_1_quarter_1: {'ticker': 1, 'quarter': 1}
    ⚠️  UNIQUE constraint found!

🗑️  Dropping old unique index...
✅ Dropped ticker_1_quarter_1 index

🔧 Creating new indexes (without unique constraint)...
✅ Created: (ticker, quarter)
✅ Created: (ticker, quarter, source.file_type)
✅ Created: (ticker, year, quarter_num)
✅ Created: (last_updated)
✅ Created: (document_id)

📊 New indexes:
  - _id_: {'_id': 1}
  - ticker_1_quarter_1: {'ticker': 1, 'quarter': 1}
  - ticker_1_quarter_1_source.file_type_1: {...}
  - ...

✅ MongoDB indexes fixed successfully!
👉 You can now upload multiple documents for the same ticker/quarter
```

### **Step 2: Test Upload Again**

After running the fix:
1. Upload management presentation → Should create 1 document
2. Upload sell-side report → Should create **2nd document** (not overwrite!)
3. Add buy-side commentary → Should create **3rd document**

---

## 🔍 **How to Verify in MongoDB**

### **Check Indexes:**
```javascript
// In MongoDB shell or Compass
db.QuarterlyEarningsData.getIndexes()

// Look for any index with "unique: true"
// There should be NO unique indexes except on _id
```

### **Check Documents:**
```javascript
// Count documents for a specific ticker/quarter
db.QuarterlyEarningsData.find({
  "ticker": "VHM",
  "quarter": "2Q25"
}).count()

// Should return 3 if you uploaded 3 files
```

### **List All Documents:**
```javascript
db.QuarterlyEarningsData.find({
  "ticker": "VHM",
  "quarter": "2Q25"
}, {
  "_id": 1,
  "source.file_type": 1,
  "document_id": 1,
  "upload_date": 1
})

// Should show multiple documents with different source.file_type
```

---

## 🚨 **Alternative: Manual Fix in MongoDB Compass/Shell**

If you prefer to fix it manually:

### **Option A: MongoDB Compass (GUI)**
1. Open MongoDB Compass
2. Navigate to `VietnamStocks` database
3. Select `QuarterlyEarningsData` collection
4. Click on "Indexes" tab
5. Find index named `ticker_1_quarter_1` with unique constraint
6. Click "Drop Index"
7. Restart your Streamlit app

### **Option B: MongoDB Shell**
```javascript
use VietnamStocks

// Drop the unique index
db.QuarterlyEarningsData.dropIndex("ticker_1_quarter_1")

// Create new index without unique constraint
db.QuarterlyEarningsData.createIndex({"ticker": 1, "quarter": 1})
db.QuarterlyEarningsData.createIndex({"ticker": 1, "quarter": 1, "source.file_type": 1})
db.QuarterlyEarningsData.createIndex({"document_id": 1})
```

---

## 📋 **What Was Happening Before**

### **Upload Attempt 1 (Management):**
```
✅ insert_one() succeeds
✅ Document created: {ticker: "VHM", quarter: "2Q25", source.file_type: "management"}
```

### **Upload Attempt 2 (Sell-Side):**
```
❌ insert_one() FAILS - Duplicate key error!
❌ MongoDB rejects: "E11000 duplicate key error collection: VietnamStocks.QuarterlyEarningsData index: ticker_1_quarter_1 dup key: { ticker: \"VHM\", quarter: \"2Q25\" }"
❌ Or silently fails/overwrites depending on error handling
```

---

## ✅ **After the Fix**

### **Upload Attempt 1 (Management):**
```
✅ insert_one() succeeds
✅ Document 1: {_id: "abc123", ticker: "VHM", quarter: "2Q25", source.file_type: "management"}
```

### **Upload Attempt 2 (Sell-Side):**
```
✅ insert_one() succeeds
✅ Document 2: {_id: "def456", ticker: "VHM", quarter: "2Q25", source.file_type: "sell_side"}
```

### **Upload Attempt 3 (Buy-Side):**
```
✅ insert_one() succeeds
✅ Document 3: {_id: "ghi789", ticker: "VHM", quarter: "2Q25", source.file_type: "buy_side"}
```

**Total: 3 separate documents!** ✅

---

## 🎯 **Summary**

### **Problem:**
- Old unique index in MongoDB preventing multiple documents
- Code changes don't automatically update existing indexes

### **Solution:**
```bash
# Run once:
python fix_mongodb_indexes.py
```

### **Result:**
- Unique constraint removed
- Multiple documents per ticker/quarter allowed
- Each upload creates separate document

---

## 🚀 **Next Steps**

1. **Run the fix script** (or manually drop the index)
2. **Clear existing test data** (optional):
   ```javascript
   db.QuarterlyEarningsData.deleteMany({})
   ```
3. **Test the upload flow**:
   - Upload management presentation
   - Upload sell-side report
   - Add buy-side commentary
4. **Verify 3 documents** are created in MongoDB

After this fix, your system will work exactly as designed - each uploaded file creates a separate, independent document! 🎉

