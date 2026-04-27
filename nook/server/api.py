import os
import json
import shutil
import zipfile
import tempfile
import socket
import docker
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional, List

app = FastAPI(title="nook-server")

try:
    docker_client = docker.from_env()
except Exception:
    docker_client = None

class DeployConfig(BaseModel):
    app_name: str
    subdomain: str
    env_vars: Dict[str, str] = {}
    volumes: Optional[List[str]] = []

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

@app.post("/deploy")
async def deploy_app(file: UploadFile = File(...), config_str: str = Form(...)):
    if not docker_client:
         raise HTTPException(status_code=500, detail="Docker engine not available.")

    config = DeployConfig(**json.loads(config_str))
    print(f"Deploying {config.app_name}...")

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, "app.zip")
        extract_path = os.path.join(temp_dir, "source")
        os.makedirs(extract_path)

        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

        print(f"Building Docker image...")
        image, _ = docker_client.images.build(path=extract_path, tag=f"{config.app_name}:latest", rm=True)

        try:
            old_container = docker_client.containers.get(config.app_name)
            old_container.stop()
            old_container.remove()
        except docker.errors.NotFound:
            pass 

        host_port = get_free_port()
        print(f"Starting container on port {host_port}...")
        
        container = docker_client.containers.run(
            image=f"{config.app_name}:latest",
            name=config.app_name,
            detach=True,
            environment=config.env_vars,
            ports={'8000/tcp': host_port}, 
            restart_policy={"Name": "always"}
        )

    return {"status": "success", "app_name": config.app_name, "host_port": host_port}

def start_daemon(port: int = 8000):
    print(f"Starting PaaS Daemon on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")