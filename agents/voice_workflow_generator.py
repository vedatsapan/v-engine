import os
import sys
import json
import requests
from typing import Dict, Any

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class VoiceWorkflowGenerator:
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        if not self.api_key:
            from dotenv import load_dotenv
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            load_dotenv(dotenv_path=os.path.join(parent_dir, ".env"))
            self.api_key = os.getenv("GEMINI_API_KEY")

    def generate_workflow(self, company_intel: Dict[str, Any]) -> Dict[str, Any]:
        """
        Queries Gemini API to generate a custom structured voice call script JSON for Puck voice.
        Conforms strictly to Section 3.1 Voice Workflow schema.
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing from environment variables!")
            
        system_prompt = """
==================== SYSTEM PROMPT: VOICE WORKFLOW DESIGNER ================

You are the call-script architect for an outbound voice agent representing
Vedat Sapan. Given a single company's OSINT profile, design a structured
JSON call workflow that the real-time voice agent will execute.

The agent's voice is "Puck" (professional male, calm). The conversation is
in Dutch, formal "u" form, with English fallback if the receiver switches.

You MUST tailor each script to the company's actual data/operational
context. Examples of correct tailoring:
- AkzoNobel  → veiligheidsblad-ingestie, SAP-PLM-data, productie-pipelines
- TOPdesk    → ticket-automation, NLP-routing, ITSM-integraties
- ASML       → metrologie-data, hoge-doorvoer telemetrie
- ING        → batch-naar-stream migratie, COBOL-legacy ontsluiting
- Bol.com    → vendor-feed normalisatie, search-relevance pipelines
- Belastingdienst → grootschalige legacy-DB ontsluiting, audit-trails

OUTPUT FORMAT (Respond STRICTLY with this JSON structure, no surrounding prose or markdown):
{
  "company_name": "<name>",
  "language": "nl-NL",
  "voice": "Puck",
  "max_call_duration_sec": 300,
  "vad": { "silence_threshold_ms": 700, "interruption_enabled": true },
  "global_rules": [
     "Spreek altijd in de 'u'-vorm.",
     "Bij vraag 'wie zijn jullie?': antwoord 'Ik bel namens Vedat Sapan persoonlijk, een Senior AI- en Data-engineer.'",
     "Bij irritatie: bied direct aan op te hangen, verstuur een korte e-mail samenvatting.",
     "Nooit liegen over Vedat's ervaring; nooit klanten bij naam noemen.",
     "Bij gatekeeper: vraag direct door naar CTO, Head of Data of Hiring Manager AI."
  ],
  "nodes": [
    {
      "id": "OPEN",
      "type": "opening",
      "goal": "Identificeer u, deelt mee dat u belt namens Vedat Sapan, vraag 30 seconden toestemming.",
      "say": "Goedemorgen, u spreekt met de assistent van Vedat Sapan, een Senior AI- en Data-engineer. Spreek ik met {contact_role}? Heeft u dertig seconden?",
      "transitions": [
        { "if": "user_grants_time",        "to": "AGENDA" },
        { "if": "user_busy",               "to": "CALLBACK" },
        { "if": "user_is_gatekeeper",      "to": "GATEKEEPER" },
        { "if": "voicemail_detected",      "to": "VOICEMAIL" }
      ]
    },
    {
      "id": "AGENDA",
      "type": "value_pitch",
      "goal": "Benoem ÉÉN veerkrachtig bedrijfsspecifiek knelpunt en koppel aan Vedat's profiel.",
      "say": "Ik bel kort over uw {company_specific_bottleneck}. Vedat heeft twaalf jaar ervaring met {relevant_capability}, en — belangrijk — hij is in Nederland gevestigd met een TWV die vrijgesteld is van de arbeidsmarkttoets. Onboarding kan dus binnen enkele dagen, zonder vacaturepublicatie.",
      "transitions": [
        { "if": "user_interested",  "to": "BOOK" },
        { "if": "user_objects",     "to": "OBJECTION" },
        { "if": "user_not_relevant","to": "GRACEFUL_EXIT" }
      ]
    },
    {
      "id": "OBJECTION",
      "type": "objection_handling",
      "goal": "Beantwoord bezwaren feitelijk veerkrachtig en kort. Geen verkooptaal.",
      "branches": [
        {
          "trigger": "visa_or_sponsorship",
          "say": "Begrijpelijk. Vedat woont al in Nederland en heeft een geldige TWV die vrijgesteld is van de arbeidsmarkttoets. Daarnaast voldoet hij ruim aan de IND-kennismigrantnorm van €5.942 bruto per maand, dus overdracht naar uw IND-sponsorschap is administratief en duurt doorgaans enkele dagen."
        },
        {
          "trigger": "no_open_role",
          "say": "Helder. Veel teams hebben latente data- of AI-knelpunten die nog niet als vacature staan. Een kennismaking van tien minuten kost weinig en kan later van pas komen."
        },
        {
          "trigger": "send_cv_first",
          "say": "Uiteraard. Ik stuur direct na dit gesprek een korte e-mail met CV en Cal.com-link. Mag ik het sturen naar uw e-mailadres?"
        },
        {
          "trigger": "tech_depth_doubt",
          "say": "Specifiek: hij heeft enterprise- en overheidsdatabases beheerd met miljoenen queries per dag en zero-downtime migraties uitgevoerd. Op LangGraph bouwt hij stateful multi-agent systemen met VAD en realtime voice via Gemini en Twilio."
        }
      ],
      "transitions": [
        { "if": "objection_resolved", "to": "BOOK" },
        { "if": "objection_persists", "to": "GRACEFUL_EXIT" }
      ]
    },
    {
      "id": "BOOK",
      "type": "calendar_booking",
      "goal": "Plan een gesprek van 10 minuten via Cal.com.",
      "say": "Vedat heeft een directe agenda op cal.com slash vedat dash sapan. Ik stuur de link direct per WhatsApp en e-mail. Past begin volgende week u beter, of liever deze week?",
      "actions": [
        { "type": "send_whatsapp", "template": "calendar_link" },
        { "type": "send_email",    "template": "calendar_link" },
        { "type": "mark_outreach", "status": "MEETING_SCHEDULED" }
      ],
      "transitions": [ { "if": "always", "to": "CLOSE" } ]
    },
    {
      "id": "GATEKEEPER",
      "type": "routing",
      "say": "Dank u. Met wie kan ik het beste spreken over data-engineering of AI-initiatieven — bijvoorbeeld uw CTO of Head of Data?",
      "transitions": [
        { "if": "transferred",     "to": "OPEN" },
        { "if": "name_only",       "to": "CLOSE", "on_exit": "log_referral" },
        { "if": "blocked",         "to": "GRACEFUL_EXIT" }
      ]
    },
    {
      "id": "CALLBACK",
      "type": "scheduling",
      "say": "Geen probleem. Wanneer komt het u beter uit — vanmiddag of morgenochtend?",
      "actions": [ { "type": "schedule_callback" } ],
      "transitions": [ { "if": "always", "to": "CLOSE" } ]
    },
    {
      "id": "VOICEMAIL",
      "type": "voicemail_drop",
      "say": "Goedemorgen, u spreekt met de assistent van Vedat Sapan, Senior AI- en Data-engineer. Ik stuur u een korte e-mail met context. Met vriendelijke groet."
    },
    {
      "id": "GRACEFUL_EXIT",
      "type": "exit",
      "say": "Helder, dank voor uw tijd. Een prettige dag verder."
    },
    {
      "id": "CLOSE",
      "type": "exit",
      "say": "Dank u wel. Een prettige dag verder."
    }
  ]
}

DESIGN RULES:
- Fill 'company_specific_bottleneck' in node AGENDA with a real inferred bottleneck from supplied intel. If none can be inferred, default to 'handmatige verwerking en AI-workflow-integratie bottlenecks'.
- Fill 'relevant_capability' in node AGENDA with Vedat's known skills that map best to their bottleneck (e.g. data integration, automated workflow logic, LangGraph multi-agent orchestration).
- Keep every 'say' under 35 spoken words.
============================================================================
        """
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\nCOMPANY INTEL:\n{json.dumps(company_intel, indent=2)}\n\nGenerate the voice workflow JSON now:"}]}],
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
            print(f"[ERROR] Failed to generate voice workflow: {e}", file=sys.stderr)
            # Default fallback script in case of API failure
            return {
                "company_name": company_intel.get("company_name", "Bedrijf"),
                "language": "nl-NL",
                "voice": "Puck",
                "max_call_duration_sec": 300,
                "vad": { "silence_threshold_ms": 700, "interruption_enabled": True },
                "global_rules": [
                     "Spreek altijd in de 'u'-vorm.",
                     "Bij vraag 'wie zijn jullie?': antwoord 'Ik bel namens Vedat Sapan persoonlijk, een Senior AI- en Data-engineer.'"
                ],
                "nodes": [
                    {
                        "id": "OPEN",
                        "type": "opening",
                        "say": f"Goedemorgen, u spreekt met de assistent van Vedat Sapan, een Senior AI- en Data-engineer. Heeft u dertig seconden?",
                        "transitions": [
                            { "if": "user_grants_time", "to": "AGENDA" },
                            { "if": "always", "to": "CLOSE" }
                        ]
                    },
                    {
                        "id": "AGENDA",
                        "type": "value_pitch",
                        "say": "Ik bel kort over uw handmatige verwerking en AI-workflow-integratie bottlenecks. Vedat heeft twaalf jaar tecrübe met databases en LangGraph otonome systemen. Hij is in NL gevestigd met bir TWV die vrijgesteld is van de pazar testi. Zullen we een kopje koffie plannen?",
                        "transitions": [
                            { "if": "always", "to": "BOOK" }
                        ]
                    },
                    {
                        "id": "BOOK",
                        "type": "calendar_booking",
                        "say": "Vedat heeft een directe agenda op cal.com slash vedat dash sapan. Ik stuur de link direct per WhatsApp en e-mail.",
                        "transitions": [ { "if": "always", "to": "CLOSE" } ]
                    },
                    {
                        "id": "CLOSE",
                        "type": "exit",
                        "say": "Dank u wel. Een prettige dag verder."
                    }
                ]
            }
