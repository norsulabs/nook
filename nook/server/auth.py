import os
import json
import secrets
import hashlib
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SERVER_CONFIG_DIR = os.path.expanduser("~/.config/nook-server")
SERVER_CONFIG_FILE = os.path.join(SERVER_CONFIG_DIR, "auth.json")

security = HTTPBearer()

def initialize_server_auth():
    if os.path.exists(SERVER_CONFIG_FILE):
        return
    raw_token = secrets.token_hex(32)
    
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    os.makedirs(SERVER_CONFIG_DIR, exist_ok=True)
    with open(SERVER_CONFIG_FILE, "w") as f:
        json.dump({"token_hash": token_hash}, f)

    print("\n" + "="*55)
    print("FIRST RUN INITIALIZATION")
    print("Save this API Token now. It will NEVER be shown again.")
    print(f"Token: {raw_token}")
    print("="*55 + "\n")

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    if not os.path.exists(SERVER_CONFIG_FILE):
        raise HTTPException(status_code=500, detail="Server auth not initialized.")

    with open(SERVER_CONFIG_FILE, "r") as f:
        config = json.load(f)

    incoming_token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()

    if not secrets.compare_digest(incoming_token_hash, config["token_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return True