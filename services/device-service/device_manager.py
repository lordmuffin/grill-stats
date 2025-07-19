import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
import structlog
from psycopg2.extras import RealDictCursor

logger = structlog.get_logger()


class DeviceManager:
    def __init__(
        self,
        db_host: str,
        db_port: int,
        db_name: str,
        db_username: str,
        db_password: str,
    ):
        self.db_config = {
            "host": db_host,
            "port": db_port,
            "database": db_name,
            "user": db_username,
            "password": db_password,
            "cursor_factory": RealDictCursor,
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
                cur.execute(
                    """
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
                """
                )

                # Create device_health table
                cur.execute(
                    """
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
                """
                )

                # Create gateway_status table for RFX gateways
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS gateway_status (
                        id SERIAL PRIMARY KEY,
                        gateway_id VARCHAR(255) NOT NULL,
                        online BOOLEAN DEFAULT FALSE,
                        wifi_connected BOOLEAN DEFAULT FALSE,
                        wifi_ssid VARCHAR(255),
                        wifi_signal_strength INTEGER,
                        cloud_linked BOOLEAN DEFAULT FALSE,
                        last_seen TIMESTAMP,
                        status VARCHAR(50) DEFAULT 'unknown',
                        firmware_version VARCHAR(50),
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (gateway_id) REFERENCES devices(device_id)
                    )
                """
                )

                # Create indexes
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices(device_id)
                """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_devices_active ON devices(active)
                """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_device_health_device_id ON device_health(device_id)
                """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_gateway_status_gateway_id ON gateway_status(gateway_id)
                """
                )
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_gateway_status_online ON gateway_status(online)
                """
                )

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
                cur.execute(
                    "SELECT * FROM devices WHERE device_id = %s",
                    (device_data["device_id"],),
                )
                existing_device = cur.fetchone()

                if existing_device:
                    # Update existing device
                    update_fields = [
                        "name = %s",
                        "device_type = %s",
                        "configuration = %s",
                        "active = TRUE",
                        "updated_at = CURRENT_TIMESTAMP",
                    ]
                    update_values = [
                        device_data["name"],
                        device_data["device_type"],
                        device_data.get("configuration", {}),
                    ]

                    # Add user_id if provided
                    if "user_id" in device_data:
                        update_fields.insert(3, "user_id = %s")
                        update_values.append(device_data["user_id"])

                    update_values.append(device_data["device_id"])

                    cur.execute(
                        f"""
                        UPDATE devices
                        SET {', '.join(update_fields)}
                        WHERE device_id = %s
                        RETURNING *
                    """,
                        update_values,
                    )
                else:
                    # Insert new device
                    fields = ["device_id", "name", "device_type", "configuration"]
                    values = [
                        device_data["device_id"],
                        device_data["name"],
                        device_data["device_type"],
                        device_data.get("configuration", {}),
                    ]

                    # Add user_id if provided
                    if "user_id" in device_data:
                        fields.append("user_id")
                        values.append(device_data["user_id"])

                    placeholders = ", ".join(["%s"] * len(values))

                    cur.execute(
                        f"""
                        INSERT INTO devices ({', '.join(fields)})
                        VALUES ({placeholders})
                        RETURNING *
                    """,
                        values,
                    )

                device = cur.fetchone()
                conn.commit()

            conn.close()

            # Convert to dict and format timestamps
            device_dict = dict(device)
            device_dict["created_at"] = device_dict["created_at"].isoformat()
            device_dict["updated_at"] = device_dict["updated_at"].isoformat()

            logger.info("Device registered", device_id=device_data["device_id"])
            return device_dict

        except Exception as e:
            logger.error(
                "Device registration failed",
                device_id=device_data["device_id"],
                error=str(e),
            )
            raise

    def get_devices(
        self, active_only: bool = True, user_id: Optional[int] = None
    ) -> List[Dict]:
        """Get all devices, optionally filtered by user"""
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                query = "SELECT * FROM devices WHERE 1=1"
                params = []

                if active_only:
                    query += " AND active = TRUE"

                if user_id is not None:
                    query += " AND user_id = %s"
                    params.append(user_id)

                query += " ORDER BY created_at DESC"

                cur.execute(query, params)
                devices = cur.fetchall()
            conn.close()

            # Convert to list of dicts and format timestamps
            devices_list = []
            for device in devices:
                device_dict = dict(device)
                device_dict["created_at"] = device_dict["created_at"].isoformat()
                device_dict["updated_at"] = device_dict["updated_at"].isoformat()
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
                device_dict["created_at"] = device_dict["created_at"].isoformat()
                device_dict["updated_at"] = device_dict["updated_at"].isoformat()
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
                    if field in ["name", "configuration", "active"]:
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
                device_dict["created_at"] = device_dict["created_at"].isoformat()
                device_dict["updated_at"] = device_dict["updated_at"].isoformat()
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
                cur.execute(
                    """
                    UPDATE devices
                    SET active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE device_id = %s
                """,
                    (device_id,),
                )

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
                cur.execute(
                    """
                    INSERT INTO device_health (device_id, battery_level, signal_strength, last_seen, status)
                    VALUES (%s, %s, %s, %s, %s)
                """,
                    (
                        device_id,
                        health_data.get("battery_level"),
                        health_data.get("signal_strength"),
                        health_data.get("last_seen"),
                        health_data.get("status", "online"),
                    ),
                )
                conn.commit()
            conn.close()

            logger.info("Device health updated", device_id=device_id)

        except Exception as e:
            logger.error(
                "Failed to update device health", device_id=device_id, error=str(e)
            )
            raise

    def register_gateway(self, gateway_data: Dict) -> Dict:
        """
        Register a new RFX Gateway device

        Args:
            gateway_data: Gateway information including device_id, name, etc.

        Returns:
            Registered gateway information
        """
        try:
            # First register as a regular device
            device_data = {
                "device_id": gateway_data["gateway_id"],
                "name": gateway_data.get(
                    "name", f"RFX Gateway {gateway_data['gateway_id'][-6:]}"
                ),
                "device_type": "rfx_gateway",
                "configuration": gateway_data.get("configuration", {}),
            }

            device = self.register_device(device_data)

            # Then add gateway-specific status
            conn = self.get_connection()
            with conn.cursor() as cur:
                # Check if gateway status exists
                cur.execute(
                    "SELECT id FROM gateway_status WHERE gateway_id = %s",
                    (gateway_data["gateway_id"],),
                )
                exists = cur.fetchone()

                if exists:
                    # Update existing gateway status
                    cur.execute(
                        """
                        UPDATE gateway_status
                        SET online = %s,
                            wifi_connected = %s,
                            wifi_ssid = %s,
                            wifi_signal_strength = %s,
                            cloud_linked = %s,
                            last_seen = %s,
                            status = %s,
                            firmware_version = %s,
                            metadata = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE gateway_id = %s
                        RETURNING *
                    """,
                        (
                            gateway_data.get("online", False),
                            gateway_data.get("wifi_connected", False),
                            gateway_data.get("wifi_ssid"),
                            gateway_data.get("wifi_signal_strength"),
                            gateway_data.get("cloud_linked", False),
                            gateway_data.get("last_seen", datetime.utcnow()),
                            gateway_data.get("status", "unknown"),
                            gateway_data.get("firmware_version"),
                            json.dumps(gateway_data.get("metadata", {})),
                            gateway_data["gateway_id"],
                        ),
                    )
                else:
                    # Insert new gateway status
                    cur.execute(
                        """
                        INSERT INTO gateway_status (
                            gateway_id, online, wifi_connected, wifi_ssid,
                            wifi_signal_strength, cloud_linked, last_seen,
                            status, firmware_version, metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING *
                    """,
                        (
                            gateway_data["gateway_id"],
                            gateway_data.get("online", False),
                            gateway_data.get("wifi_connected", False),
                            gateway_data.get("wifi_ssid"),
                            gateway_data.get("wifi_signal_strength"),
                            gateway_data.get("cloud_linked", False),
                            gateway_data.get("last_seen", datetime.utcnow()),
                            gateway_data.get("status", "unknown"),
                            gateway_data.get("firmware_version"),
                            json.dumps(gateway_data.get("metadata", {})),
                        ),
                    )

                gateway_status = cur.fetchone()
                conn.commit()
            conn.close()

            # Combine device and gateway status
            result = device.copy()
            result["gateway_status"] = dict(gateway_status)

            # Format timestamps
            for key in ["created_at", "updated_at"]:
                if key in result["gateway_status"] and result["gateway_status"][key]:
                    result["gateway_status"][key] = result["gateway_status"][
                        key
                    ].isoformat()

            if (
                "last_seen" in result["gateway_status"]
                and result["gateway_status"]["last_seen"]
            ):
                result["gateway_status"]["last_seen"] = result["gateway_status"][
                    "last_seen"
                ].isoformat()

            logger.info("Gateway registered", gateway_id=gateway_data["gateway_id"])
            return result

        except Exception as e:
            logger.error(
                "Failed to register gateway",
                gateway_id=gateway_data.get("gateway_id"),
                error=str(e),
            )
            raise

    def update_gateway_status(self, gateway_id: str, status_data: Dict) -> Dict:
        """
        Update the status of an RFX Gateway

        Args:
            gateway_id: Gateway ID
            status_data: Status information

        Returns:
            Updated gateway status information
        """
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # Check if gateway exists
                cur.execute(
                    "SELECT id FROM devices WHERE device_id = %s", (gateway_id,)
                )
                device_exists = cur.fetchone()

                if not device_exists:
                    raise ValueError(f"Gateway {gateway_id} not found")

                # Check if gateway status exists
                cur.execute(
                    "SELECT id FROM gateway_status WHERE gateway_id = %s", (gateway_id,)
                )
                status_exists = cur.fetchone()

                # Prepare update fields
                fields = []
                values = []

                for field in [
                    "online",
                    "wifi_connected",
                    "wifi_ssid",
                    "wifi_signal_strength",
                    "cloud_linked",
                    "last_seen",
                    "status",
                    "firmware_version",
                ]:
                    if field in status_data:
                        fields.append(f"{field} = %s")
                        values.append(status_data[field])

                # Handle metadata separately to merge with existing
                if "metadata" in status_data:
                    if status_exists:
                        # Get existing metadata
                        cur.execute(
                            "SELECT metadata FROM gateway_status WHERE gateway_id = %s",
                            (gateway_id,),
                        )
                        result = cur.fetchone()
                        existing_metadata = (
                            result["metadata"] if result and result["metadata"] else {}
                        )

                        # Merge metadata
                        if isinstance(existing_metadata, str):
                            try:
                                existing_metadata = json.loads(existing_metadata)
                            except:
                                existing_metadata = {}

                        # Update with new metadata
                        existing_metadata.update(status_data["metadata"])

                        # Add to update
                        fields.append("metadata = %s")
                        values.append(json.dumps(existing_metadata))
                    else:
                        # Just use new metadata
                        fields.append("metadata = %s")
                        values.append(json.dumps(status_data["metadata"]))

                if not fields:
                    conn.close()
                    return self.get_gateway_status(gateway_id)

                # Add updated_at and gateway_id
                fields.append("updated_at = CURRENT_TIMESTAMP")
                values.append(gateway_id)

                if status_exists:
                    # Update existing status
                    query = f"""
                        UPDATE gateway_status
                        SET {', '.join(fields)}
                        WHERE gateway_id = %s
                        RETURNING *
                    """
                else:
                    # Insert new status
                    all_fields = ["gateway_id"] + [
                        f.split(" = ")[0] for f in fields[:-1]
                    ]  # Remove updated_at
                    placeholders = ["%s"] * len(all_fields)

                    query = f"""
                        INSERT INTO gateway_status ({', '.join(all_fields)})
                        VALUES ({', '.join(placeholders)})
                        RETURNING *
                    """

                cur.execute(query, values)
                gateway_status = cur.fetchone()
                conn.commit()
            conn.close()

            # Format timestamps
            result = dict(gateway_status)
            for key in ["created_at", "updated_at"]:
                if key in result and result[key]:
                    result[key] = result[key].isoformat()

            if "last_seen" in result and result["last_seen"]:
                result["last_seen"] = result["last_seen"].isoformat()

            logger.info("Gateway status updated", gateway_id=gateway_id)
            return result

        except Exception as e:
            logger.error(
                "Failed to update gateway status", gateway_id=gateway_id, error=str(e)
            )
            raise

    def get_gateway_status(self, gateway_id: str) -> Optional[Dict]:
        """
        Get the status of an RFX Gateway

        Args:
            gateway_id: Gateway ID

        Returns:
            Gateway status information or None if not found
        """
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # Get gateway status
                cur.execute(
                    """
                    SELECT gs.*, d.name, d.device_type, d.configuration
                    FROM gateway_status gs
                    JOIN devices d ON gs.gateway_id = d.device_id
                    WHERE gs.gateway_id = %s
                """,
                    (gateway_id,),
                )

                status = cur.fetchone()
            conn.close()

            if status:
                # Format timestamps
                result = dict(status)
                for key in ["created_at", "updated_at"]:
                    if key in result and result[key]:
                        result[key] = result[key].isoformat()

                if "last_seen" in result and result["last_seen"]:
                    result["last_seen"] = result["last_seen"].isoformat()

                return result

            return None

        except Exception as e:
            logger.error(
                "Failed to get gateway status", gateway_id=gateway_id, error=str(e)
            )
            raise

    def get_all_gateways(self, active_only: bool = True) -> List[Dict]:
        """
        Get all registered RFX Gateways

        Args:
            active_only: Whether to return only active gateways

        Returns:
            List of gateway information dictionaries
        """
        try:
            conn = self.get_connection()
            with conn.cursor() as cur:
                # Get all gateways with status
                query = """
                    SELECT d.*, gs.*
                    FROM devices d
                    LEFT JOIN gateway_status gs ON d.device_id = gs.gateway_id
                    WHERE d.device_type = 'rfx_gateway'
                """

                if active_only:
                    query += " AND d.active = TRUE"

                query += " ORDER BY d.created_at DESC"

                cur.execute(query)
                gateways = cur.fetchall()
            conn.close()

            # Format timestamps and clean up duplicated fields
            result = []
            for gateway in gateways:
                gateway_dict = dict(gateway)

                # Handle timestamps
                for key in ["created_at", "updated_at"]:
                    if key in gateway_dict and gateway_dict[key]:
                        gateway_dict[key] = gateway_dict[key].isoformat()

                if "last_seen" in gateway_dict and gateway_dict["last_seen"]:
                    gateway_dict["last_seen"] = gateway_dict["last_seen"].isoformat()

                result.append(gateway_dict)

            return result

        except Exception as e:
            logger.error("Failed to get all gateways", error=str(e))
            raise
