-- Add user_id to devices table to associate devices with users
ALTER TABLE devices ADD COLUMN IF NOT EXISTS user_id INTEGER;

-- Add foreign key constraint (assuming users table exists from auth service)
ALTER TABLE devices
ADD CONSTRAINT fk_devices_user_id
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- Create index for user_id to improve query performance
CREATE INDEX IF NOT EXISTS idx_devices_user_id ON devices(user_id);

-- Create a composite index for user_id + active for efficient user device queries
CREATE INDEX IF NOT EXISTS idx_devices_user_active ON devices(user_id, active);

-- Update existing devices to be associated with a default user (optional, for testing)
-- UPDATE devices SET user_id = 1 WHERE user_id IS NULL;

-- Create view for user devices with health information
CREATE OR REPLACE VIEW user_devices_summary AS
SELECT
    d.device_id,
    d.name,
    d.device_type,
    d.active,
    d.user_id,
    d.created_at,
    d.updated_at,
    dh.battery_level,
    dh.signal_strength,
    dh.last_seen,
    dh.status as health_status,
    CASE
        WHEN dh.last_seen > CURRENT_TIMESTAMP - INTERVAL '10 minutes' THEN 'online'
        WHEN dh.last_seen > CURRENT_TIMESTAMP - INTERVAL '1 hour' THEN 'idle'
        ELSE 'offline'
    END as connection_status,
    d.configuration
FROM devices d
LEFT JOIN device_health dh ON d.device_id = dh.device_id
    AND dh.id = (
        SELECT id FROM device_health dh2
        WHERE dh2.device_id = d.device_id
        ORDER BY created_at DESC LIMIT 1
    )
WHERE d.active = TRUE;

-- Grant permissions on new view
GRANT SELECT ON user_devices_summary TO grill_monitor;
