# Code Story Helm Chart

A Helm chart for deploying Code Story - an AI-powered code storytelling platform - to Kubernetes.

## Prerequisites

- Kubernetes 1.25+
- Helm 3.10+
- PV provisioner (for persistent storage)
- Ingress Controller (nginx-ingress recommended)
- cert-manager (for TLS certificates)

## Installation

### Quick Start (Development)

```bash
# Add Bitnami repo for dependencies
helm repo add bitnami https://charts.bitnami.com/bitnami

# Update dependencies
helm dependency update ./charts/code-story

# Install with default values
helm install code-story ./charts/code-story \
  --namespace code-story \
  --create-namespace \
  --set secrets.jwtSecret="your-jwt-secret" \
  --set secrets.anthropicApiKey="sk-ant-..." \
  --set secrets.elevenLabsApiKey="..." \
  --set secrets.githubToken="ghp_..."
```

### Production Deployment

```bash
# Create namespace
kubectl create namespace code-story

# Create secrets (recommended: use external-secrets or sealed-secrets)
kubectl create secret generic code-story-secrets \
  --namespace code-story \
  --from-literal=jwt-secret="$(openssl rand -base64 32)" \
  --from-literal=anthropic-api-key="sk-ant-..." \
  --from-literal=elevenlabs-api-key="..." \
  --from-literal=github-token="ghp_..." \
  --from-literal=postgresql-password="$(openssl rand -base64 24)" \
  --from-literal=redis-password="$(openssl rand -base64 24)" \
  --from-literal=aws-access-key-id="..." \
  --from-literal=aws-secret-access-key="..." \
  --from-literal=supabase-url="https://your-project.supabase.co" \
  --from-literal=supabase-anon-key="..." \
  --from-literal=supabase-service-role-key="..."

# Install with production values
helm install code-story ./charts/code-story \
  --namespace code-story \
  --values ./charts/code-story/values-production.yaml \
  --set secrets.existingSecret=code-story-secrets
```

## Configuration

### Global Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.imagePullSecrets` | Image pull secrets for private registries | `[]` |

### API Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `api.replicaCount` | Number of API replicas | `1` |
| `api.image.repository` | API image repository | `ghcr.io/your-org/code-story-api` |
| `api.image.tag` | API image tag | `Chart.appVersion` |
| `api.resources.requests.cpu` | CPU request | `250m` |
| `api.resources.requests.memory` | Memory request | `256Mi` |
| `api.resources.limits.cpu` | CPU limit | `1000m` |
| `api.resources.limits.memory` | Memory limit | `1Gi` |
| `api.autoscaling.enabled` | Enable HPA | `false` |
| `api.autoscaling.minReplicas` | Minimum replicas | `1` |
| `api.autoscaling.maxReplicas` | Maximum replicas | `5` |
| `api.ingress.enabled` | Enable ingress | `false` |
| `api.ingress.className` | Ingress class | `""` |
| `api.ingress.hosts` | Ingress hosts | `[]` |

### Celery Worker Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `celeryWorker.replicaCount` | Number of worker replicas | `1` |
| `celeryWorker.concurrency` | Worker concurrency | `2` |
| `celeryWorker.queues` | Queues to process | `[default, stories]` |
| `celeryWorker.resources.requests.cpu` | CPU request | `250m` |
| `celeryWorker.resources.requests.memory` | Memory request | `512Mi` |

### Celery Beat Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `celeryBeat.enabled` | Enable Celery Beat scheduler | `true` |
| `celeryBeat.resources.requests.cpu` | CPU request | `50m` |
| `celeryBeat.resources.requests.memory` | Memory request | `64Mi` |

### Web Frontend Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `web.replicaCount` | Number of web replicas | `1` |
| `web.apiUrl` | Backend API URL | `http://localhost:8000` |
| `web.image.repository` | Web image repository | `ghcr.io/your-org/code-story-web` |
| `web.ingress.enabled` | Enable ingress | `false` |
| `web.ingress.hosts` | Ingress hosts | `[]` |

### Database Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `postgresql.enabled` | Deploy PostgreSQL | `true` |
| `postgresql.auth.database` | Database name | `codestory` |
| `postgresql.primary.persistence.size` | Storage size | `10Gi` |
| `redis.enabled` | Deploy Redis | `true` |
| `redis.master.persistence.size` | Storage size | `1Gi` |

### Secrets Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `secrets.existingSecret` | Use existing secret | `""` |
| `secrets.jwtSecret` | JWT signing secret | `""` |
| `secrets.anthropicApiKey` | Anthropic API key | `""` |
| `secrets.elevenLabsApiKey` | ElevenLabs API key | `""` |
| `secrets.githubToken` | GitHub access token | `""` |

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         Ingress                               │
│                    (nginx-ingress)                           │
└─────────────────────┬────────────────┬───────────────────────┘
                      │                │
          ┌───────────▼──────┐   ┌─────▼──────────┐
          │   Web Frontend   │   │   API Backend  │
          │     (nginx)      │   │   (FastAPI)    │
          │    2+ replicas   │   │   3+ replicas  │
          └──────────────────┘   └───────┬────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    │                    │                    │
          ┌─────────▼────────┐  ┌────────▼────────┐  ┌───────▼───────┐
          │  Celery Workers  │  │   PostgreSQL    │  │     Redis     │
          │   2-8 replicas   │  │   (primary +    │  │   (master +   │
          │                  │  │    replicas)    │  │    replicas)  │
          └──────────────────┘  └─────────────────┘  └───────────────┘
                    │
          ┌─────────▼────────┐
          │   Celery Beat    │
          │   (singleton)    │
          └──────────────────┘
```

## Security Features

- **Non-root containers**: All containers run as non-root users
- **Read-only filesystems**: Containers use read-only root filesystems
- **Network policies**: Restrict pod-to-pod communication
- **Pod security contexts**: Drop all capabilities, prevent privilege escalation
- **Secret management**: Support for external secrets managers
- **TLS**: Full TLS encryption with cert-manager integration

## Scaling

### Horizontal Pod Autoscaling

HPA is configured for API, Celery Workers, and Web Frontend based on CPU and memory utilization.

```bash
# View HPA status
kubectl get hpa -n code-story

# Manual scaling
kubectl scale deployment code-story-api --replicas=5 -n code-story
```

### Database Scaling

PostgreSQL supports read replicas for read-heavy workloads:

```yaml
postgresql:
  readReplicas:
    replicaCount: 3
```

## Monitoring

### Prometheus Metrics

Enable metrics exporters for PostgreSQL and Redis:

```yaml
postgresql:
  metrics:
    enabled: true

redis:
  metrics:
    enabled: true
```

### Health Checks

All deployments include liveness and readiness probes:
- API: `/api/health`
- Web: `/`

## Troubleshooting

### Check pod status

```bash
kubectl get pods -n code-story
kubectl describe pod <pod-name> -n code-story
kubectl logs <pod-name> -n code-story
```

### Database migrations

Migrations run automatically as a pre-upgrade hook. To run manually:

```bash
kubectl exec -it deploy/code-story-api -n code-story -- alembic upgrade head
```

### Common Issues

1. **Pods in CrashLoopBackOff**: Check logs and ensure all secrets are properly configured
2. **Database connection errors**: Verify PostgreSQL is running and secrets match
3. **Ingress not working**: Ensure ingress controller is installed and configured

## Uninstallation

```bash
helm uninstall code-story -n code-story
kubectl delete namespace code-story
```

**Warning**: This will delete all data. Backup PostgreSQL before uninstalling in production.

## License

MIT License - see LICENSE file for details.
