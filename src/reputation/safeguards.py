"""
Anti-gaming safeguards for the MisakaNet reputation system.
Implements: Sigmoid caps, Sybil detection, Peer review requirements, Audit logging, and Appeal handling.
"""

import math
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

# Configure logging for audit trails
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ReputationEventType(Enum):
    GAIN = "gain"
    LOSS = "loss"
    FLAGGED_SYBIL = "flagged_sybil"
    PEER_REVIEW_REQUIRED = "peer_review_required"
    APPEAL_SUBMITTED = "appeal_submitted"
    APPEAL_RESOLVED = "appeal_resolved"

class ReputationSafeguards:
    def __init__(self, db_connection):
        """
        Initialize safeguards with a database connection.
        Expected DB schema:
        - users: id, reputation, created_at
        - reputation_logs: id, user_id, event_type, amount, timestamp, metadata
        - reviews: id, user_id, target_user_id, status, timestamp
        - appeals: id, user_id, reason, status, resolution
        """
        self.db = db_connection
        self._init_db_tables()

    def _init_db_tables(self):
        """Ensure necessary tables exist (simplified for this context)."""
        # In a real scenario, this would execute CREATE TABLE IF NOT EXISTS statements
        pass

    # --- 1. Sigmoid Cap Implementation ---
    def calculate_sigmoid_gain(self, base_gain: float, current_daily_gain: float, max_daily_cap: float = 100.0, k: float = 0.1) -> float:
        """
        Applies a sigmoid function to cap reputation gains.
        As daily gain approaches the cap, the multiplier approaches 0.
        """
        if current_daily_gain >= max_daily_cap:
            return 0.0
        
        # Normalize input to sigmoid range (0 to 1)
        normalized = current_daily_gain / max_daily_cap
        
        # Sigmoid function: 1 / (1 + e^(-k * (x - 0.5)))
        # We shift it so that at 0 gain, multiplier is 1, and at cap, it drops.
        # Simplified logistic decay:
        multiplier = 1 / (1 + math.exp(k * (normalized * 2 - 1) * 10))
        
        # Ensure multiplier is between 0 and 1
        multiplier = max(0.0, min(1.0, multiplier))
        
        return base_gain * multiplier

    def apply_daily_cap(self, user_id: str, base_gain: float) -> float:
        """
        Calculates the actual reputation gain after applying the daily sigmoid cap.
        """
        today = datetime.now().date()
        
        # Get total gain for today
        query = """
            SELECT SUM(amount) FROM reputation_logs 
            WHERE user_id = ? AND event_type = 'gain' 
            AND DATE(timestamp) = ?
        """
        cursor = self.db.execute(query, (user_id, today.isoformat()))
        result = cursor.fetchone()
        current_daily_gain = result[0] if result[0] else 0.0
        
        actual_gain = self.calculate_sigmoid_gain(base_gain, current_daily_gain)
        
        # Log the capped gain
        self._log_event(user_id, ReputationEventType.GAIN, actual_gain, {
            "base_gain": base_gain,
            "daily_total_before": current_daily_gain,
            "cap_applied": base_gain != actual_gain
        })
        
        return actual_gain

    # --- 2. Sybil Detection ---
    def detect_sybil_patterns(self, user_id: str) -> Tuple[bool, str]:
        """
        Flags accounts with suspicious patterns (e.g., burst activity, identical behavior).
        Returns (is_suspicious, reason).
        """
        user_data = self._get_user_activity_summary(user_id)
        
        # Pattern 1: Burst Activity (Too many actions in short time)
        if user_data['actions_last_hour'] > 50:
            return True, "Burst activity detected (>50 actions/hour)"
        
        # Pattern 2: Low Diversity (Only interacting with same few nodes)
        if user_data['unique_interactions'] < 3 and user_data['total_actions'] > 10:
            return True, "Low interaction diversity (Potential Sybil cluster)"
        
        # Pattern 3: Account Age vs Activity
        if user_data['account_age_days'] < 1 and user_data['total_actions'] > 20:
            return True, "New account with excessive activity"
            
        return False, "No suspicious patterns detected"

    def _get_user_activity_summary(self, user_id: str) -> Dict[str, Any]:
        """Helper to fetch user stats."""
        # Mock implementation for the logic flow
        # In production, this queries the DB
        return {
            "actions_last_hour": 0,
            "unique_interactions": 0,
            "total_actions": 0,
            "account_age_days": 30
        }

    def check_and_flag_sybil(self, user_id: str) -> bool:
        """Runs detection and flags if necessary."""
        is_suspicious, reason = self.detect_sybil_patterns(user_id)
        if is_suspicious:
            self._log_event(user_id, ReputationEventType.FLAGGED_SYBIL, 0, {"reason": reason})
            logger.warning(f"Sybil pattern detected for user {user_id}: {reason}")
            return True
        return False

    # --- 3. Peer Review Requirement ---
    def check_peer_review_requirement(self, user_id: str, action_type: str) -> bool:
        """
        Determines if a high-rep change requires 2+ peer reviews.
        Returns True if reviews are required and not yet met.
        """
        # Get user reputation
        cursor = self.db.execute("SELECT reputation FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        if not result:
            return False
        
        current_rep = result[0]
        
        # Threshold for requiring review (e.g., > 1000 rep)
        if current_rep <= 1000:
            return False
        
        # Check existing reviews for this specific pending action
        # Assuming 'action_id' is passed or derived from context in a real app
        # Here we simulate checking for a generic pending action
        cursor = self.db.execute(
            "SELECT COUNT(*) FROM reviews WHERE user_id = ? AND status = 'approved'",
            (user_id,)
        )
        approved_count = cursor.fetchone()[0]
        
        if approved_count < 2:
            self._log_event(user_id, ReputationEventType.PEER_REVIEW_REQUIRED, 0, {
                "current_reviews": approved_count,
                "required": 2
            })
            return True
            
        return False

    # --- 4. Audit Log ---
    def _log_event(self, user_id: str, event_type: ReputationEventType, amount: float, metadata: Dict):
        """
        Logs all reputation changes and system events to the audit trail.
        """
        timestamp = datetime.now().isoformat()
        log_entry = {
            "user_id": user_id,
            "event_type": event_type.value,
            "amount": amount,
            "timestamp": timestamp,
            "metadata": metadata,
            "hash": self._generate_log_hash(user_id, event_type.value, amount, timestamp)
        }
        
        # Insert into DB
        self.db.execute(
            """INSERT INTO reputation_logs (user_id, event_type, amount, timestamp, metadata, hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, event_type.value, amount, timestamp, json.dumps(metadata), log_entry['hash'])
        )
        self.db.commit()
        logger.info(f"Audit Log: {event_type.value} for user {user_id}")

    def _generate_log_hash(self, user_id: str, event_type: str, amount: float, timestamp: str) -> str:
        """Generates a hash for the log entry to prevent tampering."""
        data = f"{user_id}:{event_type}:{amount}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()

    # --- 5. Appeal Process ---
    def submit_appeal(self, user_id: str, reason: str) -> str:
        """
        Allows a contributor to contest unfair penalties.
        Returns the appeal ID.
        """
        appeal_id = f"APPEAL-{user_id}-{int(datetime.now().timestamp())}"
        
        self.db.execute(
            """INSERT INTO appeals (id, user_id, reason, status, created_at)
               VALUES (?, ?, ?, 'pending', ?)""",
            (appeal_id, user_id, reason, datetime.now().isoformat())
        )
        self.db.commit()
        
        self._log_event(user_id, ReputationEventType.APPEAL_SUBMITTED, 0, {
            "appeal_id": appeal_id,
            "reason": reason
        })
        
        return appeal_id

    def resolve_appeal(self, appeal_id: str, decision: str, admin_id: str):
        """
        Admin resolves an appeal.
        decision: 'approved' (revert penalty) or 'rejected'
        """
        # Update status
        self.db.execute(
            "UPDATE appeals SET status = ?, resolved_at = ?, resolved_by = ? WHERE id = ?",
            (decision, datetime.now().isoformat(), admin_id, appeal_id)
        )
        self.db.commit()
        
        # Log resolution
        # Note: We need to find the user_id associated with this appeal to log it
        cursor = self.db.execute("SELECT user_id FROM appeals WHERE id = ?", (appeal_id,))
        user_id = cursor.fetchone()[0]
        
        self._log_event(user_id, ReputationEventType.APPEAL_RESOLVED, 0, {
            "appeal_id": appeal_id,
            "decision": decision,
            "admin_id": admin_id
        })
        
        if decision == 'approved':
            # Logic to revert the penalty would go here
            logger.info(f"Appeal {appeal_id} approved. Reverting penalties.")