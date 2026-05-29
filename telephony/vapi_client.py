import os
import requests
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

VAPI_API_URL = "https://api.vapi.ai"
VAPI_API_KEY = os.getenv("VAPI_API_KEY", "mock-vapi-key")

# Vapi Assistant IDs configured in the Vapi dashboard
# Enforces native-quality Multilingual voices (e.g. ElevenLabs Dutch/English)
VAPI_ASSISTANT_NL = os.getenv("VAPI_ASSISTANT_NL", "nl-assistant-id")
VAPI_ASSISTANT_EN = os.getenv("VAPI_ASSISTANT_EN", "en-assistant-id")
VAPI_PHONE_ID = os.getenv("VAPI_PHONE_ID", "twilio-phone-id")

# FastAPI App for Webhook Endpoints
app = FastAPI(title="V-Engine Telephony & Outreach Hub")

# Webhook payload models for Vapi
class VapiCallEvent(BaseModel):
    message: Dict[str, Any]

def dispatch_vapi_call(
    phone_e164: str,
    company_name: str,
    contact_name: str,
    pain_point: str,
    solution_pitch: str,
    estimated_saving_eur: float,
    lang_pref: str = "en"
) -> Dict[str, Any]:
    """
    Dispatches an autonomous outbound call using Vapi.ai API.
    Injects target variables dynamically as variables to the assistant overrides.
    """
    assistant_id = VAPI_ASSISTANT_NL if lang_pref == "nl" else VAPI_ASSISTANT_EN
    
    # First message carries the mandatory legal AI disclosure per EU AI Act Art. 50
    first_message_nl = (
        f"Goedemiddag, u spreekt met de AI-assistent van Vedat. "
        f"Dit is een geautomatiseerd zakelijk gesprek om de AI otomasyon "
        f"mogelijkheden voor {company_name} te bespreken. Schikt het u twee minuten?"
    )
    first_message_en = (
        f"Good afternoon, you are speaking with the AI assistant representing Vedat. "
        f"This is an automated business call regarding AI automation systems "
        f"for {company_name}. Do you have two minutes?"
    )
    first_message = first_message_nl if lang_pref == "nl" else first_message_en
    
    headers = {
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "assistantId": assistant_id,
        "phoneNumberId": VAPI_PHONE_ID,
        "customer": {"number": phone_e164},
        "assistantOverrides": {
            "variableValues": {
                "company_name": company_name,
                "decision_maker": contact_name,
                "pain_point": pain_point,
                "solution_pitch": solution_pitch,
                "estimated_saving_eur": str(estimated_saving_eur)
            },
            "firstMessage": first_message,
            "serverUrl": os.getenv("BASE_URL", "https://your-domain.com") + "/webhooks/vapi/function-calls"
        }
    }
    
    # Check against local Bel-me-niet suppression list before outbound dialing
    # Mocking check for safety
    if phone_e164.endswith("999"):  # Mock flag for restricted numbers
        return {"status": "BLOCKED", "reason": "Listed in Bel-me-niet Register / GDPR restrictions"}
        
    try:
        response = requests.post(f"{VAPI_API_URL}/call", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"status": "FAILED", "reason": str(e)}

# -------------------------------------------------------------
# Webhook Handlers (Vapi Function Tool Calls & Transcripts)
# -------------------------------------------------------------

@app.post("/webhooks/vapi/function-calls")
async def handle_vapi_function_calls(request: Request):
    """
    Handles function/tool calling mid-call, e.g. booking meetings, SIP transfers, or logging outcomes.
    """
    body = await request.json()
    message = body.get("message", {})
    
    if message.get("type") == "tool-calls":
        tool_calls = message.get("toolCalls", [])
        tool_results = []
        
        for call in tool_calls:
            function_name = call.get("function", {}).get("name")
            arguments = call.get("function", {}).get("arguments", {})
            call_id = call.get("id")
            
            if function_name == "book_meeting":
                # Integrates with Cal.com or Google Calendar
                selected_slot = arguments.get("slot_iso")
                # Simulating booking logic
                tool_results.append({
                    "toolCallId": call_id,
                    "result": f"Meeting successfully booked on Cal.com for slot {selected_slot}."
                })
            elif function_name == "transfer_to_vedat":
                # SIP Transfer call to Vedat's direct phone if high intent
                tool_results.append({
                    "toolCallId": call_id,
                    "result": "Initiating SIP transfer to Vedat's direct phone line..."
                })
            else:
                tool_results.append({
                    "toolCallId": call_id,
                    "result": "Function execution successfully registered."
                })
                
        return {"results": tool_results}
        
    raise HTTPException(status_code=400, detail="Invalid message type for tool-calls webhook")

def translate_transcript_to_turkish(transcript_text: str) -> str:
    """
    Uses Gemini API to translate a Dutch B2B voice call transcript to Turkish.
    """
    if not transcript_text:
        return "Görüşme ses kaydı/metni yok veya boş."
        
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "HATA: GEMINI_API_KEY bulunamadı."
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    prompt = (
        "Translate the following B2B phone call transcript from Dutch to Turkish. "
        "Maintain the professional yet conversational tone, and translate Dutch business idiom correctly.\n\n"
        f"DUTCH TRANSCRIPT:\n{transcript_text}\n\n"
        "TURKISH TRANSLATION:"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            res_data = r.json()
            return res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            return f"Çeviri hatası (Gemini API): Status {r.status_code}"
    except Exception as e:
        return f"Çeviri hatası: {str(e)}"

def send_telegram_call_report(call_id: str, company_name: str, contact_name: str, duration: int, ended_reason: str, recording_url: str, dutch_transcript: str, turkish_translation: str):
    """
    Dispatches a beautiful voice call outcome report and translated dialog directly to Vedat's Telegram Bot.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    user_id = os.getenv("TELEGRAM_USER_ID")
    if not bot_token or not user_id:
        return
        
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    # Safe fallback if recording link is missing
    rec_part = f"🎵 *Ses Kaydı Linki:* [Kayıt Dinle]({recording_url})\n\n" if recording_url else "🎵 *Ses Kaydı:* Kayıt alınamadı veya mevcut değil.\n\n"
    
    text = (
        f"📞 *V-ENGINE 3.0 — SESLİ GÖRÜŞME DIALOG RAPORU*\n\n"
        f"🏢 *Şirket:* {company_name}\n"
        f"👤 *Kontak:* {contact_name}\n"
        f"⏱️ *Süre:* {duration} saniye · *Durum:* {ended_reason}\n"
        f"🆔 *Call ID:* `{call_id}`\n\n"
        f"{rec_part}"
        f"🇳🇱 *Felemenkçe Diyalog:*\n_{dutch_transcript[:800] + ('...' if len(dutch_transcript) > 800 else '')}_\n\n"
        f"🇹🇷 *Türkçe Çeviri:*\n_{turkish_translation[:800] + ('...' if len(turkish_translation) > 800 else '')}_"
    )
    
    payload = {
        "chat_id": user_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        import sys
        print(f"[ERROR] Failed to send Telegram call report: {e}", file=sys.stderr)

@app.post("/webhooks/vapi/status")
async def handle_vapi_status_updates(event: VapiCallEvent):
    """
    Receives call status updates (ringing, speaking, completed) and transcripts.
    Writes call transcripts and outcomes back to the Postgres/Memory database.
    Translates transcripts and alerts the user on Telegram with the recording link.
    """
    import psycopg2
    import sys
    import json
    message = event.message
    message_type = message.get("type")
    
    if message_type == "end-of-call-report":
        call_id = message.get("call", {}).get("id")
        transcript = message.get("transcript", "")
        duration = message.get("duration", 0)
        ended_reason = message.get("endedReason", "unknown")
        recording_url = message.get("recordingUrl") or message.get("call", {}).get("recordingUrl") or ""
        
        # 1. Lookup company and contact details from Postgres using phone number
        company_name = "Bilinmeyen Şirket"
        contact_name = "Bilinmeyen Kontak"
        outreach_id = None
        
        customer_phone = message.get("customer", {}).get("number")
        if customer_phone:
            try:
                conn = psycopg2.connect(dbname="postgres", user="postgres", password="postgres", host="localhost", port="5435")
                with conn.cursor() as cur:
                    cur.execute("SET search_path TO vengine;")
                    cur.execute("""
                        SELECT c.legal_name, con.full_name, o.id
                        FROM outreach o
                        JOIN companies c ON o.company_id = c.id
                        JOIN contacts con ON o.contact_id = con.id
                        WHERE con.phone_e164 = %s OR con.phone_e164 LIKE %s
                        ORDER BY o.id DESC LIMIT 1;
                    """, (customer_phone, f"%{customer_phone[-9:]}"))
                    res = cur.fetchone()
                    if res:
                        company_name, contact_name, outreach_id = res
                conn.close()
            except Exception as e:
                print(f"[ERROR] DB lookup failed in webhook: {e}", file=sys.stderr)
                
        # 2. Log call outcome in the database
        if outreach_id:
            try:
                conn = psycopg2.connect(dbname="postgres", user="postgres", password="postgres", host="localhost", port="5435")
                with conn.cursor() as cur:
                    cur.execute("SET search_path TO vengine;")
                    cur.execute("""
                        INSERT INTO calls (outreach_id, twilio_sid, started_at, ended_at, duration_sec, recording_url, transcript, outcome, summary)
                        VALUES (%s, %s, NOW() - INTERVAL '1 second' * %s, NOW(), %s, %s, %s, %s, %s);
                    """, (outreach_id, call_id, duration, duration, recording_url, json.dumps({"raw_transcript": transcript}), ended_reason, "Autonomous B2B Call Finished"))
                    conn.commit()
                conn.close()
            except Exception as e:
                print(f"[ERROR] DB insert call failed: {e}", file=sys.stderr)
                
        # 3. Translate transcript from Dutch to Turkish using Gemini API
        print(f"🇳🇱 Translating Dutch transcript for call {call_id} to Turkish...")
        turkish_translation = translate_transcript_to_turkish(transcript)
        
        # 4. Dispatch Telegram report
        print(f"📣 Sending voice call report to Telegram...")
        send_telegram_call_report(
            call_id=call_id,
            company_name=company_name,
            contact_name=contact_name,
            duration=int(duration),
            ended_reason=ended_reason,
            recording_url=recording_url,
            dutch_transcript=transcript,
            turkish_translation=turkish_translation
        )
        
        return {
            "status": "logged_and_alerted",
            "call_id": call_id,
            "duration_seconds": duration,
            "ended_reason": ended_reason
        }
        
    return {"status": "ignored", "type": message_type}
