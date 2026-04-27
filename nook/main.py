import typer
from typing import List
from nook.server.api import start_daemon
from nook.client.deploy import push_to_server
from nook.client.config import save_config

app = typer.Typer(help="nook-cli")
server_app = typer.Typer(help="Manage the nook Server.")

app.add_typer(server_app, name="server")

@server_app.command("start")
def server_start(
    port: int = typer.Option(8000, help="Port to run the daemon on"),
    domain: str = typer.Option(None, "--domain", "-d", help="Base domain (e.g., example.com)")
):
    from nook.server.config import get_server_config, initialize_server
    from nook.server.api import start_daemon

    config = get_server_config()
    
    if not config:
        if not domain:
            typer.secho("Error: Server not initialized. Run with --domain [yourdomain.com]", fg=typer.colors.RED)
            raise typer.Exit(1)
        
        raw_token = initialize_server(domain)
        typer.secho(f"\nSERVER INITIALIZED", fg=typer.colors.CYAN, bold=True)
        typer.echo(f"Domain: {domain}")
        typer.echo(f"API Token: {raw_token}")
        typer.secho("Save this token! It will not be shown again.\n", fg=typer.colors.YELLOW)

    start_daemon(port=port,domain=domain)


@app.command()
def login(
    url: str = typer.Option("http://localhost:8000", "--url", "-u", help="URL of your VPS daemon")
):
    typer.echo(f"Logging into nook daemon at {url}")
    
    token = typer.prompt("Paste your API Token", hide_input=True)
    
    save_config(token, url)
    typer.secho("Authentication successful! Config saved.", fg=typer.colors.GREEN)

@app.command("deploy")
def client_deploy(
    name: str = typer.Option(..., "--name", "-n", help="Name of the application"),
    subdomain: str = typer.Option(..., "--subdomain", "-s", help="Subdomain for routing"),
    app_port: int = typer.Option(8000, "--port", "-p", help="Port the application exposes internally"),
    env: List[str] = typer.Option([], "-e", "--env", help="Environment variables (e.g. -e KEY=VAL)"),
    daemon_url: str = typer.Option("http://localhost:8000", help="URL of your VPS daemon")
):
    env_dict = dict(e.split("=", 1) for e in env)
    push_to_server(app_name=name, subdomain=subdomain, app_port=app_port, env_vars=env_dict, server_url=daemon_url)

def main():
    app()

if __name__ == "__main__":
    main()