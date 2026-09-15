from __future__ import annotations

from enum import Enum


class BamStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    VERIFIED_CLEAR = "VERIFIED_CLEAR"
    BLOCKED = "BLOCKED"


class IncidentStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    VERIFIED_CLEAR = "VERIFIED_CLEAR"
    PRESENT_RESOLVED = "PRESENT_RESOLVED"
    PRESENT_UNRESOLVED = "PRESENT_UNRESOLVED"


class BlockingStatus(str, Enum):
    NOT_CHECKED = "NOT_CHECKED"
    CLEAR = "CLEAR"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class AnalysisJobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


class FinancialReadinessStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    READY = "READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class DecisionEligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"


class DossierWorkflowStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    REVIEW = "review"
    APPROVED = "approved"
    RESERVED = "reserved"
    REJECTED = "rejected"
