"""
Hyundai Invoice Parser - Ultimate Precision Row Extraction
"""
import re
from .base_parser import InvoiceParser

class HyundaiParser(InvoiceParser):
    def __init__(self):
        print("[HYUNDAI PARSER v3.6 - Final Shield Loaded]")
        # VIN Regex: Must end with digits (serial number) to avoid swallowing noise at the end
        self.VIN_PATTERN = re.compile(r'(MF3|KM|KN|MAL|RLL|RLU)[A-Z0-9]{5,11}[0-9]{4,6}')
        
        # Column detection
        self.SK_PATTERN = r'S[ÔỐOÓÖ06B]?\s*KHUNG|VIN\s*NO|CHASSIS\s*N[O09\)]'
        self.SM_PATTERN = r'S[ÔỐOÓÖ06B]?\s*M[ÂÁA]Y|ENGINE\s*NO|ENGINE\s*N[O09\)]'
        self.STT_PATTERN = r'STT|No\.?'
        
        self.ENGINE_BLACKLIST = ["HOADON", "GIATRI", "VAT", "INVOICE", "THANHTIEN", "SOLUONG", "DONGIA"]
        self.VIN_BLACKLIST = ["PRODUCTION", "OVERALL", "DIMENSIONS", "TECHNICAL", "SPECIFICATION", "COUNTRY"]

    def _is_real_vin(self, vin: str) -> bool:
        """Strict VIN validation for Hyundai VN - Golden Principle #2 (Strict)"""
        # 1. Flexible Length (handling OCR fragments and splits: 10-20 chars)
        if not vin or len(vin) < 10 or len(vin) > 20:
            return False

        # 2. Correct common OCR errors before validation
        vin = vin.replace('O', '0').replace('I', '1').replace('Q', '0')

        # 3. Must start with valid prefixes
        if not vin.startswith(("MF3", "KM", "KN", "MAL", "RLL", "RLU")):
            return False

        # 4. Must have digits (avoids pure text labels)
        if sum(c.isdigit() for c in vin) < 4:
            return False

        return True

    def _clean_engine(self, raw_text: str) -> str | None:
        """Strict Engine No validation - Golden Principle #3 (Strict)"""
        if not raw_text:
            return None

        text = raw_text.upper().replace(" ", "")

        # Blacklist model names and industrial metadata/labels
        BLACKLIST = [
            "STARGAZER", "HYUNDAI", "XEOTO", "CONCHO", "NGUOI",
            "CONCH", "SEAT", "CHO", "CRETA", "TUCSON", "SANTAFE", "VENUE",
            "CHASSIS", "ENGINE", "PRODUCTION", "OVERALL", "DIMENSIONS",
            "TOKHAI", "HANGHOA", "NHAPKHAU", "CUSTOMS", "DECLARATION",
            "S6TOKHAI", "SỐTK", "TRUNG", "LOAI", "TYPE", "VARIANT", "MODEL", "IOAI"
        ]
        if any(b in text for b in BLACKLIST):
            return None

        # Engine usually 8-20 chars, mixed alphanumeric
        candidates = re.findall(r'[A-Z0-9]{8,20}', text)
        for c in candidates:
            # FIX: Convert Q -> 0 (extremely common OCR error in engine numbers)
            c = c.replace('Q', '0')
            if any(ch.isdigit() for ch in c) and any(ch.isalpha() for ch in c):
                # Ensure it's not a VIN fragment (prefix check)
                if c.startswith(("MF3", "KM", "KN", "MAL", "RLL", "RLU")):
                    continue
                return c

        return None

    def can_handle(self, ocr_text: str) -> bool:
        keywords = ["HYUNDAI", "THANH CONG", "Số khung", "Số máy", "Vin No"]
        return sum(1 for k in keywords if k.upper() in ocr_text.upper()) >= 2

    def extract_invoice_number(self, text: str) -> str:
        """Extract invoice number from header only - Golden Principle #1 (Robust)"""
        if not text: return None
        patterns = [
            # Handle variations of S[ốoö6] (Inv No) : 000123
            r'S.?\s*\((?:Inv|Invoice)\s*No\.?\)\s*[:\-]?\s*([A-Z0-9]{5,20})',
            r'INV\s*NO\.?\s*[:\-]?\s*([A-Z0-9]{5,20})',
            # Multi-line match for Hóa đơn ... Số
            r'H[ÓO]A\s*[ĐD]ƠN[^\n]*\n.*?S.?\s*[:\-]?\s*([0-9]{5,20})',
            r'H[ÓO]A\s*[ĐD]ƠN.*?S.?\s*[:\-]?\s*([0-9]{5,20})'
        ]
        for pat in patterns:
            m = re.search(pat, text, re.I | re.S | re.UNICODE)
            if m: return m.group(1).strip()
        return None

    def extract_color(self, pages_data: list) -> str:
        if not pages_data: return None
        # Scan all pages for color
        full_text = " ".join([l["text"] for page in pages_data for l in page])
        color_patterns = [
            r'M[aà]u\s*s[aắ]c\s*[:\-]?\s*([A-ZÀ-Ỹ\s]{2,20})',
            r'M[aà]u\s*s[oơ]n\s*[:\-]?\s*([A-ZÀ-Ỹ\s]{2,20})'
        ]
        for pat in color_patterns:
            match = re.search(pat, full_text, re.I | re.UNICODE)
            if match:
                color = match.group(1).strip()
                color = re.split(r'[,.\-\n\s]{2,}', color)[0].strip()
                if len(color) >= 2: return color
        return None

    def extract_vehicles(self, pages_data: list, full_text: str) -> list:
        """
        Cluster-based Line Merging Strategy - Golden Principle #2
        Solves split-box VINs (e.g. prefix and tail in different boxes).
        """
        vehicles = []
        vin_hits = []
        seen_vins = set()
        
        for page_idx, page in enumerate(pages_data):
            # 1. Cluster items into lines by Y coordinate (Distance-based)
            sorted_items = sorted(page, key=lambda x: x["y"])
            lines_data = []
            if sorted_items:
                current_line = [sorted_items[0]]
                for i in range(1, len(sorted_items)):
                    # Merge if vertical gap is small (up to 25px is safer for car rows)
                    if sorted_items[i]["y"] - current_line[-1]["y"] <= 25:
                        current_line.append(sorted_items[i])
                    else:
                        lines_data.append(current_line)
                        current_line = [sorted_items[i]]
                lines_data.append(current_line)

            # 2. Analyze each merged line
            for line_items in lines_data:
                line_items.sort(key=lambda x: x["x"])
                # Merge into a single string for fragment reconstruction
                line_text = "".join([it["text"] for it in line_items]).upper().replace(" ", "")
                # Normalize OCR errors
                line_text = line_text.replace('O', '0').replace('I', '1').replace('Q', '0').replace('$', 'S')
                
                if "MF3" in line_text:
                    print(f"DEBUG MERGED LINE (len={len(line_text)}): {line_text}")
                
                # Use finditer with the flexible but non-greedy regex
                for match in self.VIN_PATTERN.finditer(line_text):
                    vin = match.group(0)
                    if self._is_real_vin(vin) and vin not in seen_vins:
                        # Find the Y center of this cluster
                        avg_y = sum(it["y"] for it in line_items) / len(line_items)
                        vin_hits.append({
                            "vin": vin,
                            "x": line_items[0]["x"],
                            "y": avg_y,
                            "page_idx": page_idx,
                            "page_data": page
                        })
                        seen_vins.add(vin)
        
        # 3. Final VIN Hits Post-Processing
        # (Already handled by seen_vins and self._is_real_vin)
        vin_hits.sort(key=lambda x: (x["page_idx"], x["y"]))
        print(f"DEBUG [Hyundai]: Total UNIQUE VIN anchors found: {len(vin_hits)}")

        # 4. Data Association logic
        for hit in vin_hits:
            vin = hit["vin"]
            vy = hit["y"]
            vx = hit["x"]
            page = hit["page_data"]
            
            # Row Window: Search for Engine/Desc within the neighborhood
            engine = None
            desc_items = []
            
            for item in page:
                # Same row logic (+/- 55px from cluster center)
                if abs(item["y"] - vy) <= 55:
                    # Engine extraction
                    e = self._clean_engine(item["text"])
                    if e and e != vin:
                        # Preference for 10-12 char alphanumeric strings
                        engine = e
                    
                    # Description extraction (exclude what we already know)
                    it_txt = item["text"].upper()
                    if not any(bl in it_txt for bl in self.VIN_BLACKLIST + self.ENGINE_BLACKLIST + ["STARGAZER X"]):
                        if len(item["text"]) > 2 and item["x"] < vx + 100:
                            desc_items.append(item)
            
            desc_items.sort(key=lambda d: (d["y"], d["x"]))
            description = " ".join([d["text"] for d in desc_items]).strip()

            vehicles.append({
                "chassis_number": vin,
                "engine_number": engine,
                "description_hint": description
            })
            
        return vehicles

    def _find_column_x(self, page_data, pattern):
        for l in page_data:
            if re.search(pattern, l["text"].upper().replace(" ", ""), re.I):
                return l["x"]
        return None
