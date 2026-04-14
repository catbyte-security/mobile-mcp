# mobile-mcp  - MCP Server for Android App Security Testing

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server that gives AI agents full control over Android devices  - UI automation, Frida runtime hooking, and device management through a standard tool interface.

Think "Chrome MCP, but for Android apps." Connect Claude, GPT, or any MCP-compatible AI to an Android device and let it tap, type, read screens, hook functions, and inspect app internals.

## Features

**UI Automation** (via uiautomator2)
- `read_screen`  - Dump all visible UI elements with text, resource IDs, bounds
- `find_element`  - Search for elements by text, resource ID, class, or description
- `tap` / `type_text` / `swipe`  - Interact with the UI
- `screenshot`  - Capture the current screen
- `press_key`  - Press hardware/software keys (back, home, enter, etc.)

**Frida Hooking**
- `frida_attach`  - Attach to a running app (or spawn it)
- `frida_hook`  - Load custom Frida scripts for runtime instrumentation
- `frida_call`  - Call exported RPC methods in loaded scripts
- `frida_trace`  - Quick method tracing
- `frida_messages`  - Read messages from hooked functions

**Device Management**
- `device_info`  - Connection status, model, Android version, SDK level
- `list_packages`  - Installed apps with optional filtering
- `shell`  - Run ADB shell commands

## Install

```bash
git clone https://github.com/catbyte-security/mobile-mcp.git
cd mobile-mcp
pip install -e .
```

**Requirements:**
- Python 3.10+
- Android device connected via USB with USB debugging enabled
- ADB installed and in PATH
- Frida server running on the Android device (for hooking features)

## Setup

1. Connect your Android device via USB
2. Enable USB debugging in Developer Options
3. Verify connection: `adb devices`
4. For Frida features, push frida-server to the device:
   ```bash
   adb push frida-server /data/local/tmp/
   adb shell "chmod 755 /data/local/tmp/frida-server"
   adb shell "/data/local/tmp/frida-server &"
   ```

## Usage with Claude Code

Add to your MCP config:

```json
{
  "mcpServers": {
    "mobile": {
      "command": "python",
      "args": ["/path/to/mobile-mcp/server.py"]
    }
  }
}
```

Then ask Claude to interact with your Android device:

> "Read the current screen and tap the login button"
> "Attach Frida to com.example.app and hook the checkPassword method"
> "List all installed packages that contain 'bank'"

## Usage as Standalone Server

```bash
# Start the MCP server
mobile-mcp

# Or run directly
python server.py
```

## Architecture

```
server.py     # MCP server  - registers all tools via FastMCP
device.py     # ADB device management layer
ui.py         # uiautomator2 UI automation (screen reading, tapping, typing)
hooking.py    # Frida session management (attach, hook, trace, RPC calls)
```

## License

MIT
