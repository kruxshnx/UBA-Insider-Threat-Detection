"""
Employee Management System - Real User Tracking
Simple version for demo - no email validation issues
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import sqlite3

app = FastAPI(title="Employee Management", version="1.0")
DB_PATH = "data/employees.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'Employee',
            department TEXT,
            monitoring_enabled BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activity_type TEXT NOT NULL,
            application TEXT,
            title TEXT,
            url TEXT,
            duration_seconds INTEGER,
            risk_score REAL DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✓ Database initialized")

class EmployeeCreate(BaseModel):
    employee_id: str
    name: str
    email: Optional[str] = None
    role: str = "Employee"
    department: Optional[str] = None
    monitoring_enabled: bool = True

class ActivityCreate(BaseModel):
    employee_id: str
    activity_type: str
    application: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    duration_seconds: Optional[int] = None
    risk_score: float = 0.0

@app.on_event("startup")
async def startup():
    init_db()

@app.get("/")
async def root():
    return {"message": "Employee Monitoring API", "status": "running"}

@app.get("/dashboard/stats")
async def get_stats():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM employees WHERE monitoring_enabled = 1")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT employee_id) FROM activities WHERE timestamp > datetime('now', '-5 minutes')")
    active = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM activities WHERE risk_score > 0.7")
    high_risk = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM activities WHERE date(timestamp) = date('now')")
    today = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total_employees": total,
        "active_now": active,
        "high_risk_events": high_risk,
        "today_activities": today
    }

@app.post("/employees/")
async def create_employee(employee: EmployeeCreate):
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO employees (employee_id, name, email, role, department, monitoring_enabled)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (employee.employee_id, employee.name, employee.email, 
              employee.role, employee.department, employee.monitoring_enabled))
        conn.commit()
        return {"status": "success", "employee_id": employee.employee_id}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Employee already exists")
    finally:
        conn.close()

@app.get("/employees/")
async def list_employees():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees")
    employees = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"employees": employees, "count": len(employees)}

@app.post("/activities/")
async def track_activity(activity: ActivityCreate):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO activities (employee_id, activity_type, application, title, url, duration_seconds, risk_score)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (activity.employee_id, activity.activity_type, activity.application,
          activity.title, activity.url, activity.duration_seconds, activity.risk_score))
    
    cursor.execute("UPDATE employees SET last_active = CURRENT_TIMESTAMP WHERE employee_id = ?", 
                   (activity.employee_id,))
    conn.commit()
    conn.close()
    
    return {"status": "success", "activity_id": cursor.lastrowid}

@app.get("/activities/recent")
async def get_recent(limit: int = 20):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.*, e.name as employee_name 
        FROM activities a 
        LEFT JOIN employees e ON a.employee_id = e.employee_id
        ORDER BY a.timestamp DESC 
        LIMIT ?
    ''', (limit,))
    activities = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"activities": activities, "count": len(activities)}

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*70)
    print("  EMPLOYEE MONITORING SYSTEM")
    print("="*70)
    print("\n  ✓ Server: http://localhost:8001")
    print("  ✓ API Docs: http://localhost:8001/docs")
    print("  ✓ Dashboard: Open dashboard.html in browser")
    print("\n  Press Ctrl+C to stop\n")
    print("="*70 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8001)
