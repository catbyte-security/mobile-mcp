"""Frida hooking layer for runtime instrumentation."""

from __future__ import annotations

import frida
import threading
import json
from collections import deque

# Session state
_device: frida.core.Device | None = None
_session: frida.core.Session | None = None
_scripts: dict[str, frida.core.Script] = {}
_messages: deque[dict] = deque(maxlen=500)
_attached_pkg: str | None = None


def _get_device() -> frida.core.Device:
    """Get the USB device."""
    global _device
    if _device is None:
        _device = frida.get_usb_device(timeout=5)
    return _device


def _on_message(message, data):
    """Handle messages from Frida scripts."""
    if message["type"] == "send":
        _messages.append(message["payload"])
    elif message["type"] == "error":
        _messages.append({"error": message.get("description", str(message))})


def attach(package: str, spawn: bool = False) -> str:
    """Attach Frida to a running app (or spawn it)."""
    global _session, _attached_pkg
    detach()  # Clean up any existing session

    dev = _get_device()
    if spawn:
        pid = dev.spawn([package])
        _session = dev.attach(pid)
        dev.resume(pid)
        _attached_pkg = package
        return f"Spawned and attached to {package} (PID {pid})"
    else:
        _session = dev.attach(package)
        _attached_pkg = package
        return f"Attached to {package}"


def detach() -> str:
    """Detach from the current session."""
    global _session, _attached_pkg
    for name, script in list(_scripts.items()):
        try:
            script.unload()
        except Exception:
            pass
    _scripts.clear()
    if _session:
        try:
            _session.detach()
        except Exception:
            pass
        _session = None
    pkg = _attached_pkg
    _attached_pkg = None
    return f"Detached from {pkg}" if pkg else "No active session"


def run_script(code: str, name: str = "default") -> str:
    """Run a Frida JavaScript snippet."""
    if _session is None:
        raise RuntimeError("Not attached to any app. Call attach() first.")

    # Unload existing script with same name
    if name in _scripts:
        try:
            _scripts[name].unload()
        except Exception:
            pass

    script = _session.create_script(code)
    script.on("message", _on_message)
    script.load()
    _scripts[name] = script
    return f"Script '{name}' loaded"


def get_messages(clear: bool = True) -> list[dict]:
    """Get collected messages from Frida scripts."""
    msgs = list(_messages)
    if clear:
        _messages.clear()
    return msgs


def list_classes(filter_str: str | None = None) -> list[str]:
    """Enumerate loaded Java classes."""
    if _session is None:
        raise RuntimeError("Not attached to any app. Call attach() first.")

    results = []
    event = threading.Event()

    js = """
    Java.perform(function() {
        var classes = Java.enumerateLoadedClassesSync();
        send(classes);
    });
    """
    script = _session.create_script(js)

    def on_msg(message, data):
        if message["type"] == "send":
            results.extend(message["payload"])
        event.set()

    script.on("message", on_msg)
    script.load()
    event.wait(timeout=10)
    script.unload()

    if filter_str:
        results = [c for c in results if filter_str.lower() in c.lower()]
    results.sort()
    return results


def list_methods(class_name: str) -> list[str]:
    """List methods of a Java class."""
    if _session is None:
        raise RuntimeError("Not attached to any app. Call attach() first.")

    results = []
    event = threading.Event()

    js = f"""
    Java.perform(function() {{
        try {{
            var cls = Java.use("{class_name}");
            var methods = cls.class.getDeclaredMethods();
            var names = [];
            for (var i = 0; i < methods.length; i++) {{
                names.push(methods[i].toString());
            }}
            send(names);
        }} catch(e) {{
            send({{"error": e.toString()}});
        }}
    }});
    """
    script = _session.create_script(js)

    def on_msg(message, data):
        if message["type"] == "send":
            payload = message["payload"]
            if isinstance(payload, list):
                results.extend(payload)
            elif isinstance(payload, dict) and "error" in payload:
                results.append(f"ERROR: {payload['error']}")
        event.set()

    script.on("message", on_msg)
    script.load()
    event.wait(timeout=10)
    script.unload()
    return results


def hook_method(class_name: str, method_name: str, log_args: bool = True, log_retval: bool = True) -> str:
    """Hook a Java method and log calls."""
    if _session is None:
        raise RuntimeError("Not attached to any app. Call attach() first.")

    hook_name = f"hook_{class_name}_{method_name}"

    js = f"""
    Java.perform(function() {{
        try {{
            var cls = Java.use("{class_name}");
            var overloads = cls.{method_name}.overloads;
            for (var i = 0; i < overloads.length; i++) {{
                overloads[i].implementation = function() {{
                    var msg = {{
                        "hook": "{class_name}.{method_name}",
                        "overload": i,
                    }};
                    {"" if not log_args else '''
                    var args = [];
                    for (var j = 0; j < arguments.length; j++) {
                        try {
                            args.push(String(arguments[j]));
                        } catch(e) {
                            args.push("<error: " + e + ">");
                        }
                    }
                    msg["args"] = args;
                    '''}
                    var retval = this.{method_name}.apply(this, arguments);
                    {"" if not log_retval else '''
                    try {
                        msg["retval"] = String(retval);
                    } catch(e) {
                        msg["retval"] = "<error: " + e + ">";
                    }
                    '''}
                    send(msg);
                    return retval;
                }};
            }}
            send({{"status": "hooked", "target": "{class_name}.{method_name}", "overloads": overloads.length}});
        }} catch(e) {{
            send({{"error": e.toString()}});
        }}
    }});
    """
    return run_script(js, name=hook_name)


def list_processes() -> list[dict]:
    """List running processes on the device."""
    dev = _get_device()
    procs = dev.enumerate_processes()
    return [{"pid": p.pid, "name": p.name} for p in procs]


def status() -> dict:
    """Get current hooking session status."""
    return {
        "attached": _attached_pkg,
        "scripts_loaded": list(_scripts.keys()),
        "pending_messages": len(_messages),
    }
