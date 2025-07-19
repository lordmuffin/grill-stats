# Database Monitoring

This directory contains all the necessary configurations and scripts for monitoring the databases used in the Grill Stats application.

## Components

- **Prometheus**: Collects metrics from exporters and triggers alerts based on predefined rules
- **Grafana**: Visualizes metrics in dashboards
- **Alertmanager**: Handles and routes alerts to appropriate channels (email, Slack, etc.)
- **Exporters**: Collect metrics from specific databases
  - PostgreSQL Exporter: Metrics from PostgreSQL
  - InfluxDB: InfluxDB exposes its own metrics endpoint
  - Redis Exporter: Metrics from Redis

## Local Development Setup

To run the monitoring stack locally:

1. Start the main application with database services:
   ```
   docker-compose up -d
   ```

2. Start the monitoring stack:
   ```
   docker-compose -f docker-compose-monitoring.yml up -d
   ```

3. Access the following services:
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3001 (admin/admin)
   - Alertmanager: http://localhost:9093

## Dashboards

The following dashboards are available in Grafana:

1. **PostgreSQL Dashboard**: Database size, connections, transaction counts, and application-specific metrics
2. **InfluxDB Dashboard**: Query performance, write performance, memory usage, and temperature readings
3. **Redis Dashboard**: Memory usage, cache hit rate, connected clients, and application-specific queue metrics

## Alerts

The system includes alerts for various database conditions:

- Database availability (down alerts)
- Performance issues (high query times, too many connections)
- Capacity issues (disk space, memory usage)
- Application-specific alerts (low battery devices, offline devices, etc.)

## Directory Structure

- `/prometheus/`: Prometheus configuration and alerting rules
- `/alertmanager/`: Alertmanager configuration
- `/grafana/`: Grafana dashboards and data source configuration
- `/exporters/`: Exporter configurations for different databases

## Production Deployment

For production deployment, use the Kubernetes manifests in the `/kubernetes/` directory, which deploy the same monitoring stack in a Kubernetes environment.
