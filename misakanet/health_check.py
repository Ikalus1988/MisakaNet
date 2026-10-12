from datetime import datetime, timedelta

class HealthChecker:
    def __init__(self, service_name, max_restarts_per_day=6):
        self.service_name = service_name
        self.max_restarts_per_day = max_restarts_per_day
        self.restart_count_today = 0
        self.last_restart_time = None
        self.event_counts = {}
        self.state_machine_signals = {}
        self.last_successful_output_time = {}

    def check_health(self, event_data):
        """
        Checks the health of the service based on event data.

        Args:
            event_data (dict): A dictionary containing event information.
                               Expected keys: 'event_type', 'task_id', 'timestamp', 'output_status'.

        Returns:
            tuple: A tuple containing (health_status, message).
                   health_status can be 'OK', 'BUSY', 'DEGRADED', 'CRITICAL'.
                   message is a human-readable explanation.
        """
        event_type = event_data.get('event_type')
        task_id = event_data.get('task_id')
        timestamp = event_data.get('timestamp', datetime.now())
        output_status = event_data.get('output_status')

        if event_type == "session_busy":
            self.event_counts[task_id] = self.event_counts.get(task_id, 0) + 1
            self.state_machine_signals[task_id] = self.state_machine_signals.get(task_id, {})
            self.state_machine_signals[task_id]['last_event_time'] = timestamp
            self.state_machine_signals[task_id]['event_count'] = self.event_counts[task_id]

            # Rule 1: True deadlock = same task_id repeatedly delayed >= 3 times
            if self.event_counts[task_id] >= 3:
                return 'CRITICAL', f"Task '{task_id}' repeatedly delayed ({self.event_counts[task_id]} times). Potential deadlock."

            # Rule 2: Delay exists, and last successful output is too old
            last_success_time = self.last_successful_output_time.get(task_id)
            if last_success_time and timestamp - last_success_time > timedelta(minutes=5):
                return 'DEGRADED', f"Task '{task_id}' delayed. Last successful output more than 5 minutes ago (at {last_success_time})."

            # If neither critical nor degraded, it's just busy
            return 'BUSY', f"Task '{task_id}' is busy. Event count: {self.event_counts[task_id]}. Normal backpressure."

        elif event_type == "output_success":
            self.last_successful_output_time[task_id] = timestamp
            # Reset event count for this task_id as it has now succeeded
            if task_id in self.event_counts:
                del self.event_counts[task_id]
            if task_id in self.state_machine_signals:
                del self.state_machine_signals[task_id]
            return 'OK', f"Task '{task_id}' completed successfully. Last success at {timestamp}."

        else:
            # For any other event type, consider it OK for now, or handle as needed
            return 'OK', f"Event '{event_type}' processed. Status OK."

    def should_restart(self):
        """
        Determines if a restart is warranted based on the health check.
        This method should be called after check_health has returned a non-OK status.
        """
        # This logic is intentionally kept separate to allow for different restart policies
        # For this issue, the restart is triggered by the caller based on CRITICAL/DEGRADED status.
        # The daily restart limit is handled externally or by a separate watchdog mechanism.
        return True # Placeholder, actual restart decision is based on check_health return

    def record_restart(self):
        """Records a restart action."""
        now = datetime.now()
        if self.last_restart_time and now.date() != self.last_restart_time.date():
            self.restart_count_today = 0
        self.restart_count_today += 1
        self.last_restart_time = now
        return self.restart_count_today <= self.max_restarts_per_day

# Example Usage (for demonstration, not part of the final code)
if __name__ == '__main__':
    checker = HealthChecker("MisakaNetService")

    # Simulate logs
    log1 = {'event_type': 'session_busy', 'task_id': 'msg_123', 'timestamp': datetime.now(), 'output_status': 'delayed'}
    log2 = {'event_type': 'session_busy', 'task_id': 'msg_123', 'timestamp': datetime.now() + timedelta(minutes=1), 'output_status': 'delayed'}
    log3 = {'event_type': 'session_busy', 'task_id': 'msg_123', 'timestamp': datetime.now() + timedelta(minutes=2), 'output_status': 'delayed'}
    log4 = {'event_type': 'session_busy', 'task_id': 'msg_123', 'timestamp': datetime.now() + timedelta(minutes=3), 'output_status': 'delayed'} # This should trigger CRITICAL
    log5 = {'event_type': 'output_success', 'task_id': 'msg_123', 'timestamp': datetime.now() + timedelta(minutes=6), 'output_status': 'success'} # This should reset

    print(checker.check_health(log1))
    print(checker.check_health(log2))
    print(checker.check_health(log3))
    print(checker.check_health(log4))
    print(checker.check_health(log5))

    # Simulate another scenario with delay and old success
    log6 = {'event_type': 'session_busy', 'task_id': 'msg_456', 'timestamp': datetime.now() + timedelta(minutes=10), 'output_status': 'delayed'}
    log7 = {'event_type': 'output_success', 'task_id': 'msg_456', 'timestamp': datetime.now() - timedelta(minutes=7), 'output_status': 'success'} # Old success
    log8 = {'event_type': 'session_busy', 'task_id': 'msg_456', 'timestamp': datetime.now() + timedelta(minutes=11), 'output_status': 'delayed'} # This should trigger DEGRADED

    print(checker.check_health(log6))
    print(checker.check_health(log7))
    print(checker.check_health(log8))
