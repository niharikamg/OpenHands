# Sandbox Routing Configuration

OpenHands Enterprise supports two routing modes for sandbox (runtime) URLs. This document explains the configuration options and their implications for TLS certificates and DNS setup.

## Overview

When a user starts a conversation, OpenHands creates a sandbox environment for secure agent execution. The browser needs to connect to this sandbox via WebSocket and HTTP. The **routing mode** determines how these sandbox URLs are structured.

## Routing Modes

### Subdomain Mode (Default)

In subdomain mode, each sandbox is accessible at its own subdomain:

```
https://{sandbox_id}.runtime.example.com
```

**Requirements:**
- **Wildcard DNS record**: `*.runtime.example.com` → cluster ingress IP
- **Wildcard TLS certificate**: Certificate with SAN for `*.runtime.example.com`
- One Kubernetes Ingress resource per sandbox

**Example URLs:**
```
https://abc123.runtime.example.com/api/...
https://def456.runtime.example.com/api/...
```

### Path-Based Mode

In path-based mode, all sandboxes share a single hostname with different path prefixes:

```
https://runtime.example.com/{sandbox_id}
```

**Requirements:**
- **Single DNS record**: `runtime.example.com` → cluster ingress IP
- **Non-wildcard TLS certificate**: Certificate with SAN for `runtime.example.com` only
- Single Kubernetes Gateway API Gateway shared by all sandboxes

**Example URLs:**
```
https://runtime.example.com/abc123/api/...
https://runtime.example.com/def456/api/...
```

## When to Use Path-Based Routing

Path-based routing is recommended when:

1. **Internal CA restrictions**: Your organization's certificate authority does not issue wildcard certificates
2. **Compliance requirements**: Security policies prohibit wildcard certificates
3. **Simplified certificate management**: You prefer managing a single certificate rather than wildcards
4. **DNS limitations**: Wildcard DNS records are not supported in your environment

## Configuration

### Replicated Installer (Embedded Cluster)

When installing via Replicated, configure the routing mode in the Admin Console:

1. Navigate to **Sandbox Configuration** in the config screen
2. Find **Sandbox Routing Mode**
3. Select either:
   - **Subdomain** (default): Routes at `{id}.{runtime_base}`
   - **Path-based**: Routes at `{runtime_base}/{id}`

### Environment Variables

When path-based mode is enabled, the following environment variables are automatically configured:

| Variable | Value | Description |
|----------|-------|-------------|
| `RUNTIME_ROUTING_MODE` | `path` | Enables path-based URL construction |
| `RUNTIME_URL_PATTERN` | `https://runtime.example.com/{runtime_id}` | URL template for sandbox access |
| `USE_GATEWAY_API` | `true` | Uses Kubernetes Gateway API instead of Ingress |
| `GATEWAY_NAME` | `sandbox-gateway` | Name of the shared Gateway resource |
| `RUNTIME_URL_SEPARATOR` | `/` | Path separator for routing |

### Helm Chart Values

For direct Helm deployments, configure in your values override:

```yaml
env:
  RUNTIME_ROUTING_MODE: "path"
  RUNTIME_URL_PATTERN: "https://runtime.example.com/{runtime_id}"

runtime-api:
  env:
    RUNTIME_ROUTING_MODE: "path"
    RUNTIME_URL_SEPARATOR: "/"
    USE_GATEWAY_API: "true"
    GATEWAY_NAME: "sandbox-gateway"
    RUNTIME_CERT_SECRET: "openhands-tls"
  ingressBase:
    enabled: false
  sandboxGateway:
    enabled: true
    hostname: "runtime.example.com"
    tlsSecretName: "openhands-tls"
```

## TLS Certificate Requirements

### Subdomain Mode

Your TLS certificate must include a wildcard Subject Alternative Name (SAN):

```
DNS Names:
  - example.com
  - *.example.com
  - runtime.example.com
  - *.runtime.example.com   # Required for sandbox access
```

### Path-Based Mode

Your TLS certificate only needs the base runtime hostname:

```
DNS Names:
  - example.com
  - *.example.com           # Optional, for app subdomains
  - runtime.example.com     # Required for sandbox access (no wildcard needed)
```

## Architecture

### Subdomain Mode Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster                        │
│                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │  Ingress    │    │  Ingress    │    │  Ingress    │          │
│  │  abc123.*   │    │  def456.*   │    │  ghi789.*   │   ...    │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘          │
│         │                  │                  │                  │
│         ▼                  ▼                  ▼                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │  Sandbox    │    │  Sandbox    │    │  Sandbox    │          │
│  │  abc123     │    │  def456     │    │  ghi789     │          │
│  └─────────────┘    └─────────────┘    └─────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### Path-Based Mode Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster                        │
│                                                                   │
│                    ┌──────────────────────┐                      │
│                    │   Gateway API        │                      │
│                    │   (sandbox-gateway)  │                      │
│                    └──────────┬───────────┘                      │
│                               │                                  │
│         ┌─────────────────────┼─────────────────────┐            │
│         │                     │                     │            │
│         ▼                     ▼                     ▼            │
│  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐    │
│  │ HTTPRoute   │       │ HTTPRoute   │       │ HTTPRoute   │    │
│  │ /abc123/*   │       │ /def456/*   │       │ /ghi789/*   │    │
│  └──────┬──────┘       └──────┬──────┘       └──────┬──────┘    │
│         │                     │                     │            │
│         ▼                     ▼                     ▼            │
│  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐    │
│  │  Sandbox    │       │  Sandbox    │       │  Sandbox    │    │
│  │  abc123     │       │  def456     │       │  ghi789     │    │
│  └─────────────┘       └─────────────┘       └─────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisites

### Path-Based Mode Requirements

Path-based routing requires:

1. **Gateway API CRDs**: Installed in the cluster (Traefik's `kubernetesGateway` provider installs these automatically in embedded-cluster deployments)
2. **Traefik with Gateway API support**: The embedded-cluster configuration enables this by default
3. **TLS certificate**: Stored in a Kubernetes Secret referenced by `tlsSecretName`

## Troubleshooting

### Gateway Not Ready

If the Gateway shows as not `Accepted` or `Programmed`:

```bash
kubectl get gateway sandbox-gateway -n openhands
kubectl describe gateway sandbox-gateway -n openhands
```

Common issues:
- Missing Gateway API CRDs
- TLS secret not found
- Hostname mismatch with certificate SAN

### HTTPRoutes Not Resolving

Check HTTPRoute status:

```bash
kubectl get httproutes -n openhands
kubectl describe httproute <route-name> -n openhands
```

Verify the `ResolvedRefs` condition is `True`.

### WebSocket Connection Failures

Ensure your ingress controller or Gateway supports WebSocket connections. Traefik handles this automatically.

## Related Documentation

- [Authentication Flow](./authentication.md) - Keycloak-based authentication
- [External Integrations](./external-integrations.md) - GitHub, Slack, Jira integrations
- [Kubernetes Gateway API](https://gateway-api.sigs.k8s.io/) - Official Gateway API documentation
