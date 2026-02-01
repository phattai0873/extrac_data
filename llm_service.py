import ollama
import json
import re

# Dictionary sửa lỗi OCR phổ biến (chữ mờ/sai) → chữ đúng tiếng Việt
OCR_FIX_DICT = [
    # Cụm dài trước để tránh ghi đè
    ("Xe 6 tô ", "Xe ô tô "),
    ("Xe 6 tô", "Xe ô tô"),
    ("Xe tö con", "Xe ô tô con"),
    ("Xe t con", "Xe ô tô con"),
    ("xe tö con", "Xe ô tô con"),
    ("xe t con", "Xe ô tô con"),
    ("khöng ké nguri", "không kể người"),
    ("khong ke nguri", "không kể người"),
    ("khöng ké người", "không kể người"),
    ("khong ke người", "không kể người"),
    ("ngui läi", "người lái"),
    ("ngui lai", "người lái"),
    ("nguri lái", "người lái"),
    ("nguri lai", "người lái"),
    ("ch ngöi", "chỗ ngồi"),
    ("ch ngói", "chỗ ngồi"),
    ("ch ngoi", "chỗ ngồi"),
    ("Ma loai", "Mã loại"),
    ("ma loai", "Mã loại"),
    ("Ma loại", "Mã loại"),
    ("chiéc 1.0 x", "chiếc 1.0 X"),
    ("chiec 1.0 x", "chiếc 1.0 X"),
    ("chiéc 1.0 X", "chiếc 1.0 X"),
    ("STARGAZER chiec", "STARGAZER X"),
    ("STARGAZER chiéc", "STARGAZER X"),
    ("m6i 100%", "mới 100%"),
    ("mÓi 100%", "mới 100%"),
    ("moi 100%", "mới 100%"),
    ("m6i chiéc", "mới chiếc"),
    ("moi chiéc", "mới chiếc"),
    ("khöng ké", "không kể"),
    ("khong ke", "không kể"),
    ("nguri ", "người "),
    ("ngui ", "người "),
    ("hieu ", "hiệu "),
    ("chiéc", "chiếc"),
    ("chiec", "chiếc"),
    ("läi", "lái"),
    ("ké ", "kể "),
    ("loai", "loại"),
    ("m6i", "mới"),
    ("mÓi", "mới"),
    ("moi ", "mới "),
    ("ngoi", "ngồi"),
    ("ngöi", "ngồi"),
    ("ngói", "ngồi"),
    ("läi]", "lái)"),
    ("lai]", "lái)"),
    ("ngoi hieu", "ngồi hiệu"),
    ("ngöi hieu", "ngồi hiệu"),
    # VinFast / form chung
    ("ch ngi", "chỗ ngồi"),
    ("chỗ ngéi", "chỗ ngồi"),
    ("chỗ ngei", "chỗ ngồi"),
    ("N7TP0I", "N7TP01"),
    ("Tring", "Trắng"),
    ("Tráng", "Trắng"),
    ("Mau Tráng", "Màu Trắng"),
    ("Mau Trang", "Màu Trắng"),
    ("tay lái thuan", "tay lái thuận"),
    ("mói 100%", "mới 100%"),
    ("nhan hiéu", "nhãn hiệu"),
    ("nhan hieu", "nhãn hiệu"),
    ("94KI04", "94KL04"),
    # Hyundai mô tả
    ("ch06 nguikhng kể", "chở 06 người (không kể"),
    ("ch06 người", "chở 06 người"),
    ("ch&06", "chở 06"),
    ("l6W7D661V", "I6W7D661V"),
    ("STARGAZER .1.0 chiếc X", "STARGAZER X"),
    ("khng ke", "không kể"),
    ("nguikhng", "người (không"),
]

def _parse_description_fallback(hint):
    """Refine vehicle description from raw hint text when LLM is unavailable."""
    if not hint:
        return "", None, None
    text = hint.replace("\n", " ").strip()
    
    # 1. Try to extract specific description (Xe + Brand + Details)
    # Supports VinFast, Hyundai, etc.
    desc_match = re.search(
        r"Xe\s+[^;]+?(?:Vinfast|Hyundai|Toyota|Ford)[^;]+?(?:\d+\s*ch[^;]*?)(?:Mau\s+[A-Za-zÀ-ỹ]+)?",
        text, re.I | re.DOTALL
    )
    if not desc_match:
        # Fallback to anything starting with "Xe " or containing "Hyundai/Vinfast"
        desc_match = re.search(r"(?:Xe|Hyundai|Vinfast)\s+[^;]+", text, re.I | re.DOTALL)
    
    desc = (desc_match.group(0).strip() if desc_match else text[:250].strip()).strip()
    
    # 2. Extract Color: Look for "Màu" or specific keywords
    color = None
    color_match = re.search(r"(?:Mau|Màu)\s+([A-Za-zÀ-ỹ ]+)", text, re.I)
    if color_match:
        color_val = color_match.group(1).strip()
        # Clean up: take first 1-2 words or until delimiter
        color = re.split(r'[,.;\-]', color_val)[0].split('  ')[0].strip()
    
    # 3. Extract Seats: e.g., "5 chỗ", "7 chỗ"
    seats = None
    seats_match = re.search(r"(\d+)\s*ch[ỗo]", text, re.I)
    if seats_match:
        seats = seats_match.group(1)
        
    return desc, color, seats

class LLMService:
    def __init__(self, model_name="llama3:8b"):
        self.model_name = model_name

    @staticmethod
    def apply_ocr_dictionary(text):
        """Áp dụng dictionary sửa lỗi OCR cho chuỗi (vehicle_description, color, ...)."""
        if not text or not isinstance(text, str):
            return text
        s = text
        for wrong, right in OCR_FIX_DICT:
            s = s.replace(wrong, right)
        return s

    def refine_extraction(self, raw_ocr_text, extracted_data, layout_type, invoice_no_from_ocr=None):
        if not extracted_data:
            return {"invoice_number": invoice_no_from_ocr, "vehicle_list": []}

        fallback_invoice = (
            extracted_data[0].get("invoice_no_from_header") or invoice_no_from_ocr
        )

        system_prompt = "You are a Professional Data Entry Robot. Output ONLY JSON. No conversation."
        
        user_prompt = f"""
YOUR TASK:
Extract details for EVERY vehicle listed below. You MUST return exactly {len(extracted_data)} items in the 'vehicle_list' array. Use ONLY the provided REFERENCE OCR TEXT below.

VERIFIED LIST (Target vehicles):
{json.dumps(extracted_data, ensure_ascii=False)}

REFERENCE OCR TEXT (Source of truth):
<<<
{raw_ocr_text[:15000]}
>>>

STRICT FORMAT RULES:
1. "invoice_number": find the official number in OCR. If not found, use "{fallback_invoice}".

2. "vehicle_list": for each chassis_number, extract:
   a) "chassis_number": COPY EXACTLY from VERIFIED LIST (17 characters)
   b) "engine_number": COPY EXACTLY from VERIFIED LIST
   c) "vehicle_description": 
      - Find the EXACT text describing THIS vehicle in OCR
      - For Hyundai: Copy "Tên hàng hóa" field (e.g., "Xe ô tô con chở 06 người (không kể người lái), hiệu Hyundai CRETA 1.5 MPI GLS FL, mới 100%")
      - For VinFast: Copy vehicle model and specs (e.g., "Xe ô tô con 5 chỗ ngồi, hiệu Vinfast VF5 Plus")
      - DO NOT include metadata like "Mau VAQ25-01", "10206/VAQ18-01", "QCVN09:2024/BGTVT", "377.6V-61.36kWh"
      - ONLY human-readable vehicle name, seats, brand, model, condition
   d) "color": 
      - Extract ONLY color name in Vietnamese (e.g., "TRẮNG", "ĐEN", "XANH", "LIMO GREEN")
      - Must be 1-2 words maximum. If unclear, return null
   e) "number_of_seats": 
      - Extract ONLY the digit(s) representing seats
      - Valid: "5", "6", "7", "06"
      - Look for "5 chỗ ngồi", "chở 06 người", "6 seater"
      - Return ONLY number as string. If not found, return null
      - DO NOT return sentences
   f) "quantity": Always "1"

CRITICAL: number_of_seats MUST be 1-2 digits ONLY. vehicle_description MUST be main name, NOT metadata.

OUTPUT JSON ONLY:"""

        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                format='json',
                options={"temperature": 0}
            )
            
            content = response['message']['content'].strip()
            print(f"DEBUG [LLM]: Raw response length: {len(content)} chars")
            print(f"DEBUG [LLM]: Response preview: {content[:300]}...")
            
            result = json.loads(content)
            print(f"DEBUG [LLM]: Parsed JSON - invoice: {result.get('invoice_number')}, vehicles: {len(result.get('vehicle_list', []))}")
            
            if not result.get("invoice_number"):
                result["invoice_number"] = fallback_invoice
            
            validated = self.validate_and_restore(result, extracted_data)
            print(f"DEBUG [LLM]: After validation - vehicles: {len(validated.get('vehicle_list', []))}")
            return validated
            
        except Exception as e:
            print(f"ERROR [LLM]: {e}")
            import traceback
            traceback.print_exc()
            inv = fallback_invoice if fallback_invoice else invoice_no_from_ocr
            # Luôn trả format chuẩn (vehicle_description, color, seats), không trả description_hint
            vehicle_list = self._normalize_vehicle_list(extracted_data)
            return {"invoice_number": inv, "vehicle_list": vehicle_list}

    def _normalize_vehicle_list(self, verified):
        """Chuẩn hóa danh sách xe từ OCR (có description_hint) → format chuẩn (vehicle_description, color, seats)."""
        out = []
        for v in verified:
            hint = v.get("description_hint")
            desc, color, seats = _parse_description_fallback(hint)
            out.append(self._to_standard_vehicle(
                v.get("chassis_number"), v.get("engine_number"),
                desc or (hint[:300] if hint else None), color, seats
            ))
        return out

    def _to_standard_vehicle(self, chassis_number, engine_number, vehicle_description, color, number_of_seats, quantity="1"):
        """Chuẩn hóa một item xe: chỉ các trường chuẩn, không description_hint/invoice_no_from_header."""
        desc = self.apply_ocr_dictionary(vehicle_description or "")
        col = self.apply_ocr_dictionary(color) if color else None
        return {
            "chassis_number": chassis_number,
            "engine_number": engine_number,
            "vehicle_description": desc or None,
            "color": col,
            "number_of_seats": str(number_of_seats) if number_of_seats else "",
            "quantity": str(quantity),
        }

    def validate_and_restore(self, result, verified):
        if "vehicle_list" not in result or not result["vehicle_list"]:
            return {
                "invoice_number": result.get("invoice_number") if result else None,
                "vehicle_list": self._normalize_vehicle_list(verified),
            }

        final_list = []
        for i, v_orig in enumerate(verified):
            v_llm = next((x for x in result["vehicle_list"] if x.get("chassis_number") == v_orig.get("chassis_number")), None)
            if not v_llm and i < len(result["vehicle_list"]):
                v_llm = result["vehicle_list"][i]

            if v_llm:
                chassis_number = v_orig.get("chassis_number")
                engine_number = v_orig.get("engine_number")
                vehicle_description = v_llm.get("vehicle_description")
                color = v_llm.get("color")
                number_of_seats = v_llm.get("number_of_seats", "")
                quantity = str(v_llm.get("quantity", "1"))
                # VinFast: nếu LLM không trả vehicle_description thì lấy từ description_hint
                if not vehicle_description and v_orig.get("description_hint"):
                    desc, parsed_color, parsed_seats = _parse_description_fallback(v_orig["description_hint"])
                    vehicle_description = desc or vehicle_description
                    if not color:
                        color = parsed_color
                    if not number_of_seats and parsed_seats:
                        number_of_seats = parsed_seats
                final_list.append(self._to_standard_vehicle(
                    chassis_number, engine_number, vehicle_description, color, number_of_seats, quantity
                ))
            else:
                hint = v_orig.get("description_hint")
                desc, color, seats = _parse_description_fallback(hint)
                final_list.append(self._to_standard_vehicle(
                    v_orig.get("chassis_number"), v_orig.get("engine_number"),
                    desc or (hint[:300] if hint else None), color, seats
                ))

        result["vehicle_list"] = final_list
        return result
