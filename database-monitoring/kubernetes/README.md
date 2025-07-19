# Kubernetes Monitoring Manifests

This directory contains Kubernetes manifests for deploying the database monitoring stack in production environments.

## Components

- **Prometheus**: Time-series database for storing metrics and triggering alerts
- **Alertmanager**: Handles alert notifications via various channels (email, Slack, etc.)
- **Grafana**: Visualization platform for metrics and dashboards
- **Exporters**: Specialized components for collecting metrics from databases:
  - PostgreSQL Exporter
  - Redis Exporter
  - InfluxDB metrics endpoint

## Deployment

To deploy the monitoring stack in a Kubernetes environment:

1. Create the namespace if it doesn't exist:
   ```
   kubectl create namespace grill-stats
   ```

2. Apply the configuration files in the following order:

   **ConfigMaps:**
   ```
   kubectl apply -f prometheus-config-configmap.yaml
   kubectl apply -f prometheus-rules-configmap.yaml
   kubectl apply -f alertmanager-config-configmap.yaml
   kubectl apply -f postgres-exporter-queries-configmap.yaml
   kubectl apply -f redis-exporter-script-configmap.yaml
   kubectl apply -f grafana-datasources-configmap.yaml
   kubectl apply -f grafana-dashboards-configmap.yaml
   ```

   **Persistent Volume Claims:**
   ```
   kubectl apply -f prometheus-pvc.yaml
   kubectl apply -f alertmanager-pvc.yaml
   kubectl apply -f grafana-pvc.yaml
   ```

   **Secrets:**
   ```
   kubectl apply -f db-credentials-secret.yaml
   kubectl apply -f grafana-admin-credentials-secret.yaml
   ```

   **Deployments and Services:**
   ```
   kubectl apply -f prometheus-deployment-only.yaml
   kubectl apply -f prometheus-service.yaml
   kubectl apply -f alertmanager-deployment-only.yaml
   kubectl apply -f alertmanager-service.yaml
   kubectl apply -f grafana-deployment-only.yaml
   kubectl apply -f grafana-service.yaml
   kubectl apply -f postgres-exporter-deployment.yaml
   kubectl apply -f postgres-exporter-service.yaml
   kubectl apply -f redis-exporter-deployment.yaml
   kubectl apply -f redis-exporter-service.yaml
   ```

## Configuration

### Secrets

The deployment uses a `db-credentials` Secret for database credentials. Before deploying, ensure you have created this Secret with the correct credentials:

```
kubectl create secret generic db-credentials \
  --namespace=grill-stats \
  --from-literal=postgres-uri="postgresql://username:password@postgres:5432/grill_stats?sslmode=disable" \
  --from-literal=redis-password="your-redis-password"
```

Also, update the Grafana admin password in the `grafana-admin-credentials` Secret:

```
kubectl create secret generic grafana-admin-credentials \
  --namespace=grill-stats \
  --from-literal=password="strong-password"
```

### Alerting Configuration

To configure alerting channels:

1. Edit the `alertmanager-config-configmap.yaml` file:
   - Update SMTP settings for email alerts
   - Update Slack webhook URLs for Slack alerts

2. Apply the changes:
   ```
   kubectl apply -f alertmanager-config-configmap.yaml
   ```

## Access

After deployment, services are available at:

- **Prometheus**: Access via port-forwarding or ingress
  ```
  kubectl port-forward -n grill-stats svc/prometheus 9090:9090
  ```

- **Grafana**: Access via port-forwarding or ingress
  ```
  kubectl port-forward -n grill-stats svc/grafana 3000:3000
  ```

- **Alertmanager**: Access via port-forwarding or ingress
  ```
  kubectl port-forward -n grill-stats svc/alertmanager 9093:9093
  ```

## Ingress Configuration

For production environments, configure proper ingress resources for Grafana, Prometheus, and Alertmanager. Example:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: monitoring-ingress
  namespace: grill-stats
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  rules:
  - host: grafana.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: grafana
            port:
              number: 3000
  - host: prometheus.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: prometheus
            port:
              number: 9090
  tls:
  - hosts:
    - grafana.example.com
    - prometheus.example.com
    secretName: monitoring-tls
```

## Persistence

All stateful components use PersistentVolumeClaims for data storage:

- `prometheus-data`: Stores Prometheus time-series data
- `alertmanager-data`: Stores Alertmanager state
- `grafana-data`: Stores Grafana dashboards, users, and other configurations

Adjust the storage size and class according to your cluster's capabilities.
