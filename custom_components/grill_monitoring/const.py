"""Constants for the Grill Monitoring integration."""

DOMAIN = "grill_monitoring"
DEFAULT_NAME = "Grill Monitoring"

# Configuration keys
CONF_DEVICE_SERVICE_URL = "device_service_url"
CONF_TEMPERATURE_SERVICE_URL = "temperature_service_url"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"

# Default values
DEFAULT_DEVICE_SERVICE_URL = "http://localhost:8080"
DEFAULT_TEMPERATURE_SERVICE_URL = "http://localhost:8081"
DEFAULT_SCAN_INTERVAL = 30  # seconds
DEFAULT_TIMEOUT = 10  # seconds

# Device and entity attributes
ATTR_DEVICE_ID = "device_id"
ATTR_PROBE_ID = "probe_id"
ATTR_BATTERY_LEVEL = "battery_level"
ATTR_SIGNAL_STRENGTH = "signal_strength"
ATTR_LAST_SEEN = "last_seen"
ATTR_DEVICE_TYPE = "device_type"
ATTR_FIRMWARE_VERSION = "firmware_version"
ATTR_TEMPERATURE_UNIT = "temperature_unit"

# Sensor types
SENSOR_TYPE_TEMPERATURE = "temperature"
SENSOR_TYPE_BATTERY = "battery"
SENSOR_TYPE_SIGNAL = "signal_strength"

# Device classes
DEVICE_CLASS_TEMPERATURE = "temperature"
DEVICE_CLASS_BATTERY = "battery"
DEVICE_CLASS_SIGNAL_STRENGTH = "signal_strength"

# Units
TEMP_FAHRENHEIT = "°F"
TEMP_CELSIUS = "°C"
PERCENTAGE = "%"

# Endpoints
ENDPOINT_DEVICES = "/api/devices"
ENDPOINT_DEVICE_DETAIL = "/api/devices/{device_id}"
ENDPOINT_DEVICE_HEALTH = "/api/devices/{device_id}/health"
ENDPOINT_CURRENT_TEMPERATURE = "/api/temperature/current/{device_id}"
ENDPOINT_TEMPERATURE_HISTORY = "/api/temperature/history/{device_id}"
ENDPOINT_TEMPERATURE_STATS = "/api/temperature/stats/{device_id}"

# Error messages
ERROR_CANNOT_CONNECT = "Cannot connect to service"
ERROR_INVALID_CONFIG = "Invalid configuration"
ERROR_TIMEOUT = "Request timeout"
ERROR_UNKNOWN = "Unknown error"

# Update intervals
UPDATE_INTERVAL_FAST = 15  # seconds - for active monitoring
UPDATE_INTERVAL_NORMAL = 30  # seconds - for regular monitoring
UPDATE_INTERVAL_SLOW = 60  # seconds - for background monitoring
