# Streamlit Cloud Deployment Guide for PDF_Extractor

## Files Required for Deployment

### 1. requirements.txt
Contains Python package dependencies:
```
streamlit
pandas
numpy
plotly
typing
openpyxl
requests
python-dotenv
openai
google-api-python-client
pymongo
certifi
pytesseract
pdf2image
pillow
reportlab
```

### 2. packages.txt
Contains system-level dependencies for Ubuntu (Streamlit Cloud uses Ubuntu):
```
tesseract-ocr
tesseract-ocr-eng
tesseract-ocr-vie
poppler-utils
```

## Deployment Steps

### Step 1: Prepare Your Repository
1. Ensure both `requirements.txt` and `packages.txt` are in your repository root
2. Your main app file should be accessible (e.g., `pages/PDF_Extractor.py`)
3. Commit and push all changes to your GitHub repository

### Step 2: Deploy to Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with your GitHub account
3. Click "New app"
4. Select your repository: `dzasmint/Company_Dashboard`
5. Set the main file path: `pages/PDF_Extractor.py`
6. Click "Deploy"

### Step 3: Monitor Deployment
- The deployment process will:
  1. Install system packages from `packages.txt`
  2. Install Python packages from `requirements.txt`
  3. Start your Streamlit app
- Check the deployment logs for any errors

## Important Notes

### Language Support
The `packages.txt` includes:
- `tesseract-ocr-eng`: English language pack
- `tesseract-ocr-vie`: Vietnamese language pack

To add more languages, add to `packages.txt`:
```
tesseract-ocr-fra  # French
tesseract-ocr-deu  # German
tesseract-ocr-spa  # Spanish
tesseract-ocr-chi-sim  # Chinese Simplified
tesseract-ocr-chi-tra  # Chinese Traditional
```

### File Upload Limits
Streamlit Cloud has file upload limits:
- Default: 200MB per file
- For larger files, consider implementing file chunking or compression

### Memory Considerations
- OCR processing can be memory-intensive
- Large PDFs might cause memory issues
- Consider adding file size validation in your app

## Troubleshooting

### Common Issues and Solutions

1. **Tesseract not found**
   - Ensure `tesseract-ocr` is in `packages.txt`
   - Check deployment logs for installation errors

2. **Poppler not found**
   - Ensure `poppler-utils` is in `packages.txt`
   - Verify `pdf2image` is in `requirements.txt`

3. **Language pack errors**
   - Add specific language packs to `packages.txt`
   - Default installation includes English

4. **Memory errors**
   - Reduce image DPI in `extract_pdf_text_ocr()` function
   - Process fewer pages at once
   - Add file size limits

### Environment Variables (if needed)
If your app requires environment variables:
1. Go to your app settings in Streamlit Cloud
2. Add environment variables in the "Secrets" section
3. Access them in your code using `st.secrets`

## Testing Your Deployment

1. **Test file uploads**: Try various PDF and image formats
2. **Test OCR languages**: Verify Vietnamese and English recognition
3. **Test error handling**: Upload invalid files to check error messages
4. **Monitor performance**: Check processing speed with different file sizes

## App URL
Once deployed, your app will be available at:
`https://dzasmint-company-dashboard-pagespdf-extractor-[hash].streamlit.app`

## Updates and Maintenance

To update your deployed app:
1. Make changes to your code locally
2. Commit and push to your GitHub repository
3. Streamlit Cloud will automatically redeploy

For dependency updates:
1. Update `requirements.txt` or `packages.txt`
2. Commit and push changes
3. Streamlit Cloud will reinstall dependencies on next deployment
