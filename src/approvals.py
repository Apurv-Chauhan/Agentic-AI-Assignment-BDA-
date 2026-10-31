
import json
import uuid
from datetime import datetime, timezone

from src.config import STUDENTS_DB_FILE, DATA_DIR
from src.tools import AUDIT_LOG_FILE

APPROVALS_FILE = DATA_DIR / "approval_requests.json"


def _read_json(path, default):
    if not path.exists():
        return default

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")

    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

    temp_path.replace(path)


def _audit(
    requester_id,
    action,
    student_id,
    allowed,
    approval_status,
    result,
    approver_id=None,
):
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "requester_id": requester_id,
        "action": action,
        "requested_student_id": student_id,
        "allowed": allowed,
        "approval_status": approval_status,
        "result": result,
    }

    if approver_id is not None:
        event["approver_id"] = approver_id

    AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(event) + "\n")


def request_fee_waiver(student_id, amount, reason):
    """Create a pending waiver request. Never change fees here."""
    sid = str(student_id).strip().upper()

    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return {"status": "error", "message": "Amount must be a whole number."}

    reason = str(reason).strip()

    if amount <= 0:
        return {"status": "error", "message": "Amount must be greater than zero."}

    if not reason:
        return {"status": "error", "message": "A reason is required."}

    students = _read_json(STUDENTS_DB_FILE, {})
    student = students.get(sid)

    if not student:
        return {"status": "error", "message": "Student record not found."}

    fee = student.get("fee_record", {})
    balance = int(fee.get("pending_balance", 0))

    if amount > balance:
        return {
            "status": "error",
            "message": f"Requested waiver exceeds the current balance of ₹{balance:,}.",
        }

    requests = _read_json(APPROVALS_FILE, [])

    request_id = "APR-" + uuid.uuid4().hex[:8].upper()

    request = {
        "request_id": request_id,
        "requester_id": sid,
        "action": "fee_waiver",
        "amount": amount,
        "reason": reason,
        "balance_before": balance,
        "status": "PENDING",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "decided_at": None,
        "approver_id": None,
        "result": None,
    }

    requests.append(request)
    _write_json(APPROVALS_FILE, requests)

    _audit(
        sid,
        "request_fee_waiver",
        sid,
        True,
        "pending",
        "awaiting_human_approval",
    )

    return {
        "status": "success",
        "request_id": request_id,
        "message": (
            f"Waiver request for ₹{amount:,} is pending approval. "
            f"The current balance remains ₹{balance:,}."
        ),
    }


def list_pending_approvals():
    requests = _read_json(APPROVALS_FILE, [])
    return [r for r in requests if r.get("status") == "PENDING"]


def decide_approval(request_id, decision, approver_id):
    """Apply a waiver only after explicit approval; rejection never mutates fees."""
    request_id = str(request_id).strip().upper()
    decision = str(decision).strip().upper()
    approver_id = str(approver_id).strip().upper()

    if decision not in {"APPROVE", "REJECT"}:
        return {"status": "error", "message": "Decision must be APPROVE or REJECT."}

    requests = _read_json(APPROVALS_FILE, [])
    request = next(
        (r for r in requests if r.get("request_id") == request_id),
        None,
    )

    if request is None:
        return {"status": "error", "message": "Approval request not found."}

    if request.get("status") != "PENDING":
        return {
            "status": "error",
            "message": f"Request has already been decided: {request.get('status')}.",
        }

    students = _read_json(STUDENTS_DB_FILE, {})
    sid = request["requester_id"]
    student = students.get(sid)

    if not student:
        return {"status": "error", "message": "Student record no longer exists."}

    if decision == "REJECT":
        request["status"] = "REJECTED"
        request["decided_at"] = datetime.now(timezone.utc).isoformat()
        request["approver_id"] = approver_id
        request["result"] = "rejected_no_change"

        _write_json(APPROVALS_FILE, requests)
        _audit(
            sid,
            "decide_fee_waiver",
            sid,
            True,
            "rejected",
            "rejected_no_change",
            approver_id,
        )

        return {
            "status": "success",
            "message": "Request rejected. The student's fee record was not changed.",
        }

    fee = student.setdefault("fee_record", {})
    current_balance = int(fee.get("pending_balance", 0))
    amount = int(request["amount"])

    # Fail closed if the balance changed while awaiting approval.
    if current_balance != int(request["balance_before"]):
        _audit(
            sid,
            "decide_fee_waiver",
            sid,
            False,
            "approval_blocked",
            "balance_changed_since_request",
            approver_id,
        )
        return {
            "status": "error",
            "message": (
                "Approval blocked: the fee balance changed after this request "
                "was created. Submit a new request using the current balance."
            ),
        }

    if amount <= 0 or amount > current_balance:
        return {
            "status": "error",
            "message": "Approval blocked because the requested amount is invalid.",
        }

    new_balance = current_balance - amount

    # Record the approved adjustment separately from payments.
    fee.setdefault("adjustment_history", []).append({
        "type": "APPROVED_FEE_WAIVER",
        "request_id": request_id,
        "amount": amount,
        "balance_before": current_balance,
        "balance_after": new_balance,
        "reason": request["reason"],
        "approved_by": approver_id,
        "approved_at": datetime.now(timezone.utc).isoformat(),
    })

    fee["pending_balance"] = new_balance

    # Do not misrepresent a waiver as a payment.
    if new_balance == 0:
        fee["payment_status"] = "WAIVED_BALANCE"
    else:
        fee["payment_status"] = "PARTIALLY_PAID"

    request["status"] = "APPROVED"
    request["decided_at"] = datetime.now(timezone.utc).isoformat()
    request["approver_id"] = approver_id
    request["result"] = "waiver_applied"
    request["balance_after"] = new_balance

    # Save the changed student record and request history.
    _write_json(STUDENTS_DB_FILE, students)
    _write_json(APPROVALS_FILE, requests)

    _audit(
        sid,
        "decide_fee_waiver",
        sid,
        True,
        "approved",
        "waiver_applied",
        approver_id,
    )

    return {
        "status": "success",
        "message": (
            f"Request approved. Waiver: ₹{amount:,}. "
            f"New pending balance: ₹{new_balance:,}."
        ),
    }
