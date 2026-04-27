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
    """Deletes the Nginx config file and reloads."""
    config_path = os.path.join(NGINX_CONF_DIR, f"{app_name}.conf")
    if os.path.exists(config_path):
        os.remove(config_path)
        subprocess.run(["sudo", "nginx", "-s", "reload"], check=True)
        print(f"Removed Nginx config for {app_name}")

def provision_ssl(subdomain: str):
    config = get_server_config()
    if not config:
        return
    
    base_domain = config["base_domain"]
    full_domain = f"{subdomain}.{base_domain}"

    print(f"Provisioning SSL certificate for {full_domain}...")
    
    command = [
        "sudo", "certbot", "--nginx",
        "-d", full_domain,
        "--non-interactive",
        "--agree-tos",
        "--register-unsafely-without-email",
        "--redirect"
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print(f"SSL successfully provisioned for {full_domain}")
        else:
            print(f"Certbot failed: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print("SSL Provisioning timed out. Check your DNS propagation.")
    except Exception as e:
        print(f"Unexpected error during SSL setup: {e}")