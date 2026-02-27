import re
from sqlalchemy.orm import Session
from app.models.ticket import Ticket
from app.models.student import Student
from app.services.email_service import EmailService
from app.services.extractor import ExtractorService
from app.services.validator import ValidatorService
from app.services.otp_service import OTPService
from app.services.admin_service import AdminService

class ProcessorService:
    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService()
        self.extractor = ExtractorService()
        self.validator = ValidatorService(db)

    def process_inbox(self):
        print("Buscando correos nuevos...")
        messages = self.email_service.check_inbox()
        
        if not messages:
            print("No hay correos nuevos.")
            return

        print(f"Encontrados {len(messages)} correos.")
        
        for msg in messages:
            try:
                self.process_message(msg)
                self.email_service.graph_service.mark_as_read(msg['id'])
                print(f"   Mensaje marcado como leido: {msg['id'][-5:]}")
            except Exception as e:
                print(f"   Error procesando mensaje {msg['id'][-5:]}: {e}")

    def process_message(self, msg: dict):
        sender = msg['from']
        body = msg['body']
        
        print(f"Procesando correo de: {sender}")

        from app.core.config import settings
        bot_email = (settings.GRAPH_USER_EMAIL or "").strip().lower()
        sender_clean = (sender or "").strip().lower()
        
        if sender_clean == bot_email:
            print(f"   Ignorando correo propio ({sender}) para evitar bucles.")
            return

        if "postmaster" in sender_clean or "no-reply" in sender_clean:
            print(f"   Ignorando correo de sistema ({sender}).")
            return
        
        if sender_clean == (settings.GRAPH_USER_EMAIL or "").lower() and "aprobado" in body.lower():
            print("   Respuesta de aprobacion detectada.")
            import re
            ticket_match = re.search(r"Ticket:\s*([a-f0-9\-]+)", body, re.IGNORECASE)
            
            if ticket_match:
                ticket_id_to_approve = ticket_match.group(1).strip()
                t_to_approve = self.db.query(Ticket).filter(Ticket.id == ticket_id_to_approve, Ticket.status == "PENDING_APPROVAL").first()
                if t_to_approve:
                    print(f"   Aprobando Ticket {t_to_approve.id[:8]}...")
                    t_to_approve.status = "VERIFIED"
                    self.db.commit()
                    
                    otp = OTPService.create_otp_for_ticket(self.db, t_to_approve.id)
                    sent = self.email_service.send_otp_email(t_to_approve.sender_email, otp, "Estudiante")
                    if sent:
                        t_to_approve.status = "OTP_SENT"
                    else:
                        t_to_approve.status = "ERROR_SENDING_OTP"
                    self.db.commit()
                    self.email_service.send_email(sender, "Aprobacion Exitosa", f"Se ha enviado el OTP al correo {t_to_approve.sender_email}.")
                    return
            
            t_to_approve = self.db.query(Ticket).filter(Ticket.status == "PENDING_APPROVAL").first()
            if t_to_approve:
                 print(f"   Aprobando Ticket (Mas antiguo) {t_to_approve.id[:8]}...")
                 t_to_approve.status = "VERIFIED"
                 self.db.commit()
                 
                 otp = OTPService.create_otp_for_ticket(self.db, t_to_approve.id)
                 sent = self.email_service.send_otp_email(t_to_approve.sender_email, otp, "Estudiante")
                 if sent:
                        t_to_approve.status = "OTP_SENT"
                 else:
                        t_to_approve.status = "ERROR_SENDING_OTP"
                 self.db.commit()
                 self.email_service.send_email(sender, "Aprobacion Exitosa", f"Se ha enviado el OTP al correo {t_to_approve.sender_email}.")
                 return
            else:
                 print("   No hay tickets pendientes de aprobacion.")
            return

        active_tickets = self.db.query(Ticket).filter(Ticket.status == "OTP_SENT").all()
        candidate_ticket = None
        for t in active_tickets:
            if (t.sender_email or "").strip().lower() == sender_clean:
                candidate_ticket = t
                break
        
        print(f"   Buscando ticket para {sender_clean}...")
        if candidate_ticket:
            print(f"   Respuesta de usuario pendiente detectada (Ticket {candidate_ticket.id[:8]})")
            self.handle_otp_response(candidate_ticket, body, sender)
            return
        else:
             print(f"   No se encontro ticket pendiente para {sender_clean}.")

        self.handle_new_request(sender, body)

    def handle_otp_response(self, ticket: Ticket, body: str, sender: str):
        print(f"   Analizando posible OTP...")
        import re
        match_strict = re.search(r"\b\d{6}\b", body)
        
        if match_strict:
            input_otp = match_strict.group(0)
            print(f"   OTP encontrado: {input_otp}")
            
            is_valid = OTPService.validate_ticket_otp(self.db, ticket.id, input_otp)
            print(f"   Resultado Validacion: {is_valid}")
            
            if is_valid:
                print("   OTP VALIDO. Procediendo con el reset...")
                ticket.status = "VERIFIED_OTP"
                self.db.commit()
                
                admin = AdminService()
                student = self.db.query(Student).filter(Student.matricula == ticket.student_matricula).first()
                target_email = student.institutional_email if (student and student.institutional_email) else ticket.sender_email
                
                success, msg = admin.reset_password(target_email)
                
                if success:
                    new_password = msg 

                    success_msg = f"""Hola {student.full_name if student else 'Estudiante'},
                    
Hemos restablecido tu contraseña institucional exitosamente.

Tu nueva contraseña temporal es: {new_password}

Por razones de seguridad, Microsoft te pedirá cambiar esta contraseña por una definitiva la próxima vez que inicie sesión.

Atentamente,
Soporte Tecnico - UT Matamoros"""

                    self.email_service.send_email(sender, "Nueva Contrasena Institucional", success_msg)
                    ticket.status = "COMPLETED"
                else:
                    friendly_error = "Por el momento no se puede procesar su solicitud. Por favor espere unos minutos e intente de nuevo."
                    print(f"   Fallo en Reset ({msg}).")
                    self.email_service.send_email(sender, "Aviso del Sistema", friendly_error)
                    ticket.status = "FAILED_EXECUTION"
                
                self.db.commit()
            else:
                print("   OTP INVALIDO o EXPIRADO.")
                self.email_service.send_email(sender, "Error", "El código es incorrecto o ha expirado.")
        else:
            print("   No se encontró un código OTP de 6 dígitos.")
            
            body_lower = body.lower()
            escape_keywords = ["ayuda", "reiniciar", "cancelar", "hola", "buenas", "clave", "contraseña", "password", "recuperar", "reset", "solicitud"]
            
            if any(k in body_lower for k in escape_keywords):
                print("   Usuario solicita cancelar flujo OTP. Cancelando ticket...")
                ticket.status = "CANCELLED_USER"
                self.db.commit()
                self.handle_new_request(sender, body)

    def handle_new_request(self, sender: str, body: str):
        sender_clean = (sender or "").strip().lower()
        intent_data = self.extractor.classify_intent(body)
        intent = intent_data.get("intent", "OTHER")
        print(f"   Intencion: {intent}")

        if intent in ["CAMPUS_INFO", "OTHER"]:
            print(f"   Derivando consulta no relacionada ({intent}).")
            generic_response = (
                "Hola. Este es el Soporte Tecnico de la UT Matamoros.\n\n"
                "He recibido tu mensaje, pero mi función es ayudarte con el restablecimiento de tu contraseña institucional.\n\n"
                "Para dudas sobre Servicios Escolares o información general, por favor comunícate directamente con el campus.\n\n"
                "Saludos."
            )
            self.email_service.send_email(sender, "Informacion sobre tu consulta", generic_response)
            return

        ticket = Ticket(sender_email=sender, status="OPEN")
        self.db.add(ticket)
        self.db.commit()
        ticket_id = ticket.id

        data = self.extractor.extract_student_data(body)
        print(f"   Datos extraidos: {data}")
        
        matricula = data.get("matricula")
        nombre = data.get("name")
        carrera = data.get("carrera")

        if not matricula or not nombre:
            import re
            if re.search(r"\b\d{6}\b", body):
                print("   Posible OTP sin ticket activo detectado.")
                self.email_service.send_email(
                    sender,
                    "Solicitud No Encontrada",
                    "Recibimos un código de verificación, pero no tenemos una solicitud activa para ti.\n\nPor favor envia tus datos para iniciar una nueva solicitud."
                )
                ticket.status = "ORPHAN_OTP"
                self.db.commit()
                return

            print("   Datos incompletos. Solicitando informacion.")
            self.email_service.send_data_request_email(sender)
            ticket.status = "WAITING_INFO"
            self.db.commit()
            return

        is_valid, student, reason = self.validator.validate_student_identity(matricula, nombre, carrera)
        
        if not is_valid:
            print(f"   Validacion fallida: {reason}")
            self.email_service.send_rejection_email(sender, f"Validacion de identidad: {reason}")
            ticket.status = "REJECTED_VALIDATION"
            self.db.commit()
            return

        from app.core.config import settings
        if not sender_clean.endswith("@tu-dominio.edu.mx"): 
            print(f"   Correo externo detectado ({sender}). Requiere aprobacion.")
            admin_msg = f"""
            Solicitud de Restablecimiento Externa
            
            El estudiante {student.full_name} (Matricula: {student.matricula}) ha solicitado restablecer su contraseña institucional desde un correo personal externo: '{sender}'.
            
            Ticket: {ticket.id}
            
            Para aprobar, responda a este correo con la palabra 'APROBADO'.
            """
            self.email_service.send_email(settings.GRAPH_USER_EMAIL, "Aprobacion Requerida", admin_msg)
            ticket.status = "PENDING_APPROVAL"
            ticket.student_matricula = student.matricula
            self.db.commit()
            
            self.email_service.send_email(sender, "Solicitud recibida", "Tu solicitud está siendo revisada por un administrador.")
            return
            
        print(f"   Identidad Verificada: {student.full_name}")
        ticket.student_matricula = student.matricula
        ticket.status = "VERIFIED"
        
        otp = OTPService.create_otp_for_ticket(self.db, ticket_id)
        print(f"   Enviando OTP a: {sender}")
        sent = self.email_service.send_otp_email(sender, otp, nombre)
        
        if sent:
            print("   OTP enviado.")
            ticket.status = "OTP_SENT"
        else:
            ticket.status = "ERROR_SENDING_OTP"
        
        self.db.commit()
