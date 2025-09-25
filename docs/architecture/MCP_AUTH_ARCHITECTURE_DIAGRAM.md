# MCP Authentication & Deployment Diagram

```mermaid
graph TD
    subgraph Clients
        A[Claude Desktop / stdio]
        B[Web MCP Clients]
    end

    subgraph Runtime
        M[QuiltAuthMiddleware]
        RC[Runtime Context<br/>ContextVars]
        AS[AuthenticationService]
        BS[BearerAuthService]
        GS[GraphQLBearerService]
        BT[Bucket Tools]
    end

    subgraph AWS
        ALB[(Application Load Balancer)]
        TG[(Target Group)]
        ECS[ECS Fargate Service]
        CW[(CloudWatch Logs)]
        SM[(Secrets Manager)]
        IAM[IAM Roles/Policies]
        S3[(S3 Buckets)]
        STS[(STS AssumeRole)]
        Glue[(Athena/Glue)]
    end

    A -->|stdio transport| RC
    B -->|HTTPS / SSE / JWT| M

    M --> RC
    RC --> AS
    RC --> BS
    RC --> BT
    RC --> GS

    M -->|Sets env vars (legacy)| AS
    M -->|Restores env on exit| RC

    AS -->|Token validation| BS
    AS -->|AssumeRole| STS
    STS --> IAM
    STS --> ECS

    BS -->|JWT claims| RC
    BS -->|Signed requests| GS
    GS -->|GraphQL queries| ALB

    RC -->|Auth metadata| BT
    BT -->|S3 / Quilt API| S3

    B -->|HTTPS| ALB
    ALB --> TG --> ECS
    ECS -->|Logs| CW
    SM -->|Secrets| ECS
    IAM --> ECS
    ECS -->|AWS APIs| Glue
    ECS -->|AWS APIs| S3
```

**Legend**
- Runtime context isolates per-request auth state for both desktop and web clients.
- Middleware establishes environment, validates JWTs, and triggers automatic role assumption.
- AWS section highlights Fargate deployment behind ALB with Secrets Manager and IAM integration.
