# V-Engine: Autonomous Multi-Agent B2B Outreach & CRM Pipeline

V-Engine is a production-grade, stateful autonomous customer acquisition and talent marketing engine built with **LangGraph**, **PostgreSQL**, **Twilio**, and the **Gemini API**. It automates target research, copy generation, compliance review, dynamic call script synthesis, and multi-channel outreach dispatch with zero human intervention.

Designed to be run as an autonomous daemon, V-Engine evaluates business databases, scrapes company OSINT profiles, conducts multi-pass copy writing with self-correction, queues messages based on local timezone business hours, and categorizes incoming replies.

---

## 🏗️ Architecture & Flow

V-Engine models B2B campaign pipelines as a stateful, directed graph utilizing **LangGraph**:

```mermaid
graph TD
    A[Company Finder / CSV Scraper] --> B[State Initialization]
    B --> C[Career Copywriter Agent]
    C --> D[QA Compliance Reviewer]
    D -- "Fails Validation" --> C
    D -- "Passes Validation" --> E[Voice Call Workflow Generator]
    E --> F[PostgreSQL Draft Queue]
    F --> G[Telegram Operator Approval Card]
    G -- "Approve" --> H[Multi-Channel Dispatcher]
    H --> I[Gmail SMTP with PDF Attachments]
    H --> J[Puppeteer WhatsApp Client]
    H --> K[Puck Voice Call Daemon]
    L[WhatsApp / Email Incoming Listener] --> M[Reply Classifier & Responder]
```

---

## 🌟 Core Technical Highlights

### 1. Stateful Multi-Agent Orchestration (LangGraph)
*   Routes the flow between creative copywriters, strict QA compliance critics, and technical telephony planners.
*   Retains execution memory across states so agents can inspect critique logs and iteratively refine drafts.

### 2. Multi-Channel Outreach Dispatch
*   **Email:** Custom SMTP engine sending multipart emails with PDF attachments.
*   **WhatsApp:** Integrates with Puppeteer to control a local WhatsApp Web session for B2B communications.
*   **Voice Calls:** Synthesizes structured IVR workflows for Twilio voice nodes using real-time Voice Activity Detection (VAD) handlers.

### 3. Smart Timezone-Aware Queue Scheduler
*   Outreach is filtered through an Amsterdam business-hours scheduler. If approved outside quiet hours, campaigns are put in a `QUEUED` state and automatically dispatched by background threads when the business window opens.

### 4. High-Integrity Compliance Hard-Gates
*   **Strict Length Limits:** Email body capped at 120 words; WhatsApp capped at 60 words.
*   **Tone Compliance:** Auto-rejects aggressive pitches, visa/sponsorship mentions, or overly bold claims.
*   **Tone Refinements:** Ensures respectful, professional, and understated Dutch business communications.

---

## 🛠️ Tech Stack

*   **Core Orchestrator:** Python 3.11, LangGraph, LangChain, asyncio
*   **Database:** PostgreSQL 15 (Dockerised) for robust B2B lead caching and campaign telemetry
*   **Telephony & Messaging:** Twilio Voice, Puppeteer Web Client, custom SMTP
*   **Operator Dashboard:** Telegram Bot API
*   **LLM Engine:** Gemini API (using Gemini 1.5 Pro & Flash)

---

## 🚀 Getting Started

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your-gemini-key
TELEGRAM_BOT_TOKEN=your-telegram-token
TELEGRAM_CHAT_ID=your-chat-id
DATABASE_URL=postgresql://user:pass@localhost:5432/db
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-email-app-password
```

### 3. Run Database Migrations
Initialize the PostgreSQL schema:
```bash
python3 scratch/migrate_vengine_3_0.py
```

### 4. Start the Autonomous Pipeline
Run the background pipeline orchestrator:
```bash
python3 run_pipeline.py
```

---

## 🛡️ Privacy & Security

*   Credentials and API tokens must always live in `.env` and are strictly excluded from git tracking.
*   V-Engine includes strict GDPR safeguards: contact data is synchronized locally and is processed strictly inside memory spaces.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
