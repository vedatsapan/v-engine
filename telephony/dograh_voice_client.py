import os
import sys
from dotenv import load_dotenv

# Ensure environment variables are loaded
env_path = os.path.join(os.path.dirname(__file__), "../.env")
load_dotenv(dotenv_path=env_path)

# Automatically add the Dograh Python SDK directory to system path
sys.path.append("/Users/vedat/dograh/sdk/python/src")

try:
    from dograh_sdk import DograhClient
    from dograh_sdk._generated_models import CreateWorkflowRequest, InitiateCallRequest
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

def dispatch_dograh_voice_call(
    phone_number: str,
    contact_name: str,
    company_name: str,
    voice_script: str,
    bottlenecks: str = None,
    value_prop: str = None,
    language: str = None
) -> dict:
    """
    Creates a highly personalized B2B voice agent workflow inside Dograh AI 
    and initiates an outbound Twilio call dynamically using the Dograh Client SDK.
    Dynamic language overrides are applied so VAD and barge-in work perfectly in Turkish or Dutch.
    """
    if not SDK_AVAILABLE:
        return {
            "status": "FAILED",
            "error": "Dograh SDK not found at '/Users/vedat/dograh/sdk/python/src'. Please check the path."
        }

    # Fetch configuration endpoints and tokens
    api_endpoint = os.environ.get("DOGRAH_API_ENDPOINT", "http://localhost:8000")
    api_token = os.environ.get("DOGRAH_API_TOKEN", "mock-token")

    # Clean the phone number format
    clean_phone = phone_number.replace(" ", "").replace("-", "")
    if not clean_phone.startswith("+"):
        clean_phone = f"+{clean_phone}"

    # Auto-detect language if not explicitly provided
    if not language:
        turkish_keywords = ["merhaba", "bey", "hanım", "nasılsınız", "blives", "otonom"]
        script_lower = voice_script.lower()
        if any(keyword in script_lower for keyword in turkish_keywords):
            language = "tr"
        else:
            language = "nl"

    # Set up language-specific labels and personas
    if language == "tr":
        target_language_name = "Turkish (Türkçe)"
        style_rules = (
            f"- Language: Turkish (Türkçe). Speak naturally and professionally.\n"
            f"- Keep responses extremely brief (maximum 1-2 sentences) to ensure low latency and natural conversation flow.\n"
            f"- Allow the user to interrupt you at any point. Address their points immediately. When they speak, STOP speaking immediately.\n"
            f"- Always be highly professional, polite, and transparent that you are an AI assistant representing Vedat Sapan.\n"
        )
    else:
        target_language_name = "Dutch (Felemenkçe)"
        style_rules = (
            f"- Language: Dutch (Felemenkçe). If the user prefers English, switch immediately and naturally.\n"
            f"- Keep responses extremely brief (maximum 1-2 sentences) to ensure low latency and natural conversation flow.\n"
            f"- Allow the user to interrupt you at any point. Address their points immediately. When they speak, STOP speaking immediately.\n"
            f"- Always be highly professional, polite, and transparent that you are an AI assistant representing Vedat Sapan.\n"
        )

    # Build prompts for the rich interactive node-based workflow
    global_prompt = (
        f"# GLOBAL PERSONA — JARVIS\n"
        f"You are Jarvis, the professional autonomous B2B AI Voice Assistant representing Vedat Sapan (Principal of blives).\n\n"
        f"## CORE IDENTITY\n"
        f"- Name: Jarvis\n"
        f"- Role: AI voice agent built on Gemini Live technology for blives\n"
        f"- Created by: Vedat Sapan\n\n"
        f"## STYLE & RULES\n"
        f"{style_rules}"
    )

    start_prompt = (
        f"# OPENING — GREETING\n"
        f"Start by speaking the following introduction in {target_language_name}:\n"
        f"\"{voice_script}\"\n\n"
        f"Wait for the user's response. If they agree to continue or express interest, transition to the Main Agenda node.\n"
    )

    if language == "tr":
        agenda_prompt = (
            f"# ANA GÜNDEM — B2B DETAYLARI\n"
            f"{company_name} firması ve {contact_name} için özelleştirilmiş çözümlerimizi sunun.\n\n"
            f"## ÖNEMLİ NOKTALAR:\n"
            f"- {company_name} operasyonlarını analiz ettik ve manuel süreçleri tespit ettik.\n"
            f"- Tespit edilen darboğazlar: \"{bottlenecks or 'manuel iş yükü ve entegrasyon kayıpları'}\"\n"
            f"- Çözüm / Değer Önerisi: \"{value_prop or 'LangGraph tabanlı otonom entegrasyon ajanları kurarak zaman kayıplarını sıfıra indirmek'}\"\n"
            f"- Bu canlı görüşmenin kendi Gemini Live altyapımızda çalışan yapay zeka asistanının ne kadar akıcı konuşabildiğinin doğrudan bir kanıtı olduğunu belirtin!\n\n"
            f"Kendilerine bu konularda destek olmak isteyip istemediklerini veya Vedat Sapan ile görüşmek isteyip istemediklerini sorun."
        )

        summary_prompt = (
            f"# ÖZET VE TOPLANTI ÖNERİSİ\n"
            f"Görüşmeyi kısaca özetleyin:\n"
            f"\"{company_name} için bu entegrasyonları iki hafta içinde otonom olarak kurarak manuel süreçleri tamamen ortadan kaldırabiliriz.\"\n\n"
            f"Vedat Sapan ile cal.com üzerinden kısa bir online toplantı planlamak isteyip istemediklerini sorun.\n"
            f"Kabul ederlerse: \"Harika! Vedat Sapan cal.com üzerinden veya e-posta ile sizinle irtibata geçecektir.\" deyin."
        )

        end_prompt = (
            f"# GÖRÜŞMEYİ SONLANDIR\n"
            f"Kibarca ve hemen görüşmeyi sonlandırın.\n"
            f"Değin: \"Zaman ayırdığınız için çok teşekkürler {contact_name}. İyi günler dilerim, hoşça kalın!\"\n"
        )
    else:
        agenda_prompt = (
            f"# MAIN AGENDA — B2B OPPORTUNITY BRIEFING\n"
            f"Present our personalized findings and solutions for {company_name} to {contact_name}.\n\n"
            f"## KEY POINTS:\n"
            f"- We analyzed {company_name}'s operations and identified manual overhead.\n"
            f"- Bottlenecks identified: \"{bottlenecks or 'manual process overhead'}\"\n"
            f"- Solution / Value Prop: \"{value_prop or 'implementing real-time multi-agent workflows to automate manual integration tasks'}\"\n"
            f"- Note that this very conversational call is running live on our local Gemini Live engine as a direct demonstration of what we build!\n\n"
            f"Ask them if they have experienced these bottlenecks or if they would like to know how we can solve them. Address any questions factually.\n"
        )

        summary_prompt = (
            f"# SUMMARY & MEETING PROPOSAL\n"
            f"Summarize the conversation:\n"
            f"\"To summarize, we can fully automate these manual integration workflows for {company_name} within two weeks, eliminating overhead.\"\n\n"
            f"Ask if they would be open to a quick follow-up conversation or online meeting with Vedat Sapan.\n"
            f"If they agree, say: \"Great! Vedat will contact you via WhatsApp or Email to coordinate a suitable time.\"\n"
        )

        end_prompt = (
            f"# END CALL\n"
            f"Politely and immediately conclude the call.\n"
            f"Say: \"Hartelijk bedankt voor uw tijd, {contact_name}. Een fijne dag gewenst. Tot ziens!\"\n"
        )

    # Construct the complete interactive 6-node workflow definition (Pipecat / Gemini Live layout)
    workflow_definition = {
        "nodes": [
            {
                "id": "trigger-api",
                "type": "trigger",
                "position": {"x": 500, "y": -150},
                "data": {
                    "name": "API Trigger",
                    "enabled": True
                }
            },
            {
                "id": "0",
                "type": "globalNode",
                "position": {"x": 175, "y": 60},
                "data": {
                    "name": "Global Persona",
                    "prompt": global_prompt,
                    "allow_interrupt": True,
                    "is_static": False
                }
            },
            {
                "id": "1",
                "type": "startCall",
                "position": {"x": 925, "y": 60},
                "data": {
                    "name": "Greeting",
                    "greeting_type": "text",
                    "prompt": start_prompt,
                    "allow_interrupt": True,
                    "add_global_prompt": True,
                    "wait_for_user_response": True,
                    "delayed_start": False,
                    "delayed_start_duration": 0,
                    "interrupt_on_start": True,
                    "is_start": True
                }
            },
            {
                "id": "2",
                "type": "agentNode",
                "position": {"x": 1332, "y": 480},
                "data": {
                    "name": "Main Agenda",
                    "prompt": agenda_prompt,
                    "allow_interrupt": True,
                    "add_global_prompt": True,
                    "interrupt_on_start": True,
                    "extraction_enabled": False
                }
            },
            {
                "id": "3",
                "type": "agentNode",
                "position": {"x": 122, "y": 900},
                "data": {
                    "name": "Summary & Proposal",
                    "prompt": summary_prompt,
                    "allow_interrupt": True,
                    "add_global_prompt": True,
                    "interrupt_on_start": True,
                    "extraction_enabled": False
                }
            },
            {
                "id": "4",
                "type": "endCall",
                "position": {"x": 935, "y": 1320},
                "data": {
                    "name": "End Call",
                    "prompt": end_prompt,
                    "allow_interrupt": False,
                    "add_global_prompt": False,
                    "is_end": True
                }
            }
        ],
        "edges": [
            {
                "id": "1-2",
                "source": "1",
                "target": "2",
                "animated": True,
                "type": "custom",
                "data": {
                    "condition": "Choose this bot pathway everytime after the initial user response to discuss details.",
                    "label": "Move to Main Agenda"
                }
            },
            {
                "id": "2-3",
                "source": "2",
                "target": "3",
                "animated": True,
                "type": "custom",
                "data": {
                    "condition": "Choose this pathway when its time to move to summarise the conversation.",
                    "label": "Move to Summary"
                }
            },
            {
                "id": "3-4",
                "source": "3",
                "target": "4",
                "animated": True,
                "type": "custom",
                "data": {
                    "condition": "Choose this pathway whenever you are supposed to end the call.",
                    "label": "End call"
                }
            },
            {
                "id": "3-2",
                "source": "3",
                "target": "2",
                "animated": True,
                "type": "custom",
                "data": {
                    "condition": "Choose this pathway if the user has more questions or wants to discuss more topics.",
                    "label": "Back to Agenda"
                }
            },
            {
                "id": "1-4",
                "source": "1",
                "target": "4",
                "animated": True,
                "type": "custom",
                "data": {
                    "condition": "Choose this pathway if the user wishes to end the call immediately.",
                    "label": "Direct Hangup"
                }
            },
            {
                "id": "2-4",
                "source": "2",
                "target": "4",
                "animated": True,
                "type": "custom",
                "data": {
                    "condition": "Choose this pathway if the user hangs up or wishes to end during the agenda.",
                    "label": "Hangup"
                }
            }
        ],
        "viewport": {"x": 184.25, "y": 23.5, "zoom": 0.5}
    }

    try:
        # Check against Bel-me-niet list or mock safety filters
        if clean_phone.endswith("999"):
            return {
                "status": "BLOCKED",
                "reason": "Number is restricted by Bel-me-niet register/privacy policies."
            }

        # Initialize the dynamic Dograh SDK Client
        with DograhClient(base_url=api_endpoint, api_key=api_token) as client:
            # Step 1: Create the target workflow
            workflow = client.create_workflow(
                body=CreateWorkflowRequest(
                    name=f"V-Engine: {company_name} - {contact_name}",
                    workflow_definition=workflow_definition,
                )
            )
            workflow_id = workflow.id
            
            # Step 1.5: Set workflow configurations (apply correct language code model overrides)
            from dograh_sdk._generated_models import UpdateWorkflowRequest
            client.update_workflow(
                workflow_id=workflow_id,
                body=UpdateWorkflowRequest(
                    workflow_configurations={
                        "model_overrides": {
                            "realtime": {
                                "language": language
                            }
                        }
                    }
                )
            )
            
            # Step 2: Dispatch the phone call (Twilio -> Pipecat)
            call_response = client.test_phone_call(
                body=InitiateCallRequest(
                    workflow_id=workflow_id,
                    phone_number=clean_phone,
                )
            )
            
            return {
                "status": "SUCCESS",
                "workflow_id": workflow_id,
                "call_response": str(call_response)
            }
            
    except Exception as e:
        return {
            "status": "FAILED",
            "error": f"Failed to dispatch Dograh voice call: {str(e)}"
        }

if __name__ == "__main__":
    # Test script if executed directly
    print("Dograh Voice Client Loaded. SDK Status: ", "OK" if SDK_AVAILABLE else "FAILED")

