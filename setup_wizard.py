#!/usr/bin/env python3
"""
Research Consensus Council (RCC) — Interactive Setup Wizard
Automates installation of required Python dependencies and configures the environment (.env file).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def safe_input(prompt_text: str, default: str = "") -> str:
    """Non-interactive safe input reader."""
    if not sys.stdin.isatty():
        print(f"{prompt_text}{default}")
        return default
    try:
        val = input(prompt_text).strip()
        return val if val else default
    except (EOFError, KeyboardInterrupt):
        print(f"\n[INFO] Non-interactive mode detected. Using default: '{default}'")
        return default


def print_banner():
    print("=" * 65)
    print("   Research Consensus Council (RCC) — Setup & Installation Wizard")
    print("=" * 65)
    print()


def check_python_version():
    print("[1/5] Checking Python environment...")
    v = sys.version_info
    print(f"      Detected Python {v.major}.{v.minor}.{v.micro}")
    if v.major < 3 or (v.major == 3 and v.minor < 10):
        print("      [WARNING] Python 3.10 or higher is recommended.")
    else:
        print("      [OK] Python version is compatible.")
    print()


def install_dependencies():
    print("[2/5] Installing Python dependencies...")
    req_file = Path(__file__).parent / "requirements.txt"
    if not req_file.exists():
        print("      [ERROR] requirements.txt not found.")
        sys.exit(1)

    choice = safe_input("      Install/Upgrade required packages via pip? [Y/n]: ", "y").lower()
    if choice in ("", "y", "yes"):
        cmd = [sys.executable, "-m", "pip", "install", "-r", str(req_file)]
        print(f"      Running: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True)
            print("      [OK] All Python dependencies installed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"      [ERROR] Pip installation failed: {e}")
            sys.exit(1)
    else:
        print("      Skipped pip installation.")
    print()


def prompt_env_config():
    print("[3/5] Configuring Environment Settings (.env file)...")
    env_path = Path(__file__).parent / ".env"

    existing_config = {}
    if env_path.exists():
        print(f"      Notice: Existing .env file found at {env_path.name}.")
        overwrite = safe_input("      Do you want to re-configure and overwrite it? [y/N]: ", "n").lower()
        if overwrite not in ("y", "yes"):
            print("      Keeping existing .env file.")
            print()
            return

        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    existing_config[key.strip()] = val.strip()

    print("\n      --- Interactive Configuration ---")
    provider_map = {"1": "stub", "2": "openai", "3": "ollama"}
    default_provider = existing_config.get("LLM_PROVIDER", "stub")

    p_choice = safe_input(f"      Choose provider [1-3] (default: {default_provider}): ", default_provider)
    llm_provider = provider_map.get(p_choice, p_choice if p_choice in provider_map.values() else default_provider)

    openai_key_default = existing_config.get("OPENAI_API_KEY", "dummy_openai_key")
    openai_key = safe_input("      Enter OpenAI API Key (optional): ", openai_key_default)

    ollama_default = existing_config.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    ollama_host = safe_input(f"      Enter Ollama Host URL (default: {ollama_default}): ", ollama_default)

    webhook_default = existing_config.get("WEBHOOK_URL", "http://127.0.0.1:8090/dummy-webhook")
    webhook_url = safe_input(f"      Enter Webhook URL for alerts (default: {webhook_default}): ", webhook_default)

    fallback_default = existing_config.get("FALLBACK_PROVIDER", "stub")
    fallback_provider = safe_input(f"      Enter Fallback LLM Provider (default: {fallback_default}): ", fallback_default)

    db_default = existing_config.get("DB_PATH", "council.db")
    db_path = safe_input(f"      Enter SQLite Database Path (default: {db_default}): ", db_default)

    chroma_default = existing_config.get("CHROMA_DB_PATH", "chroma_db")
    chroma_path = safe_input(f"      Enter ChromaDB Storage Path (default: {chroma_default}): ", chroma_path)

    env_content = f"""# Research Consensus Council — Generated Environment Configuration

LLM_PROVIDER={llm_provider}
FALLBACK_PROVIDER={fallback_provider}
OPENAI_API_KEY={openai_key}
WEBHOOK_URL={webhook_url}
OLLAMA_HOST={ollama_host}
DB_PATH={db_path}
CHROMA_DB_PATH={chroma_path}
RETRIEVAL_BACKEND=hybrid
"""

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)

    print(f"      [OK] Configuration saved to {env_path.name}")
    print()


def init_database():
    print("[4/5] Initializing Database Schema...")
    try:
        import db
        db.init_db()
        print("      [OK] Database schema initialized successfully.")
    except Exception as e:
        print(f"      [WARNING] Could not initialize database directly: {e}")
    print()


def setup_frontend():
    print("[5/5] Checking Frontend Dependencies...")
    frontend_dir = Path(__file__).parent / "frontend"
    if not frontend_dir.exists():
        print("      Frontend directory not found. Skipping.")
        return

    npm_path = shutil.which("npm")
    if not npm_path:
        print("      npm not detected on system PATH. Skipping frontend setup.")
        return

    choice = safe_input("      Install frontend dependencies via npm in ./frontend? [y/N]: ", "n").lower()
    if choice in ("y", "yes"):
        try:
            print(f"      Running npm install in {frontend_dir}...")
            subprocess.run([npm_path, "install"], cwd=str(frontend_dir), check=True)
            print("      [OK] Frontend dependencies installed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"      [WARNING] npm install encountered an error: {e}")
    else:
        print("      Skipped frontend installation.")
    print()


def main():
    print_banner()
    check_python_version()
    install_dependencies()
    prompt_env_config()
    init_database()
    setup_frontend()

    print("=" * 65)
    print("   [SUCCESS] RCC Setup Completed!")
    print("=" * 65)


if __name__ == "__main__":
    main()
