#!/usr/bin/env python3
"""
Mobile MCP Server — Control Android apps like Chrome MCP controls browsers.

Tools for UI automation, Frida hooking, device management, and traffic analysis.
Connects to Android devices via ADB + uiautomator2 + Frida.
"""

from __future__ import annotations

import base64
import json

from mcp.server.fastmcp import FastMCP, Image

import device
import ui
import hooking

mcp = FastMCP(
    "mobile",
    instructions=(
        "Mobile app automation tools for Android. "
        "Use read_screen to see what's on screen, tap/type to interact, "
        "frida_* tools for runtime hooking and inspection, "
        "and device_* tools for ADB operations. "
        "Start with device_info to verify connection."
    ),
)

# ─── UI Tools ──────────────────────────────────────────────────────────────────

@mcp.tool()
def read_screen() -> str:
    """Read all visible UI elements on the current screen.

    Returns a JSON list of elements with text, resource_id, class, bounds,
    and interaction properties. Use this to understand what's on screen
    before tapping or typing.
    """
    elements = ui.dump_screen()
    if not elements:
        return "Screen appears empty or could not parse UI hierarchy."
    return json.dumps(elements, indent=2)


@mcp.tool()
def find_element(
    text: str | None = None,
    resource_id: str | None = None,
    class_name: str | None = None,
    description: str | None = None,
) -> str:
    """Find UI elements matching the given criteria.

    Args:
        text: Match elements containing this text (case-insensitive)
        resource_id: Match elements with this resource ID (substring match)
        class_name: Match elements with this class name (substring match)
        description: Match elements with this content description (case-insensitive)
    """
    if not any([text, resource_id, class_name, description]):
        return "Provide at least one of: text, resource_id, class_name, description"
    results = ui.find_elements(text, resource_id, class_name, description)
    if not results:
        return "No matching elements found."
    return json.dumps(results, indent=2)


@mcp.tool()
def tap(
    text: str | None = None,
    resource_id: str | None = None,
    description: str | None = None,
    x: int | None = None,
    y: int | None = None,
) -> str:
    """Tap a UI element or screen coordinates.

    Specify ONE of: text, resource_id, description, or (x, y) coordinates.

    Args:
        text: Tap element containing this text
        resource_id: Tap element with this resource ID
        description: Tap element with this content description
        x: X coordinate to tap
        y: Y coordinate to tap
    """
    return ui.tap_element(text=text, resource_id=resource_id, description=description, x=x, y=y)


@mcp.tool()
def long_press(
    text: str | None = None,
    resource_id: str | None = None,
    x: int | None = None,
    y: int | None = None,
    duration: float = 1.0,
) -> str:
    """Long press a UI element or coordinates.

    Args:
        text: Long press element containing this text
        resource_id: Long press element with this resource ID
        x: X coordinate
        y: Y coordinate
        duration: Press duration in seconds (default 1.0)
    """
    return ui.long_press(text=text, resource_id=resource_id, x=x, y=y, duration=duration)


@mcp.tool()
def type_text(
    text: str,
    resource_id: str | None = None,
    clear_first: bool = True,
) -> str:
    """Type text into a field.

    Args:
        text: The text to type
        resource_id: Target field resource ID. If omitted, types into currently focused field.
        clear_first: Clear existing text before typing (default True)
    """
    return ui.type_into(text=text, resource_id=resource_id, clear_first=clear_first)


@mcp.tool()
def swipe(direction: str = "up", scale: float = 0.6) -> str:
    """Swipe/scroll the screen.

    Args:
        direction: One of 'up', 'down', 'left', 'right'
        scale: Swipe distance as fraction of screen (0.0-1.0, default 0.6)
    """
    return ui.swipe_screen(direction=direction, scale=scale)


@mcp.tool()
def screenshot() -> Image:
    """Take a screenshot of the current screen. Returns the image directly."""
    png_bytes = ui.take_screenshot()
    return Image(data=png_bytes, format="png")


@mcp.tool()
def press_key(key: str) -> str:
    """Press a hardware/system key.

    Args:
        key: Key name — back, home, enter, menu, recent, volume_up, volume_down,
             power, tab, delete, search
    """
    return ui.press_key(key)


# ─── App / Device Tools ───────────────────────────────────────────────────────

@mcp.tool()
def device_info() -> str:
    """Get connected device info. Call this first to verify connection."""
    info = device.check_device()
    return json.dumps(info, indent=2)


@mcp.tool()
def current_app() -> str:
    """Get the current foreground app package and activity."""
    info = device.current_foreground()
    return json.dumps(info, indent=2)


@mcp.tool()
def launch_app(package: str) -> str:
    """Launch an app by package name.

    Args:
        package: Android package name (e.g., 'com.example.app')
    """
    d = ui.get_device()
    d.app_start(package)
    return f"Launched {package}"


@mcp.tool()
def stop_app(package: str) -> str:
    """Force stop an app.

    Args:
        package: Android package name
    """
    d = ui.get_device()
    d.app_stop(package)
    return f"Stopped {package}"


@mcp.tool()
def list_apps(filter: str | None = None) -> str:
    """List installed apps, optionally filtered.

    Args:
        filter: Substring to filter package names (case-insensitive)
    """
    pkgs = device.installed_packages(filter)
    return json.dumps(pkgs[:100])  # Cap at 100


@mcp.tool()
def shell(command: str) -> str:
    """Run an ADB shell command on the device.

    Args:
        command: Shell command to execute (e.g., 'cat /proc/version')
    """
    return device.shell_cmd(command)


@mcp.tool()
def logcat(package: str | None = None, lines: int = 50) -> str:
    """Read device logs, optionally filtered by app.

    Args:
        package: Filter logs to this package name
        lines: Number of recent log lines (default 50)
    """
    return device.read_logcat(package=package, lines=lines)


# ─── Frida Hooking Tools ──────────────────────────────────────────────────────

@mcp.tool()
def frida_attach(package: str, spawn: bool = False) -> str:
    """Attach Frida to a running app for runtime instrumentation.

    Args:
        package: App package name (e.g., 'com.example.app')
        spawn: If True, spawn the app fresh instead of attaching to running instance
    """
    return hooking.attach(package, spawn=spawn)


@mcp.tool()
def frida_detach() -> str:
    """Detach Frida from the current app and unload all scripts."""
    return hooking.detach()


@mcp.tool()
def frida_script(code: str, name: str = "default") -> str:
    """Run a Frida JavaScript snippet in the attached app.

    The script runs in the app's process. Use Java.perform() for Java hooking.
    Use send() to send data back — retrieve it with frida_messages().

    Args:
        code: Frida JavaScript code to execute
        name: Name for this script (for management). Replaces any script with same name.
    """
    return hooking.run_script(code, name=name)


@mcp.tool()
def frida_hook(
    class_name: str,
    method_name: str,
    log_args: bool = True,
    log_retval: bool = True,
) -> str:
    """Hook a Java method and log all calls to it.

    Retrieve logged calls with frida_messages().

    Args:
        class_name: Full Java class name (e.g., 'com.example.app.AuthManager')
        method_name: Method name to hook (e.g., 'checkPassword')
        log_args: Log method arguments (default True)
        log_retval: Log return values (default True)
    """
    return hooking.hook_method(class_name, method_name, log_args=log_args, log_retval=log_retval)


@mcp.tool()
def frida_list_classes(filter: str | None = None) -> str:
    """List loaded Java classes in the attached app.

    Args:
        filter: Substring to filter class names (case-insensitive)
    """
    classes = hooking.list_classes(filter)
    return json.dumps(classes[:200])  # Cap output


@mcp.tool()
def frida_list_methods(class_name: str) -> str:
    """List all methods of a Java class.

    Args:
        class_name: Full Java class name (e.g., 'com.example.app.LoginActivity')
    """
    methods = hooking.list_methods(class_name)
    return json.dumps(methods)


@mcp.tool()
def frida_messages(clear: bool = True) -> str:
    """Get messages collected from Frida hooks and scripts.

    Args:
        clear: Clear messages after reading (default True)
    """
    msgs = hooking.get_messages(clear=clear)
    if not msgs:
        return "No messages."
    return json.dumps(msgs, indent=2, default=str)


@mcp.tool()
def frida_processes() -> str:
    """List running processes on the device (useful to find target PIDs)."""
    procs = hooking.list_processes()
    return json.dumps(procs)


@mcp.tool()
def frida_status() -> str:
    """Get Frida session status — what's attached, which scripts are loaded."""
    return json.dumps(hooking.status(), indent=2)


# ─── Entry Point ───────────────────────────────────────────────────────────────

def main():
    mcp.run()


if __name__ == "__main__":
    main()
