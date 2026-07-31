# Real Estate Lead Automation

Full-stack MVP for real estate lead validation, scoring, assignment, and email follow-up.

## Stack

- Backend: FastAPI, SQLite, Python services
- Frontend: Next.js App Router
- Uploads: fixed-format CSV or Excel
- Email: SMTP
- Phone validation: Twilio Lookup
- Email validation: external deliverability API
- AI email writing: OpenRouter chat completions API

## MVP Features

- Fixed-format CSV/XLSX lead upload
- Email and phone validation
- Duplicate check by email or phone
- Valid, Invalid, and Duplicate lead status with validation remarks
- Rule-based lead score and Hot/Warm/Cold category
- High-priority filtered view for valid Hot leads
- Hot lead assignment to active agents
- Email template library
- OpenRouter AI email draft generation from old templates/data
- Review/edit email draft before sending
- SMTP test email, reviewed email sending, and sent-status tracking
- Demo mode with seeded agents, old email templates, sample leads, and simulated sending when SMTP is not configured
- Follow-up queue with due-processing endpoint
- Manual mark-as-replied flow that stops automation
- Dashboard, leads, upload, agents, templates, follow-ups, and settings UI

## Required Upload Columns

Use these exact headers in the first row:

```text
name
email
phone
source
property_type
configuration
location_preference
budget
timeline
message
```

See `docs/sample_leads.csv` for an example.

## Demo Mode

`DEMO_MODE=true` is enabled by default for local MVP testing.

In demo mode:

- Missing email validation API credentials fall back to simple email format validation.
- Missing Twilio credentials fall back to simple phone length validation.
- Missing SMTP credentials capture the reviewed email and mark it as sent instead of sending a real email.
- Missing OpenRouter credentials use the local demo email writer instead of a real AI call.
- Startup seeds dummy agents and old email templates with reply/conversion rates.
- Sample CSV files in `docs/` can be uploaded to test valid, duplicate, and invalid leads.

Set `DEMO_MODE=false` and configure real API/SMTP credentials when you want external validation and real email delivery.

## OpenRouter Email Writer

The backend generates email drafts through OpenRouter when `OPENROUTER_API_KEY` is configured.

OpenRouter is called from the FastAPI backend only. Do not put the key in the frontend or any `NEXT_PUBLIC_*` variable.

```env
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=~openai/gpt-latest
OPENROUTER_SITE_URL=http://127.0.0.1:3000
OPENROUTER_APP_NAME=Real Estate Lead Automation
```

The AI prompt uses:

- Lead details and score category
- Selected old template ranked by reply/conversion rate
- Dummy inventory context for the MVP
- A fixed mail-writing prompt

If the OpenRouter key is missing or the API call fails, the app falls back to the local demo writer so the workflow still works.

## Backend Setup

```bash
pip install -r requirements.txt
copy .env.example .env
uvicorn src.app.main:app --reload
```

Backend runs at:

```text
http://127.0.0.1:8000
```

## Frontend Setup

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

Frontend runs at:

```text
http://127.0.0.1:3000
```

## Environment Variables

```env
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
EMAIL_VALIDATOR_API_KEY=your_email_validator_key
DEMO_MODE=true
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=~openai/gpt-latest
OPENROUTER_SITE_URL=http://127.0.0.1:3000
OPENROUTER_APP_NAME=Real Estate Lead Automation
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@domain.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=your_email@domain.com
SMTP_FROM_NAME=Real Estate Sales Team
SMTP_USE_TLS=true
DATA_DIR=data
DATABASE_PATH=data/lead_automation.sqlite3
```

For Gmail SMTP, use a Gmail App Password.

## Main Backend APIs

- `GET /api/v1/leads/dashboard`
- `POST /api/v1/leads/upload-leads`
- `GET /api/v1/leads`
- `GET /api/v1/leads/high-priority`
- `GET /api/v1/leads/{lead_id}`
- `POST /api/v1/leads/{lead_id}/generate-email`
- `POST /api/v1/leads/{lead_id}/email-draft`
- `POST /api/v1/leads/{lead_id}/send-email-draft`
- `POST /api/v1/leads/{lead_id}/duplicates/replace`
- `POST /api/v1/leads/{lead_id}/duplicates/skip`
- `POST /api/v1/leads/{lead_id}/send-followup`
- `POST /api/v1/leads/{lead_id}/mark-replied`
- `GET /api/v1/leads/followups/queue`
- `POST /api/v1/leads/followups/process-due`
- `GET /api/v1/leads/agents/list`
- `POST /api/v1/leads/agents`
- `GET /api/v1/leads/templates/list`
- `POST /api/v1/leads/templates`
- `POST /api/v1/leads/demo/load`
- `POST /api/v1/leads/send-test-email`

## Project Structure

```text
src/
  app/
    api/endpoints/
    core/
    db/
    models/
    services/
frontend/
  app/
  lib/
docs/
  sample_leads.csv
```
