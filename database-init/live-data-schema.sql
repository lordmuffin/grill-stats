-- Database schema for User Story 3: Live Device Data
-- This script creates tables for device channels and live temperature data

-- Create device_channels table for channel configuration
CREATE TABLE IF NOT EXISTS device_channels (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    channel_id INTEGER NOT NULL,
    channel_name VARCHAR(100) NOT NULL,
    probe_type VARCHAR(50) NOT NULL DEFAULT 'meat',
    unit VARCHAR(1) NOT NULL DEFAULT 'F',
    is_active BOOLEAN DEFAULT true,
    min_temp DECIMAL(5,2) DEFAULT 32.0,
    max_temp DECIMAL(5,2) DEFAULT 500.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key constraint
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,

    -- Unique constraint for device + channel combination
    UNIQUE(device_id, channel_id),

    -- Check constraints
    CONSTRAINT valid_probe_type CHECK (probe_type IN ('meat', 'ambient', 'water', 'oil', 'custom')),
    CONSTRAINT valid_unit CHECK (unit IN ('F', 'C')),
    CONSTRAINT valid_temp_range CHECK (min_temp < max_temp)
);

-- Create live_temperature_readings table for real-time data
CREATE TABLE IF NOT EXISTS live_temperature_readings (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    channel_id INTEGER NOT NULL,
    temperature DECIMAL(5,2),
    unit VARCHAR(1) NOT NULL DEFAULT 'F',
    is_connected BOOLEAN DEFAULT true,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',

    -- Foreign key constraints
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,
    FOREIGN KEY (device_id, channel_id) REFERENCES device_channels(device_id, channel_id) ON DELETE CASCADE,

    -- Check constraints
    CONSTRAINT valid_temp_unit CHECK (unit IN ('F', 'C')),
    CONSTRAINT valid_temperature CHECK (temperature >= -40 AND temperature <= 1000)
);

-- Create device_status_log table for tracking device health over time
CREATE TABLE IF NOT EXISTS device_status_log (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    battery_level INTEGER CHECK (battery_level >= 0 AND battery_level <= 100),
    signal_strength INTEGER CHECK (signal_strength >= 0 AND signal_strength <= 100),
    connection_status VARCHAR(20) NOT NULL DEFAULT 'unknown',
    firmware_version VARCHAR(50),
    hardware_version VARCHAR(50),
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',

    -- Foreign key constraint
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,

    -- Check constraints
    CONSTRAINT valid_connection_status CHECK (connection_status IN ('online', 'offline', 'error', 'unknown'))
);

-- Create temperature_alerts table for temperature threshold monitoring
CREATE TABLE IF NOT EXISTS temperature_alerts (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    channel_id INTEGER NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    threshold_value DECIMAL(5,2) NOT NULL,
    current_value DECIMAL(5,2) NOT NULL,
    alert_level VARCHAR(20) NOT NULL DEFAULT 'info',
    is_active BOOLEAN DEFAULT true,
    acknowledged BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP,
    resolved_at TIMESTAMP,

    -- Foreign key constraints
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,
    FOREIGN KEY (device_id, channel_id) REFERENCES device_channels(device_id, channel_id) ON DELETE CASCADE,

    -- Check constraints
    CONSTRAINT valid_alert_type CHECK (alert_type IN ('high_temp', 'low_temp', 'disconnected', 'battery_low', 'signal_poor')),
    CONSTRAINT valid_alert_level CHECK (alert_level IN ('info', 'warning', 'error', 'critical'))
);

-- Create indexes for performance optimization
CREATE INDEX IF NOT EXISTS idx_device_channels_device_id ON device_channels(device_id);
CREATE INDEX IF NOT EXISTS idx_device_channels_active ON device_channels(is_active);
CREATE INDEX IF NOT EXISTS idx_device_channels_probe_type ON device_channels(probe_type);

CREATE INDEX IF NOT EXISTS idx_live_temp_device_id ON live_temperature_readings(device_id);
CREATE INDEX IF NOT EXISTS idx_live_temp_channel_id ON live_temperature_readings(channel_id);
CREATE INDEX IF NOT EXISTS idx_live_temp_timestamp ON live_temperature_readings(timestamp);
CREATE INDEX IF NOT EXISTS idx_live_temp_device_timestamp ON live_temperature_readings(device_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_live_temp_recent ON live_temperature_readings(timestamp DESC) WHERE timestamp > CURRENT_TIMESTAMP - INTERVAL '1 hour';

CREATE INDEX IF NOT EXISTS idx_device_status_device_id ON device_status_log(device_id);
CREATE INDEX IF NOT EXISTS idx_device_status_timestamp ON device_status_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_device_status_connection ON device_status_log(connection_status);

CREATE INDEX IF NOT EXISTS idx_temp_alerts_device_id ON temperature_alerts(device_id);
CREATE INDEX IF NOT EXISTS idx_temp_alerts_active ON temperature_alerts(is_active);
CREATE INDEX IF NOT EXISTS idx_temp_alerts_level ON temperature_alerts(alert_level);
CREATE INDEX IF NOT EXISTS idx_temp_alerts_acknowledged ON temperature_alerts(acknowledged);

-- Create trigger to update updated_at timestamp for device_channels
CREATE TRIGGER update_device_channels_updated_at
    BEFORE UPDATE ON device_channels
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create view for current device status
CREATE OR REPLACE VIEW current_device_status AS
SELECT
    d.device_id,
    d.name as device_name,
    d.device_type,
    d.active as device_active,
    dsl.battery_level,
    dsl.signal_strength,
    dsl.connection_status,
    dsl.firmware_version,
    dsl.hardware_version,
    dsl.last_seen,
    dsl.timestamp as status_timestamp,
    CASE
        WHEN dsl.last_seen > CURRENT_TIMESTAMP - INTERVAL '5 minutes' THEN 'online'
        WHEN dsl.last_seen > CURRENT_TIMESTAMP - INTERVAL '15 minutes' THEN 'idle'
        ELSE 'offline'
    END as live_status
FROM devices d
LEFT JOIN device_status_log dsl ON d.device_id = dsl.device_id
    AND dsl.id = (
        SELECT id FROM device_status_log dsl2
        WHERE dsl2.device_id = d.device_id
        ORDER BY timestamp DESC LIMIT 1
    )
WHERE d.active = TRUE;

-- Create view for live device data summary
CREATE OR REPLACE VIEW live_device_data_summary AS
SELECT
    d.device_id,
    d.name as device_name,
    d.device_type,
    d.user_id,
    cds.battery_level,
    cds.signal_strength,
    cds.connection_status,
    cds.last_seen,
    cds.live_status,
    COUNT(dc.id) as total_channels,
    COUNT(CASE WHEN dc.is_active THEN 1 END) as active_channels,
    COUNT(ltr.id) as recent_readings,
    MAX(ltr.timestamp) as last_reading_time
FROM devices d
LEFT JOIN current_device_status cds ON d.device_id = cds.device_id
LEFT JOIN device_channels dc ON d.device_id = dc.device_id
LEFT JOIN live_temperature_readings ltr ON d.device_id = ltr.device_id
    AND ltr.timestamp > CURRENT_TIMESTAMP - INTERVAL '10 minutes'
WHERE d.active = TRUE
GROUP BY d.device_id, d.name, d.device_type, d.user_id,
         cds.battery_level, cds.signal_strength, cds.connection_status,
         cds.last_seen, cds.live_status;

-- Create view for current channel temperatures
CREATE OR REPLACE VIEW current_channel_temperatures AS
SELECT
    dc.device_id,
    dc.channel_id,
    dc.channel_name,
    dc.probe_type,
    dc.unit,
    dc.is_active,
    ltr.temperature,
    ltr.is_connected,
    ltr.timestamp as reading_time,
    CASE
        WHEN ltr.timestamp > CURRENT_TIMESTAMP - INTERVAL '2 minutes' THEN 'current'
        WHEN ltr.timestamp > CURRENT_TIMESTAMP - INTERVAL '10 minutes' THEN 'recent'
        ELSE 'stale'
    END as reading_status
FROM device_channels dc
LEFT JOIN live_temperature_readings ltr ON dc.device_id = ltr.device_id
    AND dc.channel_id = ltr.channel_id
    AND ltr.id = (
        SELECT id FROM live_temperature_readings ltr2
        WHERE ltr2.device_id = dc.device_id
        AND ltr2.channel_id = dc.channel_id
        ORDER BY timestamp DESC LIMIT 1
    )
WHERE dc.is_active = TRUE;

-- Insert sample data for testing
INSERT INTO device_channels (device_id, channel_id, channel_name, probe_type, unit) VALUES
    ('test_device_001', 1, 'Meat Probe 1', 'meat', 'F'),
    ('test_device_001', 2, 'Ambient Probe', 'ambient', 'F'),
    ('test_device_002', 1, 'Brisket Probe', 'meat', 'F'),
    ('test_device_002', 2, 'Pork Shoulder', 'meat', 'F'),
    ('test_device_002', 3, 'Smoker Temp', 'ambient', 'F'),
    ('test_device_002', 4, 'Water Pan', 'water', 'F')
ON CONFLICT (device_id, channel_id) DO NOTHING;

-- Insert sample live readings
INSERT INTO live_temperature_readings (device_id, channel_id, temperature, unit, is_connected) VALUES
    ('test_device_001', 1, 165.5, 'F', true),
    ('test_device_001', 2, 225.0, 'F', true),
    ('test_device_002', 1, 185.2, 'F', true),
    ('test_device_002', 2, 175.8, 'F', true),
    ('test_device_002', 3, 250.0, 'F', true),
    ('test_device_002', 4, 180.0, 'F', true);

-- Insert sample device status
INSERT INTO device_status_log (device_id, battery_level, signal_strength, connection_status, last_seen) VALUES
    ('test_device_001', 85, 92, 'online', CURRENT_TIMESTAMP),
    ('test_device_002', 78, 88, 'online', CURRENT_TIMESTAMP);

-- Create function to cleanup old live data (keep last 24 hours)
CREATE OR REPLACE FUNCTION cleanup_old_live_data()
RETURNS void AS $$
BEGIN
    -- Keep only last 24 hours of live temperature readings
    DELETE FROM live_temperature_readings
    WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '24 hours';

    -- Keep only last 7 days of device status logs
    DELETE FROM device_status_log
    WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '7 days';

    -- Keep only last 30 days of temperature alerts
    DELETE FROM temperature_alerts
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '30 days'
    AND is_active = false;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions
GRANT ALL PRIVILEGES ON device_channels TO grill_monitor;
GRANT ALL PRIVILEGES ON live_temperature_readings TO grill_monitor;
GRANT ALL PRIVILEGES ON device_status_log TO grill_monitor;
GRANT ALL PRIVILEGES ON temperature_alerts TO grill_monitor;
GRANT SELECT ON current_device_status TO grill_monitor;
GRANT SELECT ON live_device_data_summary TO grill_monitor;
GRANT SELECT ON current_channel_temperatures TO grill_monitor;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO grill_monitor;

-- Create completion marker
SELECT 'Live data schema initialization completed successfully' as status;
