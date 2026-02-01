"""
VinFast Invoice Parser - Text block-based extraction
"""
import re
from .base_parser import InvoiceParser

class VinFastParser(InvoiceParser):
    def __init__(self):
        self.VIN_REGEX = re.compile(r'[A-HJ-NPR-Z0-9]{17}')
    
    def can_handle(self, ocr_text: str) -> bool:
        """Detect if this is a VinFast invoice"""
        return bool(re.search(r'VINFAST', ocr_text, re.I))
    
    def extract_invoice_number(self, text: str) -> str:
        """Extract VinFast invoice number from header only - Golden Principle #1 (Robust)"""
        if not text: return None
        patterns = [
            r'S.?\s*\((?:Inv|Invoice)\s*No\.?\)\s*[:\-]?\s*([A-Z0-9]{5,20})',
            r'INV\s*NO\.?\s*[:\-]?\s*([A-Z0-9]{5,20})',
            r'H[ÓO]A\s*[ĐD]ƠN.*?S.?\s*[:\-]?\s*([0-9]{5,20})'
        ]
        for pat in patterns:
            m = re.search(pat, text, re.I | re.S | re.UNICODE)
            if m:
                num = m.group(1).strip()
                if not num.upper().startswith(('VIN', 'SK', 'SM')):
                    return num
        return None
    
    def extract_color(self, pages_data: list) -> str:
        """Extract color from VinFast invoice"""
        if not pages_data: return None
        full_text = " ".join([l["text"] for page in pages_data for l in page])
        color_patterns = [
            r'M[aà]u\s*s[oơ][n]\s*[:\-]?\s*([A-ZÀ-Ỹ ]{2,30})',
            r'M[aà]u\s*s[aắ]c\s*[:\-]?\s*([A-ZÀ-Ỹ ]{2,30})'
        ]
        for pat in color_patterns:
            m = re.search(pat, full_text, re.I | re.UNICODE)
            if m:
                color = m.group(1).strip()
                color = re.split(r'[,.\-\n]', color)[0].strip()
                return color
        return None
    
    def _is_real_vin(self, vin: str) -> bool:
        """VIN validation for VinFast"""
        if not vin or len(vin) != 17: return False
        # VinFast prefixes
        return vin.startswith(('RLL', 'RLU'))

    def extract_vehicles(self, pages_data: list, full_text: str) -> list:
        """
        VIN-Anchor Absolute Strategy - Golden Principle #2
        Unified with Hyundai logic but adapted for VinFast keywords (SK:, SM:)
        """
        vehicles = []
        vin_hits = []
        
        # 1. Collect ALL valid VINs
        for page_idx, page in enumerate(pages_data):
            for item in page:
                txt = item["text"].replace(" ", "").upper()
                # VinFast often has "SK:" prefix, search for the 17-char VIN
                match = re.search(r'([A-Z0-9]{17})', txt)
                if match:
                    vin = match.group(1)
                    if self._is_real_vin(vin):
                        vin_hits.append({
                            "vin": vin,
                            "x": item["x"],
                            "y": item["y"],
                            "page_idx": page_idx,
                            "page_data": page
                        })
        
        # 2. Sort by page and Y
        vin_hits.sort(key=lambda x: (x["page_idx"], x["y"]))
        
        # 3. Associate Engine and Description - Golden Principle #3
        for hit in vin_hits:
            vin = hit["vin"]
            vy = hit["y"]
            vx = hit["x"]
            page = hit["page_data"]
            
            # A. Engine Assignment (within same page, ±80px Y)
            engine = None
            for item in page:
                if abs(item["y"] - vy) <= 80:
                    # Look for SM: patterns
                    sm_match = re.search(r'SM[:\- ]*([A-Z0-9]{6,20})', item["text"].replace(" ", "").upper())
                    if sm_match:
                        engine = sm_match.group(1)
                        break
            
            # B. Description Assignment (Back-trace from VIN pos)
            # Find lines above the VIN that look like vehicle names
            desc_items = []
            for item in page:
                # Items slightly above or on the same line, to the left
                if item["x"] < vx - 50 and -100 <= (vy - item["y"]) <= 30:
                    txt = item["text"].upper()
                    # Filter noise
                    if re.search(r'\d{1,3}(?:\.\d{3}){2,}', txt): continue 
                    if txt in ["CÁI", "CAI", "CHIẾC", "CHIEC"]: continue
                    if any(kw in txt for kw in ["CỘNG", "TIỀN", "THUẾ", "VAT", "TỔNG"]): continue
                    desc_items.append(item)
            
            desc_items.sort(key=lambda d: (d["y"], d["x"]))
            description = " ".join([d["text"] for d in desc_items]).strip()
            
            vehicles.append({
                "chassis_number": vin,
                "engine_number": engine,
                "description_hint": description if description else vin
            })
            
        print(f"DEBUG [VinFast]: VIN hits found: {len(vin_hits)}")
        return vehicles
