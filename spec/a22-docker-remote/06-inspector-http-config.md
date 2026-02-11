# MCP Inspector HTTP Configuration

## Quick Start

### Default: ngrok Remote Access (Recommended)

```bash
make run-docker-remote
```

**Automatically:**

- ✅ Builds and starts Docker container
- ✅ Starts ngrok tunnel
- ✅ Exposes at `https://uniformly-alive-halibut.ngrok-free.app/mcp`
- ✅ Opens Inspector UI with configuration instructions
- ✅ Ready for Claude.ai Desktop!

### Local Testing Only (Optional)

```bash
make run-docker-remote WITH_NGROK=0
```

For testing without ngrok. Configure Inspector UI for `http://localhost:8000/mcp`

## Manual Configuration

### Step 1: Access Inspector UI

The Inspector opens automatically at: <http://localhost:6274/>

### Step 2: Configure for HTTP Transport

In the Inspector UI form, manually configure:

1. **Transport Type**: Select "Streamable HTTP" from dropdown (NOT "STDIO")
2. **URL**: Enter `http://localhost:8000/mcp` (replace any default URL)
3. **Connection Type**: "Direct"
4. Click "Connect"

### Expected Result

Once connected, you should see:

- ✅ Available tools listed in the UI
- ✅ Available resources listed in the UI
- ✅ Ability to test tool calls interactively

## For ngrok Remote Access

After you expose via ngrok in another terminal:

```bash
ngrok http 8000 --domain=uniformly-alive-halibut.ngrok-free.app
```

You can also test the Inspector with the ngrok URL:

1. **Transport Type**: "HTTP (SSE)"
2. **URL**: `https://uniformly-alive-halibut.ngrok-free.app/mcp`
3. Click "Connect"

## Verify Container is Running

Check that the container is healthy:

```bash
# Check container status
docker ps | grep mcp-remote-ngrok

# Check MCP endpoint is responding
curl http://localhost:8000/mcp

# View container logs
docker logs mcp-remote-ngrok
```

## Troubleshooting

If connection fails:

1. Verify container is running: `docker ps`
2. Check logs: `docker logs mcp-remote-ngrok`
3. Test endpoint: `curl -v http://localhost:8000/mcp`
4. Ensure you selected "HTTP (SSE)" not "STDIO" in Inspector
