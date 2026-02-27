import json
import os
from groq import Groq
from app.core.config import settings

class ExtractorService:
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = "llama-3.1-8b-instant"

    def extract_student_data(self, email_body: str) -> dict:
        system_prompt = """
        ROLE: Data Extractor.
        TASK: Identify the following entities from the email body:
        - name (Full Name)
        - matricula (Student ID)
        - carrera (Degree/Major)

        RESTRICTION: Output ONLY a valid JSON object. 
        Format: {"name": "...", "matricula": "...", "carrera": "..."}
        If any data is missing, use null.
        DO NOT engage in conversation.
        """

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": email_body}
                ],
                model=self.model,
                temperature=0,
                stream=False,
                response_format={"type": "json_object"}, 
            )
            
            result_content = chat_completion.choices[0].message.content
            return json.loads(result_content)

        except Exception as e:
            print(f"Error in extraction: {e}")
            return {"name": None, "matricula": None, "carrera": None}

    def classify_intent(self, email_body: str) -> dict:
        system_prompt = """
        ROLE: Intent Classifier for University IT Support.
        TASK: Classify the primary intent into EXACTLY ONE of these categories:
        - "RESET_PASSWORD": Help with password or login.
        - "CAMPUS_INFO": Info about admissions, grades, etc.
        - "OTHER": Anything else.

        RESTRICTION: Output ONLY a valid JSON object.
        Format: {"intent": "CATEGORY_NAME_HERE"}
        """

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": email_body}
                ],
                model=self.model,
                temperature=0,
                stream=False,
                response_format={"type": "json_object"}, 
            )
            
            result_content = chat_completion.choices[0].message.content
            return json.loads(result_content)

        except Exception as e:
            print(f"Error in intent classification: {e}")
            return {"intent": "OTHER"}
