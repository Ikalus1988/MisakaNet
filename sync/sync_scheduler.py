"""
Sync Scheduler - Periodic sync coordination
"""
import asyncio
from datetime import datetime, timedelta
from typing import Callable, Optional
import threading


class SyncScheduler:
    """
    Scheduler for periodic sync operations.
    Manages the 30-minute sync cycle.
    """

    def __init__(self, interval_minutes: int = 30):
        self.interval_minutes = interval_minutes
        self.interval_seconds = interval_minutes * 60
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._callbacks: list[Callable] = []
        self._last_sync: Optional[datetime] = None
        self._sync_version = 0

    def add_callback(self, callback: Callable):
        """Add a callback to be called on each sync cycle"""
        self._callbacks.append(callback)

    async def start(self):
        """Start the sync scheduler"""
        self._running = True
        self._task = asyncio.create_task(self._run())
        print(f"Sync scheduler started (interval: {self.interval_minutes} min)")

    async def stop(self):
        """Stop the scheduler"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("Sync scheduler stopped")

    async def _run(self):
        """Main scheduler loop"""
        while self._running:
            try:
                await asyncio.sleep(self.interval_seconds)
                await self._trigger_sync()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Sync error: {e}")

    async def _trigger_sync(self):
        """Trigger a sync cycle"""
        self._sync_version += 1
        self._last_sync = datetime.now()
        print(f"[SYNC] Starting sync cycle #{self._sync_version}")

        # Execute all callbacks
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self._sync_version)
                else:
                    callback(self._sync_version)
            except Exception as e:
                print(f"Callback error: {e}")

        print(f"[SYNC] Completed sync cycle #{self._sync_version}")

    async def trigger_manual_sync(self):
        """Manually trigger a sync (e.g., from Master API)"""
        print("[SYNC] Manual sync triggered")
        await self._trigger_sync()

    def get_status(self) -> dict:
        """Get scheduler status"""
        return {
            "running": self._running,
            "interval_minutes": self.interval_minutes,
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "sync_version": self._sync_version,
            "callbacks_registered": len(self._callbacks)
        }

    def get_next_sync_time(self) -> Optional[datetime]:
        """Calculate next scheduled sync time"""
        if self._last_sync:
            return self._last_sync + timedelta(minutes=self.interval_minutes)
        return None


class PollingManager:
    """
    ⚠️  DEAD CODE — 当前架构使用 GitHub Issues 异步通信，无 polling 需求。
    保留供未来实时通信场景参考。
    """

    def __init__(self, interval_minutes: int = 5):
        self.interval_minutes = interval_minutes
        self.agents: dict[str, dict] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def register_agent(self, agent_id: str, last_sync_version: int = 0):
        """Register a polling agent"""
        self.agents[agent_id] = {
            "last_sync_version": last_sync_version,
            "last_poll": None,
            "status": "active"
        }
        print(f"Polling agent registered: {agent_id}")

    def unregister_agent(self, agent_id: str):
        """Unregister a polling agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            print(f"Polling agent unregistered: {agent_id}")

    async def start(self, hub_poll_endpoint: str):
        """
        Start polling loop.

        Args:
            hub_poll_endpoint: URL of Hub's poll endpoint
        """
        self._running = True
        self._hub_endpoint = hub_poll_endpoint
        self._task = asyncio.create_task(self._run())
        print(f"Polling manager started (interval: {self.interval_minutes} min)")

    async def stop(self):
        """Stop polling"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self):
        """Main polling loop"""
        while self._running:
            try:
                await asyncio.sleep(self.interval_minutes * 60)
                await self._poll_all()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Polling error: {e}")

    async def _poll_all(self):
        """Poll hub for all registered agents"""
        for agent_id, info in self.agents.items():
            try:
                # Check if sync is needed
                # In production, actually call hub endpoint
                print(f"Polling {agent_id}...")
                self.agents[agent_id]["last_poll"] = datetime.now()
            except Exception as e:
                print(f"Poll error for {agent_id}: {e}")

    def get_status(self) -> dict:
        """Get polling status for all agents"""
        return {
            "agents": self.agents,
            "polling_interval_minutes": self.interval_minutes
        }
