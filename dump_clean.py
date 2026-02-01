import os
from ocr_service import OCRService

POPPLER_PATH = r"C:\poppler\poppler-24.08.0\Library\bin"
ocr = OCRService(poppler_path=POPPLER_PATH)

pdf_path = r"D:\Cua_Mai\Extract_data\FIle_PDF\078110_0001.pdf"
images = ocr.pdf_to_images(pdf_path)
with open("full_text_clean.txt", "w", encoding="utf-8") as f:
    for i, img in enumerate(images):
        lines = ocr.ocr_page(img)
        # Sort lines by Y then X
        lines.sort(key=lambda x: (x["y"], x["x"]))
        for l in lines:
            f.write(f"P{i+1}|Y{l['y']:.1f}|X{l['x']:.1f}|{l['text']}\n")
