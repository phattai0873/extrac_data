import os
from ocr_service import OCRService

POPPLER_PATH = r"C:\poppler\poppler-24.08.0\Library\bin"
ocr = OCRService(poppler_path=POPPLER_PATH)

pdf_path = r"D:\Cua_Mai\Extract_data\FIle_PDF\078110_0001.pdf"

if os.path.exists(pdf_path):
    extracted, layout, full_text, invoice_no = ocr.extract_text_from_pdf(pdf_path)
    with open("final_debug_output.txt", "w", encoding="utf-8") as f:
        f.write(f"Layout: {layout}\n")
        f.write(f"Invoice No: {invoice_no}\n")
        f.write(f"Vehicles: {len(extracted)}\n")
        for v in extracted:
            f.write(f"VIN: {v['chassis_number']}, Engine: {v.get('engine_number')}, Desc: {v.get('description_hint')[:50]}\n")
        f.write("\n--- FULL TEXT ---\n")
        f.write(full_text)
else:
    print(f"File not found: {pdf_path}")
