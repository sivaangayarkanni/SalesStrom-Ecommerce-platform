# 02 – Deployment Diagram

```mermaid
flowchart TB
  USERS[Users] --> CDN[Global CDN and WAF edge POPs]
  CDN --> ALB[Regional Load Balancer]
  subgraph Region
    subgraph AZ1[Availability Zone 1]
      K1[Kubernetes nodes - all services]
      PGP[(Postgres Primary)]
      R1[(Redis shard primary)]
      KF1[[Kafka broker]]
    end
    subgraph AZ2[Availability Zone 2]
      K2[Kubernetes nodes - all services]
      PGS[(Postgres Sync Standby)]
      R2[(Redis replica)]
      KF2[[Kafka broker]]
    end
    subgraph AZ3[Availability Zone 3]
      K3[Kubernetes nodes - all services]
      PGR[(Postgres Read Replica)]
      R3[(Redis replica)]
      KF3[[Kafka broker]]
    end
  end
  ALB --> K1
  ALB --> K2
  ALB --> K3
  PGP -->|sync replication| PGS
  PGP -->|async replication| PGR
```

| Element | Deployment choice | Why |
|---|---|---|
| Services | Kubernetes, stateless pods, HPA on CPU + request rate; **pre-scaled before sale** | Autoscaling is too slow for a 1-second spike |
| Postgres | Primary + synchronous standby (RPO≈0) + read replicas for catalog | Money and stock need zero data loss |
| Redis | Cluster, 3 shards × replica, AOF on | L3 speed; loss only slows us (DB is truth) |
| Kafka | 3 brokers, replication factor 3, `acks=all` | Durable events across AZs |
| CDN | Edge POPs, WAF rules, bot management | L1 tier; protects origin |
| Secrets | Vault / cloud secrets manager | No secrets in images |
| Observability | Prometheus, Grafana, OpenTelemetry, ELK | Metrics, traces, logs |

> **Defend it**
> - "We pre-scale before the sale because autoscalers take minutes and the spike takes one second."
> - "Losing an AZ loses no orders: sync standby for Postgres, RF=3 for Kafka."
