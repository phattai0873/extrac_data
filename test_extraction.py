from ocr_service import OCRService
import json

# Test with real PDF
ocr = OCRService(poppler_path=r"C:\poppler\poppler-24.08.0\Library\bin")
pdf_path = r"d:\Cua_Mai\Extract_data\FIle_PDF\080285_0001.pdf"

print(f"Testing with: {pdf_path}")
print("=" * 80)

vehicles, layout, raw_text, invoice_no = ocr.extract_text_from_pdf(pdf_path)

print("\n" + "=" * 80)
print(f"RESULTS:")
print(f"Layout: {layout}")
print(f"Invoice No: {invoice_no}")
print(f"Vehicles found: {len(vehicles)}")
print("\nVehicles:")
for i, v in enumerate(vehicles, 1):
    print(f"\n{i}. VIN: {v.get('chassis_number')}")
    print(f"   Engine: {v.get('engine_number')}")
    print(f"   Description: {v.get('description_hint', '')[:80]}...")
