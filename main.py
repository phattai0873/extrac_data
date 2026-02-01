from fastapi import FastAPI, UploadFile, File, BackgroundTasks
import shutil
import os
import uuid
from ocr_service import OCRService
from llm_service import LLMService

app = FastAPI(title="Invoice Extraction Engine")

# Cấu hình Poppler
POPPLER_PATH = os.getenv("POPPLER_PATH")
if not POPPLER_PATH and os.name == 'nt':
    # Thử đường dẫn mặc định trên máy bạn (đã thấy trong test_extraction.py)
    default_path = r"C:\poppler\poppler-24.08.0\Library\bin"
    if os.path.exists(default_path):
        POPPLER_PATH = default_path

# Khởi tạo services khi startup
ocr_service = OCRService(poppler_path=POPPLER_PATH)
llm_service = LLMService(model_name=os.getenv("OLLAMA_MODEL", "llama3:8b"))

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/extract")
async def extract_invoice(file: UploadFile = File(...)):
    # 1. Lưu file tạm
    file_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1]
    temp_path = os.path.join(UPLOAD_DIR, f"{file_id}{file_extension}")
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # 1. Chạy OCR + Layout Detection + Specialized Extraction
        extracted_data, layout_type, full_raw_text, invoice_no = ocr_service.extract_text_from_pdf(temp_path)
        
        print(f"Layout Detected: {layout_type}")
        print(f"Items found: {len(extracted_data)}")
        print(f"Invoice No (OCR): {invoice_no}")
        if extracted_data:
            print(f"DEBUG: First vehicle description_hint: {extracted_data[0].get('description_hint', '')[:200]}")

        # 2. Dùng AI làm sạch và ánh xạ JSON (Refine)
        json_data = llm_service.refine_extraction(
            full_raw_text, extracted_data, layout_type, invoice_no_from_ocr=invoice_no
        )
        if not json_data.get("invoice_number") and invoice_no:
            json_data["invoice_number"] = invoice_no
        
        return {
            "status": "success",
            "layout_detected": layout_type,
            "filename": file.filename,
            "data": json_data
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        # Dọn dẹp file tạm
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
