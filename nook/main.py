import typer
from typing import List
from nook.server.api import start_daemon
from nook.client.deploy import push_to_server

app = typer.Typer(help="nook-cli")
server_app = typer.Typer(help="Manage the nook Server.")

app.add_typer(server_app, name="server")

@server_app.command("start")
def server_start(port: int = typer.Option(8000, help="Port to run the daemon on")):
    start_daemon(port=port)

@app.command("deploy")
def client_deploy(
    name: str = typer.Option(..., "--name", "-n", help="Name of the application"),
    subdomain: str = typer.Option(..., "--subdomain", "-s", help="Subdomain for routing"),
    env: List[str] = typer.Option([], "-e", "--env", help="Environment variables (e.g. -e KEY=VAL)"),
    daemon_url: str = typer.Option("http://localhost:8000", help="URL of your VPS daemon")
):
    env_dict = dict(e.split("=", 1) for e in env)
    push_to_server(app_name=name, subdomain=subdomain, env_vars=env_dict, server_url=daemon_url)

def main():
    app()

if __name__ == "__main__":
    main()