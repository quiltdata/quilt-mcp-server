# Deploying Quilt MCP Server Remotely

This guide explains how to launch your Quilt MCP server with a streamable HTTP interface and connect to it from Claude as a remote MCP server.

## Prerequisites

You must have [ngrok](https://ngrok.com/) installed and authenticated to expose your local server to the internet.

### a. Install ngrok

If you do not have ngrok installed, download it from [ngrok.com/download](https://ngrok.com/download) and follow the installation instructions for your platform.

For example, on macOS with Homebrew:

```bash
brew install ngrok/ngrok/ngrok
```

Or download and unzip manually:

```bash
# Download from https://ngrok.com/download
unzip ngrok-stable-*.zip
sudo mv ngrok /usr/local/bin
```

### b. Authenticate ngrok (first time only)

Sign up for a free ngrok account at [ngrok.com](https://ngrok.com/), then get your auth token from your dashboard.

Authenticate ngrok with your token:

```bash
ngrok config add-authtoken <YOUR_NGROK_AUTHTOKEN>
```

## 1. Launch the Server

Navigate to the `quilt` directory and run the remote server script:

```bash
python remote.py
```

By default, this will start the server on `http://0.0.0.0:8000/mcp/`.


## 2. Expose the Server Remotely (Required: ngrok)

To access the server from outside your local machine (e.g., from Claude or other clients), you **must** use ngrok to expose your local server to the internet.

Start ngrok to forward HTTP traffic to your local server:

```bash
ngrok http 8000
```

You will see output like:

```
Forwarding    https://<random>.ngrok.io -> http://localhost:8000
```

Your public URL will be `https://<random>.ngrok.io/mcp/`.

Leave ngrok running while you want your server to be accessible remotely.

## 3. Connect from Claude as a Remote MCP Server

In Claude, add a new remote MCP server with the following settings:

- **URL:** `https://<random>.ngrok.io/mcp/`
- **Type:** Streamable HTTP (or "http")
- **API Key:** (leave blank unless you have added authentication)

Use the public URL provided by ngrok (ending with `/mcp/`).

## 4. Security Notes

- For production, consider adding authentication and HTTPS.
- Do not expose the server to the public internet without proper security controls.
- The ngrok free plan provides a random URL each time you start it; for a fixed domain, see ngrok paid plans.

## 5. Troubleshooting

- Ensure the server is running and accessible from the client machine.
- Check firewall and network settings if you cannot connect.
- Make sure ngrok is running and the tunnel is active.
- Review server and ngrok logs for errors.

---
For more details, see the [FastMCP documentation](https://gofastmcp.com/deployment/running-server#streamable-http).
