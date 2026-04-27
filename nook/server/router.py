import os
import subprocess
import typer
from nook.server.config import get_server_config

NGINX_CONF_DIR = "/etc/nginx/conf.d"

NGINX_TEMPLATE = """
server {{
    listen 80;
    server_name {subdomain}.{base_domain};

    location / {{
        proxy_pass http://127.0.0.1:{host_port};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""

def update_nginx_config(app_name: str, subdomain: str, host_port: int):
    config = get_server_config()
    if not config:
        raise Exception("Server configuration missing.")

    base_domain = config["base_domain"]
    
    config_content = NGINX_TEMPLATE.format(
        subdomain=subdomain,
        base_domain=base_domain,
        host_port=host_port
    )

    config_path = os.path.join(NGINX_CONF_DIR, f"{app_name}.conf")

    try:
        with open(config_path, "w") as f:
            f.write(config_content)
        print(f"Created Nginx config at {config_path}")
    except PermissionError:
        print(f"Error: Permission denied. Run nook server with sudo to write to {NGINX_CONF_DIR}")
        return

    try:
        subprocess.run(["sudo", "nginx", "-s", "reload"], check=True)
        print("Nginx reloaded successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to reload Nginx: {e}")

def remove_nginx_config(app_name: str):
    config_path = os.path.join(NGINX_CONF_DIR, f"{app_name}.conf")
    if os.path.exists(config_path):
        os.remove(config_path)
        subprocess.run(["sudo", "nginx", "-s", "reload"], check=True)