-- PostgreSQL initialization script for Grill Monitoring
-- This script sets up the database structure for the Device Management Service

-- Create extension for UUID generation if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create devices table with enhanced schema
CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    device_type VARCHAR(100) NOT NULL DEFAULT 'thermoworks',
    configuration JSONB DEFAULT '{}',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Add constraints
    CONSTRAINT valid_device_type CHECK (device_type IN ('thermoworks', 'rfx', 'custom')),
    CONSTRAINT valid_device_id CHECK (char_length(device_id) > 0)
);

-- Create device_health table for monitoring
CREATE TABLE IF NOT EXISTS device_health (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    battery_level INTEGER CHECK (battery_level >= 0 AND battery_level <= 100),
    signal_strength INTEGER CHECK (signal_strength >= 0 AND signal_strength <= 100),
    last_seen TIMESTAMP,
    status VARCHAR(50) DEFAULT 'unknown',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key constraint
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,

    -- Status constraint
    CONSTRAINT valid_status CHECK (status IN ('online', 'offline', 'error', 'unknown', 'maintenance'))
);

-- Create device_configuration table for advanced settings
CREATE TABLE IF NOT EXISTS device_configuration (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    config_key VARCHAR(100) NOT NULL,
    config_value TEXT,
    config_type VARCHAR(50) DEFAULT 'string',
    is_encrypted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key constraint
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,

    -- Unique constraint for device + key combination
    UNIQUE(device_id, config_key),

    -- Type constraint
    CONSTRAINT valid_config_type CHECK (config_type IN ('string', 'integer', 'float', 'boolean', 'json'))
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id);
CREATE INDEX IF NOT EXISTS idx_devices_active ON devices(active);
CREATE INDEX IF NOT EXISTS idx_devices_type ON devices(device_type);
CREATE INDEX IF NOT EXISTS idx_devices_updated_at ON devices(updated_at);

CREATE INDEX IF NOT EXISTS idx_device_health_device_id ON device_health(device_id);
CREATE INDEX IF NOT EXISTS idx_device_health_last_seen ON device_health(last_seen);
CREATE INDEX IF NOT EXISTS idx_device_health_status ON device_health(status);
CREATE INDEX IF NOT EXISTS idx_device_health_created_at ON device_health(created_at);

CREATE INDEX IF NOT EXISTS idx_device_config_device_id ON device_configuration(device_id);
CREATE INDEX IF NOT EXISTS idx_device_config_key ON device_configuration(config_key);

-- Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_devices_updated_at
    BEFORE UPDATE ON devices
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_device_config_updated_at
    BEFORE UPDATE ON device_configuration
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert sample data for testing
INSERT INTO devices (device_id, name, device_type, configuration) VALUES
    ('test_device_001', 'Test Grill Monitor', 'thermoworks', '{"probe_count": 2, "max_temp": 500}'),
    ('test_device_002', 'Test Smoker Monitor', 'thermoworks', '{"probe_count": 4, "max_temp": 300}'),
    ('rfx_device_001', 'RFX Test Probe', 'rfx', '{"frequency": "433MHz", "protocol": "oregon"}')
ON CONFLICT (device_id) DO NOTHING;

-- Insert sample health data
INSERT INTO device_health (device_id, battery_level, signal_strength, last_seen, status) VALUES
    ('test_device_001', 85, 95, CURRENT_TIMESTAMP - INTERVAL '5 minutes', 'online'),
    ('test_device_002', 92, 88, CURRENT_TIMESTAMP - INTERVAL '2 minutes', 'online'),
    ('rfx_device_001', 78, 76, CURRENT_TIMESTAMP - INTERVAL '10 minutes', 'online')
ON CONFLICT DO NOTHING;

-- Insert sample configuration data
INSERT INTO device_configuration (device_id, config_key, config_value, config_type) VALUES
    ('test_device_001', 'temperature_unit', 'fahrenheit', 'string'),
    ('test_device_001', 'sync_interval', '300', 'integer'),
    ('test_device_001', 'auto_sync', 'true', 'boolean'),
    ('test_device_002', 'temperature_unit', 'celsius', 'string'),
    ('test_device_002', 'sync_interval', '180', 'integer'),
    ('rfx_device_001', 'frequency', '433.92', 'float'),
    ('rfx_device_001', 'protocol_settings', '{"modulation": "OOK", "bandwidth": "narrow"}', 'json')
ON CONFLICT (device_id, config_key) DO NOTHING;

-- Create a view for device summary
CREATE OR REPLACE VIEW device_summary AS
SELECT
    d.device_id,
    d.name,
    d.device_type,
    d.active,
    d.created_at,
    d.updated_at,
    dh.battery_level,
    dh.signal_strength,
    dh.last_seen,
    dh.status as health_status,
    COUNT(dc.id) as config_count
FROM devices d
LEFT JOIN device_health dh ON d.device_id = dh.device_id
    AND dh.id = (
        SELECT id FROM device_health dh2
        WHERE dh2.device_id = d.device_id
        ORDER BY created_at DESC LIMIT 1
    )
LEFT JOIN device_configuration dc ON d.device_id = dc.device_id
GROUP BY d.device_id, d.name, d.device_type, d.active, d.created_at, d.updated_at,
         dh.battery_level, dh.signal_strength, dh.last_seen, dh.status;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO grill_monitor;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO grill_monitor;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO grill_monitor;

-- Create completion marker
SELECT 'PostgreSQL initialization completed successfully' as status;
