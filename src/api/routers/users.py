"""
User Management API - Create, read, update employees and assign roles.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Optional
from datetime import datetime
import logging
import sqlite3
import os

from src.api.security import require_role

logger = logging.getLogger("uba.api.users")

router = APIRouter(tags=["Users"])

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "telemetry.db")

# Guard so the users table is created at most once per process even if
# ensure_users_table() is called lazily from several endpoints.
_users_table_ready = False


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_users_table() -> None:
    """
    Create the ``users`` table (and a default admin row) if they do not exist.

    Invoked from the application lifespan in ``src.api.main`` on startup, and
    lazily on first mutating call as a safety net. Replaces the old
    ``@router.on_event("startup")`` handler, which is deprecated on routers and
    never fires when the router is mounted via ``include_router``.
    """
    global _users_table_ready
    if _users_table_ready:
        return
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT DEFAULT 'Employee',
            department TEXT DEFAULT 'General',
            created_at TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            manager_id TEXT,
            last_seen TEXT,
            risk_score REAL DEFAULT 0.0,
            productivity_score REAL DEFAULT 1.0
        )
        """)

        # Create default admin user
        cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, name, email, role, department, created_at)
        VALUES ('admin', 'System Administrator', 'admin@company.com', 'Admin', 'IT', ?)
        """, (datetime.now().isoformat(),))

        conn.commit()
        conn.close()
        _users_table_ready = True
        logger.info("Users table initialized")
    except Exception as e:
        logger.error(f"Error creating users table: {e}")


@router.post("/users/", response_model=dict, dependencies=[Depends(require_role("Admin"))])
async def create_user(
    user_id: str,
    name: str,
    email: str,
    role: str = "Employee",
    department: str = "General",
    manager_id: Optional[str] = None
):
    """Create a new employee/user. Requires Admin role (demo RBAC)."""
    ensure_users_table()  # lazy safety net if lifespan init was skipped
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
        INSERT INTO users (user_id, name, email, role, department, created_at, manager_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, name, email, role, department, datetime.now().isoformat(), manager_id))
        
        conn.commit()
        logger.info(f"Created user: {user_id} ({role})")
        
        return {
            "status": "success",
            "message": f"User {user_id} created successfully",
            "user_id": user_id,
            "role": role,
            "name": name,
            "email": email,
            "department": department
        }
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"User {user_id} already exists")
    finally:
        conn.close()

@router.get("/users/risk", response_model=list)
async def get_users_risk(limit: int = 50, sort: str = "desc"):
    """Get ranked list of users by risk score (from ML pipeline CSV output)."""
    from src.api.services.data_loader import data_loader
    return data_loader.get_users_risk_data(limit=limit, sort_desc=(sort == "desc"))


@router.get("/users/", response_model=List[dict])
async def list_users(is_active: bool = True):
    """List all active users with latest telemetry context."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT u.user_id, u.name, u.email, u.role, u.department,
           u.created_at, u.is_active, u.manager_id,
           u.last_seen, u.risk_score, u.productivity_score,
           t.active_app AS last_active_app,
           t.window_title AS last_window_title,
           t.keystroke_count, t.mouse_click_count,
           COUNT(t2.id) AS event_count
    FROM users u
    LEFT JOIN telemetry_raw t ON t.id = (
        SELECT id FROM telemetry_raw
        WHERE user_id = u.user_id
        ORDER BY timestamp DESC LIMIT 1
    )
    LEFT JOIN telemetry_raw t2 ON t2.user_id = u.user_id
    WHERE u.is_active = 1 OR u.is_active IS NULL
    GROUP BY u.user_id
    ORDER BY u.risk_score DESC
    """)

    users = []
    for row in cursor.fetchall():
        score = row["risk_score"] or 0.0
        users.append({
            "user_id": row["user_id"],
            "name": row["name"],
            "email": row["email"],
            "role": row["role"],
            "department": row["department"],
            "created_at": row["created_at"],
            "is_active": bool(row["is_active"]),
            "manager_id": row["manager_id"],
            "last_seen": row["last_seen"],
            "risk_score": round(score, 1),
            "productivity_score": row["productivity_score"] or 1.0,
            "risk_level": (
                "Critical" if score >= 80 else
                "High" if score >= 60 else
                "Medium" if score >= 40 else "Low"
            ),
            "last_active_app": row["last_active_app"] or "—",
            "last_window_title": row["last_window_title"] or "",
            "event_count": int(row["event_count"] or 0),
        })

    conn.close()
    return users

@router.get("/users/{user_id}", response_model=dict)
async def get_user(user_id: str):
    """Get specific user details."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT user_id, name, email, role, department, created_at, is_active, 
           manager_id, last_seen, risk_score, productivity_score
    FROM users
    WHERE user_id = ?
    """, (user_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    
    return {
        "user_id": row["user_id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "department": row["department"],
        "created_at": row["created_at"],
        "is_active": bool(row["is_active"]),
        "manager_id": row["manager_id"],
        "last_seen": row["last_seen"],
        "risk_score": row["risk_score"] or 0.0,
        "productivity_score": row["productivity_score"] or 1.0
    }

@router.put("/users/{user_id}", response_model=dict, dependencies=[Depends(require_role("Admin"))])
async def update_user(
    user_id: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    role: Optional[str] = None,
    department: Optional[str] = None,
    is_active: Optional[bool] = None
):
    """Update user details."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if email is not None:
        updates.append("email = ?")
        params.append(email)
    if role is not None:
        updates.append("role = ?")
        params.append(role)
    if department is not None:
        updates.append("department = ?")
        params.append(department)
    if is_active is not None:
        updates.append("is_active = ?")
        params.append(1 if is_active else 0)
    
    if not updates:
        conn.close()
        raise HTTPException(status_code=400, detail="No fields to update")
    
    params.append(user_id)
    query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"
    
    cursor.execute(query, params)
    conn.commit()
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    
    conn.close()
    logger.info(f"Updated user: {user_id}")
    
    return {"status": "success", "message": f"User {user_id} updated"}

@router.delete("/users/{user_id}", response_model=dict, dependencies=[Depends(require_role("Admin"))])
async def deactivate_user(user_id: str):
    """Deactivate a user (soft delete). Requires Admin role (demo RBAC)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE users SET is_active = 0 WHERE user_id = ?", (user_id,))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    
    conn.commit()
    conn.close()
    logger.info(f"Deactivated user: {user_id}")
    
    return {"status": "success", "message": f"User {user_id} deactivated"}

@router.get("/users/{user_id}/profile", response_model=dict)
async def get_user_profile(user_id: str):
    """Get risk profile for a specific user (from ML pipeline CSV output)."""
    from src.api.services.data_loader import data_loader
    profile = data_loader.get_user_profile(user_id)
    if not profile:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, name, role, department, risk_score, productivity_score, last_seen FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        score = row["risk_score"] or 0.0
        return {
            "user": row["user_id"],
            "total_risk_score": score,
            "role": row["role"],
            "department": row["department"],
            "risk_level": "Critical" if score > 80 else "High" if score > 50 else "Medium" if score > 25 else "Low",
            "rank": None,
        }
    return profile


@router.get("/users/{user_id}/risk-profile", response_model=dict)
async def get_user_risk_profile(user_id: str):
    """Get detailed risk profile for a user."""
    from src.telemetry.database import telemetry_db
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT user_id, name, role, department, risk_score, productivity_score, last_seen
    FROM users
    WHERE user_id = ?
    """, (user_id,))
    
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    
    # Get recent telemetry
    recent_telemetry = telemetry_db.get_user_telemetry(user_id, limit=100)
    
    # Calculate statistics
    if recent_telemetry:
        avg_risk = sum(t.get('risk_score', 0) for t in recent_telemetry) / len(recent_telemetry)
        avg_productivity = sum(t.get('productivity_score', 1) for t in recent_telemetry) / len(recent_telemetry)
        max_risk = max(t.get('risk_score', 0) for t in recent_telemetry)
    else:
        avg_risk = 0
        avg_productivity = 1.0
        max_risk = 0
    
    return {
        "user_id": user["user_id"],
        "name": user["name"],
        "role": user["role"],
        "department": user["department"],
        "current_risk": user["risk_score"] or 0.0,
        "current_productivity": user["productivity_score"] or 1.0,
        "avg_risk_24h": avg_risk,
        "avg_productivity_24h": avg_productivity,
        "max_risk_24h": max_risk,
        "last_seen": user["last_seen"],
        "telemetry_count": len(recent_telemetry),
        "status": "active" if user["last_seen"] else "inactive"
    }
