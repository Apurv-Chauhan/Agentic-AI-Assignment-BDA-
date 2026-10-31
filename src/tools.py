
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from src.config import STUDENTS_DB_FILE, TICKETS_DB_FILE


PROJECT_ROOT = Path(__file__).resolve().parent.parent
AUDIT_LOG_FILE = PROJECT_ROOT / "data" / "audit_log.jsonl"


def _load_students() -> Dict[str, Any]:
    if not STUDENTS_DB_FILE.exists():
        return {}

    with open(STUDENTS_DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_tickets() -> list:
    if not TICKETS_DB_FILE.exists():
        return []

    with open(TICKETS_DB_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []


def _save_tickets(tickets: list) -> None:
    TICKETS_DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TICKETS_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(tickets, f, indent=2)


def _audit(
    requester_id: Optional[str],
    action: str,
    requested_student_id: Optional[str],
    allowed: bool,
    result: str,
    approval_status: str = "not_required",
) -> None:
    """Write an audit event without storing credentials or full private records."""
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "requester_id": requester_id,
        "action": action,
        "requested_student_id": requested_student_id,
        "allowed": allowed,
        "approval_status": approval_status,
        "result": result,
    }

    AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def _authorize(
    action: str,
    student_id: str,
    authenticated_student_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    Enforce ownership inside the tool.
    The authenticated identity must come from the application session,
    not from the LLM-generated tool arguments.
    """
    requested_id = (
        str(student_id).strip().upper() if student_id else ""
    )
    requester_id = (
        str(authenticated_student_id).strip().upper()
        if authenticated_student_id
        else None
    )

    if not requester_id:
        _audit(
            None, action, requested_id or None,
            False, "missing_authenticated_identity",
        )
        return {
            "status": "denied",
            "message": "Access denied: authenticated identity is required.",
        }

    if not requested_id or requested_id != requester_id:
        _audit(
            requester_id, action, requested_id or None,
            False, "cross_student_access_blocked",
        )
        return {
            "status": "denied",
            "message": "Access denied: you may only access your own records.",
        }

    return None


def check_student_record(
    student_id: str,
    authenticated_student_id: Optional[str] = None,
) -> Dict[str, Any]:
    denied = _authorize(
        "check_student_record", student_id, authenticated_student_id
    )
    if denied:
        return denied

    students = _load_students()
    sid = student_id.strip().upper()

    if sid not in students:
        _audit(
            authenticated_student_id, "check_student_record",
            sid, True, "record_not_found",
        )
        return {
            "status": "error",
            "message": "The requested student record was not found.",
        }

    rec = students[sid]

    result = {
        "status": "success",
        "student_id": rec.get("student_id", sid),
        "full_name": rec.get("full_name"),
        "programme": rec.get("programme"),
        "batch": rec.get("batch"),
        "current_term": rec.get("current_term"),
        "cgpa": rec.get("cgpa"),
        "attendance_percentage": rec.get("attendance_percentage"),
        "faculty_advisor": rec.get("faculty_advisor"),
    }

    _audit(
        authenticated_student_id, "check_student_record",
        sid, True, "success",
    )
    return result


def check_fee_status(
    student_id: str,
    authenticated_student_id: Optional[str] = None,
) -> Dict[str, Any]:
    denied = _authorize(
        "check_fee_status", student_id, authenticated_student_id
    )
    if denied:
        return denied

    students = _load_students()
    sid = student_id.strip().upper()

    if sid not in students:
        _audit(
            authenticated_student_id, "check_fee_status",
            sid, True, "record_not_found",
        )
        return {
            "status": "error",
            "message": "Fee information could not be found.",
        }

    rec = students[sid]
    fee = rec.get("fee_record", {})

    result = {
        "status": "success",
        "student_id": rec.get("student_id", sid),
        "student_name": rec.get("full_name"),
        "programme": rec.get("programme"),
        "current_term": rec.get("current_term"),
        "term_fee": fee.get("term_fee"),
        "paid_amount": fee.get("paid_amount"),
        "pending_balance": fee.get("pending_balance"),
        "due_date": fee.get("due_date"),
        "payment_status": fee.get("payment_status"),
        "late_fee_accrued": fee.get("late_fee_accrued", 0),
        "recent_installment": (
            fee.get("installment_history", [])[-1]
            if fee.get("installment_history")
            else None
        ),
    }

    _audit(
        authenticated_student_id, "check_fee_status",
        sid, True, "success",
    )
    return result


def check_scholarship_status(
    student_id: str,
    authenticated_student_id: Optional[str] = None,
) -> Dict[str, Any]:
    denied = _authorize(
        "check_scholarship_status", student_id, authenticated_student_id
    )
    if denied:
        return denied

    students = _load_students()
    sid = student_id.strip().upper()

    if sid not in students:
        _audit(
            authenticated_student_id, "check_scholarship_status",
            sid, True, "record_not_found",
        )
        return {
            "status": "error",
            "message": "Scholarship information could not be found.",
        }

    rec = students[sid]
    scholarship = rec.get("scholarship", {})

    result = {
        "status": "success",
        "student_id": rec.get("student_id", sid),
        "student_name": rec.get("full_name"),
        "has_scholarship": scholarship.get("has_scholarship", False),
        "scheme_name": scholarship.get("scheme_name"),
        "waiver_percentage": scholarship.get("waiver_percentage", 0),
        "scholarship_status": scholarship.get("status"),
        "min_cgpa_required": scholarship.get("min_cgpa_required"),
        "student_current_cgpa": rec.get("cgpa"),
        "student_attendance": rec.get("attendance_percentage"),
        "eligibility_remarks": scholarship.get("eligibility_remarks"),
    }

    _audit(
        authenticated_student_id, "check_scholarship_status",
        sid, True, "success",
    )
    return result


def create_support_ticket(
    student_id: str,
    category: str,
    issue_description: str,
    priority: str = "Medium",
    authenticated_student_id: Optional[str] = None,
) -> Dict[str, Any]:
    denied = _authorize(
        "create_support_ticket", student_id, authenticated_student_id
    )
    if denied:
        return denied

    sid = student_id.strip().upper()
    students = _load_students()

    if sid not in students:
        _audit(
            authenticated_student_id, "create_support_ticket",
            sid, False, "student_not_found",
        )
        return {
            "status": "error",
            "message": "Cannot create a ticket for an unknown student.",
        }

    allowed_categories = {
        "Fee & Finance",
        "Academic / Course",
        "Scholarship",
        "IT & Portal Failure",
        "General Support",
    }
    allowed_priorities = {"Low", "Medium", "High", "Urgent"}

    if category not in allowed_categories:
        return {
            "status": "error",
            "message": "Invalid support-ticket category.",
        }

    if priority not in allowed_priorities:
        priority = "Medium"

    # Do not store credential-like content in a ticket description.
    import re

    safe_description = str(issue_description)
    for pattern in (
        r"\b(password|passwd|pwd)\s*(?:is|=|:)\s*\S+",
        r"\b(otp|one[\s-]?time[\s-]?pass(?:code|word))"
        r"\s*(?:is|=|:)\s*\d{4,8}\b",
        r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
        r"\b(cvv|cvc|pin)\s*(?:is|=|:)\s*\d{3,4}\b",
    ):
        safe_description = re.sub(
            pattern, "[REDACTED CREDENTIAL]", safe_description,
            flags=re.IGNORECASE,
        )

    ticket_id = (
        f"TICK-{datetime.now().year}-{uuid.uuid4().hex[:6].upper()}"
    )

    new_ticket = {
        "ticket_id": ticket_id,
        "student_id": sid,
        "category": category,
        "priority": priority,
        "issue_description": safe_description,
        "created_at": datetime.now().isoformat(),
        "status": "OPEN",
        "assigned_department": "Student Affairs & Helpdesk",
        "estimated_sla": "24 to 48 business hours",
    }

    tickets = _load_tickets()
    tickets.append(new_ticket)
    _save_tickets(tickets)

    _audit(
        authenticated_student_id, "create_support_ticket",
        sid, True, "ticket_created",
    )

    return {
        "status": "success",
        "ticket_id": ticket_id,
        "message": f"Support ticket {ticket_id} created successfully.",
        "category": category,
        "priority": priority,
        "estimated_sla": "24 to 48 business hours",
        "next_steps": (
            "Your request has been routed to Student Affairs & Helpdesk. "
            "The support team can provide further updates."
        ),
    }


TOOL_DISPATCH = {
    "check_student_record": check_student_record,
    "check_fee_status": check_fee_status,
    "check_scholarship_status": check_scholarship_status,
    "create_support_ticket": create_support_ticket,
}


GROQ_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "check_student_record",
            "description": (
                "Fetch the active student's academic profile, programme, "
                "term, CGPA, attendance, and faculty advisor."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "string"},
                },
                "required": ["student_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_fee_status",
            "description": (
                "Retrieve the active student's fee details, pending balance, "
                "due date, and recent payment history."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "string"},
                },
                "required": ["student_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_scholarship_status",
            "description": (
                "Retrieve the active student's scholarship and renewal details."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "string"},
                },
                "required": ["student_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_support_ticket",
            "description": (
                "Create a support ticket for the active student when an issue "
                "requires administrative assistance."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "student_id": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "Fee & Finance",
                            "Academic / Course",
                            "Scholarship",
                            "IT & Portal Failure",
                            "General Support",
                        ],
                    },
                    "issue_description": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["Low", "Medium", "High", "Urgent"],
                    },
                },
                "required": [
                    "student_id",
                    "category",
                    "issue_description",
                ],
            },
        },
    },
]
