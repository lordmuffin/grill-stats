-- Fix PostgreSQL schema to match requirements
-- This script updates the schema without modifying existing tables

-- Check if required extensions exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create a test user if none exists
INSERT INTO users (email, password, name, is_active, is_locked, failed_login_attempts, created_at)
VALUES
    ('test@example.com', 'password-hash', 'Test User', true, false, 0, CURRENT_TIMESTAMP)
ON CONFLICT DO NOTHING;

-- Create device_summary view
DROP VIEW IF EXISTS device_summary;
CREATE OR REPLACE VIEW device_summary AS
SELECT
    d.id,
    d.device_id,
    d.nickname as name,
    'thermoworks' as device_type,
    d.is_active as active,
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
GROUP BY d.id, d.device_id, d.nickname, d.is_active, d.created_at, d.updated_at,
         dh.battery_level, dh.signal_strength, dh.last_seen, dh.status;

-- Get the first user ID
DO $$
DECLARE
    first_user_id INTEGER;
BEGIN
    SELECT id INTO first_user_id FROM users LIMIT 1;

    -- Insert sample data for testing
    INSERT INTO devices (user_id, device_id, nickname, status, is_active)
    SELECT first_user_id, 'TW-ABC-123', 'Test Grill Monitor', 'offline', true
    WHERE NOT EXISTS (SELECT 1 FROM devices WHERE device_id = 'TW-ABC-123');

    INSERT INTO devices (user_id, device_id, nickname, status, is_active)
    SELECT first_user_id, 'TW-DEF-456', 'Test Smoker Monitor', 'offline', true
    WHERE NOT EXISTS (SELECT 1 FROM devices WHERE device_id = 'TW-DEF-456');
END $$;

-- Insert sample health data
INSERT INTO device_health (device_id, battery_level, signal_strength, last_seen, status)
SELECT 'TW-ABC-123', 85, 95, CURRENT_TIMESTAMP - INTERVAL '5 minutes', 'online'
WHERE EXISTS (SELECT 1 FROM devices WHERE device_id = 'TW-ABC-123')
  AND NOT EXISTS (SELECT 1 FROM device_health WHERE device_id = 'TW-ABC-123');

INSERT INTO device_health (device_id, battery_level, signal_strength, last_seen, status)
SELECT 'TW-DEF-456', 92, 88, CURRENT_TIMESTAMP - INTERVAL '2 minutes', 'online'
WHERE EXISTS (SELECT 1 FROM devices WHERE device_id = 'TW-DEF-456')
  AND NOT EXISTS (SELECT 1 FROM device_health WHERE device_id = 'TW-DEF-456');

-- Insert sample configuration data
INSERT INTO device_configuration (device_id, config_key, config_value, config_type)
SELECT 'TW-ABC-123', 'temperature_unit', 'fahrenheit', 'string'
WHERE EXISTS (SELECT 1 FROM devices WHERE device_id = 'TW-ABC-123')
  AND NOT EXISTS (SELECT 1 FROM device_configuration
                 WHERE device_id = 'TW-ABC-123' AND config_key = 'temperature_unit');

INSERT INTO device_configuration (device_id, config_key, config_value, config_type)
SELECT 'TW-ABC-123', 'sync_interval', '300', 'integer'
WHERE EXISTS (SELECT 1 FROM devices WHERE device_id = 'TW-ABC-123')
  AND NOT EXISTS (SELECT 1 FROM device_configuration
                 WHERE device_id = 'TW-ABC-123' AND config_key = 'sync_interval');

INSERT INTO device_configuration (device_id, config_key, config_value, config_type)
SELECT 'TW-DEF-456', 'temperature_unit', 'celsius', 'string'
WHERE EXISTS (SELECT 1 FROM devices WHERE device_id = 'TW-DEF-456')
  AND NOT EXISTS (SELECT 1 FROM device_configuration
                 WHERE device_id = 'TW-DEF-456' AND config_key = 'temperature_unit');

-- Create completion marker
SELECT 'PostgreSQL schema fix completed successfully' as status;
