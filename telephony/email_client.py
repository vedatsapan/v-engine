import os
import requests
from typing import Dict, Any, Optional

RESEND_API_URL = "https://api.resend.com/emails"
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "mock-resend-key")

# List of rotating verified sender domains for V-Engine
# Enforces SPF/DKIM/DMARC at DNS level
SENDER_DOMAINS = [
    "vedat@v-systems.nl",
    "vedat@vedat-engine.com",
    "vedat@kennismigrant-tech.eu"
]

def get_rotating_sender(campaign_index: int = 0) -> str:
    """
    Returns a rotating sender email to balance load and preserve domain reputation.
    """
    index = campaign_index % len(SENDER_DOMAINS)
    return SENDER_DOMAINS[index]

import re
import subprocess

def validate_email_syntax(email: str) -> bool:
    """Verifies that the email has correct standard RFC syntax."""
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))

def validate_email_mx(email: str) -> bool:
    """Uses DNS MX records lookup to verify that the target domain accepts mail."""
    if "@" not in email:
        return False
    domain = email.split("@")[1].strip()
    try:
        proc = subprocess.run(["host", "-t", "mx", domain], capture_output=True, text=True, timeout=4)
        if "mail is handled by" in proc.stdout or "MX" in proc.stdout:
            return True
        return False
    except Exception:
        return False

def send_outbound_email(
    to_email: str,
    subject: str,
    body_html: str,
    campaign_index: int = 0,
    reply_to: str = "operator@example.com"
) -> Dict[str, Any]:
    """
    Sends a hyper-personalized B2B cold email using Resend API.
    Bakes in RFC 8058 standard List-Unsubscribe headers for absolute GDPR and delivery compliance.
    """
    # 1. Syntax Validation
    if not validate_email_syntax(to_email):
        return {"status": "BLOCKED", "reason": "Syntax Error: The email address has an invalid format."}
        
    # 2. DNS MX Records Validation
    if not validate_email_mx(to_email):
        return {"status": "BLOCKED", "reason": "DNS MX Error: The domain does not have any active mail server configured."}

    # 3. Suppression check for consumer personal domains
    if to_email.endswith("@gmail.com") or to_email.endswith("@outlook.com") or to_email.endswith("@hotmail.com"):
         return {"status": "BLOCKED", "reason": "Restricted: Cold B2B outreach must target role-based corporate emails only."}

    from_email = get_rotating_sender(campaign_index)
    
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # GDPR Mandated List-Unsubscribe headers
    unsubscribe_link = f"https://vedat.ai/unsubscribe?email={to_email}"
    
    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "html": body_html,
        "reply_to": reply_to,
        "headers": {
            "List-Unsubscribe": f"<{unsubscribe_link}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            "X-Campaign-ID": f"v-engine-campaign-{campaign_index}"
        }
    }
    
    try:
        response = requests.post(RESEND_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"status": "FAILED", "reason": str(e)}
