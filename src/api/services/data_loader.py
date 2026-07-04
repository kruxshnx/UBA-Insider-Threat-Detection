"""
Central data-access layer for the API.
- TTL-based in-memory caching for CSV data
- Proper structured logging (no print statements)
- Defensive data parsing
"""

import pandas as pd
import os
import time
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.api.config import settings

DB_PATH = os.path.join("data", "telemetry.db")


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

logger = logging.getLogger("uba.data_loader")


# =============================================================================
# CACHE
# =============================================================================
class _Cache:
    """Simple TTL-based in-memory cache."""

    def __init__(self, ttl_seconds: int = 30):
        self.ttl = ttl_seconds
        self._store: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}

    def get(self, key: str):
        ts = self._timestamps.get(key)
        if ts is not None and (time.time() - ts) < self.ttl:
            return self._store.get(key)
        return None

    def set(self, key: str, value):
        self._store[key] = value
        self._timestamps[key] = time.time()

    def clear(self):
        self._store.clear()
        self._timestamps.clear()
        logger.info("Data cache cleared.")


# =============================================================================
# DATA LOADER
# =============================================================================
class DataLoader:
    """Central data access layer for the API."""

    def __init__(self):
        self._cache = _Cache(ttl_seconds=settings.DATA_CACHE_TTL_SECONDS)

    def clear_cache(self):
        """Public method for admin endpoint."""
        self._cache.clear()

    # ── CSV Loading ──────────────────────────────────────────────────────────
    def _load_csv(self, filename: str, directory: str = None) -> Optional[pd.DataFrame]:
        """Load a CSV file, with cache support."""
        dir_path = directory or settings.RISK_OUTPUT_DIR
        cache_key = f"{dir_path}/{filename}"

        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        path = os.path.join(dir_path, filename)
        if not os.path.exists(path):
            logger.debug("File not found: %s", path)
            return None
        try:
            df = pd.read_csv(path, encoding="utf-8")
            self._cache.set(cache_key, df)
            logger.debug("Loaded %s (%d rows)", filename, len(df))
            return df
        except Exception as e:
            logger.error("Error loading %s: %s", filename, e)
            return None

    # ── User Risk (SQLite) ───────────────────────────────────────────────────
    def get_users_risk_data(self, limit: int = 50, sort_desc: bool = True) -> List[dict]:
        """Return users ranked by real risk_score from SQLite users table."""
        try:
            order = "DESC" if sort_desc else "ASC"
            conn = _get_db()
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT user_id AS user, name, role, department,
                       risk_score AS total_risk_score,
                       productivity_score, last_seen
                FROM users
                WHERE is_active = 1 OR is_active IS NULL
                ORDER BY risk_score {order}
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            conn.close()
            result = []
            for r in rows:
                score = float(r["total_risk_score"] or 0)
                result.append({
                    "user": r["user"],
                    "name": r["name"],
                    "role": r["role"] or "Employee",
                    "department": r["department"] or "General",
                    "total_risk_score": round(score, 2),
                    "productivity_score": float(r["productivity_score"] or 1.0),
                    "last_seen": r["last_seen"],
                    "risk_level": (
                        "Critical" if score >= 80 else
                        "High" if score >= 60 else
                        "Medium" if score >= 40 else "Low"
                    ),
                })
            return result
        except Exception as e:
            logger.error("get_users_risk_data SQLite error: %s", e)
            return []

    # ── Single User Profile (SQLite) ─────────────────────────────────────────
    def get_user_profile(self, user_id: str) -> Optional[dict]:
        """Return risk profile for a single user from SQLite."""
        try:
            conn = _get_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id, name, role, department,
                       risk_score, productivity_score, last_seen
                FROM users WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            score = float(row["risk_score"] or 0)
            # Count events and avg from telemetry
            cursor.execute("""
                SELECT COUNT(*) as cnt, AVG(risk_score) as avg_r,
                       MAX(risk_score) as max_r, AVG(productivity_score) as avg_p
                FROM telemetry_raw WHERE user_id = ?
            """, (user_id,))
            tel = cursor.fetchone()
            # Rank by risk_score
            cursor.execute("""
                SELECT COUNT(*) FROM users
                WHERE risk_score > ? AND (is_active = 1 OR is_active IS NULL)
            """, (score,))
            rank_row = cursor.fetchone()
            conn.close()
            return {
                "user": user_id,
                "name": row["name"],
                "role": row["role"] or "Employee",
                "department": row["department"] or "General",
                "total_risk_score": round(score, 2),
                "productivity_score": float(row["productivity_score"] or 1.0),
                "last_seen": row["last_seen"],
                "risk_level": (
                    "Critical" if score >= 80 else
                    "High" if score >= 60 else
                    "Medium" if score >= 40 else "Low"
                ),
                "event_count": int(tel["cnt"] or 0) if tel else 0,
                "avg_risk_score": round(float(tel["avg_r"] or 0), 2) if tel else 0,
                "max_risk_score": round(float(tel["max_r"] or 0), 2) if tel else 0,
                "rank": int(rank_row[0]) + 1 if rank_row else None,
            }
        except Exception as e:
            logger.error("get_user_profile SQLite error: %s", e)
            return None

    # ── Event Risk ───────────────────────────────────────────────────────────
    # Behavioral / metadata columns surfaced from risk_report_events.csv when
    # present. Anything absent is returned as None (not a fabricated value).
    _EVENT_INT_COLS = (
        "file_copy_count", "usb_count", "removable_media_count",
        "delete_count", "event_count", "file_count", "email_count",
    )
    _EVENT_FLOAT_COLS = ("after_hours_ratio", "far", "eds", "iav", "oaf", "login_entropy", "lstm_score")
    _EVENT_STR_COLS = ("role", "day", "explanation", "mitre_tactic", "alert_severity")

    def get_events_risk_data(self, limit: int = 100, min_score: float = 0.0) -> List[dict]:
        """
        Return risk-scored events from the pipeline's risk_report_events.csv.

        Surfaces the real behavioral columns (file_copy_count, usb_count,
        removable_media_count, after_hours_ratio, delete_count, event_count) plus
        risk_score / explanation / mitre_tactic / should_alert / alert_severity
        when present. Returns a typed empty list — never raises — if the file or
        the risk_score column is missing.
        """
        df = self._load_csv("risk_report_events.csv")
        if df is None or df.empty:
            return []

        # Filter / sort only if risk_score exists; otherwise degrade gracefully.
        if "risk_score" in df.columns:
            df = df.copy()
            df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce").fillna(0.0)
            if min_score > 0:
                df = df[df["risk_score"] >= min_score]
            df = df.sort_values("risk_score", ascending=False)
        else:
            logger.warning("risk_report_events.csv missing 'risk_score' column")

        df = df.head(limit)
        events: List[dict] = []
        for _, row in df.iterrows():
            event = {
                "user": str(row.get("user", "")) if pd.notna(row.get("user", "")) else "",
                "risk_score": float(row.get("risk_score", 0) or 0),
                # 'date' preferred, fall back to 'day' for the timestamp field
                "timestamp": self._nz_str(row.get("date")) or self._nz_str(row.get("day")),
                # No real 'activity' column in the pipeline output -> leave null
                # rather than injecting a placeholder like "Unknown Activity".
                "activity": self._nz_str(row.get("activity")),
                "should_alert": self._to_bool(row.get("should_alert")),
            }
            for c in self._EVENT_STR_COLS:
                if c in df.columns:
                    event[c] = self._nz_str(row.get(c))
            for c in self._EVENT_INT_COLS:
                if c in df.columns:
                    event[c] = self._to_int(row.get(c))
            for c in self._EVENT_FLOAT_COLS:
                if c in df.columns:
                    event[c] = self._to_float(row.get(c))
            events.append(event)
        return events

    # ── Coercion helpers (defensive, never raise) ────────────────────────────
    @staticmethod
    def _nz_str(v) -> Optional[str]:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        s = str(v).strip()
        return s or None

    @staticmethod
    def _to_int(v) -> Optional[int]:
        try:
            if v is None or pd.isna(v):
                return None
            return int(float(v))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_float(v) -> Optional[float]:
        try:
            if v is None or pd.isna(v):
                return None
            return round(float(v), 4)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_bool(v) -> Optional[bool]:
        if v is None:
            return None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        return str(v).strip().lower() in {"true", "1", "yes"}

    # ── System Stats (single source of truth = risk pipeline CSVs) ───────────
    HIGH_RISK_THRESHOLD = 50.0

    def get_system_stats(self) -> dict:
        """
        Headline risk/threat numbers for the dashboard.

        Single source of truth: the risk pipeline's CSV output
        (``risk_report_users.csv`` for user-level numbers,
        ``risk_report_events.csv`` for event-level numbers). This keeps the
        dashboard coherent with ``/events/risk``, which reads the same event
        CSV. Falls back to the live SQLite telemetry DB only when the CSVs are
        absent, and always returns a fully typed payload (never raises).
        """
        stats = {
            "total_users": 0,
            "high_risk_users": 0,
            "total_events": 0,
            "high_risk_events": 0,
            "avg_risk_score": 0.0,
            "top_threat": "None",
            "data_source": "unavailable",
        }

        users_df = self._load_csv("risk_report_users.csv")
        events_df = self._load_csv("risk_report_events.csv")

        used_csv = False

        # ── User-level headline numbers from risk_report_users.csv ────────────
        if users_df is not None and not users_df.empty and "total_risk_score" in users_df.columns:
            used_csv = True
            scores = pd.to_numeric(users_df["total_risk_score"], errors="coerce").fillna(0.0)
            stats["total_users"] = int(len(users_df))
            stats["high_risk_users"] = int((scores >= self.HIGH_RISK_THRESHOLD).sum())
            stats["avg_risk_score"] = round(float(scores.mean()) if len(scores) else 0.0, 2)
            if "user" in users_df.columns and len(scores):
                top_idx = scores.idxmax()
                top_user = users_df.loc[top_idx, "user"]
                stats["top_threat"] = str(top_user) if pd.notna(top_user) else "None"

        # ── Event-level headline numbers from risk_report_events.csv ──────────
        if events_df is not None and not events_df.empty and "risk_score" in events_df.columns:
            used_csv = True
            escores = pd.to_numeric(events_df["risk_score"], errors="coerce").fillna(0.0)
            stats["total_events"] = int(len(events_df))
            stats["high_risk_events"] = int((escores >= self.HIGH_RISK_THRESHOLD).sum())

        if used_csv:
            stats["data_source"] = "risk_report (CSV pipeline output)"
            return stats

        # ── Fallback: live telemetry SQLite (clearly labelled) ────────────────
        try:
            conn = _get_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN risk_score >= 50 THEN 1 ELSE 0 END) as high_risk,
                       AVG(risk_score) as avg_risk
                FROM users
                WHERE is_active = 1 OR is_active IS NULL
            """)
            u = cursor.fetchone()
            if u and u["total"]:
                stats["total_users"] = int(u["total"])
                stats["high_risk_users"] = int(u["high_risk"] or 0)
                stats["avg_risk_score"] = round(float(u["avg_risk"] or 0), 2)
                cursor.execute("""
                    SELECT user_id FROM users
                    WHERE is_active = 1 OR is_active IS NULL
                    ORDER BY risk_score DESC LIMIT 1
                """)
                top = cursor.fetchone()
                stats["top_threat"] = top["user_id"] if top else "None"
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN t.risk_score >= 50 THEN 1 ELSE 0 END) as high_risk
                FROM telemetry_raw t
                INNER JOIN users u ON t.user_id = u.user_id
            """)
            t = cursor.fetchone()
            if t and t["total"]:
                stats["total_events"] = int(t["total"])
                stats["high_risk_events"] = int(t["high_risk"] or 0)
            conn.close()
            stats["data_source"] = "telemetry.db (live fallback)"
        except Exception as e:
            logger.error("get_system_stats SQLite fallback error: %s", e)
        return stats

    # ── Dashboard Summary ────────────────────────────────────────────────────
    def get_dashboard_summary(self) -> dict:
        """Combined payload for the dashboard: stats + top users + recent alerts + model health."""
        return {
            "stats": self.get_system_stats(),
            "top_risky_users": self.get_users_risk_data(limit=5),
            "recent_alerts": self.get_alerts(limit=5).get("alerts", []),
            "models": self.get_model_status(),
        }

    # ── User Timeline (SQLite) ───────────────────────────────────────────────
    def get_user_timeline(
        self, user_id: str, limit: int = 200, offset: int = 0
    ) -> dict:
        """Return real telemetry timeline for a user from SQLite."""
        try:
            conn = _get_db()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, active_app, window_title, risk_score,
                       anomaly_score, productivity_score,
                       mouse_velocity_avg, keystroke_flight_avg_ms
                FROM telemetry_raw
                WHERE user_id = ?
                ORDER BY timestamp DESC
            """, (user_id,))
            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return {"user_id": user_id, "total_events": 0, "anomaly_count": 0, "events": []}

            timeline = []
            for r in rows:
                risk = float(r["risk_score"] or 0)
                app = r["active_app"] or "unknown"
                timeline.append({
                    "timestamp": r["timestamp"],
                    "event_type": "Telemetry",
                    "activity": f"{app} — {r['window_title'] or ''}".strip(" —"),
                    "anomaly_score": round(float(r["anomaly_score"] or 0), 4),
                    "risk_score": round(risk, 2),
                    "is_anomaly": risk >= 50,
                    "pc": None,
                    "details": {
                        "mouse_velocity": round(float(r["mouse_velocity_avg"] or 0), 1),
                        "keystroke_flight_ms": round(float(r["keystroke_flight_avg_ms"] or 0), 1),
                        "productivity": round(float(r["productivity_score"] or 0), 3),
                    },
                })

            total = len(timeline)
            anomaly_count = sum(1 for e in timeline if e["is_anomaly"])
            paginated = timeline[offset: offset + limit]
            return {
                "user_id": user_id,
                "total_events": total,
                "anomaly_count": anomaly_count,
                "events": paginated,
            }
        except Exception as e:
            logger.error("get_user_timeline SQLite error: %s", e)
            return {"user_id": user_id, "total_events": 0, "anomaly_count": 0, "events": []}

    # ── Alerts (SQLite) ──────────────────────────────────────────────────────
    def get_alerts(
        self,
        severity: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Generate alerts from real telemetry_raw events where risk_score >= 50."""
        try:
            conn = _get_db()
            cursor = conn.cursor()

            conditions = ["t.risk_score >= 50"]
            params: list = []

            sev_filter = ""
            if severity:
                # map severity label to score range for post-filter
                pass
            if user_id:
                conditions.append("t.user_id = ?")
                params.append(user_id)

            where = " AND ".join(conditions)
            cursor.execute(f"""
                SELECT t.id, t.user_id, t.timestamp, t.risk_score,
                       t.active_app, t.window_title, t.productivity_score,
                       t.mitre_tactic, t.mitre_technique,
                       u.name, u.role, u.department
                FROM telemetry_raw t
                INNER JOIN users u ON t.user_id = u.user_id
                WHERE {where}
                ORDER BY t.risk_score DESC
            """, params)

            rows = cursor.fetchall()
            conn.close()

            alerts = []
            for i, r in enumerate(rows):
                score = float(r["risk_score"] or 0)
                sev = (
                    "Critical" if score >= 80 else
                    "High"     if score >= 60 else
                    "Medium"
                )
                app = r["active_app"] or "unknown"
                win = r["window_title"] or ""
                ctx = f" — {win}" if win and win != app else ""
                alert = {
                    "alert_id": f"ALT-{r['id']:05d}",
                    "user": r["user_id"],
                    "name": r["name"] or r["user_id"],
                    "role": r["role"] or "Employee",
                    "department": r["department"] or "General",
                    "severity": sev,
                    "risk_score": round(score, 2),
                    "activity": f"Anomalous behaviour detected in {app}{ctx}",
                    "timestamp": r["timestamp"],
                    "status": "open",
                    "active_app": app,
                    "window_title": win,
                    "mitre_tactic": r["mitre_tactic"],
                    "mitre_technique": r["mitre_technique"],
                }
                alerts.append(alert)

            # Post-filter by severity
            if severity:
                alerts = [a for a in alerts if a["severity"].lower() == severity.lower()]
            if status and status.lower() != "open":
                alerts = []

            total = len(alerts)
            paginated = alerts[offset: offset + limit]
            return {"total": total, "offset": offset, "limit": limit, "alerts": paginated}

        except Exception as e:
            logger.error("get_alerts SQLite error: %s", e)
            return {"total": 0, "offset": offset, "limit": limit, "alerts":[]}

    # ── Model Status ─────────────────────────────────────────────────────────
    def get_model_status(self) -> dict:
        """Check model files and return metadata."""
        model_entries = [
            {"name": "LSTM Autoencoder", "path": os.path.join(settings.MODELS_DIR, "lstm", "lstm_ae.pth")},
            {"name": "LSTM Scaler", "path": os.path.join(settings.MODELS_DIR, "lstm", "scaler.joblib")},
            {"name": "Isolation Forest", "path": os.path.join(settings.MODELS_DIR, "baseline", "isolation_forest.joblib")},
            {"name": "XGBoost (Hybrid)", "path": os.path.join(settings.MODELS_DIR, "hybrid", "xgboost.joblib")},
            {"name": "Bi-LSTM Attention (Hybrid)", "path": os.path.join(settings.MODELS_DIR, "hybrid", "bilstm.pth")},
        ]

        models_list = []
        available = 0
        for entry in model_entries:
            exists = os.path.exists(entry["path"])
            info = {
                "name": entry["name"],
                "path": entry["path"],
                "exists": exists,
                "size_bytes": None,
                "last_modified": None,
            }
            if exists:
                available += 1
                stat = os.stat(entry["path"])
                info["size_bytes"] = stat.st_size
                info["last_modified"] = datetime.fromtimestamp(stat.st_mtime).isoformat()
            models_list.append(info)

        # Load evaluation metrics
        eval_metrics = None
        eval_path = os.path.join(settings.RISK_OUTPUT_DIR, "evaluation_results.json")
        if not os.path.exists(eval_path):
            eval_path = os.path.join(
                os.path.dirname(settings.RISK_OUTPUT_DIR), "evaluation_results_full.txt"
            )
        if os.path.exists(eval_path):
            try:
                with open(eval_path, "r", encoding="utf-8", errors="replace") as f:
                    eval_metrics = f.read()
            except Exception:
                pass

        return {
            "models": models_list,
            "total_models": len(models_list),
            "available_models": available,
            "evaluation_summary": eval_metrics,
        }


data_loader = DataLoader()
