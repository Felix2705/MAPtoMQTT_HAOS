import logging
import re
import xml.etree.ElementTree as ET
from typing import Dict

logger = logging.getLogger(__name__)


def load_translation_map(xml_path: str) -> Dict[str, Dict[str, str]]:
    """Load SIID to name/type mapping from a MAP XML config export."""
    if not xml_path:
        return {}
    try:
        tree = ET.parse(xml_path)
    except Exception as exc:
        logger.warning("Failed to parse translation XML: %s", exc)
        return {}

    root = tree.getroot()
    result: Dict[str, Dict[str, str]] = {}
    for elem in root.iter("Config_Package"):
        siid = elem.attrib.get("SIID")
        name = elem.attrib.get("Name")
        if not siid or not name:
            continue
        entry_type = elem.attrib.get("Type", "")
        normalized = normalize_siid(siid)
        result[normalized] = {"name": name, "type": entry_type}
    return result


def normalize_siid(value: str) -> str:
    text = value.strip().lstrip("/")
    parts = text.split(".")
    normalized = []
    for part in parts:
        if part.isdigit():
            normalized.append(str(int(part)))
        else:
            normalized.append(part)
    return ".".join(normalized)


def topicize_name(name: str) -> str:
    """Normalize a display name into a safe MQTT topic segment."""
    if not name:
        return ""
    text = name.strip()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9._-]", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text
