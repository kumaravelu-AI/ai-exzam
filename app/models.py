from typing import Annotated, Any, Dict, List, Optional
from pydantic import AliasChoices, BaseModel, Field, StringConstraints


StudentId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")]


class StartSessionRequest(BaseModel):
    student_id: StudentId
    student_name: str = "Student"
    subject: str
    level: str
    topic: str
    mode: str = "learning"


class ChatRequest(BaseModel):
    student_id: StudentId
    message: str
    mode: Optional[str] = None


class ExplainRequest(BaseModel):
    student_id: StudentId
    ask: str = Field(validation_alias=AliasChoices("ask", "question"))


class GenericResponse(BaseModel):
    ok: bool = True
    message: str = ""
    data: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    ok: bool = True
    reply: str
    data: Optional[Dict[str, Any]] = None


class SessionState(BaseModel):
    student_id: str
    mode: str
    subject: str
    level: str
    topic: str
    current_question_id: Optional[str] = None
    asked_questions: List[str] = []
    clarification_open: bool = False
    topic_status: str = "in_progress"
