# Grill-Stats Kubernetes Manifests

This directory contains the Kubernetes manifests needed to deploy the Grill-Stats application to a Kubernetes cluster using ArgoCD.

## Files

- `deployment.yaml`: Main application deployment
- `svc.yaml`: Service for network access
- `db.yaml`: PostgreSQL database deployment and service
- `pvc.yaml`: Persistent volume claim for database storage
- `cm.yaml`: ConfigMap for application configuration
- `ingress.yaml`: Ingress for external access
- `kustomization.yaml`: Ties all resources together for Kustomize
- `argocd-application.yaml`: ArgoCD Application manifest

## Deployment Steps

### 1. Prepare Registry Secret

Create a secret for pulling from your Gitea registry:

```bash
kubectl create secret docker-registry gitea-registry \
  --namespace services \
  --docker-server=gitea.lab.apj.dev \
  --docker-username=your-gitea-username \
  --docker-password=your-gitea-password \
  --docker-email=your-email@example.com
```

### 2. Create Application Secrets

```bash
# API keys
kubectl create secret generic grill-stats-secrets \
  --namespace services \
  --from-literal=thermoworks-api-key=your-api-key \
  --from-literal=homeassistant-token=your-token

# Database credentials
kubectl create secret generic grill-stats-db-credentials \
  --namespace services \
  --from-literal=username=grill-admin \
  --from-literal=password=$(openssl rand -base64 20)
```

### 3. Deploy with ArgoCD

1. Copy these manifests to your homelab repository at `apps/services/grill-stats/`
2. Apply the ArgoCD Application manifest:

```bash
kubectl apply -f argocd-application.yaml
```

3. Check the ArgoCD UI to verify the application is syncing.

## Customization

- Update the domain in `ingress.yaml` to match your actual domain
- Adjust the `homeassistant-url` in `cm.yaml` to point to your Home Assistant service
- Modify resource limits in deployment.yaml and db.yaml as needed
- Update the storage class in `pvc.yaml` to match your cluster's available storage classes