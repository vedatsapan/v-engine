---
name: v-engine-campaign
description: >-
  Autonomous multi-channel B2B career acquisition, CRM database sync, copywriter-critic quality loops, self-healing message dispatching, and Twilio-Gemini Voice AI telephony workflows for Vedat Sapan (Blives).
---

# 🚀 V-Engine Campaign & Talent Acquisition Skill

## Overview
This skill encapsulates the entire autonomous CRM execution, OSINT target enrichment, copywriter quality assurance, multi-channel messaging (WhatsApp & Email), and real-time interactive telephony calling pipeline designed for **Vedat Sapan (Founder @ Blives)**. 

It provides an end-to-end framework to discover high-value targets, personalize outbound campaigns in formal Dutch, bypass security sandboxes, and automatically track and log outreach statuses in a PostgreSQL CRM store.

---

## 🛠️ System Architecture

The pipeline consists of four major operational layers:
1.  **OSINT Target enrichment (Gemini Flash):** Selects targets from the official IND recognized sponsors dataset, infers operational database/IT bottlenecks, identifies CTO/Head of Engineering stakeholders, and generates corporate contact info.
2.  **Multi-Pass Critic copywriter (Gemini Pro/Flash):** Drafts a candidate introduction in first-person formal Dutch. Uses a double-pass review loop to audit compliance with:
    *   Strict u-form register (no "je/jij").
    *   No English marketing buzzwords ("game-changer", "revolutionair").
    *   Zero flattery policy (suspect to Dutch corporate contacts).
    *   No visa/sponsorship mentions (strict visa ban on first touch).
    *   High impact Meta-Automation Hook (explaining that this email/WhatsApp was researched and dispatched by a stateful multi-agent LangGraph system built by Vedat himself, serving as an active demo).
3.  **Self-Healing messaging daemons (Puppeteer & Node.js):** Launches a dynamic WhatsApp listener on port 5001. If the port is down, the system checks sockets and auto-respawns `node whatsapp_listener.js` programmatically to prevent Puppeteer lockouts.
4.  **Interactive voice AI Telephony (Twilio & Gemini Live API):** Streams audio via WebSockets, handles voice activity detection (VAD) to immediately pause audio when the call recipient interrupts, and polls completed calls from the PostgreSQL backend to auto-translate and send summaries & recording links to Telegram.

---

## 📂 Codebase Inventory

All files are located in the active workspace `/Users/vedat/Desktop/Ai Agent/`:
*   `scratch/generate_dossiers.py`: Batch OSINT scanner, DB registrar, and dossier compiler.
*   `agents/copywriter.py`: Twin-pass copywriter-critic loop with strict stylometric audits.
*   `scratch/generate_cv.py`: reportlab-based high-density PDF CV compilation script.
*   `telephony/telegram_bot.py`: Telegram HITL gateway bot, background telephony poller, and listener daemon.
*   `telephony/whatsapp_listener.js`: Puppeteer client API serving at `http://localhost:5001`.
*   `v_engine.db` / PostgreSQL: Campaign data schemas.

---

## 📋 Campaign Dossier Structure

For each target company scanned, a structured B2B dossier directory is compiled under `missions/<company_name>_<domain>/` containing:
1.  `intel.json`: Tech stack, employee band, HQ location, specific inferred bottleneck, proposed technical solution, and contact manager details.
2.  `draft_email.txt`: The precise personalized Dutch cold email including the meta-automation hook, GitHub profile (`https://github.com/your-username`), and Cal.com schedule link.
3.  `draft_wa.txt`: The corresponding WhatsApp message body.
4.  `status.json`: Live state tracker (e.g. `scanned: true`, `email_sent: false`, `wa_sent: false`, `call_made: false`) and a complete chronological event log.

---

## 🚀 Quick Start & Execution

### 1. Run the OSINT Scanner & Build Dossiers
To scan IND sponsors, enrich 30+ targets, register them as `PENDING_APPROVAL` in PostgreSQL, and build local `missions/` dossiers:
```bash
/Users/vedat/.gemini/antigravity/scratch/v_engine/venv/bin/python3 scratch/generate_dossiers.py
```

### 2. Verify WhatsApp Daemon Status
Ensure the self-healing Puppeteer HTTP listener is active on port 5001:
```bash
node telephony/whatsapp_listener.js
```

### 3. Launch the Telegram HITL Bot & Telephony Poller
Launch the bot to enable Telegram approval card callbacks and run the real-time call transcript translator & MinIO audio linker:
```bash
/Users/vedat/.gemini/antigravity/scratch/v_engine/venv/bin/python3 telephony/telegram_bot.py
```

---

## ⚠️ Common Pitfalls

1.  **Visa Mentions:** Never include TWV, visa, work permit, salary criteria, or sponsorship keywords in first-touch copy. The copywriter critic will reject the draft instantly.
2.  **Port Conflicts:** Port 8000 is reserved for the local `Dograh` outbound telephony API, and port 5001 is reserved for the WhatsApp Puppeteer API. Do not bind other services to these ports.
3.  **Cal.com Avatars:** Make sure any avatar edits use public URLs (like the public Catbox cdn: `https://files.catbox.moe/ydy1l7.png`) to bypass authentication tokens on external calendar forms.
