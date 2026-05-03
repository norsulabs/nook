import os
import json
import secrets
import hashlib
from pathlib import Path
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

CONFIG_DIR = Path.home() / ".config" / "nook-server"
CONFIG_FILE = CONFIG_DIR / "config.json"
security = HTTPBearer()

def get_server_config():
    if not CONFIG_FILE.exists():
        return None
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def initialize_server(domain: str):
    if CONFIG_FILE.exists():
        return None

    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_data = {
        "token_hash": token_hash,
        "base_domain": domain
    }

    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f)

    return raw_token

def generate_new_token():
    config_data = get_server_config()
    if not config_data:
        return None

    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    
    config_data["token_hash"] = token_hash

    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f)

    return raw_token

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    config = get_server_config()
    if not config:
        raise HTTPException(status_code=500, detail="Server not initialized.")

    incoming_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    if not secrets.compare_digest(incoming_hash, config["token_hash"]):
        raise HTTPException(status_code=401, detail="Invalid API Token")
    return True