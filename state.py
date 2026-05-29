from typing import TypedDict, List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum

class CampaignStatus(str, Enum):
    DRAFT = "DRAFT"
    OSINT_COMPLETED = "OSINT_COMPLETED"
    VALUE_PROP_GENERATED = "VALUE_PROP_GENERATED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    APPROVED = "APPROVED"
    EMAIL_SENT = "EMAIL_SENT"
    WHATSAPP_SENT = "WHATSAPP_SENT"
    VOICE_DIALING = "VOICE_DIALING"
    VOICE_COMPLETED = "VOICE_COMPLETED"
    REJECTED = "REJECTED"
    BOOKED = "BOOKED"

class ChannelStrategy(str, Enum):
    EMAIL_ONLY = "EMAIL_ONLY"
    WHATSAPP_ONLY = "WHATSAPP_ONLY"
    CALL_ONLY = "CALL_ONLY"
    COMBINED_EMAIL_WHATSAPP = "COMBINED_EMAIL_WHATSAPP"
    COMBINED_ALL = "COMBINED_ALL"

class CompanyContext(BaseModel):
    name: str = Field(description="Name of the company")
    domain: str = Field(description="Web domain of the company")
    tech_stack: List[str] = Field(default=[], description="Detected frontend, backend, and cloud stacks")
    recent_news: List[str] = Field(default=[], description="Recent B2B news signals or company blog updates")
    open_positions: List[str] = Field(default=[], description="Open roles currently listed on their career page")
    inferred_bottlenecks: List[str] = Field(default=[], description="Identified manual friction points or technical bottlenecks")
    contact_name: Optional[str] = Field(None, description="Name of the technical decision-maker (e.g. CTO/IT Director)")
    contact_email: Optional[str] = Field(None, description="Direct business email of the contact")
    contact_phone: Optional[str] = Field(None, description="Public listed landline or direct B2B number")
    lang_pref: str = Field(default="en", description="Preferred language (nl/en) based on domain/LinkedIn data")

class ValueProposition(BaseModel):
    pain_observation: str = Field(description="Specific, factual pain point observed in the company's tech/operations")
    proposed_solution: str = Field(description="Concrete, high-ROI AI/Data systems automation solution")
    technical_approach: str = Field(description="Underlying tech stack/architecture (e.g. LangGraph orchestration, Twilio voice, vector DB)")
    estimated_eur_impact_per_month: float = Field(description="Estimated monthly financial savings in Euros")
    confidence_score: float = Field(description="Confidence rating of the proposed value case from 0.0 to 1.0")
    why_vedat_uniquely: str = Field(description="Why Vedat's specific portfolio matches this exact solution")

class VEngineState(TypedDict):
    thread_id: str
    current_status: CampaignStatus
    company: CompanyContext
    value_prop: Optional[ValueProposition]
    channel_strategy: Optional[ChannelStrategy]
    strategy_rationale: Optional[str]
    draft_email: Optional[Dict[str, Any]]  # {"subject": str, "body": str}
    draft_voice_script: Optional[str]
    call_id: Optional[str]
    call_transcript: Optional[str]
    calendar_slots: List[str]
    vedat_feedback: Optional[str]
    logs: List[str]
