from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, ValidationError
import json
from typing import Dict, Optional, List

app = FastAPI(title="nook")

class DeployConfig(BaseModel):
    app_name: str
    subdomain: str
    env_vars: Dict[str, str] = {}
    volumes: Optional[List[str]] = []

@app.get("/health")
def health_check():
    return {"status": "online", "version": "0.0.1"}

@app.post("/deploy")
async def deploy_app(
    file: UploadFile = File(...),
    config_str: str = Form(...) 
):
    try:
        config_data = json.loads(config_str)
        config = DeployConfig(**config_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in config_str")
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

    return {
        "status": "success",
        "message": f"Payload received for {config.app_name}",
        "filename": file.filename
    }