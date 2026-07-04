"""
SQLite Database Schema for Real-Time Telemetry.

Stores:
- timestamp, user_id, mouse_velocity, avg_flight_time
- active_app, risk_multiplier, session_id
"""

import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger("uba.telemetry.database")


class TelemetryDB:
    """SQLite database for telemetry storage."""
    
    def __init__(self, db_path: str = "data/telemetry.db"):
        self.db_path = db_path
        self.init_db()
        logger.info(f"TelemetryDB initialized at {db_path}")
    
    def init_db(self):
        """Initialize database schema."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            try:
                cursor = conn.cursor()

                # Main telemetry table.
                # NOTE: mitre_tactic / mitre_technique are declared here so a
                # freshly created database is self-consistent with insert_telemetry.
                # The ALTER TABLE block below back-fills them for older databases.
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS telemetry_raw (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        user_id TEXT NOT NULL,
                        session_id TEXT,

                        -- Mouse metrics
                        mouse_velocity_avg REAL,
                        mouse_velocity_std REAL,
                        mouse_click_count INTEGER,
                        mouse_positions_count INTEGER,

                        -- Keyboard metrics
                        keystroke_flight_avg_ms REAL,
                        keystroke_flight_std_ms REAL,
                        keystroke_count INTEGER,

                        -- Active window
                        active_app TEXT,
                        window_title TEXT,
                        process_id TEXT,

                        -- Computed metrics
                        risk_score REAL,
                        risk_multiplier REAL,
                        productivity_score REAL,
                        anomaly_score REAL,

                        -- MITRE ATT&CK mapping
                        mitre_tactic TEXT,
                        mitre_technique TEXT,

                        -- Metadata
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # User baseline table (7-day rolling averages)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_baselines (
                        user_id TEXT PRIMARY KEY,
                        mouse_velocity_avg REAL,
                        mouse_velocity_std REAL,
                        keystroke_flight_avg_ms REAL,
                        keystroke_flight_std_ms REAL,
                        productivity_score_avg REAL,
                        last_updated TEXT,
                        window_days INTEGER DEFAULT 7
                    )
                """)

                # Role-app mapping cache
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS role_app_mapping (
                        role TEXT,
                        app_name TEXT,
                        is_productive INTEGER,
                        PRIMARY KEY (role, app_name)
                    )
                """)

                # Aggregated metrics table (for faster queries)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS telemetry_aggregated (
                        user_id TEXT,
                        hour_timestamp TEXT,
                        avg_mouse_velocity REAL,
                        avg_keystroke_flight REAL,
                        avg_productivity_score REAL,
                        risk_score_avg REAL,
                        event_count INTEGER,
                        PRIMARY KEY (user_id, hour_timestamp)
                    )
                """)

                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_user ON telemetry_raw(user_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry_raw(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_session ON telemetry_raw(session_id)")

                # Migrate existing databases: add MITRE columns if absent
                for col, coltype in [("mitre_tactic", "TEXT"), ("mitre_technique", "TEXT")]:
                    try:
                        cursor.execute(f"ALTER TABLE telemetry_raw ADD COLUMN {col} {coltype}")
                    except Exception:
                        pass  # Column already exists

                conn.commit()
            except Exception:
                conn.rollback()
                raise
    
    def insert_telemetry(self, data: Dict) -> int:
        """
        Insert telemetry data.
        
        Args:
            data: Dictionary with telemetry fields
        
        Returns:
            Inserted row ID
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            try:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO telemetry_raw (
                        timestamp, user_id, session_id,
                        mouse_velocity_avg, mouse_velocity_std,
                        mouse_click_count, mouse_positions_count,
                        keystroke_flight_avg_ms, keystroke_flight_std_ms,
                        keystroke_count,
                        active_app, window_title, process_id,
                        risk_score, risk_multiplier, productivity_score, anomaly_score,
                        mitre_tactic, mitre_technique
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get('timestamp'),
                    data.get('user_id'),
                    data.get('session_id'),
                    data.get('mouse_velocity_avg'),
                    data.get('mouse_velocity_std'),
                    data.get('mouse_click_count'),
                    data.get('mouse_positions_count'),
                    data.get('keystroke_flight_avg_ms'),
                    data.get('keystroke_flight_std_ms'),
                    data.get('keystroke_count'),
                    data.get('active_app'),
                    data.get('window_title'),
                    data.get('process_id'),
                    data.get('risk_score'),
                    data.get('risk_multiplier'),
                    data.get('productivity_score'),
                    data.get('anomaly_score'),
                    data.get('mitre_tactic'),
                    data.get('mitre_technique'),
                ))

                row_id = cursor.lastrowid
                conn.commit()
                return row_id
            except Exception:
                conn.rollback()
                raise
    
    def get_user_telemetry(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """
        Get telemetry for a specific user.
        
        Args:
            user_id: User identifier
            limit: Maximum rows to return
            offset: Offset for pagination
        
        Returns:
            List of telemetry records
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM telemetry_raw
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """, (user_id, limit, offset))

            rows = cursor.fetchall()

        return [dict(row) for row in rows]
    
    def get_recent_telemetry(
        self,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get most recent telemetry across all users.
        
        Args:
            limit: Maximum rows to return
        
        Returns:
            List of telemetry records
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM telemetry_raw
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()

        return [dict(row) for row in rows]
    
    def update_user_baseline(self, user_id: str, window_days: int = 7):
        """
        Update user baseline from recent telemetry.
        
        Args:
            user_id: User identifier
            window_days: Number of days to include in baseline
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            try:
                cursor = conn.cursor()

                # Calculate rolling averages
                cursor.execute("""
                    SELECT
                        AVG(mouse_velocity_avg) as mv_avg,
                        AVG(mouse_velocity_std) as mv_std,
                        AVG(keystroke_flight_avg_ms) as kf_avg,
                        AVG(keystroke_flight_std_ms) as kf_std,
                        AVG(productivity_score) as prod_avg
                    FROM telemetry_raw
                    WHERE user_id = ?
                    AND timestamp >= datetime('now', ?)
                """, (user_id, f'-{window_days} days'))

                row = cursor.fetchone()

                if row[0] is not None:
                    cursor.execute("""
                        INSERT OR REPLACE INTO user_baselines (
                            user_id, mouse_velocity_avg, mouse_velocity_std,
                            keystroke_flight_avg_ms, keystroke_flight_std_ms,
                            productivity_score_avg, last_updated, window_days
                        ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)
                    """, (
                        user_id, row[0], row[1], row[2], row[3], row[4], window_days
                    ))

                conn.commit()
            except Exception:
                conn.rollback()
                raise
    
    def get_user_baseline(self, user_id: str) -> Optional[Dict]:
        """
        Get user baseline metrics.
        
        Args:
            user_id: User identifier
        
        Returns:
            Dictionary with baseline metrics or None
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM user_baselines WHERE user_id = ?
            """, (user_id,))

            row = cursor.fetchone()

        return dict(row) if row else None
    
    def get_global_integrity_summary(self) -> Dict:
        """
        Get global integrity overview across all users.
        
        Returns:
            Summary statistics
        """
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            # Get counts by risk level
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN risk_score < 50 THEN 1 ELSE 0 END) as in_zone,
                    SUM(CASE WHEN risk_score >= 50 AND risk_score < 80 THEN 1 ELSE 0 END) as anomalous,
                    SUM(CASE WHEN risk_score >= 80 THEN 1 ELSE 0 END) as critical,
                    AVG(risk_score) as avg_risk,
                    AVG(productivity_score) as avg_productivity
                FROM telemetry_raw
                WHERE timestamp >= datetime('now', '-1 hour')
            """)

            row = cursor.fetchone()

        return {
            'total_users': row[0],
            'in_zone': row[1],
            'anomalous': row[2],
            'critical': row[3],
            'avg_risk_score': row[4],
            'avg_productivity': row[5],
        }


# Global instance
telemetry_db = TelemetryDB()
