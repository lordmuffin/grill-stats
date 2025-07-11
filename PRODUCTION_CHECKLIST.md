# 🚀 Grill Stats Production Deployment Checklist

Since cluster connectivity is limited, here's a comprehensive **manual checklist** to validate your production deployment.

## ✅ **GO/NO-GO Production Deployment Checklist**

Run these commands in your homelab environment to verify deployment status:

### 🔧 **1. Kubernetes Cluster Health**

```bash
# Check cluster connectivity
kubectl cluster-info

# Check cluster nodes
kubectl get nodes

# Check grill-stats namespace
kubectl get namespace grill-stats
```

**Expected Results:**
- [ ] **GO** - Cluster accessible and responsive
- [ ] **GO** - All nodes in Ready status
- [ ] **GO** - Namespace `grill-stats` exists

---

### 🏢 **2. Core Microservices Status**

```bash
# Check all deployments
kubectl get deployments -n grill-stats

# Check pod status
kubectl get pods -n grill-stats

# Check services
kubectl get services -n grill-stats
```

**Expected Services & Status:**
- [ ] **GO** - `auth-service` - 1+ pods Running
- [ ] **GO** - `device-service` - 1+ pods Running  
- [ ] **GO** - `temperature-service` - 1+ pods Running
- [ ] **GO** - `historical-data-service` - 1+ pods Running
- [ ] **GO** - `encryption-service` - 1+ pods Running
- [ ] **GO** - `web-ui-service` - 1+ pods Running

---

### 🗄️ **3. Database Services Status**

```bash
# Check database statefulsets
kubectl get statefulsets -n grill-stats

# Check database pods
kubectl get pods -n grill-stats -l component=database

# Test database connectivity
kubectl exec -n grill-stats postgresql-0 -- pg_isready
kubectl exec -n grill-stats influxdb-0 -- influx ping
kubectl exec -n grill-stats redis-0 -- redis-cli ping
```

**Expected Database Status:**
- [ ] **GO** - `postgresql` - StatefulSet ready, pod Running
- [ ] **GO** - `influxdb` - StatefulSet ready, pod Running
- [ ] **GO** - `redis` - StatefulSet ready, pod Running
- [ ] **GO** - PostgreSQL responds to `pg_isready`
- [ ] **GO** - InfluxDB responds to `ping`
- [ ] **GO** - Redis responds to `ping`

---

### 🔐 **4. Security & Secrets Validation**

```bash
# Check 1Password secrets
kubectl get onepassworditem -n grill-stats

# Check Kubernetes secrets
kubectl get secrets -n grill-stats

# Check network policies
kubectl get networkpolicy -n grill-stats

# Check security contexts
kubectl get pods -n grill-stats -o jsonpath='{.items[*].spec.securityContext}'
```

**Expected Security Status:**
- [ ] **GO** - 1Password secrets properly injected
- [ ] **GO** - All required secrets exist
- [ ] **GO** - Network policies enforced
- [ ] **GO** - Pods running as non-root users

---

### 🌐 **5. Ingress & External Access**

```bash
# Check ingress routes
kubectl get ingressroute -n grill-stats

# Check TLS certificates
kubectl get certificate -n grill-stats

# Test web UI access
curl -k https://grill-stats.homelab.local/health
```

**Expected Ingress Status:**
- [ ] **GO** - Ingress routes configured
- [ ] **GO** - TLS certificates valid
- [ ] **GO** - Web UI accessible via HTTPS

---

### 🔒 **6. HashiCorp Vault Integration**

```bash
# Check Vault pods in vault namespace
kubectl get pods -n vault

# Test Vault connectivity from encryption service
kubectl exec -n grill-stats deployment/encryption-service -- \
  curl -s http://vault.vault.svc.cluster.local:8200/v1/sys/health
```

**Expected Vault Status:**
- [ ] **GO** - Vault pods running in vault namespace
- [ ] **GO** - Encryption service can reach Vault
- [ ] **GO** - Vault health check returns 200

---

### 📊 **7. Monitoring & Observability**

```bash
# Check ServiceMonitors
kubectl get servicemonitor -n grill-stats

# Check PrometheusRules
kubectl get prometheusrule -n grill-stats

# Check if Prometheus is scraping metrics
curl http://prometheus.monitoring.svc.cluster.local:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job | contains("grill-stats"))'
```

**Expected Monitoring Status:**
- [ ] **GO** - ServiceMonitors configured for all services
- [ ] **GO** - PrometheusRules configured for alerting
- [ ] **GO** - Prometheus actively scraping grill-stats metrics

---

### 🔄 **8. Backup System Validation**

```bash
# Check backup CronJobs
kubectl get cronjob -n grill-stats

# Check recent backup job executions
kubectl get jobs -n grill-stats | grep backup

# Check backup storage
kubectl get pvc -n grill-stats | grep backup
```

**Expected Backup Status:**
- [ ] **GO** - Backup CronJobs scheduled (postgresql, influxdb, redis)
- [ ] **GO** - Recent successful backup executions
- [ ] **GO** - Backup storage available

---

### 🧪 **9. Health Check Validation**

```bash
# Test service health endpoints
kubectl exec -n grill-stats deployment/auth-service -- curl -f http://localhost:8082/health
kubectl exec -n grill-stats deployment/device-service -- curl -f http://localhost:8080/health  
kubectl exec -n grill-stats deployment/temperature-service -- curl -f http://localhost:8081/health
kubectl exec -n grill-stats deployment/historical-data-service -- curl -f http://localhost:8083/health
kubectl exec -n grill-stats deployment/encryption-service -- curl -f http://localhost:8082/health
```

**Expected Health Status:**
- [ ] **GO** - All services respond to `/health` endpoint
- [ ] **GO** - Health checks return HTTP 200
- [ ] **GO** - No service errors in health responses

---

### 🔌 **10. End-to-End Integration Test**

```bash
# Test authentication flow
curl -X POST https://grill-stats.homelab.local/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}'

# Test device listing (with auth token)
curl -H "Authorization: Bearer <token>" \
  https://grill-stats.homelab.local/api/devices

# Test temperature data access
curl -H "Authorization: Bearer <token>" \
  https://grill-stats.homelab.local/api/temperature/current
```

**Expected Integration Status:**
- [ ] **GO** - Authentication endpoint responds
- [ ] **GO** - Device listing works with valid auth
- [ ] **GO** - Temperature data accessible
- [ ] **GO** - No critical errors in logs

---

## 📊 **Overall GO/NO-GO Assessment**

### ✅ **PRODUCTION READY (GO)** if:
- All core services (6/6) are Running
- All databases (3/3) are responsive  
- Security policies are enforced
- External access works via HTTPS
- Monitoring is collecting metrics
- Health checks pass

### ❌ **NOT READY (NO-GO)** if:
- Any core service is failing
- Database connectivity issues
- Security vulnerabilities detected
- External access not working
- Monitoring gaps identified
- Health checks failing

### ⚠️ **CONDITIONAL GO** if:
- Minor monitoring gaps
- Non-critical backup issues
- Performance warnings
- Documentation incomplete

---

## 🔧 **Quick Health Check Script**

Save this as a quick validation script:

```bash
#!/bin/bash
echo "🚀 Quick Grill Stats Health Check"
echo "=================================="

# Check core services
echo "📦 Core Services:"
kubectl get deployments -n grill-stats --no-headers | while read name ready up available age; do
  if [[ "$ready" == *"/"* ]] && [[ "${ready%/*}" == "${ready#*/}" ]]; then
    echo "  ✅ $name: $ready"
  else
    echo "  ❌ $name: $ready"
  fi
done

# Check databases  
echo "🗄️ Databases:"
kubectl get statefulsets -n grill-stats --no-headers | while read name ready age; do
  if [[ "$ready" == "1/1" ]]; then
    echo "  ✅ $name: Ready"
  else
    echo "  ❌ $name: $ready"
  fi
done

# Check ingress
echo "🌐 External Access:"
if kubectl get ingressroute -n grill-stats &>/dev/null; then
  echo "  ✅ Ingress routes configured"
else
  echo "  ❌ No ingress routes found"
fi

echo "=================================="
echo "Run full checklist for complete validation"
```

Use this checklist to validate your production deployment manually and determine GO/NO-GO status for each component.