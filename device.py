"""ADB device management layer."""

import subprocess
import re


def adb(*args: str, timeout: int = 10) -> str:
    """Run an ADB command and return stdout."""
    result = subprocess.run(
        ["adb", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0 and result.stderr.strip():
        raise RuntimeError(f"adb {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def check_device() -> dict:
    """Check if a device is connected and return basic info."""
    output = adb("devices")
    lines = [l for l in output.splitlines()[1:] if l.strip() and "device" in l]
    if not lines:
        raise RuntimeError("No Android device connected. Connect via USB and enable USB debugging.")
    serial = lines[0].split("\t")[0]
    model = adb("shell", "getprop", "ro.product.model")
    android_ver = adb("shell", "getprop", "ro.build.version.release")
    sdk = adb("shell", "getprop", "ro.build.version.sdk")
    return {
        "serial": serial,
        "model": model,
        "android_version": android_ver,
        "sdk_level": sdk,
    }


def installed_packages(filter_str: str | None = None) -> list[str]:
    """List installed packages, optionally filtered."""
    output = adb("shell", "pm", "list", "packages")
    pkgs = [line.replace("package:", "") for line in output.splitlines()]
    if filter_str:
        pkgs = [p for p in pkgs if filter_str.lower() in p.lower()]
    pkgs.sort()
    return pkgs


def current_foreground() -> dict:
    """Get the current foreground activity."""
    output = adb("shell", "dumpsys", "activity", "activities", timeout=5)
    for line in output.splitlines():
        if "mResumedActivity" in line or "mFocusedActivity" in line:
            match = re.search(r'u0\s+(\S+)/(\S+)', line)
            if match:
                return {"package": match.group(1), "activity": match.group(2)}
    # Fallback
    output2 = adb("shell", "dumpsys", "window", "windows", timeout=5)
    for line in output2.splitlines():
        if "mCurrentFocus" in line or "mFocusedApp" in line:
            match = re.search(r'(\S+)/(\S+)', line)
            if match:
                pkg = match.group(1).split()[-1]
                return {"package": pkg, "activity": match.group(2)}
    return {"package": "unknown", "activity": "unknown"}


def read_logcat(package: str | None = None, lines: int = 50) -> str:
    """Read recent logcat entries, optionally filtered by package."""
    if package:
        # Get PID for package
        pid_out = adb("shell", "pidof", package)
        if pid_out.strip():
            pid = pid_out.strip().split()[0]
            return adb("shell", "logcat", "-d", "-t", str(lines), f"--pid={pid}", timeout=5)
    return adb("shell", "logcat", "-d", "-t", str(lines), timeout=5)


def shell_cmd(command: str) -> str:
    """Run an arbitrary ADB shell command."""
    return adb("shell", command, timeout=15)
