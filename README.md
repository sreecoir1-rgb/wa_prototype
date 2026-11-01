# WhatsApp Broadcaster 📢

A simple, secure, and easy-to-use platform that helps small businesses broadcast **rate offers** and **referral campaigns** to opted-in customers via the **official Meta WhatsApp Business Cloud API**.

Built with **Python 3.12+**, **FastAPI**, **SQLite**, **SQLAlchemy 2.0**, and **Jinja2**.

---

## 🌟 Key Features & Compliance Safeguards

1. **Official WhatsApp Cloud API**: Built strictly on Meta's official Graph API (no personal account automation or unauthorized libraries).
2. **Mandatory Consent Filtering**: Only contacts explicitly marked `opted_in` can receive broadcasts. Contacts with `pending` or `opted_out` status are never targeted.
3. **Immediate STOP Opt-Outs**: Incoming webhook messages containing `"STOP"` immediately mark the sender as `opted_out`.
4. **Safe DRY_RUN Simulation**: Defaults to `DRY_RUN=true`. Simulate full broadcasts, preview audience sizes, and log records without sending live network calls.
5. **Webhook Security**: Authenticates incoming Meta webhook events via cryptographic `X-Hub-Signature-256` HMAC-SHA256 signatures and handles duplicate events idempotently.
6. **Privacy & PII Masking**: Customer phone numbers are masked in application logs (`+91******3210`) and authorization tokens are strictly hidden.
7. **Admin Dashboard**: Web interface for contacts management, CSV spreadsheet importing, live message previews, and campaign launches.

---

## 🏗️ Architecture & Folder Structure

```text
whatsapp-broadcaster/
├── AGENTS.md                  # Development principles & milestone roadmap
├── README.md                  # Documentation and quickstart guide
├── requirements.txt           # Project dependencies
├── .env.example               # Template environment configuration
├── .gitignore                 # Protected files (secrets, database, venv)
├── app/
│   ├── main.py                # FastAPI entry point & lifespan management
│   ├── config.py              # Pydantic settings loaded from .env
│   ├── database.py            # SQLite engine, sessions, and table initialization
│   ├── models.py              # SQLAlchemy database tables (Contact, Campaign, etc.)
│   ├── schemas.py             # Pydantic request/response validation schemas
│   ├── logging_config.py      # Structured logger with automated PII masking
│   ├── routes/
│   │   ├── contacts.py        # REST API endpoints for contacts & CSV imports
│   │   ├── campaigns.py       # REST API endpoints for templates & broadcasts
│   │   ├── webhook.py         # Meta verification and event ingestion
│   │   └── ui.py              # Admin web dashboard page routes
│   ├── services/
│   │   ├── auth_service.py    # Bcrypt password hashing & session authentication
│   │   ├── phone_utils.py     # E.164 international phone number normalization
│   │   ├── whatsapp_client.py # Meta Cloud API client with dry-run support
│   │   ├── campaign_sender.py # Broadcast dispatch engine with rate pacing & retries
│   │   └── webhook_service.py # Delivery status tracking & STOP opt-out handler
│   └── templates/             # Jinja2 HTML views (styled with Pico CSS)
│       ├── base.html          # Shared layout & navigation
│       ├── login.html         # Admin sign-in page
│       ├── contacts.html      # Contacts table with status badges & filters
│       ├── import_csv.html    # CSV bulk-import form
│       └── campaigns.html     # Broadcast studio, live preview & history
├── scripts/
│   └── send_test_message.py   # CLI tool to test WhatsApp template sends
└── tests/                     # 100% automated test suite using pytest
    ├── test_whatsapp_client.py
    ├── test_phone_utils.py
    ├── test_database.py
    ├── test_contacts_api.py
    ├── test_campaigns.py
    ├── test_webhook.py
    ├── test_ui.py
    └── test_logging.py
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- **Python 3.12+** installed on your system.
- **Git** installed.

### 2. Set Up Virtual Environment & Dependencies
```powershell
# Clone the repository
git clone <repository-url>
cd wa_prototype

# Create an isolated virtual environment
python -m venv .venv

# Activate the virtual environment
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy the example environment file:
```powershell
cp .env.example .env
```
*(By default, `.env` runs in `DRY_RUN=true` mode with safe placeholder credentials).*

### 4. Run the Automated Tests
Run the entire test suite:
```powershell
pytest -v
```
All **40 tests** covering phone validation, consent filtering, opt-outs, and webhook security should pass.

### 5. Start the Application
Start the Uvicorn web server:
```powershell
uvicorn app.main:app --reload
```
Once started, visit:
- **Admin Dashboard**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
  - **Default Username**: `admin`
  - **Default Password**: `admin123`
- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check Endpoint**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 🧪 Testing Broadcasts & CLI Script

### Safe Simulation (DRY RUN)
Test sending the pre-approved `hello_world` template without sending real HTTP calls:
```powershell
python scripts/send_test_message.py --phone "+919876543210"
```

### Live WhatsApp Sends
To send real messages to your phone:
1. Open the [Meta for Developers Portal](https://developers.facebook.com/) > Your App > WhatsApp > **API Setup**.
2. Add your personal WhatsApp phone number to **Manage phone number list** (Meta will send you a 6-digit verification code).
3. Copy your **Temporary Access Token** and **Phone Number ID**.
4. Update your local `.env`:
   ```env
   WHATSAPP_TOKEN=EAA...
   WHATSAPP_PHONE_NUMBER_ID=108...
   DRY_RUN=false
   ```
5. Run the script with your verified number:
   ```powershell
   python scripts/send_test_message.py --phone "+91XXXXXXXXXX"
   ```

---

## 🌐 Connecting Webhooks for Live Delivery & STOP Opt-Outs

When testing incoming messages and delivery receipts from Meta:

1. **Expose your server** using a secure tunnel:
   ```powershell
   ngrok http 8000
   ```
2. **Configure Meta Webhook**:
   - In Meta Developer Portal > WhatsApp > **Configuration**.
   - **Callback URL**: `https://<your-ngrok-subdomain>.ngrok-free.app/webhook`
   - **Verify Token**: Enter the value of `WEBHOOK_VERIFY_TOKEN` from your `.env`.
   - Click **Verify and Save**.
   - Under **Webhook fields**, click **Manage** and subscribe to **`messages`**.
3. **Test Opt-Out**: Reply `"STOP"` from WhatsApp to your test business number; your webhook endpoint will automatically mark the contact as `opted_out` in SQLite!

---

## 🔒 Security Best Practices
- **No Hardcoded Secrets**: Secrets are kept in `.env` and strictly excluded by `.gitignore`.
- **Masked Logging**: Customer phone numbers are masked in console and file logs.
- **CSRF & Session Security**: Admin sessions use cryptographically signed session cookies.
- **Timing-Attack Resistance**: Uses `hmac.compare_digest` for signature verification.

---

## 📄 License
This project is open-source under the MIT License.
