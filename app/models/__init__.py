"""Database models package — import all models so SQLAlchemy registers them."""
from .user import User  # noqa: F401
from .question_paper import QuestionPaper  # noqa: F401
from .question_section import QuestionSection  # noqa: F401
from .approval import Approval  # noqa: F401
from .audit_log import AuditLog  # noqa: F401
from .recovery_code import RecoveryCode  # noqa: F401
