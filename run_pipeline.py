import os
import sys
from dotenv import load_dotenv

# Ensure local directories are in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import compile_v_engine
from state import CompanyContext, CampaignStatus
from agents.copywriter import AIOutboundCopywriter
from telephony.vapi_client import dispatch_vapi_call
from telephony.email_client import send_outbound_email

# Load environment variables from .env
load_dotenv()

def run_local_v_engine_pipeline(company_name: str, company_domain: str):
    """
    Runs the V-Engine LangGraph workflow in sandbox mode with local CLI terminal
    acting as the Human-in-the-Loop (HITL) approval dashboard.
    """
    print("\n" + "="*60)
    print(f" INITIALIZING V-ENGINE CAMPAIGN FOR: {company_name.upper()}")
    print("="*60)
    
    # 1. Compile the graph with a local fallback checkpointer
    app, init_logs = compile_v_engine(use_postgres=False)
    for log in init_logs:
        print(f"[SYSTEM] {log}")
        
    # Configure thread configuration
    config = {"configurable": {"thread_id": f"campaign-{company_domain.replace('.', '-')}"}}
    
    # Define initial state with CompanyContext
    initial_company = CompanyContext(
        name=company_name,
        domain=company_domain,
        tech_stack=[],
        recent_news=[],
        inferred_bottlenecks=[],
        contact_name="CTO / IT Director",
        lang_pref="nl" if company_domain.endswith(".nl") else "en"
    )
    
    initial_state = {
        "thread_id": config["configurable"]["thread_id"],
        "current_status": CampaignStatus.DRAFT,
        "company": initial_company,
        "value_prop": None,
        "draft_email": None,
        "draft_voice_script": None,
        "call_id": None,
        "call_transcript": None,
        "calendar_slots": ["2026-06-02T10:00:00Z", "2026-06-02T14:00:00Z"],
        "vedat_feedback": None,
        "logs": []
    }
    
    print("\n[1/4] Running OSINT, Value Proposition and Copywriter Nodes...")
    
    # Stream the graph execution until the interrupt/approval node is reached
    events = app.stream(initial_state, config, stream_mode="values")
    final_state = None
    for event in events:
        final_state = event
        
    # Get current state from LangGraph history
    state = app.get_state(config)
    
    # Verify we are indeed interrupted at the approval node
    next_node = state.next
    print(f"\n[SYSTEM] State Machine paused. Next Node: {next_node}")
    
    current_values = state.values
    company_data = current_values.get("company")
    val_prop = current_values.get("value_prop")
    email = current_values.get("draft_email")
    voice_script = current_values.get("draft_voice_script")
    channel_strategy = current_values.get("channel_strategy")
    strategy_rationale = current_values.get("strategy_rationale")
    
    # Display the hyper-personalized OSINT & Value Proposition results
    print("\n" + "-"*40)
    print(" OSINT ANALYSIS & TECHNICAL VALUE PROPOSITION")
    print("-"*40)
    print(f"Company Tech Stack: {', '.join(company_data.tech_stack)}")
    print(f"Inferred Bottleneck: {company_data.inferred_bottlenecks[0] if company_data.inferred_bottlenecks else 'None'}")
    print(f"Proposed AI Solution: {val_prop.proposed_solution}")
    print(f"Estimated Monthly Savings: €{val_prop.estimated_eur_impact_per_month}")
    print(f"Sells Case (Why Vedat): {val_prop.why_vedat_uniquely}")
    print(f"Outreach Channel Strategy: {channel_strategy}")
    print(f"Strategy Rationale: {strategy_rationale}")
    
    # Display the crafted email & voice script drafts
    print("\n" + "-"*40)
    print(" DRAFT EMAIL OUTBOUND")
    print("-"*40)
    print(f"Subject: {email['subject']}")
    print(f"Body:\n{email['body']}")
    
    print("\n" + "-"*40)
    print(" DRAFT AI TELEPHONY VOICE SCRIPT")
    print("-"*40)
    print(f"Script: {voice_script}")
    print("-"*40 + "\n")
    
    # -------------------------------------------------------------
    # Human-In-The-Loop (HITL) Terminal Dashboard Interaction
    # -------------------------------------------------------------
    print("="*60)
    print(" HUMAN-IN-THE-LOOP (HITL) APPROVAL REQUIRED")
    print("="*60)
    print("[A] Approve email and voice assistant dispatch")
    print("[R] Reject and request copywriting rewrite")
    print("[Q] Quit campaign execution")
    print("="*60)
    
    user_choice = input("Select Action [A/R/Q]: ").strip().upper()
    
    if user_choice == "A":
        print("\n[SYSTEM] Outbound Campaign APPROVED. Discharging channels...")
        
        # Resume the state machine graph by passing the APPROVED status
        app.update_state(
            config,
            {"current_status": CampaignStatus.APPROVED, "logs": current_values.get("logs", []) + ["Principal manually approved the campaign."]}
        )
        
        # Resume execution
        for event in app.stream(None, config, stream_mode="values"):
            final_state = event
            
        print("\n[4/4] Campaign fully discharged! Outbox statuses logged in CRM.")
        print(f"Final Campaign State: {final_state.get('current_status')}")
        
    elif user_choice == "R":
        feedback = input("\nEnter feedback/corrections for the rewrite pass: ").strip()
        print("\n[SYSTEM] Campaign REJECTED. Routing back to copywriter with feedback...")
        
        # Resume graph with REJECTED status and feedback
        app.update_state(
            config,
            {
                "current_status": CampaignStatus.REJECTED, 
                "vedat_feedback": feedback,
                "logs": current_values.get("logs", []) + [f"Principal rejected the campaign. Feedback: {feedback}"]
            }
        )
        
        # Resume execution (will route back to copywriter and stop again at approval)
        for event in app.stream(None, config, stream_mode="values"):
            final_state = event
            
        print("\nRefined drafts successfully generated based on your feedback. Run the pipeline again to view.")
        
    else:
        print("\nCampaign paused in active memory. You can resume this thread at any time.")

if __name__ == "__main__":
    # Standard Sandbox test run
    # Let's target a high-profile IT company in our filtered list
    run_local_v_engine_pipeline(
        company_name="AND Digital Nederland B.V.",
        company_domain="and.digital"
    )
