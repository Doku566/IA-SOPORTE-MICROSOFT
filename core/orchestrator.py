import time
import re
import hashlib
import secrets
from m365_api import get_access_token, fetch_unread_emails, send_email, handle_password_reset
from nlp_engine import classify_intent, get_kb_response

# Rate limiting: track requests per sender in memory (use SQLite in production)
_request_log = {}

RATE_LIMIT = 3        # Max requests per window
RATE_WINDOW = 300     # Window in seconds (5 minutes)
OTP_TTL = 600         # OTP expiry in seconds (10 minutes)

# Pending OTP verifications: {sender_email: {"otp_hash": str, "expires": float, "student_id": str}}
_pending_otps = {}


def is_student_email(email):
    """
    Verify the target account matches a student email pattern before any write operation.
    This is a software-level guard. See README for infrastructure-level alternative (Entra ID P1).
    Adapt the regex to match your institution's student ID format.
    """
    local = email.split("@")[0] if "@" in email else ""
    return bool(re.match(r"^\d{7,}", local) or re.match(r"^utm\d+", local, re.IGNORECASE))


def check_rate_limit(sender):
    """Returns True if sender is within allowed rate, False if blocked."""
    import time
    now = time.time()
    history = _request_log.get(sender, [])
    history = [t for t in history if now - t < RATE_WINDOW]
    if len(history) >= RATE_LIMIT:
        return False
    history.append(now)
    _request_log[sender] = history
    return True


def generate_otp(sender, student_id):
    """Generate a 6-digit OTP, store its SHA-256 hash, return the plaintext code."""
    import time
    code = str(secrets.randbelow(900000) + 100000)  # 6-digit
    otp_hash = hashlib.sha256(code.encode()).hexdigest()
    _pending_otps[sender] = {
        "otp_hash": otp_hash,
        "expires": time.time() + OTP_TTL,
        "student_id": student_id
    }
    return code


def verify_otp(sender, code_provided):
    """Returns student_id if OTP is valid and not expired, else None."""
    import time
    entry = _pending_otps.get(sender)
    if not entry:
        return None
    if time.time() > entry["expires"]:
        del _pending_otps[sender]
        return None
    if hashlib.sha256(code_provided.encode()).hexdigest() == entry["otp_hash"]:
        student_id = entry["student_id"]
        del _pending_otps[sender]
        return student_id
    return None


def process_emails():
    """Main orchestration loop."""
    print("Fetching OAuth token (Client Credentials flow)...")
    token = get_access_token()
    if not token:
        print("Fatal: Could not authenticate with Microsoft Graph.")
        return

    emails = fetch_unread_emails(token)
    for email in emails:
        sender = email["sender"]["emailAddress"]["address"]
        subject = email.get("subject", "")
        body = email.get("bodyPreview", "")

        print(f"Processing email from: {sender}")

        # 1. Anti-loop filter — drop auto-replies immediately
        auto_reply_patterns = ["automatic reply", "out of office", "ausencia",
                               "respuesta automatica", "fuera de la oficina"]
        if any(p in subject.lower() for p in auto_reply_patterns):
            print("Dropped: auto-reply detected.")
            continue

        # 2. Rate limiting
        if not check_rate_limit(sender):
            print(f"Rate limited: {sender}")
            continue

        # 3. OTP verification reply — check before calling the model
        otp_match = re.search(r'\b(\d{6})\b', body)
        if otp_match and sender in _pending_otps:
            student_id = verify_otp(sender, otp_match.group(1))
            if student_id:
                print(f"OTP verified for {sender} — escalating to admin for approval.")
                # In production: notify admin with student_id for manual approval
                # Admin replies "APPROVE [student_id]" to trigger the actual reset
            else:
                print("OTP invalid or expired.")
                # send_email(token, sender, "Verification failed", "Your code was invalid or expired.")
            continue

        # 4. Classify intent with local model
        classification = classify_intent(body)
        intent = classification.get("intencion")

        # 5. Route based on intent
        if intent == "PASSWORD_RESET":
            print("Intent: PASSWORD_RESET")
            student_id_match = re.search(r'\b([0-9]{7})\b', body)

            if "@" in sender and not sender.endswith(
                    "@" + __import__("os").getenv("INSTITUTIONAL_DOMAIN", "institucion.edu.mx")):
                # External domain — OTP flow required
                ref_id = student_id_match.group(1) if student_id_match else "unknown"
                otp_code = generate_otp(sender, ref_id)
                print(f"External sender — OTP generated, sending to {sender}")
                # send_email(token, sender, "Identity verification required",
                #     f"Your verification code is: {otp_code} (valid for 10 minutes).")
            else:
                # Institutional domain — direct reset
                if not student_id_match:
                    print("Escalating: no student ID found in institutional email.")
                    continue
                target = sender
                if not is_student_email(target):
                    print(f"SECURITY: Reset blocked — {target} is not a student account.")
                    # In production: alert admin here
                    continue
                print("Executing password reset via Graph API...")
                # new_pass = handle_password_reset(token, target)
                # send_email(token, sender, "Your temporary credentials", f"Password: {new_pass}")

        elif intent == "INFORMACION":
            print("Intent: INFORMACION — running RAG lookup")
            response_html = get_kb_response(body)
            # send_email(token, sender, "Support response", response_html)

        elif intent == "ANOMALIA":
            print("Intent: ANOMALIA — escalating to IT admin")
            # send_email(token, ADMIN_EMAIL, "Anomaly detected", f"From: {sender}\n\n{body}")

        elif intent == "IGNORAR":
            print("Discarding: spam or no action required.")


if __name__ == "__main__":
    print("Starting AI Support Engine...")
    while True:
        try:
            process_emails()
            time.sleep(30)  # Poll every 30 seconds
        except Exception as e:
            print(f"Unhandled error in main loop: {e}")
            time.sleep(60)  # Backoff on failure
