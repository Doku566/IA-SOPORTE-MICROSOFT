from sqlalchemy.orm import Session
from app.models.student import Student
from typing import Optional, Tuple
import unicodedata

class ValidatorService:
    def __init__(self, db: Session):
        self.db = db

    def validate_student_identity(self, matricula: str, name_query: str, career_query: str) -> Tuple[bool, Optional[Student], str]:
        student = self.db.query(Student).filter(Student.matricula == matricula).first()

        if not student:
            return False, None, "Matricula no encontrada."

        def normalize_string(s):
            if not s: return ""
            s = str(s).strip().upper()
            s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
            return s

        db_name = normalize_string(student.full_name)
        query_name = normalize_string(name_query)
        db_career = normalize_string(student.career)
        query_career = normalize_string(career_query)

        db_name_parts = set(db_name.split())
        query_name_parts = set(query_name.split())
        
        shared_words = db_name_parts.intersection(query_name_parts)
        name_match = len(shared_words) >= 2 or query_name in db_name or db_name in query_name
        
        if len(query_name_parts) == 1 and len(shared_words) == 1:
            name_match = True

        career_match = False
        if "ESTUDIANTE" in db_career or "STUDENT" in db_career:
             career_match = True
        else:
            for query_word in query_career.split():
                 if len(query_word) > 3 and query_word in db_career:
                     career_match = True
                     break
            if query_career in db_career or db_career in query_career:
                 career_match = True

        if not name_match:
             return False, None, f"El nombre proporcionado no coincide con los registros."
        
        if not career_match:
            return False, None, "La carrera no coincide con los registros."
            
        if student.status != "ACTIVE":
             return False, None, "El alumno no esta activo."

        return True, student, "Identidad Verificada."

    def get_personal_email(self, matricula: str) -> Optional[str]:
        student = self.db.query(Student).filter(Student.matricula == matricula).first()
        if student:
            return student.personal_email
        return None
