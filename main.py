
import sys
import json
from colorama import init, Fore, Style

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.config import ensure_api_key, STUDENTS_DB_FILE
from src.agent import StudentSupportAgent
from src.policy_retriever import PolicyRetriever
from src.memory import MemoryManager
from src.approvals import (
    request_fee_waiver,
    list_pending_approvals,
    decide_approval,
)
from evaluate import run_evaluation_suite

init(autoreset=True)


def load_students():
    if not STUDENTS_DB_FILE.exists():
        return {}
    with open(STUDENTS_DB_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def confirm_decision(action, request_id):
    expected = f"{action} {request_id}"
    print(f"\nHuman confirmation required. Type exactly: {expected}")
    try:
        answer = input("> ").strip().upper()
    except (KeyboardInterrupt, EOFError):
        return False
    return answer == expected.upper()


def show_approvals():
    pending = list_pending_approvals()

    if not pending:
        print("No pending approval requests.\n")
        return

    print("\n--- Pending Approval Requests ---")
    for request in pending:
        print(f"Request ID: {request['request_id']}")
        print(f"Student: {request['requester_id']}")
        print(f"Action: {request['action']}")
        print(f"Amount: ₹{request['amount']:,}")
        print(f"Reason: {request['reason']}")
        print(f"Balance at request time: ₹{request['balance_before']:,}")
        print(f"Status: {request['status']}")
        print("-" * 40)
    print()


def main():
    print(
        f"\n{Fore.CYAN}{Style.BRIGHT}"
        "========================================================================"
    )
    print("      AGENTIC AI ENGINEERING: INTELLIGENT STUDENT SUPPORT AGENT")
    print("            PGDM (Big Data Analytics / AI & Data Science)")
    print("========================================================================" + Style.RESET_ALL)

    ensure_api_key(interactive=True)

    retriever = PolicyRetriever()
    memory = MemoryManager()
    agent = StudentSupportAgent(retriever=retriever, memory=memory)
    students = load_students()

    current_student_id = "STU101"

    if current_student_id not in students and students:
        current_student_id = next(iter(students))

    student_info = students.get(current_student_id, {})
    student_name = student_info.get("full_name", current_student_id)
    programme = student_info.get("programme", "Not specified")

    print(f"\n{Fore.GREEN}Active Student:{Style.RESET_ALL} {student_name} [{current_student_id}]")
    print(f"{Fore.GREEN}Programme:{Style.RESET_ALL}      {programme}")
    print(
        f"{Fore.YELLOW}Commands:{Style.RESET_ALL} "
        "'/eval' | '/student <ID>' | '/request-waiver <amount> <reason>' | "
        "'/approvals' | '/approve <ID>' | '/reject <ID>' | 'exit'\n"
    )
    print(
        f"{Fore.YELLOW}DEMO SECURITY NOTICE:{Style.RESET_ALL} "
        "Student switching and approval reviewer identity are not authenticated.\n"
    )
    print(
        f"{Fore.WHITE}Agent: Hello! I am your AI Student Support Agent. "
        f"How can I assist you today?{Style.RESET_ALL}\n"
    )

    history = []

    while True:
        try:
            prompt = input(
                f"{Fore.BLUE}{Style.BRIGHT}"
                f"[{current_student_id}] You > {Style.RESET_ALL}"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting session. Goodbye!")
            break

        if not prompt:
            continue

        lower = prompt.lower()

        if lower in ("exit", "quit", "/exit", "/quit"):
            print("Session ended. Goodbye!")
            break

        if lower == "/eval":
            run_evaluation_suite()
            continue

        if lower == "/approvals":
            show_approvals()
            continue

        if lower.startswith("/request-waiver"):
            parts = prompt.split(maxsplit=2)

            if len(parts) < 3:
                print(
                    "Usage: /request-waiver <amount> <reason>\n"
                    "Example: /request-waiver 10000 Approved hardship request\n"
                )
                continue

            result = request_fee_waiver(
                student_id=current_student_id,
                amount=parts[1],
                reason=parts[2],
            )
            print(f"\n{result['message']}\n")
            continue

        if lower.startswith("/approve ") or lower.startswith("/reject "):
            parts = prompt.split()

            if len(parts) != 2:
                print("Usage: /approve <REQUEST_ID> or /reject <REQUEST_ID>\n")
                continue

            action = "APPROVE" if lower.startswith("/approve ") else "REJECT"
            request_id = parts[1].upper()

            if not confirm_decision(action, request_id):
                print("Confirmation did not match. No action was taken.\n")
                continue

            result = decide_approval(
                request_id=request_id,
                decision=action,
                approver_id=current_student_id,
            )
            print(f"\n{result['message']}\n")
            continue

        if lower.startswith("/student"):
            parts = prompt.split()

            if len(parts) > 1:
                new_id = parts[1].upper()

                if new_id in students:
                    current_student_id = new_id
                    info = students[new_id]
                    print(
                        f"{Fore.GREEN}[OK] Demo identity switched to "
                        f"{info.get('full_name', new_id)} ({new_id})."
                        f"{Style.RESET_ALL}\n"
                    )
                    history = []
                else:
                    print(
                        f"{Fore.RED}[!] Student ID not found."
                        f"{Style.RESET_ALL}\n"
                    )
            else:
                print(f"Active demo identity: {current_student_id}\n")
            continue

        output = agent.process_query(
            query=prompt,
            student_id=current_student_id,
            session_history=history,
        )

        if output.get("tools_used"):
            print(
                f"{Fore.MAGENTA}[Tool Used]: "
                f"{', '.join(output['tools_used'])}{Style.RESET_ALL}"
            )

        if output.get("retrieved_evidence"):
            print(
                f"{Fore.CYAN}[Evidence]: "
                f"{', '.join(output['retrieved_evidence'])}{Style.RESET_ALL}"
            )

        if output.get("memory_notice"):
            print(
                f"{Fore.YELLOW}[Security Guard]: "
                f"{output['memory_notice']}{Style.RESET_ALL}"
            )

        print(f"\n{Fore.WHITE}{Style.BRIGHT}Agent:{Style.RESET_ALL} {output['answer']}")
        print(
            f"{Fore.LIGHTBLACK_EX}[Latency: {output['latency_seconds']}s | "
            f"Tokens: {output['prompt_tokens']} prompt + "
            f"{output['completion_tokens']} completion = "
            f"{output['total_tokens']} total]{Style.RESET_ALL}\n"
        )

        history.append({"role": "user", "content": prompt})
        history.append({"role": "assistant", "content": output["answer"]})


if __name__ == "__main__":
    main()
