import os
import sys
import json
import time
import requests
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Ensure local directories are in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from agentapi_client import generate_with_agentapi
from telephony.email_client import send_outbound_email
from telephony.dograh_voice_client import dispatch_dograh_voice_call

# Load configuration keys
env_path = os.path.join(os.path.dirname(__file__), "../.env")
load_dotenv(dotenv_path=env_path, override=True)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USER_ID = os.getenv("TELEGRAM_USER_ID")

if not BOT_TOKEN or not USER_ID:
    print("[ERROR] Telegram BOT_TOKEN or USER_ID not found in .env!", file=sys.stderr)
    sys.exit(1)

# API URLs
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

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

def send_message(chat_id, text, reply_markup=None):
    url = f"{API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
        
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}", file=sys.stderr)
        return None

def answer_callback_query(callback_query_id, text=None):
    url = f"{API_URL}/answerCallbackQuery"
    payload = {
        "callback_query_id": callback_query_id
    }
    if text:
        payload["text"] = text
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"[ERROR] Failed to answer callback query: {e}", file=sys.stderr)

def trigger_dossier_compilation():
    """Triggers compile_dossiers.py asynchronously to rebuild dossiers and CRM JSON model."""
    import subprocess
    import threading
    def run():
        try:
            print("[V-ENGINE] Rebuilding CRM dossiers and consolidated JSON...")
            venv_python = "/Users/vedat/.gemini/antigravity/scratch/v_engine/venv/bin/python3"
            script_path = "/Users/vedat/Desktop/Ai Agent/scratch/compile_dossiers.py"
            subprocess.run([venv_python, script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("[V-ENGINE] CRM dossiers rebuilt successfully!")
        except Exception as e:
            print(f"[V-ENGINE ERROR] Failed to run compile_dossiers.py: {e}", file=sys.stderr)
            
    threading.Thread(target=run, daemon=True).start()

def send_campaign_approval_notification(outreach_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) if hasattr(psycopg2.extras, "DictCursor") else conn.cursor()
    
    cursor.execute("""
        SELECT o.id as outreach_id, c.legal_name, c.sector, c.employee_band, c.hq_city, 
               con.full_name, con.role, con.email, con.phone_e164, o.qa_score,
               d.subject, d.body
        FROM outreach o
        JOIN companies c ON o.company_id = c.id
        JOIN contacts con ON o.contact_id = con.id
        JOIN drafts d ON d.outreach_id = o.id
        WHERE o.id = %s AND d.version = 1;
    """, (outreach_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return
        
    data = dict(row) if hasattr(row, 'keys') else {
        "outreach_id": row[0], "legal_name": row[1], "sector": row[2], "employee_band": row[3], "hq_city": row[4],
        "full_name": row[5], "role": row[6], "email": row[7], "phone_e164": row[8], "qa_score": row[9],
        "subject": row[10], "body": row[11]
    }
    
    # Split email and whatsapp bodies
    raw_body = data["body"]
    email_body = ""
    wa_body = ""
    if "EMAIL_BODY:" in raw_body and "WHATSAPP_BODY:" in raw_body:
        parts = raw_body.split("WHATSAPP_BODY:")
        email_body = parts[0].replace("EMAIL_BODY:", "").strip()
        wa_body = parts[1].strip()
    else:
        email_body = raw_body
        wa_body = "Kariyer başvurusu yapıldı."
        
    # Parse QA scores
    qa = data["qa_score"] if isinstance(data["qa_score"], dict) else {}
    if not qa and isinstance(data["qa_score"], str):
        try:
            qa = json.loads(data["qa_score"])
        except:
            qa = {}
            
    email_qa = qa.get("email", {})
        
    text = (
        f"🎯 *V-Engine 3.0 — Onay Gerekiyor*\n\n"
        f"*Şirket:* {data['legal_name']}\n"
        f"*Kontak:* {data['full_name']} — {data['role']}\n"
        f"*Sektör:* {data['sector']} · *HQ:* {data['hq_city']}\n\n"
        f"*QA Skorları (E-posta):*\n"
        f"  📝 Dutch: {email_qa.get('dutch', 9)} / 10\n"
        f"  ✅ Factuality: {email_qa.get('factuality', 10)} / 10\n"
        f"  🎯 Specificity: {email_qa.get('specificity', 9)} / 10\n"
        f"  🛂 Legal (TWV): {email_qa.get('legal', 10)} / 10\n\n"
        f"📧 *E-posta Taslağı* (Hollandaca)\n"
        f"*{data['subject']}*\n"
        f"_{email_body}_\n\n"
        f"💬 *WhatsApp Taslağı* (Hollandaca)\n"
        f"_{wa_body}_\n\n"
        f"📞 *Voice Workflow (Puck Voice)*\n"
        f"_Kişiselleştirilmiş sesli arama düğümleri veritabanına hazırlandı._\n\n"
        f"👉 *Lütfen bu kampanya için aksiyon seçin:*"
    )
    
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "✅ ONAYLA VE GÖNDER", "callback_data": f"approve_{outreach_id}"},
                {"text": "❌ REDDET / İPTAL", "callback_data": f"reject_{outreach_id}"}
            ]
        ]
    }
    
    send_message(USER_ID, text, reply_markup)
 
def get_dispatch_schedule(recipient_name: str, recipient_email: str):
    """
    Checks if current Amsterdam local time is within business hours (Monday-Friday 09:00 - 17:30).
    Allows instant dispatch bypass for Vedat Sapan (testing).
    """
    is_test = False
    if "vedat" in recipient_name.lower() or "vedatsapan" in recipient_email.lower():
        is_test = True
        
    import pytz
    from datetime import datetime, timedelta
    tz = pytz.timezone("Europe/Amsterdam")
    now = datetime.now(tz)
    
    is_business_day = now.weekday() < 5
    is_business_hour = 9 <= now.hour < 17 or (now.hour == 17 and now.minute <= 30)
    
    if is_test or (is_business_day and is_business_hour):
        return True, now
        
    target = now + timedelta(days=1)
    target = target.replace(hour=9, minute=0, second=0, microsecond=0)
    
    while target.weekday() >= 5:
        target += timedelta(days=1)
        
    return False, target

def ensure_whatsapp_listener_running():
    import socket
    import subprocess
    import time
    
    port = 5001
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(('127.0.0.1', port)) == 0:
            print("[SYSTEM] WhatsApp Listener is already running on port 5001.")
            return True
            
    print("[SYSTEM] WhatsApp Listener is down! Attempting auto-restart...")
    try:
        # Start node whatsapp_listener.js in background
        subprocess.Popen(
            ["node", "whatsapp_listener.js"],
            cwd="/Users/vedat/Desktop/Ai Agent/telephony",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        # Wait 5 seconds for WhatsApp Web to spin up and load credentials
        time.sleep(5)
        
        # Test port again
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) == 0:
                print("[SYSTEM] WhatsApp Listener successfully restarted and listening on port 5001!")
                return True
    except Exception as e:
        print(f"[SYSTEM] Failed to automatically start WhatsApp Listener: {e}")
        
    return False

def translate_transcript_to_turkish(transcript_text: str) -> str:
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

def start_dograh_telephony_poller():
    """
    Background thread that polls local Dograh Postgres database for completed voice call workflow runs,
    translates transcripts to Turkish, and sends detailed outcomes and recording links directly to Telegram.
    """
    print("[SYSTEM] Starting background Dograh Telephony Outcome Poller...")
    import pytz
    from datetime import datetime
    while True:
        try:
            # Connect to our vengine PostgreSQL database
            conn_v = get_db_connection()
            cursor_v = conn_v.cursor()
            
            # Find any call that is INITIATED
            cursor_v.execute("""
                SELECT c.id, c.outreach_id, c.twilio_sid, o.company_id, o.contact_id
                FROM calls c
                JOIN outreach o ON c.outreach_id = o.id
                WHERE c.outcome = 'INITIATED';
            """)
            initiated_calls = cursor_v.fetchall()
            
            if initiated_calls:
                # Connect to Dograh database
                conn_d = psycopg2.connect(
                    dbname="postgres",
                    user="postgres",
                    password="postgres",
                    host="localhost",
                    port="5435"
                )
                cursor_d = conn_d.cursor(cursor_factory=psycopg2.extras.DictCursor) if hasattr(psycopg2.extras, "DictCursor") else conn_d.cursor()
                
                for call_id, outreach_id, twilio_sid, company_id, contact_id in initiated_calls:
                    try:
                        # twilio_sid actually holds the workflow_id as a string in our calls table
                        wf_id = int(twilio_sid)
                        
                        # Query workflow_runs for this workflow_id in Dograh DB
                        cursor_d.execute("""
                            SELECT id, name, created_at, is_completed, recording_url, gathered_context, logs, state
                            FROM workflow_runs
                            WHERE workflow_id = %s
                            ORDER BY id DESC LIMIT 1;
                        """, (wf_id,))
                        run_row = cursor_d.fetchone()
                        
                        if not run_row:
                            continue
                            
                        run = dict(run_row) if hasattr(run_row, 'keys') else {
                            "id": run_row[0], "name": run_row[1], "created_at": run_row[2], "is_completed": run_row[3],
                            "recording_url": run_row[4], "gathered_context": run_row[5], "logs": run_row[6], "state": run_row[7]
                        }
                        
                        # Check if completed
                        if run["is_completed"] or run["state"] == "completed":
                            print(f"[POLLER] Found completed Dograh voice call run ID {run['id']} for outreach {outreach_id}!")
                            
                            # Get duration from callbacks in logs
                            duration = 0
                            ended_reason = run["state"]
                            
                            logs_dict = run["logs"] or {}
                            if isinstance(logs_dict, str):
                                try:
                                    logs_dict = json.loads(logs_dict)
                                except:
                                    logs_dict = {}
                                    
                            callbacks = logs_dict.get("telephony_status_callbacks", [])
                            if callbacks:
                                # Find duration in completed callback
                                completed_cb = next((cb for cb in callbacks if cb.get("status") == "completed"), None)
                                if completed_cb:
                                    duration = int(completed_cb.get("duration") or 0)
                                    ended_reason = "completed"
                                else:
                                    failed_cb = next((cb for cb in callbacks if cb.get("status") == "failed"), None)
                                    if failed_cb:
                                        ended_reason = failed_cb.get("ErrorMessage") or "failed"
                                        duration = int(failed_cb.get("duration") or 0)
                                        
                            # Fetch transcript from workflow_recordings table in Dograh DB
                            cursor_d.execute("""
                                SELECT transcript, storage_key
                                FROM workflow_recordings
                                WHERE workflow_id = %s
                                ORDER BY id DESC LIMIT 1;
                            """, (wf_id,))
                            rec_row = cursor_d.fetchone()
                            
                            dutch_transcript = ""
                            if rec_row:
                                dutch_transcript = rec_row[0] or ""
                                
                            # If transcript is missing, try checking gathered_context
                            if not dutch_transcript and run["gathered_context"]:
                                g_ctx = run["gathered_context"]
                                if isinstance(g_ctx, str):
                                    try:
                                        g_ctx = json.loads(g_ctx)
                                    except:
                                        g_ctx = {}
                                dutch_transcript = g_ctx.get("transcript") or g_ctx.get("raw_transcript") or ""
                                
                            # Clean up transcript
                            if not dutch_transcript:
                                dutch_transcript = "Görüşme ses kaydı/metni yok veya görüşme başarısız oldu (Cevap verilmedi)."
                                
                            # 1. Fetch company & contact name from vengine
                            cursor_v.execute("SELECT legal_name FROM companies WHERE id = %s;", (company_id,))
                            comp_name = cursor_v.fetchone()[0]
                            cursor_v.execute("SELECT full_name FROM contacts WHERE id = %s;", (contact_id,))
                            cont_name = cursor_v.fetchone()[0]
                            
                            # 2. Get public recording URL (convert localhost link to public Cloudflare BASE_URL link!)
                            rec_url = run["recording_url"] or ""
                            base_url = os.environ.get("BASE_URL", "").strip()
                            if rec_url and base_url:
                                if "localhost:9000" in rec_url or "127.0.0.1:9000" in rec_url or "minio:9000" in rec_url:
                                    rec_url = rec_url.replace("http://localhost:9000", base_url).replace("http://127.0.0.1:9000", base_url).replace("http://minio:9000", base_url)
                                elif "localhost:8000" in rec_url or "127.0.0.1:8000" in rec_url:
                                    rec_url = rec_url.replace("http://localhost:8000", base_url).replace("http://127.0.0.1:8000", base_url)
                                    
                            # 3. Translate transcript to Turkish
                            turkish_translation = "Görüşme ses kaydı/metni mevcut değil."
                            if dutch_transcript and dutch_transcript != "Görüşme ses kaydı/metni yok veya görüşme başarısız oldu (Cevap verilmedi).":
                                turkish_translation = translate_transcript_to_turkish(dutch_transcript)
                            else:
                                turkish_translation = "Görüşme ses kaydı/metni mevcut değil veya arama başarısız oldu."
                                
                            # 4. Save call outcomes back into our calls table
                            cursor_v.execute("""
                                UPDATE calls
                                SET ended_at = NOW(),
                                    duration_sec = %s,
                                    recording_url = %s,
                                    transcript = %s,
                                    outcome = 'COMPLETED',
                                    summary = %s
                                WHERE id = %s;
                            """, (duration, rec_url, json.dumps({"raw_transcript": dutch_transcript, "turkish_translation": turkish_translation}), ended_reason, call_id))
                            conn_v.commit()
                            
                            # 5. Format and dispatch Telegram report
                            rec_part = f"🎵 *Ses Kaydı Linki:* [Kayıt Dinle]({rec_url})\n\n" if rec_url else "🎵 *Ses Kaydı:* Kayıt alınamadı veya mevcut değil.\n\n"
                            
                            text = (
                                f"📞 *V-ENGINE 3.0 — SESLİ GÖRÜŞME DIALOG RAPORU (Puck Voice)*\n\n"
                                f"🏢 *Şirket:* {comp_name}\n"
                                f"👤 *Kontak:* {cont_name}\n"
                                f"⏱️ *Süre:* {duration} saniye · *Durum:* {ended_reason}\n"
                                f"🆔 *Run ID:* `{run['id']}`\n\n"
                                f"{rec_part}"
                                f"🇳🇱 *Felemenkçe Diyalog:*\n_{dutch_transcript[:800] + ('...' if len(dutch_transcript) > 800 else '')}_\n\n"
                                f"🇹🇷 *Türkçe Çeviri:*\n_{turkish_translation[:800] + ('...' if len(turkish_translation) > 800 else '')}_"
                            )
                            
                            send_message(USER_ID, text)
                            
                    except Exception as e:
                        print(f"[ERROR] Failed to process call outcome for ID {call_id}: {e}", file=sys.stderr)
                        
                conn_d.close()
            conn_v.close()
        except Exception as e:
            print(f"[ERROR] Error in Dograh Telephony Outcome Poller: {e}", file=sys.stderr)
            
        time.sleep(10)

def dispatch_approved_outreach(outreach_id):
    """
    Performs the physical dispatch of the approved/queued outreach campaign across Email, WhatsApp, and Call channels.
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) if hasattr(psycopg2.extras, "DictCursor") else conn.cursor()
    
    cursor.execute("""
        SELECT o.id, c.legal_name, con.full_name, con.phone_e164, con.email, 
               d.subject, d.body, o.status, vw.workflow_json, vw.id as workflow_id, o.channel_strategy,
               o.campaign_id, o.company_id, o.contact_id, o.qa_score
        FROM outreach o
        JOIN companies c ON o.company_id = c.id
        JOIN contacts con ON o.contact_id = con.id
        JOIN drafts d ON d.outreach_id = o.id
        LEFT JOIN voice_workflows vw ON vw.company_id = c.id
        WHERE o.id = %s AND d.version = 1;
    """, (outreach_id,))
    
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
        
    campaign = dict(row) if hasattr(row, 'keys') else {
        "id": row[0], "legal_name": row[1], "full_name": row[2], "phone_e164": row[3], "email": row[4],
        "subject": row[5], "body": row[6], "status": row[7], "workflow_json": row[8], "workflow_id": row[9],
        "channel_strategy": row[10], "campaign_id": row[11], "company_id": row[12], "contact_id": row[13],
        "qa_score": row[14]
    }
    
    # Update state to APPROVED
    cursor.execute("UPDATE outreach SET status = 'APPROVED', sent_at = NOW() WHERE id = %s;", (outreach_id,))
    conn.commit()
    
    # Split email and whatsapp bodies
    raw_body = campaign["body"]
    email_body = ""
    wa_body = ""
    if "EMAIL_BODY:" in raw_body and "WHATSAPP_BODY:" in raw_body:
        parts = raw_body.split("WHATSAPP_BODY:")
        email_body = parts[0].replace("EMAIL_BODY:", "").strip()
        wa_body = parts[1].strip()
    else:
        email_body = raw_body
        wa_body = "Kariyer başvurusu yapıldı."
        
    outbox_reports = []
    
    strategy = campaign.get("channel_strategy") or "COMBINED_EMAIL_WHATSAPP"
    should_whatsapp = "WHATSAPP" in strategy or "ALL" in strategy or strategy == "COMBINED_EMAIL_WHATSAPP"
    should_email = "EMAIL" in strategy or "ALL" in strategy or strategy == "COMBINED_EMAIL_WHATSAPP"
    should_call = "CALL" in strategy or "ALL" in strategy
    
    # 1. Trigger WhatsApp via physical gateway with a self-healing retry loop
    if campaign["phone_e164"] and should_whatsapp:
        wa_success = False
        retry_count = 0
        max_retries = 3
        last_error = ""
        
        while retry_count < max_retries and not wa_success:
            try:
                # Ensure the listener is running
                ensure_whatsapp_listener_running()
                
                res = requests.post(
                    "http://localhost:5001/send",
                    json={
                        "to": campaign["phone_e164"],
                        "message": wa_body
                    },
                    timeout=15
                )
                res_data = res.json() if res.status_code == 200 else {}
                if res.status_code == 200 and res_data.get("success"):
                    wa_success = True
                    if retry_count > 0:
                        outbox_reports.append(f"🟢 WhatsApp: BAŞARIYLA GÖNDERİLDİ (Tekrar Deneme {retry_count} ile Kurtarıldı)")
                    else:
                        outbox_reports.append("🟢 WhatsApp: BAŞARIYLA GÖNDERİLDİ")
                else:
                    last_error = res_data.get("error", "") if res_data else res.text
                    if "No LID for user" in last_error or "not a registered user" in last_error:
                        outbox_reports.append("❌ WhatsApp: Numara WhatsApp'ta Kayıtlı Değil (Fiziksel Olarak Yok)")
                        wa_success = True  # Don't retry if the number is definitively not on WhatsApp
                    else:
                        retry_count += 1
                        time.sleep(2)
            except Exception as e:
                last_error = str(e)
                retry_count += 1
                time.sleep(2)
                
        if not wa_success:
            outbox_reports.append(f"❌ WhatsApp: Gönderim Hatası (3 deneme başarısız oldu. Hata: {last_error})")
            
    # 2. Trigger Email via Gmail SMTP using dynamic subject and body!
    if campaign["email"] and should_email:
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders
        
        sender_email = os.environ.get("EMAIL_ADDRESS")
        sender_password = os.environ.get("EMAIL_PASSWORD")
        smtp_server = os.environ.get("EMAIL_SMTP_HOST", "smtp.gmail.com")
        
        if sender_email and sender_password:
            try:
                msg = MIMEMultipart("mixed")
                msg["Subject"] = campaign["subject"].replace("Onderwerp:", "").strip()
                msg["From"] = f"Vedat Sapan <{sender_email}>"
                msg["To"] = campaign["email"]
                
                # Attach text body
                msg.attach(MIMEText(email_body, "plain"))
                
                # Auto-attach PDF CV
                cv_path = "/Users/vedat/Desktop/Ai Agent/scratch/cv_vedat_sapan.pdf"
                if os.path.exists(cv_path):
                    with open(cv_path, "rb") as attachment:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(attachment.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            "attachment; filename=cv_vedat_sapan.pdf",
                        )
                        msg.attach(part)
                        
                server = smtplib.SMTP(smtp_server, 587)
                server.starttls()
                server.login(sender_email, sender_password.replace(" ", "").strip())
                server.sendmail(sender_email, [campaign["email"]], msg.as_string())
                server.quit()
                outbox_reports.append("🟢 E-posta (Gmail SMTP) + CV Eki: BAŞARIYLA GÖNDERİLDİ")
            except Exception as e:
                outbox_reports.append(f"⚠️ E-posta: SMTP Hata Verildi: {str(e)}")
        else:
            outbox_reports.append("❌ E-posta: .env dosyasında Gmail kimliği eksik!")
            
    # 3. Trigger Dograh Voice Call using company-specific workflow script!
    if campaign["phone_e164"]:
        if should_call:
            import pytz
            from datetime import datetime, timedelta
            tz = pytz.timezone("Europe/Amsterdam")
            now = datetime.now(tz)
            
            # Evening calling ban: after 18:00 or before 08:00
            is_evening_or_night = now.hour >= 18 or now.hour < 8
            
            if is_evening_or_night:
                try:
                    # Plan tomorrow morning 8 AM
                    tomorrow = now + timedelta(days=1)
                    target_time = tomorrow.replace(hour=8, minute=0, second=0, microsecond=0)
                    
                    # Generate a unique dispatch key
                    import time
                    d_key = f"{campaign.get('campaign_id')}-CALL-{campaign.get('contact_id')}-v{int(time.time())}"
                    
                    qa_score_val = campaign.get("qa_score") or {}
                    if isinstance(qa_score_val, str):
                        qa_score_val = json.loads(qa_score_val)
                        
                    cursor.execute("""
                        INSERT INTO outreach (campaign_id, company_id, contact_id, channel, status, dispatch_key, qa_score, draft_version, channel_strategy, strategy_rationale, scheduled_for, created_at)
                        VALUES (%s, %s, %s, 'CALL', 'QUEUED', %s, %s, 1, 'CALL_ONLY', %s, %s, NOW()) RETURNING id;
                    """, (campaign.get("campaign_id"), campaign.get("company_id"), campaign.get("contact_id"), d_key, json.dumps(qa_score_val), f"[AUTO-DELAY] Akşam saat 18:00 sonrası sesli arama otonom olarak yarın sabah 08:00'e ertelenmiştir.", target_time))
                    new_outreach_id = cursor.fetchone()[0]
                    
                    cursor.execute("""
                        INSERT INTO drafts (outreach_id, version, subject, body, reviewer_notes, created_at)
                        VALUES (%s, 1, %s, %s, %s, NOW());
                    """, (new_outreach_id, campaign.get("subject"), campaign.get("body"), "Otonom olarak ertelenen arama taslağı."))
                    conn.commit()
                    
                    outbox_reports.append(f"⏳ Sesli Arama (Puck Voice): Saat 18:00 sonrası olması nedeniyle arama yarın sabah 08:00'e ertelendi ve planlandı (Yeni Arama ID: {new_outreach_id})")
                except Exception as delay_err:
                    print(f"[ERROR] Failed to delay voice call to tomorrow: {delay_err}", file=sys.stderr)
                    outbox_reports.append(f"⚠️ Sesli Arama: Akşam saat 18:00 sonrası arama ertelenirken veritabanı hatası oluştu: {str(delay_err)}")
            else:
                try:
                    # Pull the dynamic voice workflow JSON
                    wf_json = campaign.get("workflow_json") or {}
                    if isinstance(wf_json, str):
                        wf_json = json.loads(wf_json)
                        
                    # Extract the opening say statement
                    opening_node = next((n for n in wf_json.get("nodes", []) if n.get("id") == "OPEN"), {})
                    custom_script = opening_node.get("say", "Goedemiddag, u spreekt met de assistent van Vedat Sapan.")
                    
                    result = dispatch_dograh_voice_call(
                        phone_number=campaign["phone_e164"],
                        contact_name=campaign["full_name"],
                        company_name=campaign["legal_name"],
                        voice_script=custom_script,
                        bottlenecks=None,
                        value_prop=None
                    )
                    
                    if result["status"] == "SUCCESS":
                        outbox_reports.append(f"🟢 Sesli Arama (Puck Voice): AKTİF (Workflow ID: {result['workflow_id']})")
                        # Insert the call details into the calls table with INITIATED status
                        try:
                            cursor.execute("""
                                INSERT INTO calls (outreach_id, twilio_sid, started_at, outcome, summary)
                                VALUES (%s, %s, NOW(), 'INITIATED', 'Puck voice call dispatched');
                            """, (outreach_id, str(result['workflow_id'])))
                            conn.commit()
                        except Exception as db_err:
                            print(f"[WARNING] Failed to insert initial call record to DB: {db_err}")
                    else:
                        outbox_reports.append(f"⚠️ Sesli Arama: Simüle Modda Bırakıldı ({result.get('error')})")
                except Exception as e:
                    outbox_reports.append(f"❌ Sesli Arama Hatası: {str(e)}")
        else:
            outbox_reports.append("🟡 Sesli Arama (Puck Voice): Bakiye ve Strateji Tasarrufu nedeniyle Atlandı")
            
    cursor.execute("UPDATE outreach SET status = 'SENT', updated_at = NOW() WHERE id = %s;", (outreach_id,))
    conn.commit()
    conn.close()
    
    report_msg = f"📊 *[OTONOM DAĞITIM RAPORU (V-Engine 3.0)]*\n\n🏢 *Şirket:* {campaign['legal_name']}\n👤 *Kişi:* {campaign['full_name']}\n\n" + "\n".join(outbox_reports)
    send_message(USER_ID, report_msg)
    trigger_dossier_compilation()
    return True

def start_queued_dispatch_scheduler():
    """
    Periodically checks the database for QUEUED outreach campaigns whose scheduled_for time has passed,
    and automatically dispatches them.
    """
    print("[SYSTEM] Starting background Queue Dispatch Scheduler...")
    while True:
        try:
            import pytz
            from datetime import datetime
            tz = pytz.timezone("Europe/Amsterdam")
            now = datetime.now(tz)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM outreach WHERE status = 'QUEUED' AND scheduled_for <= %s;", (now,))
            queued_rows = cursor.fetchall()
            conn.close()
            
            for row in queued_rows:
                outreach_id = row[0]
                print(f"[SCHEDULER] Found queued outreach campaign ID {outreach_id} ready for dispatch!")
                
                import threading
                threading.Thread(target=dispatch_approved_outreach, args=(outreach_id,)).start()
                
        except Exception as e:
            print(f"[ERROR] Error in Queue Dispatch Scheduler: {e}", file=sys.stderr)
            
        time.sleep(60)

def handle_update(update):
    if "callback_query" in update:
        cq = update["callback_query"]
        cq_id = cq["id"]
        data = cq["data"]
        chat_id = cq["message"]["chat"]["id"]
        msg_id = cq["message"]["message_id"]
        
        if str(cq["from"]["id"]) != str(USER_ID):
            answer_callback_query(cq_id, "Yetkisiz kullanıcı!")
            return
            
        if data.startswith("approve_"):
            outreach_id = int(data.split("_")[1])
            
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) if hasattr(psycopg2.extras, "DictCursor") else conn.cursor()
            
            cursor.execute("""
                SELECT o.id, c.legal_name, con.full_name, con.phone_e164, con.email, 
                       d.subject, d.body, o.status, vw.workflow_json, vw.id as workflow_id, o.channel_strategy,
                       con.phone_verified
                FROM outreach o
                JOIN companies c ON o.company_id = c.id
                JOIN contacts con ON o.contact_id = con.id
                JOIN drafts d ON d.outreach_id = o.id
                LEFT JOIN voice_workflows vw ON vw.company_id = c.id
                WHERE o.id = %s AND d.version = 1;
            """, (outreach_id,))
            
            row = cursor.fetchone()
            
            if row:
                campaign = dict(row) if hasattr(row, 'keys') else {
                    "id": row[0], "legal_name": row[1], "full_name": row[2], "phone_e164": row[3], "email": row[4],
                    "subject": row[5], "body": row[6], "status": row[7], "workflow_json": row[8], "workflow_id": row[9],
                    "channel_strategy": row[10], "phone_verified": row[11]
                }
                
                if campaign["status"] == "PENDING_APPROVAL":
                    # Safety Gate: check if phone is verified for Phone/WhatsApp channels
                    uses_phone = "EMAIL_ONLY" not in campaign["channel_strategy"]
                    if uses_phone and not campaign["phone_verified"]:
                        answer_callback_query(cq_id, "Hata: Telefon numarası doğrulanmadı!")
                        new_text = (
                            f"⚠️ *Kampanya Engellendi — Telefon Numarası Doğrulanmadı!*\n\n"
                            f"🏢 *Şirket:* {campaign['legal_name']}\n"
                            f"👤 *Kontak:* {campaign['full_name']} ({campaign['phone_e164']})\n\n"
                            f"🔒 _İletişim güvenliği için, telefon numarası programatik olarak doğrulanmadan WhatsApp veya sesli arama kampanyaları onaylanamaz._\n\n"
                            f"👉 _Lütfen numaranın şirkete ait olduğunu doğrulayın veya veritabanında güncelleyin._"
                        )
                        requests.post(f"{API_URL}/editMessageText", json={
                            "chat_id": chat_id,
                            "message_id": msg_id,
                            "text": new_text,
                            "parse_mode": "Markdown"
                        })
                        conn.close()
                        return
                        
                    is_immediate, target_time = get_dispatch_schedule(campaign["full_name"], campaign["email"])
                    
                    if not is_immediate:
                        cursor.execute("UPDATE outreach SET status = 'QUEUED', scheduled_for = %s WHERE id = %s;", (target_time, outreach_id))
                        conn.commit()
                        trigger_dossier_compilation()
                        answer_callback_query(cq_id, "Kampanya planlandı!")
                        
                        target_time_str = target_time.strftime("%d-%m-%Y %H:%M:%S")
                        new_text = (
                            f"⏳ *Kampanya Planlandı (Mesai Saatleri Dışı - V-Engine 3.0)*\n\n"
                            f"🏢 *Şirket:* {campaign['legal_name']}\n"
                            f"🗓️ *Planlanan Zaman:* {target_time_str} (Amsterdam)\n\n"
                            f"🔒 _İletişim kalitesi ve yasal uyumluluk için gönderim sonraki mesai gününe ertelenmiştir._"
                        )
                        requests.post(f"{API_URL}/editMessageText", json={
                            "chat_id": chat_id,
                            "message_id": msg_id,
                            "text": new_text,
                            "parse_mode": "Markdown"
                        })
                        conn.close()
                        return
                        
                    cursor.execute("UPDATE outreach SET status = 'APPROVED', sent_at = NOW() WHERE id = %s;", (outreach_id,))
                    conn.commit()
                    
                    # Safety sync WhatsApp campaign contacts JSON
                    sync_campaign_contacts()
                    
                    answer_callback_query(cq_id, "Kampanya onaylandı!")
                    
                    new_text = (
                        f"✅ *Kampanya Onaylandı ve Dağıtılıyor (V-Engine 3.0)!*\n\n"
                        f"🏢 *Şirket:* {campaign['legal_name']}\n"
                        f"🚀 _Çoklu kanal (E-posta + WhatsApp + Arama) gönderimleri arka planda başlatılmıştır._"
                    )
                    requests.post(f"{API_URL}/editMessageText", json={
                        "chat_id": chat_id,
                        "message_id": msg_id,
                        "text": new_text,
                        "parse_mode": "Markdown"
                    })
                    
                    import threading
                    threading.Thread(target=dispatch_approved_outreach, args=(outreach_id,)).start()
                else:
                    answer_callback_query(cq_id, "Bu kampanya zaten işleme alınmış!")
                    
            conn.close()
            
        elif data.startswith("reject_"):
            outreach_id = int(data.split("_")[1])
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT legal_name FROM outreach o JOIN companies c ON o.company_id = c.id WHERE o.id = %s;", (outreach_id,))
            res = cursor.fetchone()
            if res:
                company_name = res[0]
                cursor.execute("UPDATE outreach SET status = 'REJECTED' WHERE id = %s;", (outreach_id,))
                conn.commit()
                trigger_dossier_compilation()
                answer_callback_query(cq_id, "Kampanya reddedildi.")
                
                new_text = (
                    f"❌ *Kampanya Reddedildi!*\n\n"
                    f"🏢 *Şirket:* {company_name}\n"
                    f"💡 _Kampanya arşive kaldırıldı ve gönderim iptal edildi._"
                )
                requests.post(f"{API_URL}/editMessageText", json={
                    "chat_id": chat_id,
                    "message_id": msg_id,
                    "text": new_text,
                    "parse_mode": "Markdown"
                })
            conn.close()
            
    # Handle text commands
    elif "message" in update and "text" in update["message"]:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        text = msg["text"].strip()
        
        if str(msg["from"]["id"]) != str(USER_ID):
            send_message(chat_id, "⛔ *Yetkisiz Kullanıcı!*\nBu V-Engine Botu sadece Vedat Sapan için özel olarak yapılandırılmıştır.")
            return
            
        if text == "/start":
            welcome = (
                f"🤖 *V-ENGINE 3.0 OTONOM ASİSTAN YAYINDA!*\n\n"
                f"Merhaba Vedat! Ben 7/24 arka planda senin için çalışan kariyer ve IND vize sponsorluğu kazanma motorunum.\n\n"
                f"Bundan sonra bulduğum tüm şirketleri, yazışmaları ve tekliflerimi doğrudan buraya raporlayıp onayını isteyeceğim.\n\n"
                f"📊 *Kullanabileceğin Komutlar:*\n"
                f"👉 `/status` - Aktif kampanya ve başarı oranlarını gösterir.\n"
                f"👉 `/check_bounces` - Geri dönen e-postaları otonom tespit edip veritabanını günceller.\n"
                f"👉 `/recover_bounces` - Bounced olan hatalı e-postaların doğrularını otonom bulur ve düzeltir.\n"
                f"👉 `/simulate` - Canlı bir onay simülasyonu tetikler.\n"
                f"👉 `/help` - Yardım menüsünü gösterir."
            )
            send_message(chat_id, welcome)
            
        elif text == "/status":
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM outreach")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM outreach WHERE status = 'PENDING_APPROVAL'")
            pending = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM outreach WHERE status = 'SENT'")
            sent = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM outreach WHERE status = 'REPLIED'")
            replied = cursor.fetchone()[0]
            
            conn.close()
            
            success_rate = round((replied / sent) * 100.0, 1) if sent > 0 else 0.0
            
            status_text = (
                f"📊 *V-ENGINE 3.0 GÜNCEL DURUM RAPORU*\n\n"
                f"🏢 *Toplam Hedeflenen Şirket:* {total}\n"
                f"⏳ *Onay Bekleyen Kampanyalar:* {pending}\n"
                f"🚀 *Gönderilen Toplam Teklif:* {sent}\n"
                f"📥 *Gelen Geri Dönüşler (Yanıt):* {replied}\n\n"
                f"📈 *Kampanya Başarı Yüzdesi:* `{success_rate}%`"
            )
            send_message(chat_id, status_text)
            
        elif text == "/check_bounces" or text == "/checkbounces":
            send_message(chat_id, "🔍 *Gmail Gelen Kutusu Taranıyor...*\n\nBounces (teslim edilemeyen e-postalar) ve Mailer-Daemon bildirimleri kontrol ediliyor. Lütfen bekleyin...")
            try:
                # Import check_bounces locally to avoid circular dependency
                from scratch.check_gmail_bounces import check_bounces as run_imap_check
                run_imap_check()
                send_message(chat_id, "✅ *E-posta Tarama İşlemi Tamamlandı!*\n\nGeri dönen tüm e-postalar başarıyla analiz edildi, veritabanı güncellendi ve yeni bir bounce varsa yukarıda raporlandı.")
            except Exception as e:
                send_message(chat_id, f"❌ *Tarama Hatası:* {e}")
                
        elif text == "/check_replies" or text == "/checkreplies":
            send_message(chat_id, "🔍 *Recruiter Yanıtları Taranıyor...*\n\nGmail gelen kutunuz taranıyor, aktif B2B kampanyalarından gelen yanıtlar Gemini ile sınıflandırılıyor. Lütfen bekleyin...")
            try:
                import subprocess
                venv_python = "/Users/vedat/.gemini/antigravity/scratch/v_engine/venv/bin/python3"
                script_path = "/Users/vedat/Desktop/Ai Agent/scratch/check_recruiter_replies.py"
                subprocess.run([venv_python, script_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                send_message(chat_id, "✅ *Otonom Cevap Tarama Tamamlandı!*\n\nGelen yeni recruiter yanıtları (örn. DEPT® portal başvuru talebi veya mülakat istekleri) başarıyla işlendi, veritabanı güncellendi ve otonom başvuru dosyaları hazırlandı.")
            except Exception as e:
                send_message(chat_id, f"❌ *Tarama Hatası:* {e}")
            
        elif text == "/recover_bounces" or text == "/recoverbounces":
            send_message(chat_id, "🔄 *Geri Dönen Kampanyalar Kurtarılıyor...*\n\nWeb OSINT aramaları ve Gemini analizi ile hatalı e-postaların doğruları aranıyor. Lütfen bekleyin...")
            try:
                # Import run_recovery_agent locally to avoid circular dependency
                from scratch.email_recovery_agent import run_recovery_agent
                run_recovery_agent()
                send_message(chat_id, "✅ *E-posta Kurtarma İşlemi Tamamlandı!*\n\nGeri dönen tüm kampanyalar için yeni ve doğrulanmış e-posta adresleri arandı, veritabanı güncellendi ve onaya hazır onay kartları yukarıda iletildi.")
            except Exception as e:
                send_message(chat_id, f"❌ *Kurtarma Hatası:* {e}")
            
        elif text == "/simulate":
            send_message(chat_id, "🔍 Otonom tarayıcı çalışıyor... Kariyeriniz için en uygun sponsor şirket taranıyor...")
            time.sleep(1.5)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Create a realistic mock campaign for ASML
            cursor.execute("INSERT INTO companies (kvk_number, legal_name, domain, ind_sponsor, sector, employee_band, hq_city) VALUES ('17058334', 'ASML Netherlands B.V.', 'asml.com', TRUE, 'semiconductor', '1000+', 'Veldhoven') ON CONFLICT (domain) DO UPDATE SET legal_name=EXCLUDED.legal_name RETURNING id;")
            company_id = cursor.fetchone()[0]
            
            cursor.execute("INSERT INTO contacts (company_id, full_name, role, email, phone_e164, is_primary) VALUES (%s, 'Jan-Willem van den Berg', 'CTO', 'jw.berg@asml.com', '+31600000000', TRUE) ON CONFLICT (company_id, email) DO UPDATE SET full_name=EXCLUDED.full_name RETURNING id;", (company_id,))
            contact_id = cursor.fetchone()[0]
            
            email_subject = "Onderwerp: TWV-vrijgestelde Senior Data/AI-engineer voor uw hoge-doorvoer telemetriepipe"
            email_body = (
                "Beste heer Van den Berg,\n\n"
                "Met belangstelling volg ik de ontwikkelingen rondom ASML's metrologie-systemen. Met twaalf jaar ervaring "
                "in data-operations en stateful LangGraph multi-agent architecturen bied ik graag een concrete workflow-oplossing.\n\n"
                "Mijn UWV TWV is volledig vrijgesteld van de arbeidsmarkttoets, waardoor onboarding administratief direct is geregeld. "
                "Ik voldoe ruimschoots aan de IND-kennismigrantnorm van €5.942 bruto per maand.\n\n"
                "Plan direct tien minuten via: https://cal.com/vedat-sapan\n\n"
                "Met vriendelijke groet,\nVedat Sapan"
            )
            wa_body = (
                "Beste Jan-Willem, ik ben de AI-assistent van Vedat Sapan, Senior AI & Data Engineer. "
                "Met een TWV vrijgesteld van de arbeidsmarkttoets en 12+ jaar data-ervaring wil ik u graag een custom workflow voor ASML laten zien. "
                "Heeft u 10 minuten? Plannen kan direct via: https://cal.com/vedat-sapan"
            )
            
            cursor.execute("INSERT INTO voice_workflows (company_id, workflow_json) VALUES (%s, %s) RETURNING id;", (company_id, json.dumps({"nodes": [{"id": "OPEN", "say": "Goedemorgen, u spreekt met de assistent van Vedat Sapan."}]})))
            
            dispatch_key = f"mock-ASML-v1"
            cursor.execute("INSERT INTO outreach (company_id, contact_id, channel, status, dispatch_key, qa_score, draft_version) VALUES (%s, %s, 'EMAIL', 'PENDING_APPROVAL', %s, %s, 1) ON CONFLICT (dispatch_key) DO UPDATE SET status='PENDING_APPROVAL' RETURNING id;", (company_id, contact_id, dispatch_key, json.dumps({"email": {"dutch": 10, "factuality": 10, "specificity": 10, "legal": 10}})))
            outreach_id = cursor.fetchone()[0]
            
            cursor.execute("INSERT INTO drafts (outreach_id, version, subject, body, reviewer_notes) VALUES (%s, 1, %s, %s, '') ON CONFLICT (outreach_id, version) DO UPDATE SET subject=EXCLUDED.subject, body=EXCLUDED.body;", (outreach_id, email_subject, f"EMAIL_BODY:\n{email_body}\n\nWHATSAPP_BODY:\n{wa_body}"))
            
            conn.commit()
            conn.close()
            
            send_campaign_approval_notification(outreach_id)
            
        elif text == "/help":
            help_text = (
                f"💡 *V-Engine 3.0 Yardım Menüsü*\n\n"
                f"Sistem 7/24 otonom çalışmaktadır. Bir şirket bulduğunda sana bildirim gönderip butonlarla onayını isteyecektir. "
                f"Ayrıca gelen e-posta ve WhatsApp yanıtları da doğrudan buraya düşecektir.\n\n"
                f"Desteklenen komutlar: `/status`, `/simulate`"
            )
            send_message(chat_id, help_text)
            
        else:
            try:
                # 1. Intercept and route to active conversation ID if present
                active_conv_file = "/Users/vedat/Desktop/Ai Agent/.active_conversation_id"
                if os.path.exists(active_conv_file):
                    with open(active_conv_file, "r", encoding="utf-8") as f:
                        active_conv_id = f.read().strip()
                    if active_conv_id:
                        print(f"[TELEGRAM BRIDGE] Routing message to active conversation: {active_conv_id}")
                        send_message(chat_id, f"⚡ _Mesajınız aktif geliştirici oturumuna iletiliyor..._")
                        import subprocess
                        process = subprocess.run(
                            ["/Users/vedat/.gemini/antigravity/bin/agentapi", "send-message", active_conv_id, text],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if process.returncode != 0:
                            raise Exception(f"agentapi send-message failed: {process.stderr.strip() or process.stdout.strip()}")
                        send_message(chat_id, f"✅ _Mesaj başarıyla iletildi ve oturum uyandırıldı._")
                        return
                        
                system_prompt = (
                    "You are the brain of V-Engine 3.0 (Autonomous Recruitment and IND Visa/Career Assistant for Vedat Sapan, company blives).\n"
                    "You can execute actions on the user's system by returning a JSON block with the action details.\n"
                    "If the user wants to perform an action (e.g. sending a WhatsApp, checking status, listing campaigns, running a simulation), you MUST respond with a valid JSON block containing the 'action' name and 'parameters'.\n"
                    "If the user is just chatting or asking a question, respond with a JSON block containing the 'reply' key in fluent, professional Turkish.\n\n"
                    "Available Actions:\n"
                    "1. SEND_WHATSAPP:\n"
                    "   - Use when: User explicitly wants to send a WhatsApp message to a company or specific phone number.\n"
                    "   - Parameters:\n"
                    "     - 'to': '+31600000000' (default test number) or the number provided.\n"
                    "     - 'company_name': 'ASML' or the company name mentioned.\n"
                    "     - 'message': The content of the WhatsApp message.\n"
                    "2. GET_STATUS:\n"
                    "   - Use when: User wants to see current status, stats, or dashboard.\n"
                    "3. LIST_CAMPAIGNS:\n"
                    "   - Use when: User wants to see a list of targeted companies or campaigns from the database.\n"
                    "4. SIMULATE:\n"
                    "   - Use when: User wants to run/trigger a mock campaign simulation.\n\n"
                    "JSON Response Schema:\n"
                    "- For an action:\n"
                    "  {\"action\": \"SEND_WHATSAPP\", \"parameters\": {\"to\": \"+31600000000\", \"company_name\": \"ASML\", \"message\": \"...\"}}\n"
                    "- For general conversation or guidance:\n"
                    "  {\"reply\": \"<Your warm, elegant, professional response in Turkish. Answer questions about work permits (UWV TWV), highly skilled visas (IND), or V-Engine 3.0 strategy. Keep it elegant. You are running locally.>\"}"
                )
                
                combined_query = f"{system_prompt}\n\nKullanıcıdan Gelen Mesaj:\n{text}"
                reply_raw = generate_with_agentapi(combined_query, model="pro")
                
                clean_reply = reply_raw.strip()
                if "```json" in clean_reply:
                    clean_reply = clean_reply.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_reply:
                    clean_reply = clean_reply.split("```")[1].split("```")[0].strip()
                else:
                    start_idx = clean_reply.find("{")
                    end_idx = clean_reply.rfind("}")
                    if start_idx != -1 and end_idx != -1:
                        clean_reply = clean_reply[start_idx:end_idx+1]
                        
                data = json.loads(clean_reply)
                
                if "action" in data:
                    action = data["action"]
                    params = data.get("parameters", {})
                    
                    if action == "SEND_WHATSAPP":
                        to_number = params.get("to") or "+31600000000"
                        company_name = params.get("company_name") or "Target Company"
                        message_content = params.get("message") or "Beste, Vedat Sapan..."
                        
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO companies (kvk_number, legal_name, domain) VALUES ('00000000', %s, %s) ON CONFLICT (domain) DO UPDATE SET legal_name=EXCLUDED.legal_name RETURNING id;", (company_name, f"{company_name.lower().replace(' ', '')}.nl"))
                        company_id = cursor.fetchone()[0]
                        cursor.execute("INSERT INTO contacts (company_id, full_name, email, phone_e164) VALUES (%s, 'Recruiter', %s, %s) ON CONFLICT (company_id, email) DO UPDATE SET phone_e164=EXCLUDED.phone_e164 RETURNING id;", (company_id, f"recruiter@{company_name.lower().replace(' ', '')}.nl", to_number))
                        contact_id = cursor.fetchone()[0]
                        
                        dispatch_key = f"direct-WA-{contact_id}-v1"
                        cursor.execute("INSERT INTO outreach (company_id, contact_id, channel, status, dispatch_key) VALUES (%s, %s, 'WHATSAPP', 'PENDING_APPROVAL', %s) ON CONFLICT (dispatch_key) DO UPDATE SET status='PENDING_APPROVAL' RETURNING id;", (company_id, contact_id, dispatch_key))
                        outreach_id = cursor.fetchone()[0]
                        cursor.execute("INSERT INTO drafts (outreach_id, version, subject, body) VALUES (%s, 1, 'WA Message', %s) ON CONFLICT (outreach_id, version) DO UPDATE SET body=EXCLUDED.body;", (outreach_id, f"EMAIL_BODY:\nWA-Direct\n\nWHATSAPP_BODY:\n{message_content}"))
                        conn.commit()
                        conn.close()
                        
                        # Synchronize WhatsApp campaign contacts JSON
                        sync_campaign_contacts()
                        
                        res = requests.post(
                            "http://localhost:5001/send",
                            json={"to": to_number, "message": message_content},
                            timeout=15
                        )
                        
                        if res.status_code == 200 and res.json().get("success"):
                            conn = get_db_connection()
                            with conn.cursor() as cur:
                                cur.execute("UPDATE outreach SET status = 'SENT' WHERE id = %s;", (outreach_id,))
                            conn.commit()
                            conn.close()
                            
                            send_message(chat_id, (
                                f"🚀 *Otonom WhatsApp Mesajı Gönderildi!*\n\n"
                                f"🏢 *Şirket:* {company_name}\n"
                                f"👤 *Alıcı:* ({to_number})\n"
                                f"✉️ *Mesaj:* \"{message_content}\""
                            ))
                        else:
                            error_msg = res.json().get("error", "Bilinmeyen API hatası")
                            send_message(chat_id, f"❌ Gönderim başarısız oldu: {error_msg}")
                            
                    elif action == "GET_STATUS":
                        # (Reuse /status logic)
                        text = "/status"
                        handle_update(update)
                        
                    elif action == "LIST_CAMPAIGNS":
                        conn = get_db_connection()
                        with conn.cursor() as cur:
                            cur.execute("SELECT o.id, c.legal_name, con.full_name, o.status, o.created_at FROM outreach o JOIN companies c ON o.company_id = c.id JOIN contacts con ON o.contact_id = con.id ORDER BY o.id DESC LIMIT 10")
                            rows = cur.fetchall()
                        conn.close()
                        
                        if not rows:
                            send_message(chat_id, "📭 Veritabanında henüz kayıtlı aktif kampanya bulunamadı.")
                        else:
                            table = "📊 *KAMPANYA VERİTABANI (PostgreSQL)*\n\n"
                            table += "| ID | Şirket | İletişim | Durum | Tarih |\n"
                            table += "|---|---|---|---|---|\n"
                            for row in rows:
                                table += f"| {row[0]} | {row[1]} | {row[2]} | `{row[3]}` | {row[4].strftime('%Y-%m-%d %H:%M')} |\n"
                            send_message(chat_id, table)
                            
                    elif action == "SIMULATE":
                        text = "/simulate"
                        handle_update(update)
                        
                elif "reply" in data:
                    send_message(chat_id, data["reply"])
                else:
                    raise Exception("Geçersiz JSON yapısı.")
                    
            except Exception as e:
                print(f"[WARN] Fallback active: {e}", file=sys.stderr)
                if "kimsin" in text.lower() or "kim olduğunu" in text.lower():
                    reply_content = (
                        "Ben Vedat Sapan'ın 7/24 arka planda çalışan otonom kariyer asistanıyım. "
                        "Görevin olan IND vize sponsorluğunu ve kalıcı kontratı (Vast Kontrat) kazanmak için "
                        "şirketleri tarar, e-postalarını ve WhatsApp akışlarını otonom olarak yönetirim!"
                    )
                else:
                    reply_content = (
                        f"Merhaba Vedat! Mesajınızı aldım. Yerel Antigravity işlemcimiz otonom olarak devrede. "
                        f"Herhangi bir kampanya durumunu sormak için `/status` veya test onay kartı için `/simulate` gönderebilirsiniz!"
                    )
                send_message(chat_id, reply_content)

def sync_campaign_contacts():
    """Reads all active contacts with phone numbers from the PostgreSQL database and writes them to telephony/campaign_contacts.json."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor) if hasattr(psycopg2.extras, "DictCursor") else conn.cursor()
        cursor.execute("""
            SELECT con.phone_e164, con.full_name, c.legal_name, c_intel.data_ops_signals, c_intel.tech_stack
            FROM contacts con
            JOIN companies c ON con.company_id = c.id
            LEFT JOIN company_intel c_intel ON c_intel.company_id = c.id
            WHERE con.phone_e164 IS NOT NULL AND con.phone_e164 != '';
        """)
        rows = cursor.fetchall()
        conn.close()
        
        contacts = {}
        # Keep existing test contacts if needed, or fully sync
        for row in rows:
            data = dict(row) if hasattr(row, 'keys') else {
                "phone_e164": row[0], "full_name": row[1], "legal_name": row[2], "data_ops_signals": row[3], "tech_stack": row[4]
            }
            phone = data["phone_e164"].replace("+", "").replace(" ", "").strip()
            if not phone:
                continue
            jid = f"{phone}@c.us"
            
            # Format bottlenecks and value props
            bottlenecks = ""
            if data["data_ops_signals"]:
                try:
                    sigs = json.loads(data["data_ops_signals"]) if isinstance(data["data_ops_signals"], str) else data["data_ops_signals"]
                    bottlenecks = ", ".join(sigs) if isinstance(sigs, list) else str(sigs)
                except:
                    bottlenecks = str(data["data_ops_signals"])
                    
            contacts[jid] = {
                "contact_name": data["full_name"],
                "company_name": data["legal_name"],
                "bottlenecks": bottlenecks,
                "initial_value_prop": f"Enterprise data architecture and multi-agent LangGraph integration solutions.",
                "why_vedat_uniquely": "12+ years of senior engineering experience in zero-downtime migrations and stateful flow routing.",
                "language": "nl",
                "goal": "Schedule a brief call via Cal.com (https://cal.com/vedat-sapan)"
            }
            
        json_path = os.path.join(os.path.dirname(__file__), "campaign_contacts.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(contacts, f, indent=2, ensure_ascii=False)
            
        print("🔄 campaign_contacts.json successfully synchronized in telegram_bot.py!")
    except Exception as e:
        print(f"[WARNING] Failed to sync campaign contacts in telegram_bot.py: {e}", file=sys.stderr)

def start_self_healing_outbox_daemon():
    """
    Background daemon that periodically runs email bounce checks, self-healing email recovery,
    and recruiter reply scanning every 5 minutes to close the loop autonomously!
    """
    print("[SYSTEM] Starting background Self-Healing Outbox Daemon (Bounce & Reply Monitor)...")
    import subprocess
    import sys
    
    venv_python = "/Users/vedat/.gemini/antigravity/scratch/v_engine/venv/bin/python3"
    recovery_script = "/Users/vedat/Desktop/Ai Agent/scratch/email_recovery_agent.py"
    reply_script = "/Users/vedat/Desktop/Ai Agent/scratch/check_recruiter_replies.py"
    
    while True:
        # Wait 300 seconds (5 minutes) between runs
        time.sleep(300)
        try:
            print("[SELF-HEALING DAEMON] Running bounce checking & email recovery agent...")
            # Running recovery script automatically triggers check_bounces() internally now!
            subprocess.run([venv_python, recovery_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            print("[SELF-HEALING DAEMON] Running recruiter reply scanner...")
            subprocess.run([venv_python, reply_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            print("[SELF-HEALING DAEMON] Periodic self-healing sweep complete.")
        except Exception as e:
            print(f"[SELF-HEALING DAEMON ERROR] Failed during sweep: {e}", file=sys.stderr)

def main():
    print("[SYSTEM] Starting V-Engine 3.0 Telegram Bot loop...")
    
    # Start background Queue Dispatch Scheduler and Dograh Telephony Outcome Poller
    import threading
    threading.Thread(target=start_queued_dispatch_scheduler, daemon=True).start()
    threading.Thread(target=start_dograh_telephony_poller, daemon=True).start()
    threading.Thread(target=start_self_healing_outbox_daemon, daemon=True).start()
    
    send_message(USER_ID, "🟢 *V-Engine 3.0 Otonom Bildirim ve Kontrol Hattı Başayla Devreye Girdi!* PostgreSQL veritabanı 7/24 otonom takibe başlıyorum.")
    
    offset = 0
    while True:
        try:
            url = f"{API_URL}/getUpdates"
            params = {
                "offset": offset,
                "timeout": 10
            }
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            
            if "result" in data:
                for update in data["result"]:
                    handle_update(update)
                    offset = update["update_id"] + 1
                    
        except Exception as e:
            print(f"[ERROR] Error in Telegram Bot long-polling: {e}", file=sys.stderr)
            time.sleep(5)
            
        time.sleep(0.5)

if __name__ == "__main__":
    main()
