# nook
Nook is a lightweight, self-hosted Platform as a Service (PaaS) for deploying containerized apps. It automates the deployment, reverse proxy configuration, and SSL certificate provisioning.

## Features
- Single Binary for both server and client CLI
- Automatic reverse proxy configuration with Nginx
- Automatic SSL certificate provisioning with Let's Encrypt
- Basic Lifecycle Management (start, stop, restart, delete)

## Installation

### Server

#### Pre-requisites
- Docker
- Nginx
- Certbot (with Nginx plugin) (python3-certbot-nginx on Debian/Ubuntu)
- A wildcard domain pointing to your server (e.g., `*.yourdomain.com`)

1. Download the latest release from the [releases page](https://github.com/norsulabs/nook/releases)
2. Install the binary:
   ```bash
    chmod +x nook
    sudo mv nook /usr/local/bin/
    ```
3. Start the server:
   ```bash
    sudo nook server start --domain yourdomain.com
    ```

### Client

1. Authenticate:
    ```bash
     nook login --url http://yourserver:8000
    ```

## Usage

### Deploying an App

Navigate to your app directory (must contain a Dockerfile):

Deploy the app:
```bash
nook deploy --name myapp --subdomain app --port 80
```

Upon successful deployment, your app will be accessible at `https://app.yourdomain.com`.

### Managing Apps

List all deployed apps:
```bash
nook apps
```

Stop an app:
```bash
nook stop myapp
```

Start an app:
```
nook start myapp
```

Remove an app:
```bash
nook rm myapp
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.