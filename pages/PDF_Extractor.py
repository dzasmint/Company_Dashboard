import streamlit as st
import pytesseract
from PIL import Image
import io
from typing import Optional
import tempfile
import os
import platform

# Try to import pdf2image with better error handling
try:
    import pdf2image
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

def configure_paths():
    """Configure paths for different operating systems"""
    system = platform.system()
    
    if system == "Windows":
        # Common Tesseract installation paths on Windows
        tesseract_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Users\AppData\Local\Tesseract-OCR\tesseract.exe"
        ]
        
        for path in tesseract_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break
        
        # Common poppler installation paths on Windows
        poppler_paths = [
            r"C:\Program Files\poppler\bin",
            r"C:\Program Files (x86)\poppler\bin",
            r"C:\poppler\bin",
            r"C:\poppler-windows\bin"
        ]
        
        for path in poppler_paths:
            if os.path.exists(path):
                os.environ["PATH"] += os.pathsep + path
                break
    
    elif system == "Linux":
        # For Streamlit Cloud and other Linux deployments
        # Tesseract should be available in PATH after apt installation
        # Check common locations just in case
        tesseract_paths = [
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract"
        ]
        
        for path in tesseract_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break

def check_dependencies():
    """Check if required dependencies are installed"""
    configure_paths()
    issues = []
    
    if not PDF2IMAGE_AVAILABLE:
        issues.append("pdf2image is not installed")
    
    try:
        pytesseract.get_tesseract_version()
    except Exception as e:
        issues.append("Tesseract is not installed or not in PATH")
    
    # Test poppler separately
    if PDF2IMAGE_AVAILABLE:
        try:
            # Create a minimal valid PDF for testing
            from reportlab.pdfgen import canvas
            import tempfile
            
            test_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
            c = canvas.Canvas(test_file.name)
            c.drawString(100, 750, "Test")
            c.save()
            test_file.close()
            
            try:
                pdf2image.convert_from_path(test_file.name, dpi=72, first_page=1, last_page=1)
            except Exception as e:
                if "poppler" in str(e).lower() or "unable to get page count" in str(e).lower():
                    issues.append("Poppler is not installed or not in PATH")
                else:
                    issues.append(f"PDF processing error: {str(e)}")
            finally:
                os.unlink(test_file.name)
                
        except ImportError:
            # If reportlab is not available, try a different approach
            try:
                # Try to call poppler directly
                import subprocess
                result = subprocess.run(['pdftoppm', '-h'], capture_output=True, text=True)
                if result.returncode != 0:
                    issues.append("Poppler is not installed or not in PATH")
            except FileNotFoundError:
                issues.append("Poppler is not installed or not in PATH")
            except Exception:
                issues.append("Cannot verify Poppler installation")
    
    return issues

def extract_pdf_text_ocr(uploaded_file, lang_string='eng') -> Optional[str]:
    """
    Extract text from uploaded PDF file using Tesseract OCR
    """
    if not PDF2IMAGE_AVAILABLE:
        st.error("pdf2image is not installed. Please install it using: pip install pdf2image")
        return None
    
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name
        
        # Convert PDF pages to images with enhanced error handling
        try:
            pages = pdf2image.convert_from_path(
                tmp_file_path, 
                dpi=300,
                first_page=1,
                last_page=None,
                poppler_path=None  # Let pdf2image find poppler
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "poppler" in error_msg or "unable to get page count" in error_msg:
                st.error("❌ Poppler is not installed or not found in PATH. Please install Poppler:")
                st.code("""
Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases
Extract to C:\\poppler and add C:\\poppler\\bin to PATH

Or use conda: conda install -c conda-forge poppler
                """)
                return None
            else:
                st.error(f"PDF conversion error: {str(e)}")
                return None
        
        # Extract text from each page using OCR
        extracted_text = ""
        total_pages = len(pages)
        
        # Create progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for page_num, page_image in enumerate(pages):
            status_text.text(f"Processing page {page_num + 1} of {total_pages}...")
            progress_bar.progress((page_num + 1) / total_pages)
            
            # Use Tesseract to extract text from the image
            page_text = pytesseract.image_to_string(page_image, lang=lang_string)
            extracted_text += f"\n--- Page {page_num + 1} ---\n"
            extracted_text += page_text
        
        # Clean up temporary file
        os.unlink(tmp_file_path)
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
        
        return extracted_text
        
    except Exception as e:
        st.error(f"Error extracting text from PDF using OCR: {str(e)}")
        # Clean up temporary file if it exists
        if 'tmp_file_path' in locals() and os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)
        return None

def extract_image_text_ocr(uploaded_file, lang_string='eng') -> Optional[str]:
    """
    Extract text from uploaded image file using Tesseract OCR
    """
    try:
        # Open image from uploaded file
        image = Image.open(uploaded_file)
        
        # Use Tesseract to extract text
        extracted_text = pytesseract.image_to_string(image, lang=lang_string)
        
        return extracted_text
        
    except Exception as e:
        st.error(f"Error extracting text from image using OCR: {str(e)}")
        return None

def main():
    st.set_page_config(page_title="PDF/Image OCR Extractor", layout="wide")
    
    st.title("PDF/Image OCR Text Extractor")
    st.write("Upload a PDF or image file to extract text using Tesseract OCR")
    
    # Check for pdf2image dependency first
    if not PDF2IMAGE_AVAILABLE:
        st.error("❌ pdf2image is not installed!")
        st.warning("PDF extraction is not available. You can still extract text from images.")
        
        with st.expander("How to install pdf2image", expanded=True):
            st.markdown("""
            **Install pdf2image using pip:**
            ```bash
            pip install pdf2image
            ```
            
            **Or using conda:**
            ```bash
            conda install -c conda-forge pdf2image
            ```
            
            **Note:** You'll also need Poppler installed on your system for PDF processing.
            See the installation guide below for complete setup instructions.
            """)
    
    # Check dependencies and show status
    dependency_issues = check_dependencies()
    if dependency_issues:
        st.error("Additional Dependency Issues Found:")
        for issue in dependency_issues:
            st.write(f"❌ {issue}")
        st.write("Please see installation instructions below.")
        
        # Show quick fix for Windows users
        if platform.system() == "Windows" and any("poppler" in issue.lower() for issue in dependency_issues):
            st.info("🔧 Quick Fix for Windows Users:")
            st.code("""
# Install using conda (recommended)
conda install -c conda-forge poppler

# Or download manually:
# 1. Download from: https://github.com/oschwartz10612/poppler-windows/releases
# 2. Extract to C:\\poppler
# 3. Add C:\\poppler\\bin to your PATH environment variable
# 4. Restart your application
            """)
    else:
        if PDF2IMAGE_AVAILABLE:
            st.success("✅ All dependencies are properly installed!")
        else:
            st.warning("⚠️ pdf2image not installed - PDF extraction unavailable")
    
    # Add OCR configuration options
    st.sidebar.header("OCR Settings")
    languages = st.sidebar.multiselect(
        "Select OCR Languages",
        options=['eng', 'vie', 'fra', 'deu', 'spa', 'chi_sim', 'chi_tra'],
        default=['eng'],
        help="Select languages for OCR recognition"
    )
    
    # File upload widget - modify accepted types based on availability
    if PDF2IMAGE_AVAILABLE:
        file_types = ['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp']
        help_text = "Upload a PDF or image file to extract text using OCR"
    else:
        file_types = ['png', 'jpg', 'jpeg', 'tiff', 'bmp']
        help_text = "Upload an image file to extract text using OCR (PDF support requires pdf2image installation)"
    
    uploaded_file = st.file_uploader(
        "Choose a file", 
        type=file_types,
        help=help_text
    )
    
    if uploaded_file is not None:
        # Display file details
        st.subheader("File Information")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write(f"**Filename:** {uploaded_file.name}")
        with col2:
            st.write(f"**File size:** {uploaded_file.size} bytes")
        with col3:
            file_type = "PDF" if uploaded_file.type == "application/pdf" else "Image"
            st.write(f"**File type:** {file_type}")
        
        # Check if user uploaded PDF without pdf2image
        if uploaded_file.type == "application/pdf" and not PDF2IMAGE_AVAILABLE:
            st.error("Cannot process PDF files without pdf2image. Please install pdf2image or upload an image file instead.")
            st.code("pip install pdf2image")
            return
        
        # Extract text button
        if st.button("Extract Text using OCR"):
            remaining_issues = [issue for issue in dependency_issues if "pdf2image" not in issue]
            if remaining_issues:
                st.error("Cannot proceed due to missing dependencies. Please install required packages.")
                return
                
            with st.spinner("Extracting text using Tesseract OCR..."):
                # Join selected languages
                lang_string = '+'.join(languages) if languages else 'eng'
                
                if uploaded_file.type == "application/pdf":
                    extracted_text = extract_pdf_text_ocr(uploaded_file, lang_string)
                else:
                    extracted_text = extract_image_text_ocr(uploaded_file, lang_string)
            
            if extracted_text:
                st.success("OCR text extraction completed!")
                
                # Display extracted text
                st.subheader("Extracted Text Data")
                
                # Add download button for extracted text
                st.download_button(
                    label="Download Extracted Text",
                    data=extracted_text,
                    file_name=f"{uploaded_file.name}_ocr_extracted.txt",
                    mime="text/plain"
                )
                
                # Display text in expandable section
                with st.expander("View Extracted Text", expanded=True):
                    st.text_area(
                        "OCR Extracted Content",
                        value=extracted_text,
                        height=400,
                        disabled=True
                    )
                
                # Display text statistics
                st.subheader("Text Statistics")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Characters", len(extracted_text))
                with col2:
                    st.metric("Total Words", len(extracted_text.split()))
                with col3:
                    st.metric("Total Lines", len(extracted_text.split('\n')))
            
            else:
                st.error("Failed to extract text from the file using OCR.")
    
    else:
        st.info("Please upload a PDF or image file to begin OCR extraction.")
        
    # Add installation instructions
    with st.expander("Installation Requirements", expanded=bool(dependency_issues or not PDF2IMAGE_AVAILABLE)):
        st.markdown("""
        **Required Python packages:**
        ```bash
        pip install pytesseract pdf2image pillow streamlit
        ```
        
        **Or install all at once:**
        ```bash
        pip install pytesseract pdf2image pillow streamlit
        ```
        
        **Tesseract OCR Installation:**
        - **Windows:** 
          - Download from: https://github.com/UB-Mannheim/tesseract/wiki
          - Add tesseract.exe to your PATH
          - Or set path in code: `pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'`
        - **macOS:** `brew install tesseract`
        - **Linux:** `sudo apt-get install tesseract-ocr`
        
        **Poppler Installation (for PDF processing):**
        - **Windows (Method 1 - Recommended):** 
          ```bash
          conda install -c conda-forge poppler
          ```
        - **Windows (Method 2 - Manual):** 
          - Download from: https://github.com/oschwartz10612/poppler-windows/releases
          - Extract to C:\\poppler
          - Add C:\\poppler\\bin to your PATH environment variable
          - Restart your application/computer
        - **macOS:** `brew install poppler`
        - **Linux:** `sudo apt-get install poppler-utils`
        
        **Additional Language Packs:**
        
        **For macOS (using Homebrew):**
        ```bash
        # Install additional language packs for Tesseract
        brew install tesseract-lang  # This includes most languages including Vietnamese
        # Or install specific languages:
        # Note: Most language packs are included with the main tesseract installation via Homebrew
        ```
        
        **For Linux (Ubuntu/Debian):**
        ```bash
        # Install additional language packs for Tesseract
        sudo apt-get install tesseract-ocr-vie  # Vietnamese
        sudo apt-get install tesseract-ocr-fra  # French
        sudo apt-get install tesseract-ocr-deu  # German
        sudo apt-get install tesseract-ocr-spa  # Spanish
        sudo apt-get install tesseract-ocr-chi-sim  # Chinese Simplified
        sudo apt-get install tesseract-ocr-chi-tra  # Chinese Traditional
        ```
        
        **Troubleshooting:**
        - Ensure both Tesseract and Poppler are in your system PATH
        - Restart your terminal/IDE after installation
        - On Windows, you may need to restart your computer
        - If using Anaconda/Miniconda, prefer conda installation over manual installation
        """)

if __name__ == "__main__":
    main()
