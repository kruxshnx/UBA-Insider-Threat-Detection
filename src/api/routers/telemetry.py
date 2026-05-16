"""
Real-Time Telemetry API Router with Multi-User Support.

Endpoints:
- POST /v1/telemetry: Ingest real-time telemetry
- GET /v1/telemetry/recent: Get recent telemetry
- GET /v1/telemetry/user/{user_id}: Get user-specific telemetry
- GET /v1/telemetry/integrity/summary: Get global integrity overview
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from datetime import datetime
import logging
import sqlite3
import os

from src.api.schemas.responses import UserRiskProfile
from src.telemetry.database import telemetry_db
from src.telemetry.integrity_engine import integrity_engine
from src.risk_engine.advanced_scorer import advanced_scorer

logger = logging.getLogger("uba.api.telemetry")

router = APIRouter(prefix="/v1/telemetry", tags=["telemetry"])


# ── MITRE ATT&CK lookup for live telemetry ────────────────────────────────────
_MITRE_APP_MAP = [
    # Exfiltration via messaging / cloud storage
    ({'telegram', 'signal', 'whatsapp'},    'TA0010', 'Exfiltration',       'T1048', 'Exfiltration Over Alternative Protocol'),
    ({'dropbox', 'googledrive', 'onedrive', 'mega', 'wetransfer'},
                                            'TA0010', 'Exfiltration',       'T1567', 'Exfiltration to Cloud Storage'),
    # Collection / staging
    ({'7zip', 'winrar', 'winzip'},           'TA0009', 'Collection',         'T1560', 'Archive Collected Data'),
    # Execution via shell
    ({'powershell', 'cmd.exe', 'bash', 'terminal', 'wscript', 'cscript'},
                                            'TA0002', 'Execution',          'T1059', 'Command and Scripting Interpreter'),
    # Defense evasion / process inspection
    ({'taskmgr', 'processhacker', 'procmon', 'wireshark'},
                                            'TA0005', 'Defense Evasion',    'T1562', 'Impair Defenses'),
    # Credential access
    ({'keepass', 'lastpass', '1password', 'bitwarden'},
                                            'TA0006', 'Credential Access',  'T1555', 'Credentials from Password Stores'),
    # Lateral movement indicators
    ({'putty', 'mobaxterm', 'winscp', 'filezilla'},
                                            'TA0008', 'Lateral Movement',   'T1021', 'Remote Services'),
]


def _get_mitre_for_telemetry(active_app: str, risk_score: float, hour: int) -> tuple:
    """Return (tactic_id, technique_id) or (None, None) for a telemetry event."""
    app = (active_app or '').lower()

    # App-based pattern match
    for keywords, tactic, _tname, technique, _tech_name in _MITRE_APP_MAP:
        if any(k in app for k in keywords):
            return tactic, technique

    # Context-based: after-hours high-risk activity
    is_after_hours = hour < 8 or hour > 20
    if is_after_hours and risk_score >= 60:
        return 'TA0003', 'T1078'  # Persistence — Valid Accounts

    # High-risk with no other mapping → Collection
    if risk_score >= 80:
        return 'TA0009', 'T1119'  # Collection — Automated Collection

    return None, None


@router.post("/")
async def ingest_telemetry(telemetry_data: Dict):
    """
    Ingest real-time telemetry from agent.
    
    Processes telemetry, calculates risk metrics based on user's role,
    and stores in database.
    
    Args:
        telemetry_data: JSON payload from telemetry agent
        
    Returns:
        Processed metrics including risk score and anomaly status
    """
    try:
        # Extract mouse metrics
        mouse_data = telemetry_data.get('mouse', {})
        mouse_velocity_avg = mouse_data.get('velocity_avg', 0)
        mouse_velocity_std = mouse_data.get('velocity_std', 0)
        
        # Extract keyboard metrics
        keyboard_data = telemetry_data.get('keyboard', {})
        keystroke_flight_avg = keyboard_data.get('flight_time_avg_ms', 0)
        keystroke_flight_std = keyboard_data.get('flight_time_std_ms', 0)
        
        # Extract active window
        active_window = telemetry_data.get('active_window', {})
        active_app = active_window.get('app_name', 'unknown')
        window_title = active_window.get('window_title', '')
        process_id = active_window.get('pid', '')
        
        # Get user baseline and role
        user_id = telemetry_data.get('user_id')
        baseline = telemetry_db.get_user_baseline(user_id)
        
        # Get user's role from database
        user_role = "Employee"  # Default
        try:
            from src.api.routers.users import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT role FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                user_role = row["role"]
            conn.close()
        except Exception as e:
            logger.warning(f"Could not fetch user role, using default: {e}")
        
        # Prepare data for integrity engine
        telemetry_for_processing = {
            'active_app': active_app,
            'mouse_velocity_avg': mouse_velocity_avg,
            'mouse_velocity_std': mouse_velocity_std,
            'keystroke_flight_avg_ms': keystroke_flight_avg,
            'keystroke_flight_std_ms': keystroke_flight_std,
        }
        
        # Determine current hour for MITRE context
        current_hour = datetime.now().hour

        # Use advanced risk scorer for better differentiation
        telemetry_for_advanced = {
            'mouse_velocity_avg': mouse_velocity_avg,
            'mouse_velocity_std': mouse_velocity_std,
            'keystroke_flight_avg_ms': keystroke_flight_avg,
            'keystroke_flight_std_ms': keystroke_flight_std,
            'active_app': active_app,
        }
        
        # Calculate advanced risk score
        advanced_risk, advanced_explanation = advanced_scorer.calculate_risk_score(
            user_id=user_id,
            role=user_role,
            telemetry_data=telemetry_for_advanced,
            baseline=baseline
        )
        
        # Process through integrity engine with user's actual role
        integrity_metrics = integrity_engine.process_telemetry(
            telemetry_for_processing,
            user_role=user_role,
            baseline=baseline
        )
        
        # Use advanced risk score if it's higher (more conservative), capped at 100
        base_risk = integrity_metrics.get('anomaly_score', 0) * 100
        final_risk = min(100.0, max(0.0, max(base_risk, advanced_risk)))

        # Compute MITRE mapping based on app and risk context
        mitre_tactic, mitre_technique = _get_mitre_for_telemetry(
            active_app, final_risk, current_hour
        )
        
        # Override risk score with advanced calculation
        integrity_metrics['anomaly_score'] = final_risk / 100
        integrity_metrics['risk_score'] = final_risk
        integrity_metrics['advanced_explanation'] = advanced_explanation
        
        # Prepare data for database
        db_data = {
            'timestamp': telemetry_data.get('timestamp', datetime.now().isoformat()),
            'user_id': user_id,
            'session_id': telemetry_data.get('session_id'),
            
            'mouse_velocity_avg': mouse_velocity_avg,
            'mouse_velocity_std': mouse_velocity_std,
            'mouse_click_count': mouse_data.get('click_count', 0),
            'mouse_positions_count': mouse_data.get('positions_count', 0),
            
            'keystroke_flight_avg_ms': keystroke_flight_avg,
            'keystroke_flight_std_ms': keystroke_flight_std,
            'keystroke_count': keyboard_data.get('key_press_count', 0),
            
            'active_app': active_app,
            'window_title': window_title,
            'process_id': process_id,
            
            'risk_score': integrity_metrics.get('anomaly_score', 0) * 100,
            'risk_multiplier': integrity_metrics.get('risk_multiplier', 1.0),
            'productivity_score': integrity_metrics.get('productivity_score', 0),
            'anomaly_score': integrity_metrics.get('anomaly_score', 0),
            'mitre_tactic': mitre_tactic,
            'mitre_technique': mitre_technique,
        }
        
        # Insert into database
        row_id = telemetry_db.insert_telemetry(db_data)
        
        # Update user's current risk score in users table
        try:
            from src.api.routers.users import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE users 
            SET risk_score = ?, productivity_score = ?, last_seen = ?
            WHERE user_id = ?
            """, (
                db_data['risk_score'],
                db_data['productivity_score'],
                datetime.now().isoformat(),
                user_id
            ))
            conn.commit()
            conn.close()
            logger.debug(f"Updated risk score for {user_id}: {db_data['risk_score']:.1f}")
        except Exception as e:
            logger.warning(f"Could not update user risk score: {e}")
        
        # Update user baseline periodically (every 10th event)
        if row_id % 10 == 0:
            telemetry_db.update_user_baseline(user_id)
        
        # Prepare response with enhanced risk analysis
        response = {
            'status': 'success',
            'row_id': row_id,
            'risk_score': db_data['risk_score'],
            'productivity_score': db_data['productivity_score'],
            'anomaly_score': db_data['anomaly_score'],
            'productivity_category': integrity_metrics.get('productivity_category', 'unknown'),
            'deviation_interpretation': integrity_metrics.get('deviation_interpretation', ''),
            'user_role': user_role,
            'risk_breakdown': integrity_metrics.get('advanced_explanation', {}),
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing telemetry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recent")
async def get_recent_telemetry(limit: int = 100):
    """Get most recent telemetry across all users."""
    try:
        telemetry = telemetry_db.get_recent_telemetry(limit=limit)
        return {"telemetry": telemetry, "count": len(telemetry)}
    except Exception as e:
        logger.error(f"Error fetching recent telemetry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}")
async def get_user_telemetry(user_id: str, limit: int = 100, offset: int = 0):
    """Get user-specific telemetry."""
    try:
        telemetry = telemetry_db.get_user_telemetry(user_id, limit=limit, offset=offset)
        return {"telemetry": telemetry, "count": len(telemetry), "user_id": user_id}
    except Exception as e:
        logger.error(f"Error fetching user telemetry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/integrity/summary")
async def get_integrity_summary():
    """Get global integrity overview across all users."""
    try:
        summary = telemetry_db.get_global_integrity_summary()
        return summary
    except Exception as e:
        logger.error(f"Error fetching integrity summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/baseline")
async def get_user_baseline(user_id: str):
    """Get user's behavioral baseline."""
    try:
        baseline = telemetry_db.get_user_baseline(user_id)
        return {"user_id": user_id, "baseline": baseline}
    except Exception as e:
        logger.error(f"Error fetching user baseline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user/{user_id}/baseline/update")
async def update_user_baseline(user_id: str):
    """Force update of user's baseline."""
    try:
        telemetry_db.update_user_baseline(user_id)
        return {"status": "success", "message": f"Baseline updated for {user_id}"}
    except Exception as e:
        logger.error(f"Error updating baseline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


_DB_PATH = os.path.join("data", "telemetry.db")


def _heatmap_db():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/heatmap")
async def get_heatmap_data():
    """
    Return per-user, per-hour average risk scores computed from real telemetry_raw events.
    Response: { rows: [{user_id, name, role, department, risk_score, hours: [24 floats]}] }
    """
    try:
        conn = _heatmap_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.user_id, u.name, u.role, u.department, u.risk_score,
                   CAST(strftime('%H', t.timestamp) AS INTEGER) AS hour,
                   AVG(t.risk_score) AS avg_risk,
                   COUNT(*) AS event_count
            FROM telemetry_raw t
            INNER JOIN users u ON t.user_id = u.user_id
            WHERE t.timestamp >= datetime('now', '-7 days')
            GROUP BY u.user_id, hour
            ORDER BY u.risk_score DESC, u.user_id, hour
        """)
        raw = cur.fetchall()

        cur.execute("""
            SELECT u.user_id, u.name, u.role, u.department, u.risk_score
            FROM users u
            INNER JOIN telemetry_raw t ON t.user_id = u.user_id
            WHERE u.is_active = 1 OR u.is_active IS NULL
            GROUP BY u.user_id
            ORDER BY u.risk_score DESC
        """)
        user_rows = cur.fetchall()
        conn.close()

        # Build per-user 24-slot arrays
        user_map = {}
        for u in user_rows:
            uid = u["user_id"]
            user_map[uid] = {
                "user_id": uid,
                "name": u["name"] or uid,
                "role": u["role"] or "Employee",
                "department": u["department"] or "General",
                "risk_score": round(float(u["risk_score"] or 0), 1),
                "hours": [0.0] * 24,
                "event_counts": [0] * 24,
            }

        for r in raw:
            uid = r["user_id"]
            h = int(r["hour"] or 0)
            if uid in user_map and 0 <= h < 24:
                user_map[uid]["hours"][h] = round(float(r["avg_risk"] or 0), 1)
                user_map[uid]["event_counts"][h] = int(r["event_count"] or 0)

        return {"rows": list(user_map.values()), "total_users": len(user_map)}
    except Exception as e:
        logger.error(f"Error building heatmap: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/{user_id}/hourly")
async def get_user_hourly_activity(user_id: str):
    """
    Return per-hour telemetry aggregation for a single user.
    Used by Forensics MouseActivityHeatmap and KeystrokeChart.
    """
    try:
        conn = _heatmap_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT CAST(strftime('%H', timestamp) AS INTEGER) AS hour,
                   strftime('%w', timestamp) AS dow,
                   AVG(risk_score) AS avg_risk,
                   AVG(mouse_velocity_avg) AS avg_mouse,
                   AVG(keystroke_flight_avg_ms) AS avg_flight,
                   AVG(productivity_score) AS avg_prod,
                   COUNT(*) AS event_count
            FROM telemetry_raw
            WHERE user_id = ?
              AND timestamp >= datetime('now', '-7 days')
            GROUP BY dow, hour
            ORDER BY dow, hour
        """, (user_id,))
        rows = cur.fetchall()
        conn.close()
        result = []
        for r in rows:
            result.append({
                "hour": int(r["hour"] or 0),
                "day_of_week": int(r["dow"] or 0),
                "avg_risk": round(float(r["avg_risk"] or 0), 2),
                "avg_mouse_velocity": round(float(r["avg_mouse"] or 0), 2),
                "avg_keystroke_flight_ms": round(float(r["avg_flight"] or 0), 2),
                "avg_productivity": round(float(r["avg_prod"] or 0), 3),
                "event_count": int(r["event_count"] or 0),
            })
        return {"user_id": user_id, "data": result}
    except Exception as e:
        logger.error(f"Error building user hourly activity: {e}")
        raise HTTPException(status_code=500, detail=str(e))
