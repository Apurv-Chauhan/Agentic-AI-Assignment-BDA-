import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Resolve project base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

POLICY_FILE = DATA_DIR / "student_handbook.md"
STUDENTS_DB_FILE = DATA_DIR / "students_db.json"
TICKETS_DB_FILE = DATA_DIR / "tickets_db.json"
MEMORY_STORE_FILE = DATA_DIR / "memory_store.json"

LOGS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Load existing .env if present
load_dotenv(BASE_DIR / ".env")

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
FALLBACK_MODEL = "openai/gpt-oss-20b"

def get_api_key() -> str:
    """Return the currently configured Groq API key, or empty string."""
    return os.getenv("GROQ_API_KEY", "").strip()

def ensure_api_key(interactive: bool = True) -> str:
    """
    Ensure a Groq API key is configured.
    If missing, prompts the user directly in the terminal and optionally
    saves to .env for convenience.
    """
    api_key = get_api_key()
    if api_key:
        return api_key

    if not interactive:
        raise ValueError("GROQ_API_KEY is not set in environment or .env file.")

    print("\n" + "=" * 65)
    print("      AGENTIC AI ENGINEERING: STUDENT SUPPORT AGENT")
    print("=" * 65)
    print("[!] Groq API Key is required to run the agent.")
    print("    You can get a free key from: https://console.groq.com/keys\n")

    while True:
        try:
            entered_key = input("Enter your Groq API Key: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            sys.exit(1)

        if not entered_key:
            print(">> API Key cannot be empty. Please try again.")
            continue

        if not entered_key.startswith("gsk_") and len(entered_key) < 20:
            print(">> Warning: Typical Groq keys start with 'gsk_'. Please ensure it is valid.")

        os.environ["GROQ_API_KEY"] = entered_key

        # Prompt to save to .env
        try:
            save_choice = input("Would you like to save this key to .env for future runs? (y/n) [default: y]: ").strip().lower()
            if save_choice in ("", "y", "yes"):
                env_file = BASE_DIR / ".env"
                with open(env_file, "a", encoding="utf-8") as f:
                    f.write(f"\nGROQ_API_KEY={entered_key}\n")
                print(f"[✓] Saved to {env_file.name} (protected by .gitignore).")
        except Exception as e:
            print(f"[!] Could not save to .env: {e}")

        return entered_key
