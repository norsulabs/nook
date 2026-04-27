import os
import json
import shutil
import zipfile
import tempfile
import socket
import docker
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Optional, List
from nook.server.config import initialize_server, verify_token, get_server_config
from nook.server.router import update_nginx_config

app = FastAPI(title="nook-server")

try:
    docker_client = docker.from_env()
except Exception:
    docker_client = None

class DeployConfig(BaseModel):
    app_name: str
    subdomain: str
    app_port: int = 8000
    env_vars: Dict[str, str] = {}
    volumes: Optional[List[str]] = []

def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

@app.post("/deploy", dependencies=[Depends(verify_token)])
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
            ports={f'{config.app_port}/tcp': host_port}, 
            restart_policy={"Name": "always"}
        )

        try:
            update_nginx_config(
                app_name=config.app_name, 
                subdomain=config.subdomain, 
                host_port=host_port
            )
        except Exception as e:
            return {
                "status": "partial_success",
                "host_port": host_port,
                "message": f"App is running on port {host_port}, but Nginx routing failed: {str(e)}"
            }
            
    config_obj = get_server_config()
    full_url = f"http://{config.subdomain}.{config_obj['base_domain']}"

    return {
        "status": "success",
        "app_name": config.app_name,
        "host_port": host_port,
        "url": full_url,
        "message": "App is live and routed."
    }

def start_daemon(domain: str, port: int = 8000):
    initialize_server(domain = domain)
    print(f"Starting PaaS Daemon on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")