"""UI automation layer using uiautomator2."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import uiautomator2 as u2

# Module-level device connection (lazy init)
_device: u2.Device | None = None


def get_device() -> u2.Device:
    """Get or create the uiautomator2 device connection."""
    global _device
    if _device is None:
        _device = u2.connect()
    return _device


def reset_device():
    """Reset the device connection."""
    global _device
    _device = None


@dataclass
class UIElement:
    """A parsed UI element from the view hierarchy."""
    index: int
    text: str
    resource_id: str
    class_name: str
    package: str
    description: str  # content-desc
    clickable: bool
    focusable: bool
    scrollable: bool
    enabled: bool
    checked: bool
    bounds: tuple[int, int, int, int]  # left, top, right, bottom

    @property
    def center(self) -> tuple[int, int]:
        return (
            (self.bounds[0] + self.bounds[2]) // 2,
            (self.bounds[1] + self.bounds[3]) // 2,
        )

    def to_dict(self) -> dict:
        d = {
            "index": self.index,
            "class": self.class_name,
            "bounds": list(self.bounds),
            "center": list(self.center),
        }
        if self.text:
            d["text"] = self.text
        if self.resource_id:
            d["resource_id"] = self.resource_id
        if self.description:
            d["description"] = self.description
        if self.clickable:
            d["clickable"] = True
        if self.scrollable:
            d["scrollable"] = True
        if self.checked:
            d["checked"] = True
        if not self.enabled:
            d["enabled"] = False
        return d


def _parse_bounds(bounds_str: str) -> tuple[int, int, int, int]:
    """Parse '[left,top][right,bottom]' format."""
    import re
    m = re.findall(r'\d+', bounds_str)
    if len(m) >= 4:
        return int(m[0]), int(m[1]), int(m[2]), int(m[3])
    return (0, 0, 0, 0)


def parse_hierarchy(xml_str: str) -> list[UIElement]:
    """Parse UI hierarchy XML into a flat list of elements."""
    root = ET.fromstring(xml_str)
    elements = []
    idx = 0

    def walk(node: ET.Element):
        nonlocal idx
        attrib = node.attrib
        text = attrib.get("text", "")
        res_id = attrib.get("resource-id", "")
        desc = attrib.get("content-desc", "")
        clickable = attrib.get("clickable", "false") == "true"
        class_name = attrib.get("class", "")

        # Only include elements with useful properties
        has_info = text or res_id or desc or clickable
        if has_info and class_name:
            elements.append(UIElement(
                index=idx,
                text=text,
                resource_id=res_id,
                class_name=class_name,
                package=attrib.get("package", ""),
                description=desc,
                clickable=clickable,
                focusable=attrib.get("focusable", "false") == "true",
                scrollable=attrib.get("scrollable", "false") == "true",
                enabled=attrib.get("enabled", "true") == "true",
                checked=attrib.get("checked", "false") == "true",
                bounds=_parse_bounds(attrib.get("bounds", "[0,0][0,0]")),
            ))
            idx += 1

        for child in node:
            walk(child)

    walk(root)
    return elements


def dump_screen() -> list[dict]:
    """Dump the current screen UI hierarchy as a list of element dicts."""
    d = get_device()
    xml_str = d.dump_hierarchy()
    elements = parse_hierarchy(xml_str)
    return [e.to_dict() for e in elements]


def find_elements(
    text: str | None = None,
    resource_id: str | None = None,
    class_name: str | None = None,
    description: str | None = None,
) -> list[dict]:
    """Find elements matching the given criteria."""
    all_elements = dump_screen()
    results = []
    for el in all_elements:
        if text and text.lower() not in el.get("text", "").lower():
            continue
        if resource_id and resource_id not in el.get("resource_id", ""):
            continue
        if class_name and class_name not in el.get("class", ""):
            continue
        if description and description.lower() not in el.get("description", "").lower():
            continue
        results.append(el)
    return results


def tap_element(
    text: str | None = None,
    resource_id: str | None = None,
    description: str | None = None,
    x: int | None = None,
    y: int | None = None,
) -> str:
    """Tap an element by selector or coordinates."""
    d = get_device()
    if x is not None and y is not None:
        d.click(x, y)
        return f"Tapped coordinates ({x}, {y})"

    if text:
        el = d(text=text)
        if el.exists:
            el.click()
            return f"Tapped element with text '{text}'"
        raise ValueError(f"No element found with text '{text}'")

    if resource_id:
        el = d(resourceId=resource_id)
        if el.exists:
            el.click()
            return f"Tapped element with resource_id '{resource_id}'"
        raise ValueError(f"No element found with resource_id '{resource_id}'")

    if description:
        el = d(description=description)
        if el.exists:
            el.click()
            return f"Tapped element with description '{description}'"
        raise ValueError(f"No element found with description '{description}'")

    raise ValueError("Provide text, resource_id, description, or x/y coordinates")


def type_into(
    text: str,
    resource_id: str | None = None,
    clear_first: bool = True,
) -> str:
    """Type text into a field."""
    d = get_device()
    if resource_id:
        el = d(resourceId=resource_id)
        if not el.exists:
            raise ValueError(f"No element found with resource_id '{resource_id}'")
        if clear_first:
            el.clear_text()
        el.set_text(text)
        return f"Typed '{text}' into '{resource_id}'"
    else:
        # Type into currently focused element
        if clear_first:
            d.clear_text()
        d.send_keys(text)
        return f"Typed '{text}' into focused element"


def swipe_screen(direction: str = "up", scale: float = 0.6) -> str:
    """Swipe the screen in a direction."""
    d = get_device()
    info = d.info
    w = info["displayWidth"]
    h = info["displayHeight"]
    cx, cy = w // 2, h // 2
    dist_x = int(w * scale / 2)
    dist_y = int(h * scale / 2)

    moves = {
        "up": (cx, cy + dist_y, cx, cy - dist_y),
        "down": (cx, cy - dist_y, cx, cy + dist_y),
        "left": (cx + dist_x, cy, cx - dist_x, cy),
        "right": (cx - dist_x, cy, cx + dist_x, cy),
    }
    if direction not in moves:
        raise ValueError(f"Direction must be one of: {list(moves.keys())}")

    sx, sy, ex, ey = moves[direction]
    d.swipe(sx, sy, ex, ey, duration=0.3)
    return f"Swiped {direction}"


def take_screenshot() -> bytes:
    """Take a screenshot and return PNG bytes."""
    d = get_device()
    img = d.screenshot()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def long_press(
    text: str | None = None,
    resource_id: str | None = None,
    x: int | None = None,
    y: int | None = None,
    duration: float = 1.0,
) -> str:
    """Long press an element or coordinates."""
    d = get_device()
    if x is not None and y is not None:
        d.long_click(x, y, duration=duration)
        return f"Long pressed ({x}, {y}) for {duration}s"
    if text:
        el = d(text=text)
        if el.exists:
            el.long_click(duration=duration)
            return f"Long pressed '{text}'"
        raise ValueError(f"No element found with text '{text}'")
    if resource_id:
        el = d(resourceId=resource_id)
        if el.exists:
            el.long_click(duration=duration)
            return f"Long pressed '{resource_id}'"
        raise ValueError(f"No element found with resource_id '{resource_id}'")
    raise ValueError("Provide text, resource_id, or x/y coordinates")


def press_key(key: str) -> str:
    """Press a hardware/system key."""
    d = get_device()
    key_map = {
        "back": "back",
        "home": "home",
        "enter": "enter",
        "menu": "menu",
        "recent": "recent",
        "volume_up": "volume_up",
        "volume_down": "volume_down",
        "power": "power",
        "tab": "tab",
        "delete": "delete",
        "search": "search",
    }
    mapped = key_map.get(key.lower(), key)
    d.press(mapped)
    return f"Pressed '{mapped}'"
