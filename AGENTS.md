# Project: WhatsApp Broadcaster

A simple, easy-to-use platform that helps a small business broadcast **current rate offers** and **referral offers** to opted-in customers and leads via the **official WhatsApp Business Cloud API**.

---

## 1. About the developer (read this first)

- I am a **first-year computer science student** and a **beginner** at building real applications.
- I want to **learn** how enterprise applications are built, not just get working code.
- Therefore, for every task:
  - **Plan first.** Before writing code, show a short plan (files to create/change, and why) and wait for my approval.
  - **Make small changes.** One milestone at a time, ideally under ~150 lines per step.
  - **Explain as you go.** After each change, explain what the code does and why this approach was chosen, in plain language.
  - **Teach the concept.** If a new concept appears (ORM, webhook, migration, hashing), explain it in 2-3 sentences with an analogy.
  - **Leave small pieces for me** (a validation function, a test) when I ask to try something myself, then review my attempt.
  - Tell me how to **run and verify** each change (exact commands).

## 2. Hard rules (never break these)

1. **Official WhatsApp Cloud API only.** Never use unofficial libraries or automation of a personal WhatsApp account (whatsapp-web.js, Selenium, etc.). They violate WhatsApp's terms and get numbers banned.
2. **Never hardcode secrets.** Tokens, passwords, and keys go in `.env` (git-ignored). Keep a `.env.example` with fake values.
3. **Consent is mandatory.** Only message contacts with `consent_status = opted_in`. Always store when and how consent was given.
4. **Honor opt-outs immediately.** An incoming "STOP" must mark the contact opted-out, and opted-out contacts are never messaged.
5. **Broadcasts use pre-approved templates** (outside the 24-hour customer-service window).
6. **Dry-run before real sends.** Any send logic must support a dry-run that only prints who would receive what.
7. **Use fake data** in development, tests, and prompts. Never put real customer data or real tokens in code, logs, or chat.
8. **Test the risky logic:** consent filtering and opt-out handling must have automated tests.
9. **Commit often** with clear messages; one logical change per commit.

## 3. Tech stack

| Layer | Choice (Phase 1) | Later (Phase 2+) |
|---|---|---|
| Language | Python 3.12+ | same |
| Backend | FastAPI | same |
| Database | SQLite | PostgreSQL |
| ORM | SQLAlchemy 2.x | + Alembic migrations |
| UI | Jinja2 templates (+ optional HTMX) | same, or a JS frontend later |
| HTTP client | httpx | same |
| Tests | pytest | + CI on GitHub Actions |
| Tunnel for webhooks | ngrok or Cloudflare Tunnel | real HTTPS domain |
| Deploy | laptop | Docker + Render/Railway/AWS |

## 4. Target folder structure

```
whatsapp-broadcaster/
  AGENTS.md            <- this file
  README.md
  .env                 <- secrets (never commit)
  .env.example
  .gitignore
  requirements.txt
  app/
    main.py            <- FastAPI app entry
    config.py          <- loads settings from .env
    database.py        <- DB engine/session
    models.py          <- SQLAlchemy tables
    schemas.py         <- Pydantic validation models
    routes/            <- API + page routes (contacts, campaigns, webhook, auth)
    services/          <- business logic (whatsapp_client.py, campaign_sender.py)
    templates/         <- Jinja2 HTML pages
  tests/
  scripts/
```

Principle: **routes** handle HTTP, **services** hold business logic, **models** describe data. Keep them separate.

## 5. Data model (starting point)

- `contacts`: id, name, phone (E.164, e.g. +91XXXXXXXXXX), consent_status (opted_in / opted_out / pending), consent_date, consent_source, tags, created_at
- `templates`: id, name (must match the name approved in Meta), language, body_preview, variables
- `campaigns`: id, template_id, audience_filter, status (draft / sending / done), scheduled_at, created_at
- `messages_log`: id, campaign_id, contact_id, whatsapp_message_id, status (sent / delivered / read / failed), error, timestamp

## 6. Environment variables (`.env.example`)

```
WHATSAPP_TOKEN=your_test_token_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id_here
WHATSAPP_BUSINESS_ACCOUNT_ID=your_waba_id_here
WEBHOOK_VERIFY_TOKEN=choose_any_random_string
APP_SECRET=your_meta_app_secret_here
SECRET_KEY=generate_a_long_random_string
DATABASE_URL=sqlite:///./app.db
DRY_RUN=true
```

## 7. Roadmap: Phase 1 (run on my laptop)

Work one milestone at a time. Mark done with [x] when it works and is committed.

- [x] **M0 Setup:** project folder, virtual environment, git repo, `.gitignore` (includes `.env`, `.venv`, `*.db`), `requirements.txt`, `.env.example`, minimal FastAPI app with a `/health` endpoint.
- [x] **M1 Hello WhatsApp:** `whatsapp_client.py` that sends one template message to my own verified test number via the Cloud API. *Learn: REST APIs, env vars, secrets.*
- [x] **M2 Contacts database:** SQLAlchemy models for `contacts` and `messages_log`; phone normalization to E.164. *Learn: data modeling, CRUD.*
- [x] **M3 Backend API:** endpoints to add/list/edit contacts, import CSV, mark opted-out; Pydantic validation; test via `/docs`. *Learn: API design, validation.*
- [x] **M4 Templates and campaigns:** `templates` and `campaigns` tables; sender service that selects only opted-in contacts, sends, and logs each result; dry-run mode; basic rate limiting and retry. *Learn: business logic, separation of concerns.*
- [ ] **M5 Webhooks:** endpoint for Meta verification + delivery status + incoming replies; verify the `X-Hub-Signature-256` signature; STOP handling; idempotent processing of duplicate events; expose via ngrok/Cloudflare Tunnel. *Learn: event-driven design, webhook security.*
- [ ] **M6 Admin UI:** login (single admin, hashed password, session cookie); pages to view contacts, import CSV, edit today's rate, preview the message, and send a campaign (with a confirmation step). *Learn: sessions, hashing, server-rendered UI.*
- [ ] **M7 Quality:** pytest tests (consent filtering, opt-out, phone validation, webhook signature), structured logging, a clear README so anyone can run the project.

**Phase 1 is done when:** I can import contacts, edit a rate, send a campaign to my test numbers, see delivery statuses, and opt out by replying STOP.

## 8. Roadmap: Phase 2 (secure cloud deployment)

- [ ] Dockerfile and docker-compose (app + PostgreSQL)
- [ ] Switch to PostgreSQL; add Alembic migrations
- [ ] Choose host (Render/Railway for learning; AWS/Azure/GCP Mumbai or Hyderabad for enterprise-style)
- [ ] HTTPS only; secrets in the platform's secret manager
- [ ] Least-privilege DB user, private DB network, automated backups
- [ ] GitHub Actions: run tests on push, deploy on merge to `main`
- [ ] Meta Business Verification; register the real business number; point webhook to production URL
- [ ] Pilot with a few real, opted-in customers
- [ ] Monitoring: Sentry, uptime checks, searchable logs

## 9. Roadmap: Phase 3 (toward enterprise grade)

- [ ] Background job queue (Celery + Redis) for large broadcasts
- [ ] Roles/permissions (admin vs staff) and an audit log
- [ ] Segmentation, scheduling, A/B testing offers
- [ ] Referral tracking with unique codes and conversion reporting
- [ ] Compliance: consent export, data deletion requests, retention policy (India DPDP Act)
- [ ] Staging environment, infrastructure-as-code (Terraform), alerting
- [ ] Analytics dashboard: delivery rate, replies, referral conversions

## 10. Coding conventions

- Type hints on all functions; short docstrings explaining *why*, not just *what*.
- Clear names; no single-letter variables except loop counters.
- Handle errors explicitly (e.g. failed API calls); never swallow exceptions silently.
- Never log tokens, full phone numbers, or message contents at INFO level; mask phone numbers in logs (e.g. +91******1234).
- Keep functions small and single-purpose.

## 11. WhatsApp platform notes

- Free-form messages only work within 24 hours of the customer's last message; everything else needs an approved template.
- Template categories matter (marketing vs utility); marketing messages are billed per message. Check Meta's current docs for pricing and categories.
- The test number allows messaging only up to 5 verified recipient numbers; fine for all of Phase 1.
- Docs: https://developers.facebook.com/docs/whatsapp/cloud-api

---

## 12. First prompt to give the AI agent

Copy this into Antigravity's agent panel to begin:

> Read AGENTS.md fully. I'm a beginner, so follow its rules. Start with **Milestone M0** only. First give me a plan (files, commands, and why), and wait for my approval before creating anything. After I approve, build it in small steps, explain each file in plain language, and tell me exactly how to run and verify it. Do not start M1 until I say so.
