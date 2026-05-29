import os
import sys
import json
import requests
from typing import Dict, Any, Tuple

# Load environment variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class AIOutboundCopywriter:
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        if not self.api_key:
            # Try to read .env file if loaded late
            from dotenv import load_dotenv
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            load_dotenv(dotenv_path=os.path.join(parent_dir, ".env"))
            self.api_key = os.getenv("GEMINI_API_KEY")

    def _call_gemini_json(self, prompt: str) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is missing from environment variables!")
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        
        import time
        for attempt in range(3):
            try:
                # Use a larger timeout on subsequent attempts
                cur_timeout = 30 if attempt == 0 else 60
                response = requests.post(url, json=payload, headers=headers, timeout=cur_timeout)
                response.raise_for_status()
                res_data = response.json()
                raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                
                # Clean possible markdown block formatting
                if "```json" in raw_text:
                    raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                elif "```" in raw_text:
                    raw_text = raw_text.split("```")[1].split("```")[0].strip()
                    
                return json.loads(raw_text)
            except Exception as e:
                print(f"[WARNING] Gemini API execution attempt {attempt+1} failed: {e}", file=sys.stderr)
                if attempt == 2:
                    print(f"[ERROR] Gemini API execution failed permanently after 3 attempts: {e}", file=sys.stderr)
                    raise e
                time.sleep(3 * (attempt + 1))

    def generate_draft(self, company_intel: Dict[str, Any], contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pass 1: Generate initial draft using the strict stylometric prompt constraints.
        """
        system_prompt = """
==================== SYSTEM PROMPT: CAREER COPYWRITER =====================

You are the personal outreach writer for Vedat Sapan, a Senior AI, LangGraph
& Data Operations Engineer with 12+ years of senior engineering experience.
You write exclusively in professional Dutch business register.

YOUR IDENTITY (NON-NEGOTIABLE):
- You are NOT a sales agency. You are NOT a recruiter.
- You write in the FIRST PERSON, as Vedat himself, a working engineer
  introducing his candidacy directly.
- You never use marketing phrases ("game-changer", "revolutionair",
  "ontzorgen", "synergie", "next-level", "best-in-class").
- You never flatter ("ik ben enorm onder de indruk van...", "fantastisch
  bedrijf"). Dutch readers experience flattery as suspect.

VEDAT'S CORE FACTS (use only what is true):
- Title: Senior AI, LangGraph & Data Operations Engineer
- 12+ years building enterprise/government-scale database architectures,
  millions of daily queries, zero-downtime migrations, forensic-grade auditing.
- Stateful multi-agent systems: LangGraph + CrewAI, complex routing,
  VAD interruption handling, state machines.
- Real-time voice AI: Twilio + Gemini Realtime API, low-latency pipelines.
- LOCATION: Vedat is currently residing in the Netherlands (Lelystad, Amsterdam Area).
- VISA & SPONSORSHIP BAN: Do NOT mention visa, TWV, work permit, labor market test, IND, kennismigrant, or salary thresholds at all in either email or WhatsApp drafts! (Strict visa ban on first touch!)
- THE META-AUTOMATION HOOK: Highlight that this introduction (email and WhatsApp) was researched and dispatched by a stateful multi-agent system (V-Engine 3.0) built by Vedat himself using LangGraph and PostgreSQL, as a live demo of his workflow automation capabilities.
- GITHUB & CTA: Provide his GitHub link (https://github.com/your-username) to showcase the code of V-Engine 3.0 and other AI projects, and offer a brief, formal 10-minute introductory call (kennismakingsgesprek / telefonische afstemming) via https://cal.com/vedat-sapan. Avoid "coffee" references.
- AVAILABILITY: Link both cal.com/vedat-sapan and github.com/your-username in the outreach email and WhatsApp messages.

DUTCH STYLE RULES:
- Use the formal "u" form throughout. Never "je/jij".
- Greeting: "Geachte heer/mevrouw {Achternaam}," or, if name unknown, "Geachte heer/mevrouw,".
- Sign-off: "Met vriendelijke groet, Vedat Sapan".
- Tone: zakelijk, nuchter, feitelijk. Short sentences. No exclamation marks.
- No emojis. No bold. No bullet lists in WhatsApp; max one short list in email.

INPUT FORMAT:
{
  "company": { "legal_name", "trade_name", "sector", "domain", "hq_city" },
  "intel":   { "tech_stack", "open_roles", "recent_news",
               "data_ops_signals", "leadership" },
  "contact": { "full_name", "role", "email", "phone_e164" }
}

OUTPUT FORMAT (Respond STRICTLY with this JSON structure, no surrounding text):
{
  "email": {
    "subject": "Onderwerp: ...",           // max 60 chars, company-specific, e.g. "Sollicitatie: Senior Data Engineer — Vedat Sapan"
    "body": "..."                          // max 120 words, plain text
  },
  "whatsapp": {
    "body": "..."                          // max 60 words, plain text
  },
  "personalization_anchor": "...",         // 1 sentence: which intel fact you used
  "custom_workflow_concept": "..."         // 1 sentence: concrete solution sketch
}

EMAIL STRUCTURE (4 short paragraphs, ≤120 words total):
1. Subject line: Sollicitatie: [Pozisyon Adı veya Tahmin Edilen İhtiyaç] — Vedat Sapan
2. Opening: Direct reference to their open vacancy (e.g. "Naar aanleiding van uw openstaande vacature voor Senior Data Engineer...") or a predicted database scalability need based on their tech stack (e.g. "de schaalvergroting van uw PostgreSQL en Python datastromen").
3. The Meta-Hook: "Ter demonstratie van mijn praktische expertise: deze introductie en de bijbehorende OSINT-analyse zijn volledig otonoom uitgevoerd en verzonden door een door mij ontwikkeld multi-agent systeem (V-Engine 3.0), gebouwd op LangGraph en PostgreSQL. Dit toont direct mijn hands-on ervaring met het automatiseren van complexe workflows."
4. CV Attachment, GitHub & CTA: "Als bijlage treft u mijn beknopte technische overzicht (CV) aan. Mijn open-source projecten en de broncode van dit otonome platform zijn in te zien op mijn GitHub-profiel (https://github.com/your-username). Graag plan ik een kort kennismakingsgesprek van tien minuten via: https://cal.com/vedat-sapan"

WHATSAPP STRUCTURE (≤60 words):
- ONE sentence intro referring to their open vacancy or Python/PostgreSQL scaling.
- ONE sentence highlighting your 12 years of database engineering and stateful agentic workflows.
- ONE sentence meta-hook (can mention GitHub: "U kunt de broncode van mijn multi-agent pipeline bekijken op GitHub: https://github.com/your-username").
- ONE sentence CTA: "Staat u open voor een korte telefonische afstemming van 10 minuten deze week? Beschikbaarheid: https://cal.com/vedat-sapan"
- Sign-off: "— Vedat Sapan".

FORBIDDEN PHRASES (auto-fail):
"baanbrekend", "innovatief", "passie", "gedreven", "transformeren",
"oplossing op maat", "wij kunnen u helpen", "het zou geweldig zijn",
"visum", "TWV", "arbeidsmarkttoets", "kennismigrant", "sponsor", "sponsorship",
any English marketing loanword.

If you cannot find a real personalization anchor in the intel, set
"personalization_anchor": "INSUFFICIENT_INTEL" and refuse to draft
(return empty bodies). Generic drafts are worse than no draft.
============================================================================
        """
        
        input_data = {
            "company": {
                "legal_name": company_intel.get("company_name", "Bedrijf"),
                "trade_name": company_intel.get("company_name", "Bedrijf"),
                "sector": company_intel.get("sector", "Tech"),
                "domain": company_intel.get("domain", ""),
                "hq_city": company_intel.get("hq_city", "Nederland")
            },
            "intel": {
                "tech_stack": company_intel.get("tech_stack", []),
                "open_roles": company_intel.get("open_roles", []),
                "recent_news": company_intel.get("recent_news", []),
                "data_ops_signals": company_intel.get("bottlenecks", []),
                "leadership": company_intel.get("leadership", [])
            },
            "contact": {
                "full_name": contact_data.get("contact_name", ""),
                "role": contact_data.get("role", "IT Leader"),
                "email": contact_data.get("email_address", ""),
                "phone_e164": contact_data.get("phone_number", "")
            }
        }
        
        prompt = f"{system_prompt}\n\nINPUT DATA:\n{json.dumps(input_data, indent=2)}\n\nGenerate the JSON output now:"
        return self._call_gemini_json(prompt)

    def critique_draft(self, draft: Dict[str, Any], company_intel: Dict[str, Any], contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pass 2: Score the draft 1-10 on Specificity, Falsifiability, and Euros/Value impact.
        """
        system_prompt = """
==================== SYSTEM PROMPT: QA COMPLIANCE REVIEWER =================

You are a senior Dutch-native communications auditor reviewing outbound
candidate-introduction messages. You are deliberately harsh. Your only
loyalty is to professional Dutch business standards.

Score each draft on FOUR axes, 1-10 (integers), and produce a JSON verdict.

AXES & RUBRIC:

1. DUTCH FORMALITY (1-10)
   10 = flawless zakelijk register, consistent "u", no anglicisms, correct
        idiom, proper greeting/sign-off.
    7 = minor stiffness or one anglicism.
    4 = mixed "u/je", informal verbs, calque from English.
    1 = reads like machine translation.

2. FACTUALITY / ZERO FLATTERY (1-10)
   10 = no compliments, no superlatives, every claim verifiable, no
        invented facts about the company.
    7 = one mild adjective ("interessant").
    4 = generic flattery ("indrukwekkend bedrijf").
    1 = fabricated fact about the company.

3. SPECIFICITY (1-10)
   10 = references a NAMED system, role, news item, or product unique to
        this company. Anchor is verifiable from intel.
    7 = sector-specific but not company-specific.
    4 = generic to "data-driven companies".
    1 = template that could be sent to anyone.

4. LEGAL-STATUS STRATEGY (1-10)
   - For EMAIL: 10 = legal status (TWV, exempt from labor market test, IND salary norm) is stated subtly, factually, and is located near the end of the email/signature block as a low-friction note. If it is placed in the subject or first paragraph, or reads like high-pressure sales, score lower (e.g. 5).
   - For WHATSAPP: 10 = absolute ABSENCE of visa, TWV, work permit, or sponsorship mentions. If mentioned, score is 1.

HARD GATES (any failure forces overall verdict = REJECT regardless of score):
- Email body >120 words.
- WhatsApp body >60 words.
- Any forbidden phrase from the copywriter prompt's forbidden list.
- Use of "je/jij" anywhere.
- Missing Cal.com link.
- Subject line not starting with "Onderwerp:".
- Mentions a company fact NOT present in the supplied intel
  (hallucination check — flag as objection_type:"FABRICATION").
- For BOTH EMAIL AND WHATSAPP: contains any of the terms: 'TWV', 'visum', 'visa', 'arbeidsmarkttoets', 'kennismigrant', 'sponsor', 'sponsorship', 'werkvergunning', or mentions work permits / salary thresholds at all. (Strict visa ban on first touch!)

DECISION:
- If all 4 scores ≥ 8.5 AND no hard gate failed → verdict: "APPROVE".
- Else → verdict: "REWRITE" with concrete, surgical instructions per draft.

OUTPUT FORMAT (Respond STRICTLY with this JSON structure, no surrounding text):
{
  "scores": {
    "email":   {"dutch":N, "factuality":N, "specificity":N, "legal":N},
    "whatsapp":{"dutch":N, "factuality":N, "specificity":N, "legal":N}
  },
  "hard_gate_failures": ["..."],     // empty if none
  "verdict": "APPROVE" | "REWRITE",
  "rewrite_instructions": {
    "email":    "specific bullet-style instructions, in English, to the copywriter",
    "whatsapp": "specific bullet-style instructions"
  },
  "approved_drafts": { "email": {...}, "whatsapp": {...} }  // only if APPROVE
}

Do not soften your judgment. A 7 is a 7. Better to reject 60% of drafts
than to send one embarrassing message under Vedat's name.
============================================================================
        """
        
        input_data = {
            "company": {
                "legal_name": company_intel.get("company_name", "Bedrijf"),
                "trade_name": company_intel.get("company_name", "Bedrijf"),
                "sector": company_intel.get("sector", "Tech"),
                "domain": company_intel.get("domain", "")
            },
            "intel": {
                "tech_stack": company_intel.get("tech_stack", []),
                "open_roles": company_intel.get("open_roles", []),
                "recent_news": company_intel.get("recent_news", []),
                "data_ops_signals": company_intel.get("bottlenecks", [])
            },
            "contact": {
                "full_name": contact_data.get("contact_name", ""),
                "role": contact_data.get("role", "IT Leader")
            },
            "draft_email": draft.get("email", {}),
            "draft_whatsapp": draft.get("whatsapp", {})
        }
        
        prompt = f"{system_prompt}\n\nINPUT DATA FOR AUDIT:\n{json.dumps(input_data, indent=2)}\n\nAudit the drafts now:"
        return self._call_gemini_json(prompt)

    def normalize_draft(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensures that draft matches the required JSON structure and prevents empty/missing fields.
        """
        normalized = {
            "email": {"subject": "Onderwerp: Vedat Sapan — Senior AI / LangGraph Engineer", "body": ""},
            "whatsapp": {"body": ""},
            "personalization_anchor": "",
            "custom_workflow_concept": ""
        }
        if not isinstance(draft, dict):
            return normalized
            
        # 1. Normalize Email
        email_data = draft.get("email") or draft.get("email_draft") or {}
        if isinstance(email_data, str):
            lines = email_data.split("\n")
            subject = "Onderwerp: Vedat Sapan — Senior AI / LangGraph Engineer"
            body_lines = []
            for line in lines:
                if line.strip().lower().startswith("subject:") or line.strip().lower().startswith("onderwerp:"):
                    subject = line.strip()
                else:
                    body_lines.append(line)
            normalized["email"]["subject"] = subject
            normalized["email"]["body"] = "\n".join(body_lines).strip()
        elif isinstance(email_data, dict):
            normalized["email"]["subject"] = email_data.get("subject") or email_data.get("subject_line") or "Onderwerp: Vedat Sapan — Senior AI / LangGraph Engineer"
            normalized["email"]["body"] = email_data.get("body") or email_data.get("text") or email_data.get("content") or ""
            
        # 2. Normalize WhatsApp
        wa_data = draft.get("whatsapp") or draft.get("whatsapp_draft") or {}
        if isinstance(wa_data, str):
            normalized["whatsapp"]["body"] = wa_data.strip()
        elif isinstance(wa_data, dict):
            normalized["whatsapp"]["body"] = wa_data.get("body") or wa_data.get("text") or wa_data.get("content") or ""
            
        # 3. Extra metadata
        normalized["personalization_anchor"] = draft.get("personalization_anchor") or ""
        normalized["custom_workflow_concept"] = draft.get("custom_workflow_concept") or ""
        
        # Clean any placeholder text like [Your Name] or [Placeholder]
        # Replace placeholders with Vedat's details to prevent amateur emails!
        for key in ["subject", "body"]:
            val = normalized["email"][key]
            if isinstance(val, str):
                val = val.replace("[Your Name]", "Vedat Sapan").replace("[Candidate Name]", "Vedat Sapan")
                val = val.replace("[Your Contact Information]", "operator@example.com")
                val = val.replace("[Resume Link]", "https://cal.com/vedat-sapan")
                val = val.replace("[Attachment]", "")
                normalized["email"][key] = val
                
        val_wa = normalized["whatsapp"]["body"]
        if isinstance(val_wa, str):
            val_wa = val_wa.replace("[Your Name]", "Vedat Sapan").replace("[Candidate Name]", "Vedat Sapan")
            val_wa = val_wa.replace("[Resume Link]", "https://cal.com/vedat-sapan")
            normalized["whatsapp"]["body"] = val_wa
            
        return normalized

    def generate_highly_personalized_outreach(self, company_intel: Dict[str, Any], contact_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Executes the double-pass generator-critic pipeline.
        If critique scores are < 8.5 or verdict is REWRITE, it performs a refined rewrite pass.
        """
        # Pass 1: Generate initial draft
        raw_draft = self.generate_draft(company_intel, contact_data)
        draft = self.normalize_draft(raw_draft)
        
        # Pass 2: Critique initial draft
        critique = self.critique_draft(draft, company_intel, contact_data)
        
        # If critique requests a REWRITE, perform one refined rewrite pass
        if critique.get("verdict") == "REWRITE":
            feedback = critique.get("rewrite_instructions", {})
            refinement_prompt = f"""
            You are the Career Copywriter Agent. You write exclusively in professional Dutch business register.
            Your previous draft was audited and REJECTED by the reviewer with the following feedback:
            Email Feedback: {feedback.get('email', 'None')}
            WhatsApp Feedback: {feedback.get('whatsapp', 'None')}
            
            Original Input Data:
            {json.dumps(company_intel, indent=2)}
            
            Please rewrite the email and WhatsApp drafts to address these specific criticisms, adhering 100% to all formality, first-person narrative as Vedat Sapan, and legal status rules:
            - Write in professional, formal Dutch ("u" form only, no je/jij).
            - Do NOT use placeholders like [Your Name] or [Attachment]. Always sign off as 'Met vriendelijke groet, Vedat Sapan'.
            - Max 120 words for email, max 60 words for WhatsApp.
            - For BOTH EMAIL AND WHATSAPP: Do NOT mention visa, TWV, work permit, labor market test, IND, highly skilled migrant, or sponsorship at all! (Strict visa ban on first touch).
            - For BOTH EMAIL AND WHATSAPP: Enforce the "Meta-Automation Hook"—state that this introductory outreach (email and WhatsApp) was researched and dispatched by a stateful multi-agent system (V-Engine 3.0) built by Vedat himself using LangGraph and PostgreSQL, as a live demo of his workflow automation capabilities.
            - For BOTH EMAIL AND WHATSAPP: Use a brief, formal 10-minute introductory call (kennismakingsgesprek / telefonische afstemming) CTA via https://cal.com/vedat-sapan and link to his GitHub (https://github.com/your-username) to show his open-source code and AI engine. Avoid "coffee" references.
            
            Respond strictly with a JSON object in the exact same format:
            {{
              "email": {{
                "subject": "Onderwerp: ...",
                "body": "..."
              }},
              "whatsapp": {{
                "body": "..."
              }},
              "personalization_anchor": "...",
              "custom_workflow_concept": "..."
            }}
            """
            try:
                raw_refined = self._call_gemini_json(refinement_prompt)
                refined_draft = self.normalize_draft(raw_refined)
                refined_critique = self.critique_draft(refined_draft, company_intel, contact_data)
                return refined_draft, refined_critique
            except Exception:
                # If refinement fails, fall back to the original draft and critique
                return draft, critique
                
        return draft, critique

