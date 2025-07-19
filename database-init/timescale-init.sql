-- TimescaleDB initialization script for historical temperature data
-- This script sets up the database structure for the Historical Data Service

-- Create extension for TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create temperature_readings table with optimized schema for time-series data
CREATE TABLE IF NOT EXISTS temperature_readings (
    id SERIAL,
    time TIMESTAMPTZ NOT NULL,
    device_id VARCHAR(255) NOT NULL,
    probe_id VARCHAR(255),
    grill_id VARCHAR(255),
    temperature FLOAT NOT NULL,
    unit VARCHAR(10) DEFAULT 'F',
    battery_level FLOAT,
    signal_strength FLOAT,
    metadata JSONB
);

-- Create hypertable for time-series optimization
SELECT create_hypertable('temperature_readings', 'time', if_not_exists => TRUE);

-- Create indexes for query optimization
CREATE INDEX IF NOT EXISTS idx_temperature_device_id ON temperature_readings(device_id);
CREATE INDEX IF NOT EXISTS idx_temperature_probe_id ON temperature_readings(probe_id);
CREATE INDEX IF NOT EXISTS idx_temperature_grill_id ON temperature_readings(grill_id);

-- Set up retention policy to automatically delete data older than 90 days
SELECT add_retention_policy('temperature_readings', INTERVAL '90 days', if_not_exists => TRUE);

-- Create cooking_sessions table for tracking cooking sessions
CREATE TABLE IF NOT EXISTS cooking_sessions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    grill_id VARCHAR(255),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    user_id VARCHAR(255),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for sessions table
CREATE INDEX IF NOT EXISTS idx_sessions_grill_id ON cooking_sessions(grill_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON cooking_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_time ON cooking_sessions(start_time, end_time);

-- Create session_probes table to map probes to sessions
CREATE TABLE IF NOT EXISTS session_probes (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    probe_id VARCHAR(255) NOT NULL,
    probe_name VARCHAR(255),
    target_temp FLOAT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (session_id) REFERENCES cooking_sessions(id) ON DELETE CASCADE
);

-- Create index for session_probes
CREATE INDEX IF NOT EXISTS idx_session_probes_session_id ON session_probes(session_id);
CREATE INDEX IF NOT EXISTS idx_session_probes_probe_id ON session_probes(probe_id);

-- Add compression policy for older data to save space
ALTER TABLE temperature_readings SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id, probe_id'
);

SELECT add_compression_policy('temperature_readings', INTERVAL '7 days', if_not_exists => TRUE);

-- Create continuous aggregate view for hourly temperature summaries
CREATE MATERIALIZED VIEW IF NOT EXISTS temperature_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    device_id,
    probe_id,
    grill_id,
    AVG(temperature) AS avg_temp,
    MIN(temperature) AS min_temp,
    MAX(temperature) AS max_temp,
    COUNT(*) AS reading_count
FROM temperature_readings
GROUP BY bucket, device_id, probe_id, grill_id;

-- Add refresh policy to update the continuous aggregate automatically
SELECT add_continuous_aggregate_policy('temperature_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE);

-- Create continuous aggregate view for daily temperature summaries
CREATE MATERIALIZED VIEW IF NOT EXISTS temperature_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    device_id,
    probe_id,
    grill_id,
    AVG(temperature) AS avg_temp,
    MIN(temperature) AS min_temp,
    MAX(temperature) AS max_temp,
    COUNT(*) AS reading_count
FROM temperature_readings
GROUP BY bucket, device_id, probe_id, grill_id;

-- Add refresh policy to update the daily aggregate automatically
SELECT add_continuous_aggregate_policy('temperature_daily',
    start_offset => INTERVAL '2 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Insert sample data for testing
INSERT INTO cooking_sessions (name, grill_id, start_time, end_time, user_id, metadata)
VALUES
    ('Test Brisket Cook', 'test_grill_001', NOW() - INTERVAL '2 days', NOW() - INTERVAL '1 day', 'test_user', '{"notes": "Test cook", "recipe_id": "brisket_001"}'),
    ('Test Ribs Cook', 'test_grill_001', NOW() - INTERVAL '5 days', NOW() - INTERVAL '4 days', 'test_user', '{"notes": "Test cook", "recipe_id": "ribs_001"}'),
    ('Test Chicken Cook', 'test_grill_002', NOW() - INTERVAL '7 days', NOW() - INTERVAL '6 days', 'test_user', '{"notes": "Test cook", "recipe_id": "chicken_001"}')
ON CONFLICT DO NOTHING;

-- Insert sample probe data
INSERT INTO session_probes (session_id, probe_id, probe_name, target_temp, metadata)
VALUES
    (1, 'probe_001', 'Flat', 203, '{"position": "center"}'),
    (1, 'probe_002', 'Point', 203, '{"position": "end"}'),
    (2, 'probe_001', 'Ribs Left', 195, '{"position": "left"}'),
    (2, 'probe_002', 'Ribs Right', 195, '{"position": "right"}'),
    (3, 'probe_001', 'Chicken Breast', 165, '{"position": "breast"}'),
    (3, 'probe_002', 'Chicken Thigh', 175, '{"position": "thigh"}')
ON CONFLICT DO NOTHING;

-- Create completion marker
SELECT 'TimescaleDB initialization completed successfully' as status;
