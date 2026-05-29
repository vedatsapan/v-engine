import os
import sys
import json
import psycopg2
import psycopg2.extras
import requests
from dotenv import load_dotenv

# Ensure local directories are in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

env_path = os.path.join(os.path.dirname(__file__), "../.env")
load_dotenv(dotenv_path=env_path, override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def get_db_connection():
    conn = psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password="postgres",
        host="localhost",
        port="5435"
    )
    with conn.cursor() as cur:
        cur.execute("SET search_path TO vengine;")
    return conn

def _call_gemini_json(prompt: str) -> dict:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is missing from environment variables!")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        res_data = response.json()
        raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
        
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()
            
        return json.loads(raw_text)
    except Exception as e:
        print(f"[ERROR] Gemini API execution failed in incoming handler: {e}", file=sys.stderr)
        raise e

def generate_reply(sender_jid: str, incoming_message: str) -> str:
    """
    Ingests the incoming message, queries PostgreSQL to find the matching campaign,
    runs the Section 4 Classifier & Responder agents, and logs everything to database.
    """
    company_name = "Target Company"
    contact_name = "Recruitment Team"
    email_address = None
    outreach_id = None
    original_subject = "Outreach"
    original_body = ""
    
    # 1. Look up contact in PostgreSQL based on JID (phone number)
    try:
        clean_phone = sender_jid.replace("+", "").replace(" ", "").split("@")[0]
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) if hasattr(psycopg2.extras, "DictCursor") else conn.cursor()
        
        cursor.execute("""
            SELECT o.id as outreach_id, c.legal_name, con.full_name, con.email, d.subject, d.body
            FROM contacts con
            JOIN companies c ON con.company_id = c.id
            JOIN outreach o ON o.contact_id = con.id
            JOIN drafts d ON d.outreach_id = o.id
            WHERE con.phone_e164 LIKE %s AND d.version = 1
            LIMIT 1;
        """, (f"%{clean_phone}%",))
        
        row = cursor.fetchone()
        if row:
            data = dict(row) if hasattr(row, 'keys') else {
                "outreach_id": row[0], "legal_name": row[1], "full_name": row[2], "email": row[3],
                "subject": row[4], "body": row[5]
            }
            outreach_id = data["outreach_id"]
            company_name = data["legal_name"]
            contact_name = data["full_name"]
            email_address = data["email"]
            original_subject = data["subject"]
            original_body = data["body"]
            
        conn.close()
    except Exception as e:
        print(f"[ERROR] Failed to query PostgreSQL in incoming handler: {e}", file=sys.stderr)
        
    # 2. Run Section 4.2 Classifier
    classifier_prompt = f"""
==================== SYSTEM PROMPT: REPLY CLASSIFIER =======================

You classify inbound replies (Dutch or English) to Vedat Sapan's outreach.

INPUT DATA:
{
  "original_outreach": {{ "channel": "WHATSAPP", "subject": "{original_subject}", "body": "{original_body}" }},
  "reply": {{ "channel": "WHATSAPP", "from": "{contact_name}", "body_text": "{incoming_message}" }},
  "company": "{company_name}"
}

OUTPUT FORMAT (Respond STRICTLY with this JSON structure, no surrounding prose or markdown):
{{
  "classification": "INTERESTED" | "OBJECTION" | "NO_INTEREST" | "MEETING_SCHEDULED",
  "confidence": 0.0-1.0,
  "objection_type": "VISA" | "TECH" | "BUDGET" | "TIMING" | "NO_ROLE" | "OTHER" | null,
  "sentiment": -1.0 to 1.0,
  "summary_for_human": "one-sentence Dutch summary",
  "suggested_next_state": "DRAFT_RESPONSE" | "ESCALATE_HUMAN" | "AUTO_CLOSE"
}}

RULES:
- "Interesse, kunt u een tijd voorstellen?" → INTERESTED.
- "We hebben al iemand / op dit moment niet" → NO_INTEREST.
- "Hebben jullie sponsorship nodig? / Hoe zit het met visa?" → OBJECTION, objection_type=VISA. (This is the highest-value branch.)
- Calendar invite attached / Cal.com confirmation forwarded → MEETING_SCHEDULED.
- Hostile / unsubscribe language → NO_INTEREST.
============================================================================
    """
    
    try:
        class_res = _call_gemini_json(classifier_prompt)
    except Exception:
        class_res = {
            "classification": "INTERESTED",
            "confidence": 0.9,
            "objection_type": None,
            "sentiment": 0.5,
            "summary_for_human": "Kullanıcı yanıt verdi.",
            "suggested_next_state": "DRAFT_RESPONSE"
        }
        
    classification = class_res.get("classification", "INTERESTED")
    obj_type = class_res.get("objection_type")
    
    # 3. Run Section 4.3 Responder
    responder_prompt = f"""
==================== SYSTEM PROMPT: REPLY RESPONDER ========================

You draft Vedat Sapan's autonomous reply, in Dutch, formal "u" form,
matching the channel of the incoming reply (WHATSAPP). Hard limit: 45 words.

You receive the classification: {json.dumps(class_res, indent=2)}

BRANCH PLAYBOOKS:

▸ INTERESTED
  Goal: convert to a booked slot with zero friction.
  WhatsApp Reply: "Beste {contact_name}, bedankt voor uw interesse! U kunt direct een kennismaking van tien minuten inplannen via: https://cal.com/vedat-sapan. Past begin volgende week u beter?"

▸ OBJECTION → VISA
  Goal: dissolve the objection with facts, then re-offer CTA.
  WhatsApp Reply: "Beste {contact_name}, ik woon in Nederland en beschik over een geldige TWV die volledig is vrijgesteld van de arbeidsmarkttoets. Onboarding via de kennismigrantenregeling kan dus binnen enkele dagen. Laten we kort afstemmen: https://cal.com/vedat-sapan"

▸ OBJECTION → TECH
  Goal: provide one concrete, capability fact. E.g. 12+ years experience in high-scale enterprise databases and stateful agentic pipelines on LangGraph. Then re-offer CTA: https://cal.com/vedat-sapan

▸ OBJECTION → NO_ROLE
  Goal: position as latent value. E.g. "Begrijpelijk. Mocht er in de toekomst behoefte ontstaan rond data-operations of AI-orchestratie, dan bespaart een korte kennismaking nu later tijd: https://cal.com/vedat-sapan"

▸ NO_INTEREST
  Goal: gracious exit.
  WhatsApp Reply: "Bedankt voor uw bericht. Ik wens u veel succes."

▸ MEETING_SCHEDULED
  Goal: confirm.
  WhatsApp Reply: "Bedankt voor de bevestiging. Tot dan! Mocht er vooraf documentatie nuttig zijn, laat het gerust weten."

GLOBAL RULES:
- Never use the words "graag", "natuurlijk", "uiteraard" more than once.
- Always include the Cal.com link (https://cal.com/vedat-sapan) in INTERESTED and OBJECTION branches.
- Always sign "— Vedat Sapan".

OUTPUT FORMAT (Respond STRICTLY with this JSON structure, no surrounding text):
{{
  "body": "..." // plain text WhatsApp reply, max 45 words
}}
============================================================================
    """
    
    try:
        resp_res = _call_gemini_json(responder_prompt)
        reply_body = resp_res.get("body", f"Beste {contact_name}, bedankt voor uw bericht. Zullen we kort bellen via https://cal.com/vedat-sapan? — Vedat Sapan")
    except Exception:
        # High quality fallback
        if obj_type == "VISA":
            reply_body = f"Beste {contact_name}, ik woon in NL en beschik over een geldige TWV (arbeidsmarkttoetsvrij). Onboarding via de kennismigrantenregeling kan binnen enkele dagen. Laten we kort afstemmen: https://cal.com/vedat-sapan — Vedat Sapan"
        else:
            reply_body = f"Beste {contact_name}, bedankt voor uw reactie! U kunt direct bir kennismakingsgesprek plannen via: https://cal.com/vedat-sapan. Met vriendelijke groet, — Vedat Sapan"
            
    # 4. Save Inbound Reply & Autoreply inside PostgreSQL
    if outreach_id:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Save Inbound Reply
            cursor.execute("""
                INSERT INTO replies (outreach_id, channel, raw_payload, body_text, received_at, classification, sentiment, objection_type, handled)
                VALUES (%s, 'WHATSAPP', %s, %s, NOW(), %s, %s, %s, TRUE);
            """, (outreach_id, json.dumps(class_res), incoming_message, classification, class_res.get("sentiment", 0.0), obj_type))
            
            # Update outreach state
            new_status = "REPLIED"
            if classification == "MEETING_SCHEDULED":
                new_status = "MEETING_SCHEDULED"
            elif classification == "NO_INTEREST":
                new_status = "CLOSED_LOST"
                
            cursor.execute("UPDATE outreach SET status = %s, updated_at = NOW() WHERE id = %s;", (new_status, outreach_id))
            
            # Save state transition
            cursor.execute("""
                INSERT INTO state_transitions (outreach_id, from_state, to_state, actor, reason, occurred_at)
                VALUES (%s, 'SENT', %s, 'inbound_reply_agent', %s, NOW());
            """, (outreach_id, new_status, class_res.get("summary_for_human", "Auto-processed reply.")))
            
            conn.commit()
            conn.close()
            
            # Alert Vedat on Telegram bot of the new response!
            if TELEGRAM_BOT_TOKEN and TELEGRAM_USER_ID:
                text = (
                    f"📥 *[OTONOM YANIT ALINDI (V-Engine 3.0)]*\n\n"
                    f"🏢 *Şirket:* {company_name}\n"
                    f"👤 *Gönderen:* {contact_name}\n"
                    f"💬 *Mesajı:* \"_{incoming_message}_\"\n\n"
                    f"🔍 *Sınıflandırma:* `{classification}`\n"
                    f"💡 *Açıklama:* _{class_res.get('summary_for_human')}_\n\n"
                    f"🤖 *Otonom WhatsApp Yanıtımız:* \n"
                    f"\"_{reply_body}_\""
                )
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                requests.post(url, json={"chat_id": TELEGRAM_USER_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
                
        except Exception as e:
            print(f"[ERROR] Failed to save transitions/replies to PostgreSQL: {e}", file=sys.stderr)
            
    return reply_body

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python whatsapp_incoming_handler.py <sender_jid> <message_content>")
        sys.exit(1)
        
    jid = sys.argv[1]
    msg = sys.argv[2]
    
    reply = generate_reply(jid, msg)
    print(reply)
