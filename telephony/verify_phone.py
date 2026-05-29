import os
import sys
import json
import requests
from dotenv import load_dotenv

# Load env variables
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(dotenv_path=os.path.join(parent_dir, ".env"), override=True)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def lookup_twilio(phone):
    """
    Validates phone formatting and gets carrier/line type intelligence using Twilio REST API.
    """
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("[WARNING] Twilio credentials missing from .env. Skipping Twilio lookup.")
        return {"valid": True, "type": "unknown", "carrier": "unknown"}
        
    url = f"https://lookups.twilio.com/v2/PhoneNumbers/{phone}?Fields=line_type_intelligence"
    try:
        r = requests.get(url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=10)
        if r.status_code == 200:
            data = r.json()
            valid = data.get("valid", False)
            intel = data.get("line_type_intelligence") or {}
            line_type = intel.get("type", "unknown")
            carrier = intel.get("carrier_name", "unknown")
            return {"valid": valid, "type": line_type, "carrier": carrier}
        else:
            print(f"[WARNING] Twilio lookup returned status {r.status_code}: {r.text}")
            return {"valid": True, "type": "unknown", "carrier": "unknown"}
    except Exception as e:
        print(f"[WARNING] Twilio Lookup API request failed: {e}")
        return {"valid": True, "type": "unknown", "carrier": "unknown"}

def verify_google_grounding(company_name, domain, phone):
    """
    Uses Gemini 2.5 Flash Google Search Grounding to verify if a number is published on the company domain.
    """
    if not GEMINI_API_KEY:
        print("[ERROR] GEMINI_API_KEY missing from .env!")
        return {"verified": False, "official_numbers": [], "source_urls": [], "rationale": "Gemini API key missing."}
        
    prompt = (
        f"You are V-Engine 4.0 OSINT target verification agent.\n"
        f"Your task is to verify if the phone number '{phone}' belongs to the Dutch company '{company_name}' (website: {domain}).\n"
        f"Use Google Search to find the official contact phone numbers of '{company_name}' on their website or official registers (like KvK).\n"
        f"Is '{phone}' listed as an official corporate number, CTO mobile, or contact number for '{company_name}'?\n\n"
        f"Provide your response in JSON format with these exact keys:\n"
        f"- 'verified': boolean (true if confirmed to belong to the company, false otherwise)\n"
        f"- 'official_numbers': list of official corporate phone numbers you found on their website\n"
        f"- 'source_urls': list of official URLs where you found these phone numbers\n"
        f"- 'rationale': a short explanation of your findings in Turkish\n\n"
        f"Output only raw JSON, no markdown formatting (like ```json), no wrapping."
    )
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"googleSearch": {}}]
    }
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=40)
        r.raise_for_status()
        res_data = r.json()
        raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
        
        # Clean up JSON formatting wrapper
        if raw_text.startswith("```json"):
            raw_text = raw_text.replace("```json", "", 1)
        if raw_text.endswith("```"):
            raw_text = raw_text.rsplit("```", 1)[0]
        raw_text = raw_text.strip()
        
        return json.loads(raw_text)
    except Exception as e:
        print(f"[WARNING] Gemini search grounding failed: {e}")
        return {"verified": False, "official_numbers": [], "source_urls": [], "rationale": f"OSINT arama hatası: {e}"}

def verify_number(company_name, domain, phone):
    """
    Main entry point to perform complete Twilio Lookup + Google Search Grounding verification.
    """
    print(f"🚦 Starting Verification for {company_name} ({phone})...")
    
    # 1. Twilio Lookup
    twilio_res = lookup_twilio(phone)
    if not twilio_res["valid"]:
        print(f"❌ Twilio Lookup flags {phone} as INVALID!")
        return {
            "verified": False,
            "valid_format": False,
            "line_type": twilio_res["type"],
            "carrier": twilio_res["carrier"],
            "official_numbers": [],
            "source_urls": [],
            "rationale": "Numara formatı geçersiz veya Twilio tarafından aktif bir hat olarak tanınmıyor."
        }
        
    # 2. Google Search Grounding
    grounding_res = verify_google_grounding(company_name, domain, phone)
    
    # If the number is verified, or if it is our test number, we can override for testing safety
    # (So Vedat can still run test calls to his personal number if desired, but we alert him!)
    is_test_number = phone.replace("+", "").replace(" ", "") in ["31611017238", "31684418020"]
    verified = grounding_res.get("verified", False)
    
    rationale = grounding_res.get("rationale", "")
    if is_test_number:
        verified = True
        rationale += " (Geliştirici testi amacıyla şahsi numara doğrulanmış kabul edildi.)"
        
    print(f"🏁 Verification Complete! Result verified={verified}")
    
    return {
        "verified": verified,
        "valid_format": True,
        "line_type": twilio_res["type"],
        "carrier": twilio_res["carrier"],
        "official_numbers": grounding_res.get("official_numbers", []),
        "source_urls": grounding_res.get("source_urls", []),
        "rationale": rationale
    }

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 verify_phone.py <company_name> <domain> <phone_number>")
        sys.exit(1)
        
    company = sys.argv[1]
    dom = sys.argv[2]
    num = sys.argv[3]
    
    result = verify_number(company, dom, num)
    print(json.dumps(result, indent=2, ensure_ascii=False))
