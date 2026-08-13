---
{
  "title": "Tips for Debugging Kubernetes CrashLoopBackOff in a Container",
  "domain": "kubernetes",
  "tags": "",
  "language": "en",
  "status": "published",
  "source": "manual",
  "created": "2026-07-28",
  "confidence": 0.85,
  "author": "zsxh1990",
  "edited_at": "2026-07-29T09:18:36+08:00",
  "merged_by": "zsxh1990"
}
---

## Problem

CrashLoopBackOff is a Kubernetes pod status that indicates a container is crashing and being automatically restarted in a loop. This can result from several types of misconfigurations including inability to connect to persistent volumes, init-container misconfiguration, or application code failures. The primary debugging challenge is understanding why the service fails to stay running.

## Root Cause

Two common problems when starting a container are:

1. **OCI runtime create failed**: References a binary or script that doesn't exist on the container (Exit Code 127)
2. **Container "Completed" or "Error"**: The code executing on the container failed to run a service and stay running (Exit Code 1)

Exit code 137 (128 + SIGKILL 9) indicates Kubernetes hit the memory limit for the pod and killed the container.

## Solution

### Step 1: Identify Docker Entrypoint and Cmd

For containers where you lack the Dockerfile, pull and inspect the image locally:

```bash
docker pull docker.elastic.co/elasticsearch/elasticsearch:7.10.2
docker inspect docker.elastic.co/elasticsearch/elasticsearch:7.10.2 | jq '.[0].ContainerConfig.Entrypoint'
docker inspect docker.elastic.co/elasticsearch/elasticsearch:7.10.2 | jq '.[0].ContainerConfig.Cmd'
```

**Kubernetes Naming Convention**:
- Docker Entrypoint = Kubernetes `command`
- Docker Cmd = Kubernetes `args`

### Step 2: Override Container Entrypoint for Debugging

Update the deployment to replace the container entrypoint with `tail -f /dev/null` or `sleep infinity` to keep the container running without executing the problematic startup command:

```yaml
apiVersion: extensions/v1beta1
kind: Deployment
metadata:
  name: elasticsearch
  namespace: elasticsearch
spec:
  progressDeadlineSeconds: 600
  replicas: 1
  revisionHistoryLimit: 3
  selector:
    matchLabels:
      app: backend
      tier: backend
  strategy:
    rollingUpdate:
      maxSurge: 25%
      maxUnavailable: 25%
    type: RollingUpdate
  template:
    metadata:
      creationTimestamp: null
      labels:
        app: backend
        tier: backend
    spec:
      containers:
      - command:
        - tail
        - "-f"
        - /dev/null
```

### Step 3: Execute into the Container

Use kubectl or k9s to exec into the container and inspect the environment:

```
kubectl exec -it <pod-name> -- /bin/sh
```

### Step 4: Run the Intended Startup Command

Execute the original Entrypoint and Cmd you discovered to see how the application is failing and identify the specific error.

### Step 5: Install Debugging Tools

Containers may lack debugging tools (curl, lsof, vim). Try common package managers:
- Alpine Linux: `apk`
- Debian/Ubuntu: `apt-get`

## Verification

not specified in source

## Notes

- Use `kubectl describe pod <pod-name>` to view container exit codes and status messages
- Common exit statuses range from 1-125 for Unix processes
- Each Unix command has a man page with details about specific exit codes
- The `kubectl describe pod` output shows the restart count and last state of the container, which helps identify if a CrashLoopBackOff is occurring

## References

- Article: Kubernetes - How to Debug CrashLoopBackOff in a Container by David Giffin (February 4, 2021)
- Source: https://releaseapp.io/blog/kubernetes-how-to-debug-crashloopbackoff-in-a-container