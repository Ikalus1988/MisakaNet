import os
import subprocess
import logging
from typing import List, Set, Tuple, Optional

import psutil

logger = logging.getLogger(__name__)

LLM_API_HOST = "api.deepseek.com"
LLM_API_PORT = 443


def get_own_process_tree() -> Set[int]:
    """Return the PID of the current process and all its ancestors and descendants.
    This is the safety boundary used to prevent self-kill."""
    try:
        current = psutil.Process(os.getpid())
    except psutil.Error:
        return {os.getpid()}

    tree = {current.pid}
    # ancestors
    try:
        for parent in current.parents():
            tree.add(parent.pid)
    except psutil.Error:
        pass

    # descendants
    try:
        for child in current.children(recursive=True):
            tree.add(child.pid)
    except psutil.Error:
        pass

    return tree


def resolve_process_identity(pid: int) -> Tuple[Optional[str], Optional[int]]:
    """Try to resolve a PID to a name and parent PID.
    Returns (name, ppid) or (None, None) if identity is unavailable."""
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        ppid = proc.ppid()
        return name, ppid
    except psutil.AccessDenied:
        logger.warning("Access denied resolving PID %s - identity unknown", pid)
        return None, None
    except psutil.NoSuchProcess:
        return None, None
    except psutil.Error:
        return None, None


def get_pids_by_netstat(host: str, port: int) -> List[int]:
    """Read-only discovery of PIDs with ESTABLISHED TCP to host:port.
    Does NOT kill. Returns raw PIDs."""
    try:
        # Windows netstat -ano
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            check=False,
        )
        pids = []
        for line in result.stdout.splitlines():
            if host.lower() in line.lower() and f":{port}" in line:
                if "ESTABLISHED" in line:
                    parts = line.split()
                    try:
                        pid = int(parts[-1])
                        pids.append(pid)
                    except ValueError:
                        continue
        return pids
    except Exception as e:
        logger.error("netstat discovery failed: %s", e)
        return []


def kill_pids_safe(pids: List[int], require_identity: bool = True) -> List[int]:
    """Kill only PIDs whose identity can be established and which are not part of own tree.
    Never kills by proxy signal alone.

    Raises PermissionError if a PID cannot be identified and require_identity is True.
    """
    own_tree = get_own_process_tree()
    killed = []

    for pid in pids:
        if pid in own_tree:
            logger.info("Skipping PID %s - belongs to own process tree", pid)
            continue

        name, ppid = resolve_process_identity(pid)
        if require_identity and name is None:
            # Hard stop - do not guess or label
            raise PermissionError(
                f"PID {pid} identity unknown. Cannot perform destructive action without evidence. "
                "Ask user for confirmation or use a control path that does not require PID identity."
            )

        # Identity is known, still keep label neutral
        logger.info("Identified PID %s as %s ppid=%s", pid, name, ppid)

        try:
            proc = psutil.Process(pid)
            proc.kill()
            killed.append(pid)
            logger.info("Killed PID %s", pid)
        except psutil.AccessDenied:
            logger.warning("Access denied killing PID %s", pid)
        except psutil.NoSuchProcess:
            logger.info("PID %s already gone", pid)

    return killed


def stop_llm_consumer_safe() -> dict:
    """Safe cleanup workflow for LLM API consumers.

    1. Discover read-only
    2. Exclude own tree
    3. Require identity
    4. Never invent labels like 'watchdog'
    """
    pids = get_pids_by_netstat(LLM_API_HOST, LLM_API_PORT)
    logger.info("Discovered %d PIDs with connection to %s:%s", len(pids), LLM_API_HOST, LLM_API_PORT)

    own_tree = get_own_process_tree()
    filtered = [pid for pid in pids if pid not in own_tree]

    # Do not proceed with unknown identities
    for pid in filtered:
        name, _ = resolve_process_identity(pid)
        if name is None:
            return {
                "status": "hard_stop",
                "reason": f"PID {pid} identity unknown - cannot kill safely",
                "discovered_pids": pids,
                "own_tree": list(own_tree),
            }

    # If we reach here we have identifiable candidates only
    killed = kill_pids_safe(filtered, require_identity=True)
    return {
        "status": "completed",
        "killed": killed,
        "discovered_pids": pids,
        "own_tree_excluded": list(own_tree),
    }
