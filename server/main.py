from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, ValidationError
import json
from typing import Dict, Optional, List

app = FastAPI(title="nook")

try:
    docker_client = docker.from_env()
except docker.errors.DockerException:
    print("Warning: Docker is not running or accessible.")
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

@app.get("/health")
def health_check():
    return {"status": "online", "version": "0.0.1"}

@app.post("/deploy")
async def deploy_app(
    file: UploadFile = File(...),
    config_str: str = Form(...) 
):
    if not docker_client:
         raise HTTPException(status_code=500, detail="Docker engine not available on host.")

    try:
        config = DeployConfig(**json.loads(config_str))
    except (json.JSONDecodeError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    print(f"\nStarting deployment for: {config.app_name}")

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, "app.zip")
        extract_path = os.path.join(temp_dir, "source")
        os.makedirs(extract_path)

        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
            
        if not os.path.exists(os.path.join(extract_path, "Dockerfile")):
            raise HTTPException(status_code=400, detail="No Dockerfile found in the root of the uploaded zip.")

        print(f"Building Docker image for {config.app_name}...")
        try:
            image, build_logs = docker_client.images.build(
                path=extract_path,
                tag=f"{config.app_name}:latest",
                rm=True
            )
        except docker.errors.BuildError as e:
             raise HTTPException(status_code=500, detail=f"Docker build failed: {e}")

        try:
            old_container = docker_client.containers.get(config.app_name)
            print(f"Stopping old container...")
            old_container.stop()
            old_container.remove()
        except docker.errors.NotFound:
            pass

        host_port = get_free_port()
        print(f"Starting container on port {host_port}...")
        
        try:
            container = docker_client.containers.run(
                image=f"{config.app_name}:latest",
                name=config.app_name,
                detach=True,
                environment=config.env_vars,
                ports={'8000/tcp': host_port}, 
                restart_policy={"Name": "always"}
            )
        except docker.errors.APIError as e:
            raise HTTPException(status_code=500, detail=f"Failed to start container: {e}")

    return {
        "status": "success",
        "app_name": config.app_name,
        "container_id": container.short_id,
        "host_port": host_port,
        "message": "App built and running."
    }