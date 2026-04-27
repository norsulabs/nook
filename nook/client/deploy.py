import os
import json
import shutil
import tempfile
import httpx
import typer

def push_to_server(app_name: str, subdomain: str, env_vars: dict, server_url: str):
    current_dir = os.getcwd()
    
    if not os.path.exists(os.path.join(current_dir, "Dockerfile")):
        typer.secho("Error: No Dockerfile found in current directory.", fg=typer.colors.RED)
        raise typer.Exit(1)

    typer.echo(f"Packaging {app_name}...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, "payload")
        shutil.make_archive(zip_path, 'zip', current_dir)
        final_zip_path = f"{zip_path}.zip"

        config_payload = {
            "app_name": app_name,
            "subdomain": subdomain,
            "env_vars": env_vars
        }

        typer.echo(f"Uploading to {server_url}...")
        
        with open(final_zip_path, "rb") as f:
            files = {'file': (f"{app_name}.zip", f, "application/zip")}
            data = {'config_str': json.dumps(config_payload)}
            
            try:
                response = httpx.post(f"{server_url}/deploy", files=files, data=data, timeout=600.0)
                response.raise_for_status()
                
                result = response.json()
                typer.secho(f"✅ Success! {app_name} is running on host port {result['host_port']}", fg=typer.colors.GREEN)
                
            except httpx.HTTPStatusError as e:
                typer.secho(f"Server Error: {e.response.text}", fg=typer.colors.RED)
            except httpx.RequestError as e:
                typer.secho(f"Connection Error: Could not reach daemon at {server_url}", fg=typer.colors.RED)