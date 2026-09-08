---
title: "Docker Compose Basics: Multi-Container Networking and Service Healthcheck Orchestration"
domain: devops
tags:
  - docker
  - docker-compose
  - containers
  - networking
  - healthcheck
  - orchestration
  - devops
status: published
created: "2026-09-08"
language: en
evidence_level: E2
provenance:
  source: "community"
  contributor: "s6pa1rta3n-lab"
  merged_at: "2026-09-08"
  evidence: "post-publication"
---

## Problem

When managing multi-service topologies (such as a web application, background worker, relational database, and cache) via individual `docker run` commands, developers encounter common deployment failures:

1. Application containers crash immediately upon startup because dependent databases have initialized the container process but are not yet accepting incoming TCP socket connections.
2. Inter-service hostname resolution fails because containers started separately on the default bridge network lack automatic DNS resolution.
3. Inconsistent volume mounts and uncoordinated environment variables cause drift between local development and staging environments.

## Root Cause

1. **Default Network DNS Absence**: The default Docker bridge network (`bridge`) does not support automatic container name DNS resolution. Inter-container communication requires either custom user-defined bridge networks or legacy `--link` parameters.

2. **Process Start vs Service Readiness (`depends_on`)**: By default, Docker Compose's `depends_on` directive only checks that the dependency container has started (`RUNNING` status), not that the internal daemon (such as PostgreSQL, MySQL, or Redis) has finished initialization and is ready to process queries.

3. **Uncoordinated Port Collisions and Lifecycle Drift**: Manually running containers across separate terminal sessions causes host port binding collisions, orphan volumes, and unmanaged shutdown sequences.

## Fix

### 1. Define Declarative Multi-Service Specification (`compose.yaml`)

Create a standardized Compose file using explicit custom networks, named volumes, and healthcheck-gated dependencies:

```yaml
services:
  database:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${DB_NAME:-app_db}
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_HOST_AUTH_METHOD: trust
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - internal_net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres} -d ${DB_NAME:-app_db}"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s

  cache:
    image: redis:7-alpine
    restart: unless-stopped
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data:/data
    networks:
      - internal_net
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 3

  api:
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    environment:
      DATABASE_URL: postgres://${DB_USER:-postgres}@database:5432/${DB_NAME:-app_db}
      REDIS_URL: redis://cache:6379/0
      PORT: 8080
    ports:
      - "8080:8080"
    networks:
      - internal_net
    depends_on:
      database:
        condition: service_healthy
      cache:
        condition: service_healthy

networks:
  internal_net:
    driver: bridge

volumes:
  postgres_data:
  redis_data:
```

### 2. Standardize Deployment and Lifecycle Commands

Deploy services with deterministic build caching and detached state:

```bash
docker compose up -d --build --remove-orphans
```

Gracefully stop services while preserving persistent data:

```bash
docker compose stop
```

Tear down containers, networks, and purge volumes when performing a fresh schema test:

```bash
docker compose down -v --remove-orphans
```

## Verification

Execute verification commands to validate configuration syntax, service health transitions, and inter-service network connectivity:

```bash
# Validate compose syntax without starting services
docker compose config --quiet

# Inspect service health status
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"

# Verify internal DNS resolution and database port accessibility from api
docker compose exec api nc -zv database 5432
```

**Expected output:**

Configuration validation completes silently with exit code 0.

Service health inspection confirms all dependent containers reach healthy state:

```
NAME                    STATUS         HEALTH
app-database-1          Up 20 seconds  healthy
app-cache-1             Up 20 seconds  healthy
app-api-1               Up 5 seconds   healthy
```

Network probe returns confirmed TCP connection:

```
Connection to database (port 5432) succeeded!
```
