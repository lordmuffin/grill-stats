-- Migration script for adding temperature_alerts table
-- This script creates the temperature_alerts table with all required fields

BEGIN;

-- Create enum type for alert types
DO $$ BEGIN
    CREATE TYPE alert_type_enum AS ENUM ('target', 'range', 'rising', 'falling');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create temperature_alerts table
CREATE TABLE IF NOT EXISTS temperature_alerts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id VARCHAR(100) NOT NULL,
    probe_id VARCHAR(100) NOT NULL,

    -- Alert configuration
    target_temperature DECIMAL(5,2),           -- For target alerts
    min_temperature DECIMAL(5,2),              -- For range alerts
    max_temperature DECIMAL(5,2),              -- For range alerts
    threshold_value DECIMAL(5,2),              -- For rising/falling alerts

    alert_type alert_type_enum NOT NULL DEFAULT 'target',
    temperature_unit VARCHAR(1) DEFAULT 'F',   -- F or C

    -- Alert state
    is_active BOOLEAN DEFAULT true,
    triggered_at TIMESTAMP,
    last_checked_at TIMESTAMP,
    last_temperature DECIMAL(5,2),             -- Track last known temperature
    notification_sent BOOLEAN DEFAULT false,

    -- Metadata
    name VARCHAR(100),                          -- User-friendly alert name
    description VARCHAR(255),                   -- Optional description
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_target_temp CHECK (
        (alert_type = 'target' AND target_temperature IS NOT NULL) OR
        alert_type != 'target'
    ),
    CONSTRAINT valid_range_temps CHECK (
        (alert_type = 'range' AND min_temperature IS NOT NULL AND max_temperature IS NOT NULL AND min_temperature < max_temperature) OR
        alert_type != 'range'
    ),
    CONSTRAINT valid_threshold CHECK (
        (alert_type IN ('rising', 'falling') AND threshold_value IS NOT NULL AND threshold_value > 0) OR
        alert_type NOT IN ('rising', 'falling')
    ),
    CONSTRAINT valid_temp_unit CHECK (temperature_unit IN ('F', 'C'))
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_temperature_alerts_user_id ON temperature_alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_temperature_alerts_device_probe ON temperature_alerts(device_id, probe_id);
CREATE INDEX IF NOT EXISTS idx_temperature_alerts_active ON temperature_alerts(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_temperature_alerts_triggered ON temperature_alerts(triggered_at) WHERE triggered_at IS NOT NULL;

-- Create trigger to automatically update updated_at column
CREATE OR REPLACE FUNCTION update_temperature_alerts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS trigger_temperature_alerts_updated_at ON temperature_alerts;
CREATE TRIGGER trigger_temperature_alerts_updated_at
    BEFORE UPDATE ON temperature_alerts
    FOR EACH ROW
    EXECUTE FUNCTION update_temperature_alerts_updated_at();

-- Insert some sample alerts for testing (only if users table has data)
DO $$
DECLARE
    sample_user_id INTEGER;
BEGIN
    -- Check if we have any users to create sample alerts for
    SELECT id INTO sample_user_id FROM users LIMIT 1;

    IF sample_user_id IS NOT NULL THEN
        -- Sample target temperature alert
        INSERT INTO temperature_alerts (
            user_id, device_id, probe_id, name, description,
            alert_type, target_temperature, temperature_unit
        ) VALUES (
            sample_user_id, 'sample_device_1', 'probe_1', 'Grill Ready Alert',
            'Alert when grill reaches target temperature', 'target', 350.0, 'F'
        ) ON CONFLICT DO NOTHING;

        -- Sample range alert
        INSERT INTO temperature_alerts (
            user_id, device_id, probe_id, name, description,
            alert_type, min_temperature, max_temperature, temperature_unit
        ) VALUES (
            sample_user_id, 'sample_device_1', 'probe_2', 'Safe Range Alert',
            'Alert when temperature goes outside safe range', 'range', 225.0, 275.0, 'F'
        ) ON CONFLICT DO NOTHING;

        -- Sample rising alert
        INSERT INTO temperature_alerts (
            user_id, device_id, probe_id, name, description,
            alert_type, threshold_value, temperature_unit
        ) VALUES (
            sample_user_id, 'sample_device_2', 'probe_1', 'Temperature Spike Alert',
            'Alert when temperature rises quickly', 'rising', 25.0, 'F'
        ) ON CONFLICT DO NOTHING;
    END IF;
END $$;

COMMIT;

-- Verify the table was created successfully
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'temperature_alerts'
ORDER BY ordinal_position;
