import os
import json
import shutil
import zipfile
import tempfile
import socket
import docker
import uvicorn
import secrets
import hashlib
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Dict, Optional, List
from nook.server.config import initialize_server, verify_token, get_server_config
from nook.server.router import update_nginx_config

try:
    docker_client = docker.from_env()
except Exception:
    docker_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    yield
    # Shutdown logic
    if docker_client:
        try:
            docker_client.close()
        except Exception:
            pass

app = FastAPI(title="nook-server", lifespan=lifespan)

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
            labels={"managed_by": "nook"},
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
            
            from nook.server.router import provision_ssl
            provision_ssl(config.subdomain)

        except Exception as e:
            return {
                "status": "partial_success",
                "host_port": host_port,
                "message": f"App is running on port {host_port}, but Nginx routing or SSL failed: {str(e)}"
            }
            
    config_obj = get_server_config()
    full_url = f"https://{config.subdomain}.{config_obj['base_domain']}"

    return {
        "status": "success",
        "app_name": config.app_name,
        "host_port": host_port,
        "url": full_url,
        "message": "App is live with SSL encryption!"
    }


@app.get("/apps", dependencies=[Depends(verify_token)])
async def list_apps():
    containers = docker_client.containers.list(all=True, filters={"label": "managed_by=nook"})
    return [
        {
            "name": c.name,
            "status": c.status,
            "id": c.short_id,
            "ports": c.ports
        } for c in containers
    ]

@app.post("/apps/{name}/{action}", dependencies=[Depends(verify_token)])
async def manage_app(name: str, action: str):
    try:
        container = docker_client.containers.get(name)
        if action == "start":
            container.start()
        elif action == "stop":
            container.stop()
        elif action == "pause":
            container.pause()
        elif action == "unpause":
            container.unpause()
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
        return {"status": "success", "message": f"App {name} {action}ed."}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="App not found")

@app.delete("/apps/{name}", dependencies=[Depends(verify_token)])
async def delete_app(name: str):
    from nook.server.router import remove_nginx_config
    try:
        container = docker_client.containers.get(name)
        container.stop()
        container.remove()
        remove_nginx_config(name)
        return {"status": "success", "message": f"App {name} removed completely."}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail="App not found")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_view(request: Request):
    import sys
    if getattr(sys, 'frozen', False):
        template_dir = os.path.join(sys._MEIPASS, "nook", "server")
    else:
        template_dir = os.path.dirname(__file__)
        
    from fastapi.templating import Jinja2Templates
    templates = Jinja2Templates(directory=template_dir)
    
    is_authenticated = False
    apps = []
    error = request.query_params.get("error")
    
    token = request.cookies.get("nook_token")
    if token:
        config = get_server_config()
        if config:
            incoming_hash = hashlib.sha256(token.encode()).hexdigest()
            if secrets.compare_digest(incoming_hash, config["token_hash"]):
                is_authenticated = True
                
    sys_info = {}
    if is_authenticated and docker_client:
        containers = docker_client.containers.list(all=True, filters={"label": "managed_by=nook"})
        config_data = get_server_config()
        base_domain = config_data.get("base_domain", "") if config_data else ""
        
        for c in containers:
            apps.append({
                "name": c.name,
                "status": c.status,
                "id": c.short_id,
                "url": f"https://{c.name}.{base_domain}" if base_domain else ""
            })
            
        try:
            info = docker_client.info()
            sys_info = {
                "app_count": len(apps),
                "ncpu": info.get("NCPU", 0),
                "mem_total_gb": round(info.get("MemTotal", 0) / (1024**3), 2)
            }
        except Exception:
            pass
            
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html", 
        context={
            "request": request, 
            "is_authenticated": is_authenticated, 
            "apps": apps,
            "error": error,
            "sys_info": sys_info
        }
    )

@app.post("/dashboard/login")
async def dashboard_login(token: str = Form(...)):
    config = get_server_config()
    if not config:
        return RedirectResponse(url="/dashboard?error=Server+not+initialized", status_code=303)
        
    incoming_hash = hashlib.sha256(token.encode()).hexdigest()
    if not secrets.compare_digest(incoming_hash, config["token_hash"]):
        return RedirectResponse(url="/dashboard?error=Invalid+token", status_code=303)
        
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="nook_token", value=token, httponly=True)
    return response

@app.get("/dashboard/logout")
async def dashboard_logout():
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.delete_cookie("nook_token")
    return response

@app.post("/dashboard/action")
async def dashboard_action(request: Request, app_name: str = Form(...), action: str = Form(...)):
    token = request.cookies.get("nook_token")
    config = get_server_config()
    if not token or not config:
        return RedirectResponse(url="/dashboard", status_code=303)
        
    incoming_hash = hashlib.sha256(token.encode()).hexdigest()
    if not secrets.compare_digest(incoming_hash, config["token_hash"]):
        return RedirectResponse(url="/dashboard", status_code=303)
        
    try:
        container = docker_client.containers.get(app_name)
        if action == "start":
            container.start()
        elif action == "stop":
            container.stop()
        elif action == "delete":
            container.stop()
            container.remove()
            from nook.server.router import remove_nginx_config
            remove_nginx_config(app_name)
    except Exception as e:
        pass
        
    return RedirectResponse(url="/dashboard", status_code=303)

def start_daemon(domain: str, port: int = 8000):
    initialize_server(domain = domain)
    
    from nook.server.router import update_nginx_config, provision_ssl
    try:
        update_nginx_config(app_name="nook-api", subdomain="api", host_port=port)
        provision_ssl("api")
    except Exception as e:
        print(f"Failed to setup Nginx/SSL for API: {e}")
        
    print(f"Starting PaaS Daemon locally on port {port}...")
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    except (KeyboardInterrupt, SystemExit):
        pass