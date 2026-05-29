import os
import sys
import subprocess
from typing import Dict, Any

def send_personal_whatsapp(phone_number: str, message: str) -> Dict[str, Any]:
    """
    Executes the WhatsApp Web automation client to send a personal message.
    Automatically handles session persistence via the Node.js helper.
    """
    script_path = "/Users/vedat/.gemini/antigravity/scratch/v_engine/telephony/whatsapp_personal.js"
    
    # Enforces standard international format for Dutch numbers
    clean_phone = phone_number.replace("+", "").replace(" ", "")
    
    try:
        # Run node subprocess to dispatch the message using existing session
        process = subprocess.run(
            ["node", script_path, "send", clean_phone, message],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if process.returncode == 0:
            return {"status": "SUCCESS", "log": process.stdout.strip()}
        else:
            return {"status": "FAILED", "error": process.stderr.strip() or process.stdout.strip()}
            
    except subprocess.TimeoutExpired:
        # If client is waiting for QR code scan, it will timeout here
        return {
            "status": "QR_CODE_REQUIRED",
            "reason": "WhatsApp Web requires QR scan. QR image has been saved to your dashboard!"
        }
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)}
