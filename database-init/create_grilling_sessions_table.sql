-- Migration script for grilling_sessions table
-- This script creates the grilling_sessions table and related indexes

-- Create grilling_sessions table
CREATE TABLE IF NOT EXISTS grilling_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name VARCHAR(100),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    devices_used TEXT,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'completed', 'cancelled')),
    max_temperature DECIMAL(5,2),
    min_temperature DECIMAL(5,2),
    avg_temperature DECIMAL(5,2),
    duration_minutes INTEGER,
    session_type VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint to users table
    CONSTRAINT fk_grilling_sessions_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_grilling_sessions_user_id ON grilling_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_grilling_sessions_status ON grilling_sessions(status);
CREATE INDEX IF NOT EXISTS idx_grilling_sessions_start_time ON grilling_sessions(start_time);
CREATE INDEX IF NOT EXISTS idx_grilling_sessions_created_at ON grilling_sessions(created_at);

-- Create composite index for common queries
CREATE INDEX IF NOT EXISTS idx_grilling_sessions_user_status_start ON grilling_sessions(user_id, status, start_time DESC);

-- Add trigger to automatically update the updated_at column
CREATE OR REPLACE FUNCTION update_grilling_sessions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_grilling_sessions_updated_at ON grilling_sessions;
CREATE TRIGGER trigger_update_grilling_sessions_updated_at
    BEFORE UPDATE ON grilling_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_grilling_sessions_updated_at();

-- Create view for active sessions with calculated duration
CREATE OR REPLACE VIEW active_grilling_sessions AS
SELECT 
    s.*,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - s.start_time))/60 AS current_duration_minutes,
    u.email as user_email,
    u.name as user_name
FROM grilling_sessions s
JOIN users u ON s.user_id = u.id
WHERE s.status = 'active';

-- Create view for session statistics
CREATE OR REPLACE VIEW grilling_session_stats AS
SELECT 
    user_id,
    COUNT(*) as total_sessions,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_sessions,
    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_sessions,
    COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_sessions,
    AVG(duration_minutes) as avg_duration_minutes,
    MAX(max_temperature) as highest_temp_recorded,
    MIN(min_temperature) as lowest_temp_recorded,
    COUNT(CASE WHEN session_type = 'smoking' THEN 1 END) as smoking_sessions,
    COUNT(CASE WHEN session_type = 'grilling' THEN 1 END) as grilling_sessions,
    COUNT(CASE WHEN session_type = 'roasting' THEN 1 END) as roasting_sessions
FROM grilling_sessions
GROUP BY user_id;

-- Grant permissions (adjust as needed for your user setup)
-- GRANT SELECT, INSERT, UPDATE, DELETE ON grilling_sessions TO grill_stats_app;
-- GRANT SELECT ON active_grilling_sessions TO grill_stats_app;
-- GRANT SELECT ON grilling_session_stats TO grill_stats_app;
-- GRANT USAGE, SELECT ON SEQUENCE grilling_sessions_id_seq TO grill_stats_app;

-- Insert some sample data for testing (optional - uncomment if needed)
/*
INSERT INTO grilling_sessions (user_id, name, start_time, end_time, devices_used, status, max_temperature, min_temperature, avg_temperature, duration_minutes, session_type, notes)
VALUES 
    (1, 'Weekend BBQ', '2024-01-15 14:00:00', '2024-01-15 18:30:00', '["device_001", "device_002"]', 'completed', 450.5, 225.0, 325.5, 270, 'grilling', 'Great family BBQ session'),
    (1, 'Brisket Smoke', '2024-01-20 08:00:00', '2024-01-20 20:00:00', '["device_001"]', 'completed', 275.0, 225.0, 250.0, 720, 'smoking', 'Low and slow brisket cook'),
    (1, 'Quick Dinner', '2024-01-25 17:30:00', null, '["device_002"]', 'active', 400.0, 350.0, 375.0, null, 'grilling', 'Quick weeknight dinner');
*/

-- Verify the table was created successfully
SELECT 
    table_name, 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'grilling_sessions' 
ORDER BY ordinal_position;