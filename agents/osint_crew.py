import os
from typing import Dict, Any, List
from crewai import Agent, Task, Crew, Process
from pydantic import BaseModel, Field

# Ensure Pydantic model for structured output matching our CompanyContext
class OSINTOutput(BaseModel):
    tech_stack: List[str] = Field(description="List of detected technologies (frontend, backend, cloud, SaaS)")
    recent_news: List[str] = Field(description="Bullet points of recent company news, milestones, or blog posts")
    inferred_bottlenecks: List[str] = Field(description="Inferred manual operations or engineering friction points")
    contact_name: str = Field(description="Identified or suggested technical decision-maker name (CTO, VP, IT Director)")
    contact_email: str = Field(description="Identified or formatted direct email of the technical contact")

def get_osint_crew(company_name: str, company_domain: str) -> Crew:
    """
    Creates and configures the CrewAI OSINT crew to research the target company.
    """
    # -------------------------------------------------------------
    # Agents Definition
    # -------------------------------------------------------------
    
    # 1. Tech Stack Researcher
    tech_researcher = Agent(
        role="Senior Technology Archaeologist",
        goal=f"Identify the complete technical infrastructure of {company_name} ({company_domain})",
        backstory=(
            "You are an expert systems auditor. You analyze public developer footprints, "
            "careers pages, GitHub repositories, and package configurations to discover "
            "exactly what database, cloud, and programming technologies a company uses."
        ),
        verbose=True,
        allow_delegation=False
    )
    
    # 2. News Signal Analyst
    news_analyst = Agent(
        role="B2B Business Intelligence Lead",
        goal=f"Discover recent news, funding rounds, partnerships, and announcements for {company_name}",
        backstory=(
            "You are a master corporate researcher. You sift through press releases, news articles, "
            "and company blog RSS feeds to identify what is top-of-mind for the executive leadership."
        ),
        verbose=True,
        allow_delegation=False
    )
    
    # 3. Operations Bottleneck Synthesizer
    bottleneck_synthesizer = Agent(
        role="Corporate Optimization Architect & Headhunter",
        goal=(
            f"Identify the manual, expensive overhead bottlenecks at {company_name} and find the "
            "appropriate CTO/IT Director to contact."
        ),
        backstory=(
            "You are a brilliant consultant. You look at open job listings (e.g. hiring many customer care agents, "
            "data entry specialists, manual testers) and infer exactly where the company is wasting money. "
            "You also identify the most logical technical leader (CTO, Head of Data, or IT Director) to contact."
        ),
        verbose=True,
        allow_delegation=False
    )

    # -------------------------------------------------------------
    # Tasks Definition
    # -------------------------------------------------------------
    
    # Task 1: Research Tech Stack
    task_tech_stack = Task(
        description=(
            f"Examine {company_domain} and its public developer footprint. "
            "Identify the frontend framework (e.g., React, Vue), backend (e.g., Node.js, Python), "
            "cloud infrastructure (e.g., AWS, Azure, GCP), and any SaaS databases used."
        ),
        expected_output="A structured markdown list of all identified software, cloud, and library tools.",
        agent=tech_researcher
    )
    
    # Task 2: Analyze Business Signals
    task_news = Task(
        description=(
            f"Search for recent announcements, blog updates, or news regarding {company_name} from the last 90 days. "
            "Focus on scaling challenges, new product releases, or regional expansions."
        ),
        expected_output="Bullet points of the most relevant B2B business signals.",
        agent=news_analyst
    )
    
    # Task 3: Synthesize Bottlenecks & Contact Info
    task_synthesize = Task(
        description=(
            f"Synthesize the tech stack findings and business signals for {company_name} ({company_domain}). "
            "Infer at least two manual bottlenecks that could be automated using AI Agents (e.g., voice, WhatsApp, custom LLM flows). "
            "Locate or generate a likely technical contact (e.g., 'Head of Engineering' or CTO name) and standard B2B email structure."
        ),
        expected_output="A structured output mapping pain points, proposed automation focus, and the decision-maker contact details.",
        agent=bottleneck_synthesizer,
        output_json=OSINTOutput
    )

    # -------------------------------------------------------------
    # Crew Compilation
    # -------------------------------------------------------------
    
    crew = Crew(
        agents=[tech_researcher, news_analyst, bottleneck_synthesizer],
        tasks=[task_tech_stack, task_news, task_synthesize],
        process=Process.sequential,
        verbose=True
    )
    
    return crew
