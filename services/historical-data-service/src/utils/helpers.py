import json
from datetime import datetime
from typing import Any, Dict, List, Optional


def parse_iso_datetime(datetime_str: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 datetime string into a datetime object.

    Args:
        datetime_str: ISO 8601 datetime string

    Returns:
        Datetime object or None if the input is None or invalid
    """
    if not datetime_str:
        return None

    try:
        # Handle 'Z' UTC indicator
        if datetime_str.endswith("Z"):
            datetime_str = datetime_str[:-1] + "+00:00"

        return datetime.fromisoformat(datetime_str)
    except ValueError:
        return None


def format_datetime_iso(dt: Optional[datetime]) -> Optional[str]:
    """Format a datetime object as an ISO 8601 string.

    Args:
        dt: Datetime object

    Returns:
        ISO 8601 string or None if the input is None
    """
    if not dt:
        return None

    return dt.isoformat()


def safe_json_loads(json_str: str) -> Dict[str, Any]:
    """Safely parse a JSON string into a dictionary.

    Args:
        json_str: JSON string

    Returns:
        Dictionary parsed from JSON or empty dict if invalid
    """
    if not json_str:
        return {}

    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return {}


def format_temperature_data(readings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format temperature reading data for API responses.

    Args:
        readings: List of temperature reading data from database

    Returns:
        Formatted list of temperature readings
    """
    formatted = []

    for reading in readings:
        # Convert datetime objects to ISO strings
        if "time" in reading and reading["time"]:
            if isinstance(reading["time"], datetime):
                reading["time"] = format_datetime_iso(reading["time"])

        # Parse JSON metadata if it's a string
        if "metadata" in reading and reading["metadata"]:
            if isinstance(reading["metadata"], str):
                reading["metadata"] = safe_json_loads(reading["metadata"])

        # Remove None values for cleaner output
        formatted_reading = {k: v for k, v in reading.items() if v is not None}
        formatted.append(formatted_reading)

    return formatted
