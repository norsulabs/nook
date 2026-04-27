import os
import json
from pathlib import Path
import typer

CONFIG_DIR = Path.home() / ".config" / "nook"
CONFIG_FILE = CONFIG_DIR / "config.json"

def save_config(token: str, server_url: str):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_data = {
        "api_token": token,
        "server_url": server_url
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_data, f)

def load_config():
    if not CONFIG_FILE.exists():
        typer.secho("Error: Not logged in. Run 'nook login' first.", fg=typer.colors.RED)
        raise typer.Exit(1)
    
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)