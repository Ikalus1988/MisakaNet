# Resolving "port is already allocated" for Docker Compose

When you see the error

```
Bind for 0.0.0.0:8080 failed: port is already allocated
```

after restarting a stack, it means another process (possibly a leftover container or a stray application) is still holding the host port.

## Quick fix with the helper script

This repository includes a small script that frees the port:

```bash
# Free the default port (8080)
./scripts/free-port.sh

# Or specify a different port
./scripts/free-port.sh 8081
```

The script uses `lsof` or `fuser` to find the process listening on the given port and terminates it.

## Manual steps

If you prefer to handle it manually:

1. **Find the process**  
   - With `lsof`:  
     ```bash
     lsof -i :8080
     ```
   - With `fuser`:  
     ```bash
     fuser 8080/tcp
     ```

2. **Kill the process**  
   Note the PID from the output and run:
   ```bash
   kill -9 <PID>
   ```

3. **Verify the port is free**  
   ```bash
   lsof -i :8080   # should return nothing
   ```

4. **Restart your stack**  
   ```bash
   docker compose up -d
   ```

## Preventing future conflicts

- Always stop your stack with `docker compose down` before restarting.
- Consider adding a `stop_grace_period` to your `docker-compose.yml` to allow containers to shut down cleanly.
- If you frequently run multiple services on the same host, use different host ports or reverse proxy (e.g., Nginx) to route traffic.
