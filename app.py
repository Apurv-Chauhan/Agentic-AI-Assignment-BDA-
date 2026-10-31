
import json
import sys
from pathlib import Path

import streamlit as st

from src.config import (
    ensure_api_key,
    STUDENTS_DB_FILE,
)
from src.agent import StudentSupportAgent
from src.policy_retriever import PolicyRetriever
from src.memory import MemoryManager
from src.approvals import (
    request_fee_waiver,
    list_pending_approvals,
    decide_approval,
)

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="Student Support AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

PROJECT_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------
# Styling
# ---------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');

    :root {
        --bg: #0b1020;
        --panel: #111a2e;
        --panel2: #17233a;
        --border: #293650;
        --text: #edf2ff;
        --muted: #9aa9c4;
        --accent: #7c9cff;
        --accent2: #9c8cff;
    }

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }

    .stApp {
        background:
            radial-gradient(ellipse at 15% 0%, #172343 0%, transparent 40%),
            var(--bg);
        color: var(--text);
    }

    [data-testid="stSidebar"] {
        background: #0d1527;
        border-right: 1px solid var(--border);
    }

    [data-testid="stHeader"] {
        background: transparent;
    }

    .block-container {
        max-width: 1120px;
        padding-top: 2rem;
        padding-bottom: 7rem;
    }

    h1, h2, h3 {
        font-family: 'Manrope', sans-serif !important;
        letter-spacing: -0.5px;
        color: var(--text);
    }

    .brand {
        font-family: 'Manrope', sans-serif;
        font-weight: 800;
        font-size: 1.1rem;
        color: #edf2ff;
        letter-spacing: -0.5px;
    }

    .eyebrow {
        color: #9aa9c4;
        text-transform: uppercase;
        letter-spacing: 2px;
        font-size: 0.69rem;
        font-weight: 700;
    }

    .hero {
        padding: 1.8rem 0 1.3rem 0;
    }

    .hero h1 {
        font-size: clamp(2rem, 4vw, 3.1rem);
        line-height: 1.12;
        margin: 0.6rem 0;
    }

    .hero p {
        color: var(--muted);
        max-width: 680px;
        font-size: 1rem;
        line-height: 1.7;
    }

    .pill {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 999px;
        background: #1d2c49;
        border: 1px solid #33496e;
        color: #b9cbff;
        font-size: 0.75rem;
        font-weight: 600;
    }

    .side-card {
        background: linear-gradient(145deg, #15213a, #10182b);
        border: 1px solid var(--border);
        border-radius: 15px;
        padding: 14px;
        margin: 10px 0;
    }

    .side-label {
        color: var(--muted);
        font-size: 0.78rem;
        margin-bottom: 4px;
    }

    .side-value {
        color: var(--text);
        font-weight: 700;
        font-size: 0.97rem;
        overflow-wrap: anywhere;
    }

    .stChatMessage {
        border: 1px solid rgba(100, 125, 170, 0.18);
        border-radius: 16px;
        padding: 0.65rem 0.8rem;
        background: rgba(18, 28, 48, 0.72);
        margin-bottom: 0.7rem;
    }

    [data-testid="stChatInput"] {
        border: 1px solid #334565;
        border-radius: 16px;
    }

    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        min-height: 2.5rem;
    }

    .stButton > button[kind="primary"] {
        background: linear-gradient(100deg, #688aff, #9a7cff);
        border: none;
        color: white;
    }

    div[data-testid="stMetric"] {
        background: rgba(20, 31, 53, 0.8);
        border: 1px solid var(--border);
        padding: 14px;
        border-radius: 14px;
    }

    .disclaimer {
        color: #9aa9c4;
        font-size: 0.75rem;
        line-height: 1.5;
        padding: 10px 0;
    }

    hr {
        border-color: var(--border);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Data and agent initialization
# ---------------------------------------------------------
@st.cache_data
def load_students():
    if not STUDENTS_DB_FILE.exists():
        return {}

    with open(STUDENTS_DB_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def get_agent():
    if "agent_instance" not in st.session_state:
        st.session_state.agent_instance = StudentSupportAgent(
            retriever=PolicyRetriever(),
            memory=MemoryManager(),
        )
    return st.session_state.agent_instance


try:
    students = load_students()

    if not students:
        st.error("No student records found. Check data/students_db.json.")
        st.stop()

    # Uses the same local Groq key configured for main.py.
    ensure_api_key(interactive=False)

    agent = get_agent()

except Exception as exc:
    st.error(
        "The application could not initialize. "
        "Check your .env configuration and installed dependencies."
    )
    st.code(f"{type(exc).__name__}: {exc}")
    st.stop()


if "active_student_id" not in st.session_state:
    st.session_state.active_student_id = (
        "STU101" if "STU101" in students else next(iter(students))
    )

if "messages" not in st.session_state:
    st.session_state.messages = []

if "agent_history" not in st.session_state:
    st.session_state.agent_history = []


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div class="brand">✦ Agentic<span style="color:#8fa5ff">AI</span></div>',
        unsafe_allow_html=True,
    )
    st.caption("INTELLIGENT STUDENT SUPPORT")
    st.divider()

    st.markdown("#### Student context")
    st.caption("Demo identity selector — not authentication.")

    student_ids = list(students.keys())
    current_index = (
        student_ids.index(st.session_state.active_student_id)
        if st.session_state.active_student_id in student_ids
        else 0
    )

    selected_student = st.selectbox(
        "Active student",
        student_ids,
        index=current_index,
        format_func=lambda sid: (
            f"{students[sid].get('full_name', sid)} · {sid}"
        ),
    )

    if selected_student != st.session_state.active_student_id:
        st.session_state.active_student_id = selected_student
        st.session_state.messages = []
        st.session_state.agent_history = []
        st.rerun()

    student = students[selected_student]

    st.markdown(
        f"""
        <div class="side-card">
            <div class="side-label">ACTIVE PROFILE</div>
            <div class="side-value">{student.get('full_name', selected_student)}</div>
            <div class="side-label" style="margin-top:8px">STUDENT ID</div>
            <div class="side-value">{selected_student}</div>
            <div class="side-label" style="margin-top:8px">PROGRAMME</div>
            <div class="side-value">{student.get('programme', 'Not specified')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("#### Quick prompts")

    quick_prompts = [
        "What is my current fee status?",
        "Check my academic profile.",
        "What is the scholarship eligibility policy?",
        "The payment portal is failing. What should I do?",
    ]

    for i, prompt in enumerate(quick_prompts):
        if st.button(prompt, key=f"quick_{i}", use_container_width=True):
            st.session_state.pending_prompt = prompt
            st.rerun()

    st.divider()

    if st.button("＋ New conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.agent_history = []
        st.rerun()

    st.markdown(
        """
        <div class="disclaimer">
        Prototype environment · Responses are AI-generated and may require
        verification against official institute policies.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------
# Main chat area
# ---------------------------------------------------------
st.markdown(
    """
    <div class="hero">
        <div class="eyebrow">YOUR DIGITAL CAMPUS ASSISTANT</div>
        <h1>How can I help you<br>today?</h1>
        <p>
            Ask about fees, academic records, scholarships, institute policies,
            or student support. I'll look for relevant handbook information
            and use available tools when needed.
        </p>
        <span class="pill">● AI assistant online</span>
        &nbsp;
        <span class="pill">Policy-grounded responses</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# Session summary
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Conversation messages", len(st.session_state.messages))

with col2:
    st.metric("Student context", st.session_state.active_student_id)

with col3:
    st.metric("Agent", "Ready")

st.divider()

# Render previous messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message["role"] == "assistant" and message.get("meta"):
            meta = message["meta"]

            with st.expander("Agent details · tools, evidence and performance"):
                if meta.get("tools_used"):
                    st.markdown("**Tools used**")
                    st.write(", ".join(meta["tools_used"]))
                else:
                    st.write("No tool calls were made for this response.")

                if meta.get("retrieved_evidence"):
                    st.markdown("**Retrieved evidence**")
                    for evidence in meta["retrieved_evidence"]:
                        st.write(f"• {evidence}")

                if meta.get("memory_notice"):
                    st.info(meta["memory_notice"])

                st.caption(
                    f"Latency: {meta.get('latency_seconds', 0)} seconds · "
                    f"Tokens: {meta.get('total_tokens', 0)}"
                )


# Chat input supports normal user questions and quick prompts.
pending_prompt = st.session_state.pop("pending_prompt", None)
user_prompt = st.chat_input("Ask your student support question…")

if pending_prompt or user_prompt:
    question = pending_prompt or user_prompt

    st.session_state.messages.append({
        "role": "user",
        "content": question,
    })

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Reviewing your question and relevant information…"):
            try:
                output = agent.process_query(
                    query=question,
                    student_id=st.session_state.active_student_id,
                    session_history=st.session_state.agent_history,
                )

                answer = output.get(
                    "answer",
                    "Sorry, I couldn't produce a response.",
                )

                meta = {
                    "tools_used": output.get("tools_used", []),
                    "retrieved_evidence": output.get(
                        "retrieved_evidence", []
                    ),
                    "memory_notice": output.get("memory_notice", ""),
                    "latency_seconds": output.get("latency_seconds", 0),
                    "total_tokens": output.get("total_tokens", 0),
                }

                st.markdown(answer)

                with st.expander("Agent details · tools, evidence and performance"):
                    if meta["tools_used"]:
                        st.markdown("**Tools used**")
                        st.write(", ".join(meta["tools_used"]))
                    else:
                        st.write("No tool calls were made for this response.")

                    if meta["retrieved_evidence"]:
                        st.markdown("**Retrieved evidence**")
                        for evidence in meta["retrieved_evidence"]:
                            st.write(f"• {evidence}")

                    if meta["memory_notice"]:
                        st.info(meta["memory_notice"])

                    st.caption(
                        f"Latency: {meta['latency_seconds']} seconds · "
                        f"Tokens: {meta['total_tokens']}"
                    )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "meta": meta,
                })

                # Keep the same user/assistant history format as the CLI.
                st.session_state.agent_history.append({
                    "role": "user",
                    "content": question,
                })
                st.session_state.agent_history.append({
                    "role": "assistant",
                    "content": answer,
                })

            except Exception:
                st.error(
                    "Something went wrong while processing this request. "
                    "Check the terminal for the technical error. "
                    "Avoid sharing passwords, OTPs, or API keys."
                )


# ---------------------------------------------------------
# Human approval panel
# ---------------------------------------------------------
st.divider()
st.markdown("### Human approval workflow")
st.caption(
    "Demonstration controls for the existing fee-waiver approval workflow. "
    "The current identity is not an authenticated reviewer account."
)

with st.expander("Request a fee waiver"):
    with st.form("waiver_request_form"):
        waiver_amount = st.number_input(
            "Requested waiver amount (₹)",
            min_value=1,
            max_value=1000000,
            value=10000,
            step=1000,
        )
        waiver_reason = st.text_area(
            "Reason for request",
            placeholder="Explain why this fee adjustment is being requested.",
            max_chars=500,
        )

        submit_waiver = st.form_submit_button(
            "Submit for approval",
            type="primary",
            use_container_width=True,
        )

    if submit_waiver:
        if not waiver_reason.strip():
            st.warning("Please provide a reason for the request.")
        else:
            result = request_fee_waiver(
                student_id=st.session_state.active_student_id,
                amount=int(waiver_amount),
                reason=waiver_reason.strip(),
            )

            if result.get("status") == "success":
                st.success(result["message"])
            else:
                st.error(result.get("message", "Request failed."))

with st.expander("Review pending requests"):
    pending_requests = list_pending_approvals()

    if not pending_requests:
        st.info("There are no pending requests.")
    else:
        for request in pending_requests:
            request_id = request["request_id"]

            st.markdown(f"**{request_id}** · {request['requester_id']}")
            st.write(f"Amount: ₹{request['amount']:,}")
            st.write(f"Reason: {request['reason']}")
            st.write(
                f"Balance when requested: "
                f"₹{request['balance_before']:,}"
            )

            approve_col, reject_col = st.columns(2)

            with approve_col:
                if st.button(
                    "Approve",
                    key=f"approve_{request_id}",
                    type="primary",
                    use_container_width=True,
                ):
                    result = decide_approval(
                        request_id=request_id,
                        decision="APPROVE",
                        approver_id=st.session_state.active_student_id,
                    )

                    if result.get("status") == "success":
                        st.success(result["message"])
                    else:
                        st.error(result.get("message", "Approval failed."))

                    st.rerun()

            with reject_col:
                if st.button(
                    "Reject",
                    key=f"reject_{request_id}",
                    use_container_width=True,
                ):
                    result = decide_approval(
                        request_id=request_id,
                        decision="REJECT",
                        approver_id=st.session_state.active_student_id,
                    )

                    if result.get("status") == "success":
                        st.warning(result["message"])
                    else:
                        st.error(result.get("message", "Rejection failed."))

                    st.rerun()

            st.divider()
