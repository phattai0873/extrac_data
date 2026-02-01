import os
from ocr_service import OCRService

POPPLER_PATH = r"C:\poppler\poppler-24.08.0\Library\bin"
ocr = OCRService(poppler_path=POPPLER_PATH)

pdf_path = r"D:\Cua_Mai\Extract_data\FIle_PDF\078110_0001.pdf"
images = ocr.pdf_to_images(pdf_path)
for i, img in enumerate(images):
    lines = ocr.ocr_page(img)
    text = " ".join([l["text"] for l in lines])
    print(f"--- PAGE {i+1} ---")
    print(text)
    print("\n")
