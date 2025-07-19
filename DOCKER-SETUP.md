# Docker Setup Guide for Grill Stats

This guide explains how to set up and run the Grill Stats application using Docker.

## Prerequisites

- Docker and Docker Compose installed
- Git repository cloned locally

## Setup Steps

1. **Create Environment File**

   Copy the example environment file and modify it with your settings:

   ```bash
   cp .env.example .env
   ```

   For local testing with mock data, you can use the following settings in your `.env` file:

   ```
   # Enable mock mode for testing without real ThermoWorks devices
   MOCK_MODE=true

   # Development environment settings
   FLASK_ENV=development
   DEBUG=true

   # Database credentials for local Docker environment
   DB_HOST=postgres
   DB_PORT=5432
   DB_NAME=grill_stats
   DB_USER=postgres
   DB_PASSWORD=postgres

   # Redis settings
   REDIS_HOST=redis
   REDIS_PORT=6379

   # InfluxDB settings
   INFLUXDB_HOST=influxdb
   INFLUXDB_PORT=8086
   INFLUXDB_DATABASE=grill_stats
   INFLUXDB_USERNAME=admin
   INFLUXDB_PASSWORD=influx-password
   ```

2. **Build and Start Docker Containers**

   Run the following command in the project root directory:

   ```bash
   docker compose up -d
   ```

   This will start the following services:
   - PostgreSQL (device management database)
   - InfluxDB (time-series data)
   - Redis (caching and pub/sub)
   - Grill Stats Application (Flask-based web app)

3. **Verify Services Are Running**

   Check that all services are running properly:

   ```bash
   docker compose ps
   ```

   All services should show status as "Up" and health checks should pass.

4. **Access the Application**

   Once all containers are running, you can access the application at:

   - Web UI: http://localhost:5000
   - API Health Check: http://localhost:5000/health
   - API Config: http://localhost:5000/api/config

## Using Mock Mode

For development and testing, the application can run in mock mode, which simulates ThermoWorks devices and data. This is enabled by setting `MOCK_MODE=true` in your `.env` file.

In mock mode:
- Random temperature data is generated
- No real ThermoWorks API credentials are needed
- The application behaves as if real devices are connected

## User Credentials

When running the application for the first time, a test user is automatically created:

- Email: `test@example.com`
- Password: `password`

You can use these credentials to log in to the web UI.

## Troubleshooting

1. **Database Connection Issues**

   If the application cannot connect to the database, check that the database containers are running and that the `.env` file has correct database settings.

2. **Port Conflicts**

   If you encounter port conflicts (e.g., "port already in use"), modify the port mappings in `docker-compose.yml`.

3. **Container Logs**

   To view logs for debugging:

   ```bash
   docker logs grill-stats-grill-stats-1
   ```

## Shutting Down

To stop all containers:

```bash
docker compose down
```

To stop containers and remove volumes (will delete all data):

```bash
docker compose down -v
```
