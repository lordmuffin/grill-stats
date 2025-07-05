import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from typing import List, Dict, Optional
from datetime import datetime
import structlog

logger = structlog.get_logger()

class DeviceManager:
    def __init__(self, db_host: str, db_port: int, db_name: str, db_username: str, db_password: str):
        self.db_config = {
            'host': db_host,
            'port': db_port,
            'database': db_name,
            'user': db_username,
            'password': db_password,
            'cursor_factory': RealDictCursor
        }
        
    def get_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)
    
    def health_check(self):
        """Check database connection health"""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            conn.close()
            return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            raise
    
    def get_timestamp(self):
        """Get current timestamp"""
        return datetime.utcnow().isoformat()
    
    def init_db(self):
        """Initialize database tables"""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # Create devices table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS devices (
                        id SERIAL PRIMARY KEY,
                        device_id VARCHAR(255) UNIQUE NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        device_type VARCHAR(100) NOT NULL,
                        configuration JSONB,
                        active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create device_health table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS device_health (
                        id SERIAL PRIMARY KEY,
                        device_id VARCHAR(255) NOT NULL,
                        battery_level INTEGER,
                        signal_strength INTEGER,
                        last_seen TIMESTAMP,
                        status VARCHAR(50),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (device_id) REFERENCES devices(device_id)
                    )
                """)
                
                # Create indexes
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_devices_active ON devices(active)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_device_health_device_id ON device_health(device_id)
                """)
                
                conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error("Database initialization failed", error=str(e))
            raise
    
    def register_device(self, device_data: Dict) -> Dict:
        """Register a new device or update existing one"""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # Check if device exists
                cur.execute("SELECT * FROM devices WHERE device_id = %s", (device_data['device_id'],))
                existing_device = cur.fetchone()
                
                if existing_device:
                    # Update existing device
                    cur.execute("""
                        UPDATE devices 
                        SET name = %s, device_type = %s, configuration = %s, 
                            active = TRUE, updated_at = CURRENT_TIMESTAMP
                        WHERE device_id = %s
                        RETURNING *
                    """, (
                        device_data['name'],
                        device_data['device_type'],
                        device_data.get('configuration', {}),
                        device_data['device_id']
                    ))
                else:
                    # Insert new device
                    cur.execute("""
                        INSERT INTO devices (device_id, name, device_type, configuration)
                        VALUES (%s, %s, %s, %s)
                        RETURNING *
                    """, (
                        device_data['device_id'],
                        device_data['name'],
                        device_data['device_type'],
                        device_data.get('configuration', {})
                    ))
                
                device = cur.fetchone()
                conn.commit()
                
            conn.close()
            
            # Convert to dict and format timestamps
            device_dict = dict(device)
            device_dict['created_at'] = device_dict['created_at'].isoformat()
            device_dict['updated_at'] = device_dict['updated_at'].isoformat()
            
            logger.info("Device registered", device_id=device_data['device_id'])
            return device_dict
            
        except Exception as e:
            logger.error("Device registration failed", device_id=device_data['device_id'], error=str(e))
            raise
    
    def get_devices(self, active_only: bool = True) -> List[Dict]:
        """Get all devices"""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                if active_only:
                    cur.execute("SELECT * FROM devices WHERE active = TRUE ORDER BY created_at DESC")
                else:
                    cur.execute("SELECT * FROM devices ORDER BY created_at DESC")
                
                devices = cur.fetchall()
            conn.close()
            
            # Convert to list of dicts and format timestamps
            devices_list = []
            for device in devices:
                device_dict = dict(device)
                device_dict['created_at'] = device_dict['created_at'].isoformat()
                device_dict['updated_at'] = device_dict['updated_at'].isoformat()
                devices_list.append(device_dict)
            
            return devices_list
            
        except Exception as e:
            logger.error("Failed to get devices", error=str(e))
            raise
    
    def get_device(self, device_id: str) -> Optional[Dict]:
        """Get specific device by ID"""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM devices WHERE device_id = %s", (device_id,))
                device = cur.fetchone()
            conn.close()
            
            if device:
                device_dict = dict(device)
                device_dict['created_at'] = device_dict['created_at'].isoformat()
                device_dict['updated_at'] = device_dict['updated_at'].isoformat()
                return device_dict
            
            return None
            
        except Exception as e:
            logger.error("Failed to get device", device_id=device_id, error=str(e))
            raise
    
    def update_device(self, device_id: str, update_data: Dict) -> Optional[Dict]:
        """Update device"""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # Build dynamic update query
                update_fields = []
                values = []
                
                for field, value in update_data.items():
                    if field in ['name', 'configuration', 'active']:
                        update_fields.append(f"{field} = %s")
                        values.append(value)
                
                if not update_fields:
                    return self.get_device(device_id)
                
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                values.append(device_id)
                
                query = f"""
                    UPDATE devices 
                    SET {', '.join(update_fields)}
                    WHERE device_id = %s
                    RETURNING *
                """
                
                cur.execute(query, values)
                device = cur.fetchone()
                conn.commit()
            conn.close()
            
            if device:
                device_dict = dict(device)
                device_dict['created_at'] = device_dict['created_at'].isoformat()
                device_dict['updated_at'] = device_dict['updated_at'].isoformat()
                return device_dict
            
            return None
            
        except Exception as e:
            logger.error("Failed to update device", device_id=device_id, error=str(e))
            raise
    
    def delete_device(self, device_id: str) -> bool:
        """Delete device (mark as inactive)"""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE devices 
                    SET active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE device_id = %s
                """, (device_id,))
                
                deleted = cur.rowcount > 0
                conn.commit()
            conn.close()
            
            return deleted
            
        except Exception as e:
            logger.error("Failed to delete device", device_id=device_id, error=str(e))
            raise
    
    def update_device_health(self, device_id: str, health_data: Dict):
        """Update device health status"""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO device_health (device_id, battery_level, signal_strength, last_seen, status)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    device_id,
                    health_data.get('battery_level'),
                    health_data.get('signal_strength'),
                    health_data.get('last_seen'),
                    health_data.get('status', 'online')
                ))
                conn.commit()
            conn.close()
            
            logger.info("Device health updated", device_id=device_id)
            
        except Exception as e:
            logger.error("Failed to update device health", device_id=device_id, error=str(e))
            raise