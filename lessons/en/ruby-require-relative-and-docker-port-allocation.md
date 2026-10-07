---
title: Ruby Path Resolution and Docker Port Allocation Issues
domain: devops
status: published
evidence_level: E1
tags: [ruby, docker, path-resolution, port-allocation, troubleshooting, shell-helpers]
summary_plain: Solutions for Ruby require_relative path errors and Docker port allocation conflicts
trigger: "require_relative LoadError OR docker port already allocated OR Bind for 0.0.0.0:8080 failed: port is already allocated"
verify: "ruby try.rb runs without LoadError; docker ps shows no conflict on 8080"
---

## Problem

This lesson addresses two distinct but commonly encountered issues in development environments:

1. A Ruby shell helper script (`try.rb`) fails during initialization with a LoadError indicating that `require_relative` cannot find the `lib/tui` directory. Ruby version and standalone code work fine, suggesting the issue is related to the script's working directory or path resolution.

2. After restarting a Docker stack, `docker compose up` fails with a port allocation error indicating that port 8080 is already in use on the host system.

## Root Cause

### Issue 1: Ruby Path Resolution
The `require_relative` directive in Ruby loads files relative to the file containing the directive, not relative to the current working directory. When the script is run from a different directory than where it's located, the relative path to `lib/tui` becomes invalid, causing the LoadError.

### Issue 2: Docker Port Allocation
When a Docker stack is restarted, containers may not immediately release the host ports they were bound to. This can happen if the container process doesn't shut down cleanly or if there's a delay in releasing network resources. As a result, when attempting to restart the stack, Docker cannot bind to the already allocated port.

## Solution

### Issue 1: Ruby Path Resolution

#### Step 1: Verify Current Working Directory
Before running the script, ensure you're in the correct directory:
```bash
pwd
```

#### Step 2: Run Script from Correct Directory
Execute the script from its containing directory:
```bash
cd /path/to/script/directory
ruby try.rb
```

#### Step 3: Modify Script for Flexibility (Optional)
If you need to run the script from other directories, modify it to use absolute paths or adjust the relative path:
```ruby
# At the top of try.rb
require File.expand_path(File.join(File.dirname(__FILE__), 'lib', 'tui'))
```

### Issue 2: Docker Port Allocation

#### Step 1: Identify Process Using the Port
Find which process is using port 8080:
```bash
lsof -i :8080
# On Linux
sudo netstat -tulpn | grep :8080
```

#### Step 2: Terminate the Conflicting Process
Kill the process that's holding the port:
```bash
# Using PID from previous command
kill -9 <PID>
```

#### Step 3: Clean Up Docker Resources
Remove any stopped containers and networks that might be holding resources:
```bash
docker-compose down -v --remove-orphans
docker system prune -f
```

## Verification

### Issue 1: Ruby Path Resolution
After implementing the solution, verify the script runs correctly:
```bash
cd <LOCAL_DIR> && ruby try.rb
```

### Issue 2: Docker Port Allocation
After resolving the port conflict, verify the stack starts successfully:
```bash
docker compose up
```

Check that the container is running and accessible on port 8080:
```bash
docker ps | grep -E '8080/tcp'
```

## Notes

- For Ruby path issues, consider using a gem or bundler for better dependency management in larger projects.
- When working with Docker, always use `docker-compose down` before restarting to ensure clean resource release.
- Port conflicts can also occur if multiple Docker Compose files are targeting the same host port.
- The `require_relative` vs `require` distinction is important: `require` searches in the load path while `require_relative` uses relative paths from the file's location.