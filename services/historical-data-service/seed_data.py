#!/usr/bin/env python3
"""
Sample data seeder script for historical temperature data.
Run this script to populate the database with sample temperature data for testing.
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add the src directory to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from database.timescale_manager import TimescaleManager
from utils.data_seeder import TemperatureDataSeeder

# Load environment variables
load_dotenv()

def main():
    """Main function to seed the database with sample data."""
    
    print("🌱 Starting temperature data seeding...")
    
    # Initialize TimescaleDB manager
    try:
        timescale_manager = TimescaleManager(
            host=os.getenv('TIMESCALEDB_HOST', 'localhost'),
            port=int(os.getenv('TIMESCALEDB_PORT', '5432')),
            database=os.getenv('TIMESCALEDB_DATABASE', 'grill_monitoring'),
            username=os.getenv('TIMESCALEDB_USERNAME', 'grill_monitor'),
            password=os.getenv('TIMESCALEDB_PASSWORD', 'testpass')
        )
        
        # Initialize the database schema
        timescale_manager.init_db()
        print("✅ Database connection established and schema initialized")
        
    except Exception as e:
        print(f"❌ Failed to connect to TimescaleDB: {e}")
        print("Make sure TimescaleDB is running and environment variables are set correctly")
        return 1
    
    # Create data seeder
    seeder = TemperatureDataSeeder(timescale_manager)
    
    # Seed data for multiple devices
    device_configs = [
        {
            'device_id': 'test_device_001',
            'probe_ids': ['probe_1', 'probe_2', 'probe_3']
        },
        {
            'device_id': 'test_device_002',
            'probe_ids': ['probe_1', 'probe_2', 'probe_3', 'probe_4']
        },
        {
            'device_id': 'thermoworks_001',
            'probe_ids': ['probe_1', 'probe_2']
        }
    ]
    
    print(f"🔄 Seeding data for {len(device_configs)} devices...")
    
    try:
        results = seeder.seed_multiple_devices(
            device_configs=device_configs,
            days_back=7,  # Create data for the last 7 days
            interval_minutes=5  # One reading every 5 minutes
        )
        
        # Print results
        total_readings = 0
        for device_id, count in results.items():
            print(f"📊 {device_id}: {count} readings created")
            total_readings += count
        
        print(f"✅ Data seeding completed! Total readings: {total_readings}")
        
        # Verify data was created
        print("\n🔍 Verifying created data...")
        for device_id in results.keys():
            recent_data = timescale_manager.get_temperature_history(
                device_id=device_id,
                start_time=datetime.utcnow() - timedelta(hours=24),
                end_time=datetime.utcnow(),
                limit=10
            )
            print(f"   {device_id}: {len(recent_data)} readings in last 24 hours")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error during data seeding: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)