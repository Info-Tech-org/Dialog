#!/usr/bin/env python3
"""
One-shot setup for local backend/.env. Prompts for secrets and writes backend/.env.
Run from repo root: python scripts/setup_local_env.py
Existing .env is not overwritten unless you choose to.
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(REPO_ROOT, "backend")
ENV_PATH = os.path.join(BACKEND_DIR, ".env")
EXAMPLE_PATH = os.path.join(BACKEND_DIR, ".env.example")


def get_input(prompt: str, default: str = "", secret: bool = False) -> str:
    if default and not secret:
        prompt = f"{prompt} [{default}]"
    prompt = prompt + ": "
    if secret:
        try:
            import getpass
            return (getpass.getpass(prompt) or default).strip()
        except Exception:
            return (input(prompt) or default).strip()
    return (input(prompt) or default).strip()


def main() -> None:
    os.chdir(REPO_ROOT)
    if not os.path.isdir(BACKEND_DIR):
        print("backend/ not found. Run from repo root.")
        sys.exit(1)

    if os.path.exists(ENV_PATH):
        overwrite = get_input("backend/.env exists. Overwrite? (y/N)", "n").lower()
        if overwrite != "y":
            print("Leaving existing .env unchanged. Edit backend/.env manually if needed.")
            return

    # Build .env from example and prompt for key secrets
    lines = []
    if os.path.exists(EXAMPLE_PATH):
        with open(EXAMPLE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if line.startswith("TENCENT_SECRET_ID=") and not line.split("=", 1)[1].strip():
                    val = get_input("TENCENT_SECRET_ID (Tencent Cloud)", secret=True)
                    lines.append(f"TENCENT_SECRET_ID={val}")
                elif line.startswith("TENCENT_SECRET_KEY=") and not line.split("=", 1)[1].strip():
                    val = get_input("TENCENT_SECRET_KEY (Tencent Cloud)", secret=True)
                    lines.append(f"TENCENT_SECRET_KEY={val}")
                elif line.startswith("OPENROUTER_API_KEY=") and not line.split("=", 1)[1].strip():
                    val = get_input("OPENROUTER_API_KEY (OpenRouter / LLM)", secret=True)
                    lines.append(f"OPENROUTER_API_KEY={val}")
                else:
                    lines.append(line)
    else:
        lines = [
            "TENCENT_SECRET_ID=" + get_input("TENCENT_SECRET_ID (Tencent Cloud)", secret=True),
            "TENCENT_SECRET_KEY=" + get_input("TENCENT_SECRET_KEY (Tencent Cloud)", secret=True),
            "OPENROUTER_API_KEY=" + get_input("OPENROUTER_API_KEY (OpenRouter)", secret=True),
            "DATABASE_URL=sqlite:///./familymvp.db",
            "WS_HOST=0.0.0.0",
            "WS_PORT=8000",
            "JWT_SECRET_KEY=change-me-in-production",
            "OPENROUTER_MODEL=google/gemma-3-27b-it",
        ]

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {ENV_PATH}. You can edit it to add COS, EMBEDDING_*, etc.")


if __name__ == "__main__":
    main()
