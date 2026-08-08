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

    choice = input("      Install/Upgrade required packages via pip? [Y/n]: ").strip().lower()
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
    env_example = Path(__file__).parent / ".env.example"

    existing_config = {}
    if env_path.exists():
        print(f"      Notice: Existing .env file found at {env_path.name}.")
        overwrite = input("      Do you want to re-configure and overwrite it? [y/N]: ").strip().lower()
        if overwrite not in ("y", "yes"):
            print("      Keeping existing .env file.")
            print()
            return

        # Load existing values as defaults
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    existing_config[key.strip()] = val.strip()

    print("\n      --- Interactive Configuration ---")
    print("      Select Primary LLM Provider:")
    print("        1) stub   — Simulation mode (No API keys needed, offline testing)")
    print("        2) openai — OpenAI API (Requires valid OPENAI_API_KEY)")
    print("        3) ollama — Local Ollama LLM instance")

    provider_map = {"1": "stub", "2": "openai", "3": "ollama"}
    default_provider = existing_config.get("LLM_PROVIDER", "stub")

    p_choice = input(f"      Choose provider [1-3] (default: {default_provider}): ").strip()
    llm_provider = provider_map.get(p_choice, p_choice if p_choice in provider_map.values() else default_provider)

    # OpenAI API Key
    openai_key_default = existing_config.get("OPENAI_API_KEY", "dummy-openai-api-key-value")
    if llm_provider == "openai":
        openai_key = input("      Enter your OpenAI API Key: ").strip()
        if not openai_key:
            openai_key = openai_key_default
    else:
        openai_key_prompt = input(f"      Enter OpenAI API Key (optional, press Enter for default/dummy): ").strip()
        openai_key = openai_key_prompt if openai_key_prompt else openai_key_default

    # Ollama Host
    ollama_default = existing_config.get("OLLAMA_HOST", "http://localhost:11434")
    ollama_host = input(f"      Enter Ollama Host URL (default: {ollama_default}): ").strip()
    if not ollama_host:
        ollama_host = ollama_default

    # Webhook URL
    webhook_default = existing_config.get("WEBHOOK_URL", "http://localhost:8080/dummy-webhook")
    webhook_url = input(f"      Enter Webhook URL for alerts (default: {webhook_default}): ").strip()
    if not webhook_url:
        webhook_url = webhook_default

    # Fallback Provider
    fallback_default = existing_config.get("FALLBACK_PROVIDER", "stub")
    fallback_provider = input(f"      Enter Fallback LLM Provider (default: {fallback_default}): ").strip()
    if not fallback_provider:
        fallback_provider = fallback_default

    # Database & Vector DB paths
    db_default = existing_config.get("DB_PATH", "council.db")
    db_path = input(f"      Enter SQLite Database Path (default: {db_default}): ").strip()
    if not db_path:
        db_path = db_default

    chroma_default = existing_config.get("CHROMA_DB_PATH", "chroma_db")
    chroma_path = input(f"      Enter ChromaDB Storage Path (default: {chroma_default}): ").strip()
    if not chroma_path:
        chroma_path = chroma_default

    # Construct .env file content
    env_content = f"""# Research Consensus Council — Generated Environment Configuration

# Primary LLM Provider: stub | ollama | openai
LLM_PROVIDER={llm_provider}

# Fallback LLM Provider (used if primary circuit trips)
FALLBACK_PROVIDER={fallback_provider}

# OpenAI API Key
OPENAI_API_KEY={openai_key}

# Webhook URL for alerts and state notifications
WEBHOOK_URL={webhook_url}

# Ollama local host URL
OLLAMA_HOST={ollama_host}

# SQLite Database Storage path
DB_PATH={db_path}

# ChromaDB Vector Store Path
CHROMA_DB_PATH={chroma_path}
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
        print("      (You can install frontend dependencies manually in ./frontend using npm install)")
        return

    choice = input("      Install frontend dependencies via npm in ./frontend? [y/N]: ").strip().lower()
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
    print("\n   To start the API Server & Live Web Dashboard:")
    print("      python council.py --api")
    print("   Or access the dashboard at: http://127.0.0.1:8080")
    print("\n   To run a CLI deliberation on a paper:")
    print("      python council.py <paper.pdf>\n")


if __name__ == "__main__":
    main()
