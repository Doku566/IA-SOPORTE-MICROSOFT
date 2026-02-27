import secrets
import string
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.models.ticket import Ticket

class OTPService:
    @staticmethod
    def generate_otp(length: int = 6) -> str:
        return ''.join(secrets.choice(string.digits) for _ in range(length))

    @staticmethod
    def hash_otp(otp: str) -> str:
        return hashlib.sha256(otp.encode()).hexdigest()

    @staticmethod
    def verify_otp(input_otp: str, stored_hash: str) -> bool:
        return OTPService.hash_otp(input_otp) == stored_hash

    @staticmethod
    def create_otp_for_ticket(db: Session, ticket_id: str) -> str:
        otp = OTPService.generate_otp()
        otp_hash = OTPService.hash_otp(otp)
        
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if ticket:
            ticket.otp_hash = otp_hash
            ticket.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
            db.commit()
            return otp
        return None

    @staticmethod
    def validate_ticket_otp(db: Session, ticket_id: str, input_otp: str) -> bool:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket or not ticket.otp_hash or not ticket.otp_expiry:
            return False
            
        if datetime.utcnow() > ticket.otp_expiry:
            return False
            
        return OTPService.verify_otp(input_otp, ticket.otp_hash)
