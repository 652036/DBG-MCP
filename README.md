# dbgmcp

[English](README.md) | [简体中文](README.zh-CN.md)

`dbgmcp` is a thin local wrapper around the official `x64dbg_automate` MCP server.

This repository exists to make a local Windows debugger MCP setup repeatable:

- it auto-detects common local debugger installs
- it can print a ready-to-paste MCP config snippet
- it provides a plugin installer for `x64dbg_automate`
- it includes a local smoke test for debugger automation

## What this repo wraps

This project does not reimplement the debugger bridge protocol.

It delegates to the official upstream MCP server provided by `x64dbg_automate` and adds local setup helpers around it.

Upstream references used for this repo:

- x64dbg-automate MCP docs: `https://dariushoule.github.io/x64dbg-automate-pyclient/mcp-server/`
- x64dbg-automate installation docs: `https://dariushoule.github.io/x64dbg-automate-pyclient/installation/`
- PyPI package: `https://pypi.org/project/x64dbg-automate/`

## Install

```powershell
python -m pip install -e .
```

This repo depends on:

- Windows
- Python 3.10+
- `x64dbg_automate[mcp]==0.7.6`

## Local commands

### Health check

```powershell
python -m dbgmcp doctor
```

This checks:

- Python version
- `x64dbg_automate` package presence
- detected debugger executable path
- debugger plugin directory
- required plugin runtime files
- active x64dbg sessions discovered from x64dbg-automate lockfiles

### Print MCP config

```powershell
python -m dbgmcp print-mcp-config
```

This prints an MCP config that uses:

- `command = python`
- `args = ["-m", "dbgmcp", "mcp"]`
- `env.X64DBG_PATH = detected debugger path`

### Run the MCP server

```powershell
python -m dbgmcp mcp
```

Equivalent entrypoint:

```powershell
dbgmcp-server
```

### Install the x64dbg-automate plugin

```powershell
python -m dbgmcp install-plugin
```

This downloads the published plugin release whose tag matches the installed Python client's compatibility codename and copies the release files into the debugger `plugins` directory.

### Smoke test

```powershell
python -m dbgmcp smoke-test
```

By default it launches `C:\Windows\System32\notepad.exe`, validates that the debugger session is discoverable through x64dbg-automate, and then reads the current instruction pointer.

To point the smoke test at a different target executable:

```powershell
python -m dbgmcp smoke-test --target C:\path\to\target.exe
```

To validate only debugger startup and plugin connectivity without loading a target:

```powershell
python -m dbgmcp smoke-test --no-target
```

You can also override the target with an environment variable:

```powershell
$env:DBGMCP_SMOKE_TARGET = 'C:\path\to\target.exe'
python -m dbgmcp smoke-test --target $env:DBGMCP_SMOKE_TARGET
```

## Workstation defaults

On this machine, the wrapper tries the following common debugger paths first:

- executables under `C:\Users\Administrator\Desktop\vtce\KittyDebugTool\DBG\DBG64\`
- standard `x64dbg.exe`, `x32dbg.exe`, and `x96dbg.exe` paths

If your debugger executable is elsewhere, set:

```powershell
$env:X64DBG_PATH = 'C:\path\to\your\debugger.exe'
```

## Example MCP config

See:

- `.mcp.json.example`
- `mcp.config.example.json`

## External blockers

This wrapper cannot auto-complete these external steps on its own:

- installing the x64dbg-automate debugger plugin into the debugger `plugins` directory
- launching a debugger build that actually contains the plugin
- connecting to a live debug target

Without those, the MCP process can start, but tools like `start_session` or `connect_to_session` will not become useful.

On this workstation, empty sessions work with the bundled custom debugger build under `DBG64`, but loading a target executable may depend on that build's behavior. If target launch stalls, point `X64DBG_PATH` at a stock x64dbg build instead.
