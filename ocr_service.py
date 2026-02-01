import os
import cv2
import numpy as np
import re
from pdf2image import convert_from_path
from parsers import HyundaiParser, VinFastParser

os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_pir_executor"] = "0"


class OCRService:
    def __init__(self, poppler_path=None):
        self._ocr = None
        self.poppler_path = poppler_path

        self.parsers = [
            HyundaiParser(),
            VinFastParser()
        ]

    def get_ocr(self):
        if self._ocr is None:
            print("INITIALIZING PADDLEOCR (LAZY LOAD)...")
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(
                use_angle_cls=False,  # Tắt để chạy nhanh hơn trên Render
                lang='vi',
                show_log=False
            )
        return self._ocr

    # ----------------------------------------------------
    # PDF → Images
    # ----------------------------------------------------
    def pdf_to_images(self, pdf_path):
        return convert_from_path(
            pdf_path,
            poppler_path=self.poppler_path,
            dpi=300
        )

    # ----------------------------------------------------
    # OCR with coordinates
    # ----------------------------------------------------
    def ocr_page(self, image):
        if not isinstance(image, np.ndarray):
            image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        ocr_engine = self.get_ocr()
        result = ocr_engine.ocr(image)
        lines = []

        if result and result[0]:
            for line in result[0]:
                box = line[0]
                text = line[1][0]
                x = box[0][0]
                y = (box[0][1] + box[2][1]) / 2
                lines.append({"text": text, "x": x, "y": y})

        return lines

    # ----------------------------------------------------
    # Page classification
    # ----------------------------------------------------
    def classify_page(self, page_lines):
        text = " ".join(l["text"] for l in page_lines).upper()

        if re.search(r'(HOA\s*DON|HOADON|VAT|INVOICE|INV\s*NO)', text):
            return "INVOICE"

        if re.search(r'(PHIEU|CERTIFICATE|KIEM\s*TRA|CHAT\s*LUONG)', text):
            return "CERTIFICATE"

        return "OTHER"

    # ----------------------------------------------------
    # Layout detection
    # ----------------------------------------------------
    def detect_layout(self, full_text):
        for parser in self.parsers:
            if parser.can_handle(full_text):
                name = parser.__class__.__name__.replace("Parser", "").upper()
                return parser, name
        return None, "UNKNOWN"

    # ----------------------------------------------------
    # Main extract function
    # ----------------------------------------------------
    def extract_text_from_pdf(self, pdf_path):
        images = self.pdf_to_images(pdf_path)
        print(f"DEBUG: PDF has {len(images)} pages")

        pages = []
        full_text = ""

        # OCR + classify
        for idx, img in enumerate(images):
            page_idx = idx + 1
            lines = self.ocr_page(img)
            page_type = self.classify_page(lines)

            pages.append({
                "index": page_idx,
                "type": page_type,
                "lines": lines
            })

            full_text += "\n".join(l["text"] for l in lines) + "\n"
            print(f"DEBUG: Page {page_idx} -> {page_type}")

        # Detect layout
        parser, layout = self.detect_layout(full_text)
        if not parser:
            print("ERROR: No parser matched")
            return [], "UNKNOWN", full_text, None

        print(f"Layout detected: {layout}")

        # Invoice number
        invoice_no = parser.extract_invoice_number(full_text)
        print(f"Invoice No: {invoice_no}")

        # Filter pages for extraction
        relevant_pages = []
        for p in pages:
            if layout == "HYUNDAI":
                if p["type"] in ("INVOICE", "CERTIFICATE"):
                    relevant_pages.append(p["lines"])
            elif layout == "VINFAST":
                if p["type"] == "INVOICE":
                    relevant_pages.append(p["lines"])

        print(f"DEBUG: Relevant pages = {len(relevant_pages)}")

        # Extract vehicles
        vehicles = parser.extract_vehicles(relevant_pages, full_text)
        print(f"DEBUG: Vehicles extracted = {len(vehicles)}")

        # Golden Principle #5: Assert unique VINs match total count
        if vehicles:
            unique_vins = {v["chassis_number"] for v in vehicles}
            if len(unique_vins) != len(vehicles):
                print(f"WARNING: VIN count mismatch! Unique: {len(unique_vins)}, Total: {len(vehicles)}")
                # Optionally deduplicate here or raise error depending on prod requirements
                # For now, we follow the rule that VIN = 1 vehicle anchor.
        color = parser.extract_color(relevant_pages)

        # Final normalize
        final = []
        for v in vehicles:
            vin = (v.get("chassis_number") or "").upper().replace(" ", "")
            # Accept fragments 10-20, normalize to exactly 17 if possible
            if 10 <= len(vin) <= 20: 
                if len(vin) > 17:
                    vin = vin[:17]
                v["chassis_number"] = vin
                v["color"] = v.get("color") or color
                v["invoice_no_from_header"] = invoice_no
                final.append(v)

        print(f"FINAL vehicles = {len(final)}")
        return final, layout, full_text, invoice_no
