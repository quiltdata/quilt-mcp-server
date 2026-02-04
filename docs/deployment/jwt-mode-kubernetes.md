# JWT Mode (Kubernetes)

JWT mode works well with Kubernetes when secrets are injected as env vars.

## Key Points

- Store JWT secret in Kubernetes Secret and reference via env.
- Set `QUILT_MULTIUSER_MODE=true`.
- Ensure the service account can assume the required AWS roles (IRSA on EKS).

## Example Manifest

See `docs/deployment/kubernetes-jwt.yaml`.
