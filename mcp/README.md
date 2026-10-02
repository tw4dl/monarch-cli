# Monarch MCP Server

MCP server wrapper for the `monarch` CLI.

## Install

```bash
uv sync --extra mcp
```

## Run (stdio)

```bash
uv run mcp/monarch_cli_server.py
```

## Run (via CLI)

```bash
monarch mcp start
```

## Status

```bash
monarch mcp status
```

## Codex Integration

### Option A: No local checkout (recommended)

Uses your public fork directly:

```bash
codex mcp add monarch -- uvx --from "git+https://github.com/tw4dl/monarch-cli.git" --with mcp monarch mcp start
```

### Option B: Local checkout

```bash
git clone https://github.com/tw4dl/monarch-cli.git
cd monarch-cli
uv sync --extra mcp
codex mcp add monarch -- uv run --directory "$(pwd)" monarch mcp start
```

## Client Config (Example)

Most MCP clients only support `command` + `args`. Use `uv run --directory` so relative paths work:

```json
{
  "mcpServers": {
    "monarch": {
      "command": "uv",
      "args": ["run", "--directory", "/ABS/PATH/TO/monarch-cli", "monarch", "mcp", "start"],
      "env": {"MONARCH_MCP_TRANSPORT": "stdio"}
    }
  }
}
```

## Tools

- `monarch.run(argv: list[str], json_output: bool = true)`  
  Runs any non-interactive `monarch` CLI command in-process (defaults to `--json`).
- `monarch.auth_login(email: str, password: str, mfa_code?: str, storage?: "keyring"|"file")`  
  Non-interactive login flow (use this instead of `monarch auth login`).
