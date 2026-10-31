import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from src.config import MEMORY_STORE_FILE

# Regex patterns for detecting sensitive credentials
SENSITIVE_PATTERNS = [
    (r"\b(password|passwd|pwd)\s*[:=]?\s*['\"]?\S+['\"]?", "Password / Credential"),
    (r"\b(otp|one[\s-]?time[\s-]?pass(code|word))\s*[:=]?\s*\d{4,8}\b", "One-Time Password (OTP)"),
    (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "Payment Card Number"),
    (r"\b(cvv|cvc|pin|security code)\s*[:=]?\s*\d{3,4}\b", "Card CVV / Security PIN"),
    (r"\b(secret[\s-]?key|api[\s-]?key|token)\s*[:=]?\s*\S+", "API Key / Auth Token"),
]

# Patterns for detecting temporary or fleeting states that shouldn't persist across sessions
TEMPORARY_PATTERNS = [
    r"\b(tired|sleepy|exhausted|dizzy|headache|fever|sick|hungry|thirsty)\b",
    r"\b(today|right now|at the moment|just now|for now|this morning|this afternoon)\b.*\b(feel|feeling|am|mood)\b",
    r"\b(going to get|getting|grab|grabbing)\s+(a\s+)?(coffee|tea|lunch|snack|break)\b",
    r"\b(stepping out|brb|be right back|five minutes|weather is|raining)\b",
]

class MemoryManager:
    """
    Manages persistent memory across student sessions.
    Strictly filters out:
    1. Sensitive data (passwords, OTPs, PINs, credit cards).
    2. Temporary / fleeting conditions (headaches, tired feelings, momentary coffee breaks).
    Retains only durable academic preferences, programme details, and learning goals.
    """
    def __init__(self, file_path=MEMORY_STORE_FILE):
        self.file_path = file_path
        self._ensure_store()

    def _ensure_store(self):
        if not self.file_path.exists():
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)

    def _load_all(self) -> Dict[str, Any]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_all(self, data: Dict[str, Any]):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def inspect_statement(self, text: str) -> Tuple[bool, str]:
        """
        Check if a statement is sensitive or temporary.
        Returns: (is_allowed, rejection_reason)
        """
        text_lower = text.lower()

        # 1. Check for sensitive credentials
        for pat, desc in SENSITIVE_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                return False, f"REJECTED: Contains sensitive security information ({desc}). Storing credentials violates academic safety policy."

        # 2. Check for temporary / ephemeral statements
        for pat in TEMPORARY_PATTERNS:
            if re.search(pat, text_lower):
                return False, "REJECTED: Classified as a temporary/fleeting condition (e.g., mood, physical state, momentary break). Only long-term preferences are stored."

        return True, "ALLOWED"

    def store_fact(self, student_id: str, key: str, value: str) -> Dict[str, Any]:
        """
        Store a durable fact about the student if it passes the safety & privacy filter.
        """
        is_allowed, reason = self.inspect_statement(value)
        data = self._load_all()
        student_id_norm = student_id.strip().upper()

        if student_id_norm not in data:
            data[student_id_norm] = {
                "student_id": student_id_norm,
                "useful_facts": {},
                "audit_log": []
            }

        timestamp = datetime.now().isoformat()

        if not is_allowed:
            # Log the rejection for audit & transparency
            data[student_id_norm]["audit_log"].append({
                "action": "REJECTED",
                "reason": reason,
                "attempted_key": key,
                "timestamp": timestamp
            })
            self._save_all(data)
            return {"stored": False, "reason": reason}

        # Store the clean, useful fact
        data[student_id_norm]["useful_facts"][key] = {
            "value": value.strip(),
            "updated_at": timestamp
        }
        data[student_id_norm]["audit_log"].append({
            "action": "STORED",
            "key": key,
            "timestamp": timestamp
        })
        self._save_all(data)
        return {"stored": True, "key": key, "value": value.strip()}

    def get_memory(self, student_id: str) -> Dict[str, Any]:
        """Retrieve all persistent facts for a student."""
        data = self._load_all()
        student_id_norm = student_id.strip().upper()
        return data.get(student_id_norm, {}).get("useful_facts", {})

    def format_memory_for_context(self, student_id: str) -> str:
        """
        Format remembered facts into a concise string for LLM prompt context injection.
        """
        facts = self.get_memory(student_id)
        if not facts:
            return "No prior remembered student preferences found."

        lines = ["Persistent Student Memory:"]
        for k, item in facts.items():
            val = item.get("value") if isinstance(item, dict) else item
            lines.append(f"- {k.replace('_', ' ').capitalize()}: {val}")
        return "\n".join(lines)
