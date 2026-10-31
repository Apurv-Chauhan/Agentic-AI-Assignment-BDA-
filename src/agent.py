
import json
import re
import time
from typing import Dict, Any, List, Optional

from src.groq_client import GroqClientWrapper, LLMResponse
from src.tools import TOOL_DISPATCH, GROQ_TOOLS_SCHEMA
from src.policy_retriever import PolicyRetriever
from src.memory import MemoryManager


SYSTEM_PROMPT = """
You are an Intelligent Student Support Agent for the PGDM programme.

Help students with tuition fees, academic records, scholarships,
institutional policies, and support requests.

RULES:
1. Use tools for specific student-record questions.
2. Use retrieved handbook evidence. Never invent institutional policies.
3. If policy information is unavailable, explain this and offer a support ticket.
4. Use only appropriate, non-sensitive persistent student preferences.
5. Never request or store passwords, OTPs, card details, or API keys.
6. Never disclose another student's private records.
7. Never claim an action succeeded unless its tool confirms success.
8. Tool results may report denial or failure. Explain these accurately.
"""


SENSITIVE_PATTERNS = [
    (
        re.compile(
            r"\b(password|passwd|pwd)\s*(?:is|=|:)\s*[^\s,;]+",
            re.IGNORECASE,
        ),
        r"\1=[REDACTED]",
    ),
    (
        re.compile(
            r"\b(otp|one[\s-]?time[\s-]?pass(?:code|word))"
            r"\s*(?:is|=|:)\s*\d{4,8}\b",
            re.IGNORECASE,
        ),
        r"\1=[REDACTED]",
    ),
    (
        re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"),
        "[REDACTED PAYMENT CARD]",
    ),
    (
        re.compile(
            r"\b(cvv|cvc|pin|security code)\s*(?:is|=|:)\s*\d{3,4}\b",
            re.IGNORECASE,
        ),
        r"\1=[REDACTED]",
    ),
    (
        re.compile(
            r"\b(api[\s_-]?key|secret[\s_-]?key|access token)"
            r"\s*(?:is|=|:)\s*\S+",
            re.IGNORECASE,
        ),
        r"\1=[REDACTED]",
    ),
]


def redact_sensitive_text(text: str) -> str:
    """Redact common credential patterns before model processing."""
    if not isinstance(text, str):
        return ""

    cleaned = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)

    return cleaned


class StudentSupportAgent:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        retriever: Optional[PolicyRetriever] = None,
        memory: Optional[MemoryManager] = None,
    ):
        if model:
            self.llm = GroqClientWrapper(api_key=api_key, model=model)
        else:
            self.llm = GroqClientWrapper(api_key=api_key)

        self.retriever = retriever or PolicyRetriever()
        self.memory = memory or MemoryManager()

    def process_query(
        self,
        query: str,
        student_id: Optional[str] = None,
        session_history: Optional[List[Dict[str, str]]] = None,
        auto_inspect_memory: bool = True,
    ) -> Dict[str, Any]:

        start_time = time.perf_counter()
        tools_used = []
        retrieved_evidence = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        memory_notice = ""

        # Normalize the identity supplied by the application session.
        active_student_id = (
            str(student_id).strip().upper() if student_id else None
        )

        # Inspect raw input for memory safety, but don't send credential-like
        # values to the LLM or include them in conversation history.
        if auto_inspect_memory and active_student_id:
            try:
                is_allowed, reason = self.memory.inspect_statement(query)
                if not is_allowed:
                    memory_notice = reason
            except Exception:
                memory_notice = "Memory safety inspection was unavailable."

        safe_query = redact_sensitive_text(query)

        # Retrieve only relevant policy context.
        try:
            matched_chunks = self.retriever.retrieve(safe_query, top_k=2)
        except Exception:
            matched_chunks = []

        policy_context = "\n\n### Relevant Policy Handbook Chunks:\n"

        for chunk in matched_chunks:
            chunk_id = str(chunk.get("chunk_id", "unknown"))
            title = str(chunk.get("title", "Untitled policy"))
            content = redact_sensitive_text(str(chunk.get("content", "")))

            retrieved_evidence.append(f"{chunk_id} ({title})")
            policy_context += (
                f"\n--- {title} (ID: {chunk_id}) ---\n"
                f"{content}\n"
            )

        if not matched_chunks:
            policy_context += (
                "[No matching policy sections were retrieved. "
                "Do not invent policy information.]\n"
            )

        # Inject memory for this session's student only.
        student_memory_context = ""

        if active_student_id:
            student_memory_context = (
                f"\n\n### Active Student ID: {active_student_id}\n"
            )
            try:
                student_memory_context += (
                    self.memory.format_memory_for_context(active_student_id)
                )
                facts = self.memory.get_memory(active_student_id)
                for key in facts.keys():
                    retrieved_evidence.append(f"Memory: {key}")
            except Exception:
                student_memory_context += (
                    "Persistent memory is temporarily unavailable."
                )

        system_content = (
            SYSTEM_PROMPT + policy_context + student_memory_context
        )

        if memory_notice:
            system_content += (
                "\n\nSECURITY NOTICE: Sensitive or temporary information "
                "was detected. Never request credentials again or store them."
            )

        messages = [{"role": "system", "content": system_content}]

        # Redact historical messages before using them as context.
        if session_history:
            for item in session_history[-4:]:
                role = item.get("role")
                if role not in ("user", "assistant"):
                    continue

                messages.append({
                    "role": role,
                    "content": redact_sensitive_text(
                        str(item.get("content", ""))
                    ),
                })

        messages.append({"role": "user", "content": safe_query})

        # Initial LLM request.
        response: LLMResponse = self.llm.complete(
            messages=messages,
            tools=GROQ_TOOLS_SCHEMA,
            tool_choice="auto",
        )

        total_prompt_tokens += response.prompt_tokens
        total_completion_tokens += response.completion_tokens

        if response.tool_calls:
            messages.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": tc["arguments"],
                        },
                    }
                    for tc in response.tool_calls
                ],
            })

            for tc in response.tool_calls:
                func_name = tc["name"]
                tools_used.append(func_name)

                try:
                    args = json.loads(tc["arguments"])
                    if not isinstance(args, dict):
                        args = {}
                except (TypeError, ValueError):
                    args = {}

                # Current tools are student-scoped. Never trust the ID
                # generated by the LLM as the authenticated identity.
                if func_name not in TOOL_DISPATCH:
                    observation = {
                        "status": "error",
                        "message": "Unknown tool.",
                    }

                elif not active_student_id:
                    observation = {
                        "status": "denied",
                        "message": (
                            "Access denied: no active student identity."
                        ),
                    }

                else:
                    requested_id = str(
                        args.get("student_id") or ""
                    ).strip().upper()

                    if requested_id and requested_id != active_student_id:
                        observation = {
                            "status": "denied",
                            "message": (
                                "Access denied: you may only access "
                                "your own student records."
                            ),
                        }
                    else:
                        # The application supplies the trusted identity
                        # separately. The tools enforce ownership again.
                        args["student_id"] = active_student_id
                        args["authenticated_student_id"] = active_student_id

                        try:
                            observation = TOOL_DISPATCH[func_name](**args)
                        except TypeError:
                            # Fail closed if a tool has an unexpected
                            # signature; do not retry without authorization.
                            observation = {
                                "status": "error",
                                "message": (
                                    "Tool configuration error. "
                                    "No action was executed."
                                ),
                            }
                        except Exception:
                            observation = {
                                "status": "error",
                                "message": (
                                    "Tool execution failed. Please try again "
                                    "or contact student support."
                                ),
                            }

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": func_name,
                    "content": json.dumps(observation),
                })

            # Ask the model to explain the tool results.
            final_response = self.llm.complete(
                messages=messages,
                tools=None,
            )

            total_prompt_tokens += final_response.prompt_tokens
            total_completion_tokens += final_response.completion_tokens
            answer = redact_sensitive_text(final_response.content or "")

        else:
            answer = redact_sensitive_text(response.content or "")

        total_latency = time.perf_counter() - start_time

        return {
            "answer": answer,
            "tools_used": tools_used,
            "retrieved_evidence": retrieved_evidence,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "latency_seconds": round(total_latency, 3),
            "memory_notice": memory_notice,
            "model_used": response.model,
        }
