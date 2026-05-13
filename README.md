# AI Support Engine — Automated Technical Support for Microsoft 365 Environments

A Python-based orchestrator that automates Level 1 technical support tickets by integrating
Microsoft Graph API with a local language model. Built to reduce the operational load on
IT departments in educational institutions.

---

## Background

The IT support inbox at a mid-sized university was receiving dozens of daily password reset
requests and repetitive queries during enrollment periods. Staff were spending 3 to 4 hours
per day on those tasks alone, which left little room for infrastructure work or actual
problem-solving.

The system built here reads that inbox automatically, classifies each email using a local
language model, and handles the response or escalation without human intervention for
routine cases. It runs 24/7 and has cut Level 1 support load by roughly half since deployment.

---

## What This System Does and Does Not Do

Being upfront about scope matters, especially for anyone trying to adapt this for their
own environment.

**Handles automatically:**
- Reading unread emails from the support inbox via Microsoft Graph API
- Classifying email intent using a local AI model (no data leaves your server)
- Resetting passwords for student accounts and sending temporary credentials
- Answering general institutional queries using a curated knowledge base
- Logging every action to a local SQLite audit database

**Requires human approval or cannot do:**
- Password resets for staff, faculty, or admin accounts — blocked at the code level
- Requests from external email domains (Gmail, Hotmail) without OTP verification first
- Creating or deleting accounts, modifying licenses, or changing directory policies
- Anything that involves accessing mailboxes other than the designated support inbox

**On scope restriction at the infrastructure level:**

The system is designed to only touch student accounts. Any attempt to run write operations
on accounts outside that profile is rejected by the orchestrator itself.

For a proper infrastructure-level restriction (not just a software guard), you can create
an **Administrative Unit** in Microsoft Entra ID containing only student accounts and
assign the application's role with scope limited to that unit. This requires a
**Microsoft Entra ID Premium P1 or P2** license. Without that license, the software
restriction still works, but it does not have the backing of an API-level barrier from
Microsoft. The steps to complete this once you have the license are covered in the
security section below.

---

## Repository Structure

This is a reference template. The code published here reflects the real logic of the
system but contains no production configuration. Credentials, email addresses, domain
names, and any institution-specific values must be set through environment variables in
each deployment.

```
├── core/
│   ├── orchestrator.py      # Main loop: polling, filters, routing
│   ├── m365_api.py          # Microsoft Graph integration (OAuth 2.0)
│   └── nlp_engine.py        # Local inference connector (Ollama / Phi-3)
├── data/
│   ├── soporte_audit.db     # SQLite audit log and rate limit store
│   └── knowledge_base.txt   # Institutional knowledge corpus for RAG
├── config/
│   ├── .env.example         # Required environment variables (no real values)
│   └── security_rules.json  # Regex patterns for student ID validation
├── docs/
│   └── changelog.md
├── daemon_start.bat
├── requirements.txt
└── .gitignore
```

---

## Architecture Overview

Three components work together locally on the institution's server. The system only
connects to Microsoft's cloud to read the inbox and write to the directory — everything
else, including AI inference, stays on-premises.

**Authentication (Microsoft Graph — OAuth 2.0 Client Credentials)**

The system never uses a username and password. It authenticates using an App Registration
in Microsoft Entra ID with a client secret stored in OS-level environment variables.
The access token has a one-hour TTL and is renewed automatically each cycle.

**Local AI Inference (Ollama + Phi-3)**

Email content is processed entirely on the local server. Nothing is sent to external AI
providers. The Phi-3 model receives email text and returns a JSON classification object:
intent and a brief summary. Temperature is fixed at `0.05` to keep responses deterministic
and avoid the model adding unsolicited commentary.

**Audit and Rate Limiting (SQLite)**

Every processed email is recorded with sender, detected intent, and resolution status.
The same database enforces rate limiting: more than 3 requests from the same sender
within a 5-minute window triggers a silent block that prevents Graph API quota exhaustion.

**Knowledge Base Responses (RAG)**

For general information queries, the system injects the institution's knowledge base
into the model prompt and generates an HTML response. This works well at current scale.
As the knowledge base grows, migrating to a vector database (ChromaDB or FAISS) would
allow semantic retrieval instead of full-document injection.

---

## How It Works

**Main processing cycle (every 30 seconds):**

```
1. Refresh OAuth token if expired
2. Fetch unread emails from the support inbox
3. For each email:
   a. If subject matches auto-reply patterns → mark read, skip
   b. If sender exceeded rate limit → skip silently
   c. Strip email signatures and HTML noise
   d. Classify with local model
   e. Route to the appropriate handler
   f. Mark as read
```

**Password reset from an institutional email:**

The orchestrator verifies the sender matches the student account pattern, generates
a cryptographically random temporary password, calls the Graph API PATCH endpoint
with `forceChangePasswordNextSignIn: true`, and sends the credentials with Microsoft
Authenticator setup instructions.

**Password reset from an external email (Gmail, etc.):**

The system cannot verify identity from the email alone. The flow is:

1. Extract student ID from the email body using regex (reference only, not authorization)
2. Generate a 6-digit OTP with a 10-minute TTL — store the SHA-256 hash in SQLite
3. Send the OTP to the external email address
4. Notify the IT administrator about the pending request
5. Wait for the user to reply with the correct OTP
6. Once OTP validates, escalate to the administrator for final approval
7. Administrator replies with `APPROVE [STUDENT_ID]`
8. System executes the reset and notifies the external address

This flow prevents someone who knows a student's ID number from obtaining credentials
simply by sending a message from a throwaway email account.

---

## Security

**Authentication**

The client secret is stored in OS environment variables, never in source code or
tracked files. All operations executed through the App Registration are logged in
Microsoft Entra ID's audit trail.

**Student-only write guard**

Before any write operation, the orchestrator validates the target account against the
institutional student email pattern. If the check fails, the operation is cancelled and
an alert is sent to the IT administrator. This is a software control, not an
infrastructure restriction — its limitation is documented honestly below.

**Administrative Unit (partial implementation)**

An Administrative Unit containing all student accounts has been created in Microsoft
Entra ID. The intent is to assign the application's role with scope restricted to that
unit, making it architecturally impossible for the system to write to staff or admin
accounts regardless of what the code does.

This cannot be fully activated without a **Microsoft Entra ID Premium P1 or P2** license.
Without it, the unit exists but does not restrict the App Registration's permissions.
When that license becomes available, the only remaining step is assigning the
`Authentication Administrator` role to the application's service principal scoped to
that unit — a five-minute task in the Azure portal.

**MFA on the support mailbox**

The support account currently has only a password as its authentication method. The AI
does not use that password to operate (it uses Client Credentials), but the account
remains a potential attack vector for manual login. Registering Microsoft Authenticator
and enabling MFA enforced for interactive sessions is recommended before considering
this fully hardened.

---

## Problems We Hit During Development

These are the real issues encountered, documented for anyone building something similar.

**Auto-reply mail loops**

The system initially responded to Exchange auto-replies ("Out of Office"), which
triggered another auto-reply, which the bot processed again. The fix was evaluating
the email subject before invoking the model at all — if it matches patterns like
"automatic reply", "out of office", or "respuesta automática", the email is marked
read and dropped immediately.

**Graph API throttling (HTTP 429)**

During load testing, too many rapid calls to Graph API triggered `429 Too Many Requests`
responses from Microsoft. Keeping state in memory was not enough because restarting the
process lost all history. The fix was persisting each request with a timestamp in SQLite
and checking that log before processing. Senders who exceed 3 requests in 5 minutes are
silently blocked until the window resets.

**The model inventing answers**

Phi-3 has a tendency to complete information it doesn't have. Early versions would
respond to questions about exam dates or administrative fees with plausible but incorrect
data. The fix involved two things: dropping temperature to `0.05` to reduce creativity,
and adding an explicit instruction in the system prompt that requires the model to respond
with exactly "I don't have that specific information" when the answer isn't in the
knowledge base.

**Dirty email format breaking regex extraction**

The model was failing to extract student ID numbers from emails that contained complex
HTML signatures, embedded images, or CSS-heavy mobile client output. Useful content was
buried under formatting noise. The solution was removing that responsibility from the
model entirely. A regex applied to the plain text of the email extracts the ID
deterministically. The model only classifies intent.

---

## Pending Work and Roadmap

**Infrastructure (high priority)**

- Register Microsoft Authenticator on the support account and enable MFA for interactive
  sessions
- Once Entra ID P1 is available, assign the Administrative Unit scoped role to complete
  the infrastructure-level student account restriction

**Performance**

- Replace the 30-second polling cycle with Microsoft Graph Subscriptions (webhooks)
  to get near-real-time email processing
- Move inference to a server with a dedicated GPU or NPU to reduce per-email latency
  below one second

**Quality**

- Migrate the knowledge base from a plain text file to ChromaDB or FAISS for semantic
  retrieval
- Fine-tune the model on anonymized historical support tickets from the institution
- Integrate Azure AI Vision to automate credential validation for external requests,
  removing the need for manual administrator approval in those cases

---

## Configuration Reference

```env
TENANT_ID=[Entra ID tenant ID]
CLIENT_ID=[App Registration client ID]
CLIENT_SECRET=[Client secret]
OLLAMA_URL=http://[server-ip]:[port]/api/generate
SUPPORT_EMAIL=[Support inbox address]
ADMIN_EMAIL=[IT administrator email for escalations]
```

**Starting the service:**

```bash
# Activate the virtual environment
source venv/bin/activate     # Linux/Mac
venv\Scripts\activate        # Windows

python database.py           # Initialize database (first run only)
python -u orchestrator.py    # Start the orchestrator
```

---

## License

This project is published as a reference implementation. You are free to adapt it for
your institution. No production data, credentials, or institution-specific configuration
is included in this repository.
