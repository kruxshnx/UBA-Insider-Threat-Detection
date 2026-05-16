"""
Create demo users for multi-user UBA system.
Run this after starting the API server.
"""
import requests
import time

API = "http://localhost:8000/api"

# Define demo users
users = [
    {
        "user_id": "admin",
        "name": "System Administrator", 
        "email": "admin@company.com",
        "role": "Admin",
        "department": "IT"
    },
    {
        "user_id": "U001",
        "name": "John Doe",
        "email": "john.doe@company.com",
        "role": "Developer",
        "department": "Engineering"
    },
    {
        "user_id": "U002", 
        "name": "Jane Smith",
        "email": "jane.smith@company.com",
        "role": "HR Manager",
        "department": "Human Resources"
    },
    {
        "user_id": "U003",
        "name": "Bob Wilson",
        "email": "bob.wilson@company.com", 
        "role": "Sales Manager",
        "department": "Sales"
    },
    {
        "user_id": "U004",
        "name": "Alice Chen",
        "email": "alice.chen@company.com",
        "role": "Developer",
        "department": "Engineering"
    }
]

print("=" * 70)
print("Multi-User UBA System - Demo User Creation")
print("=" * 70)
print()

# Check if API is running
try:
    r = requests.get(f"{API}/users/", timeout=3)
    print(f"✓ API is running: {r.status_code}")
except Exception as e:
    print(f"✗ API is not running. Please start the API server first.")
    print(f"  Run: python start_realtime_now.py")
    exit(1)

# Create users
created = 0
failed = 0

for user in users:
    try:
        r = requests.post(f"{API}/users/", params=user, timeout=5)
        
        if r.status_code == 200 or r.status_code == 400:
            print(f"✓ {user['user_id']}: {user['name']} ({user['role']})")
            created += 1
        else:
            print(f"✗ {user['user_id']}: Failed - {r.text}")
            failed += 1
            
    except Exception as e:
        print(f"✗ {user['user_id']}: Error - {e}")
        failed += 1

print()
print("=" * 70)
print(f"Results: {created} created, {failed} failed")
print("=" * 70)
print()

# List all users
print("Current Users:")
print("-" * 70)
try:
    r = requests.get(f"{API}/users/", timeout=5)
    if r.status_code == 200:
        all_users = r.json()
        for u in all_users:
            print(f"  • {u['user_id']}: {u['name']} - {u['role']} in {u['department']}")
            print(f"    Email: {u['email']}")
            print(f"    Risk Score: {u.get('risk_score', 0):.1f} | Productivity: {u.get('productivity_score', 1):.2f}")
            print()
except Exception as e:
    print(f"Error listing users: {e}")

print()
print("Next Steps:")
print("1. Open dashboard: http://localhost:8000/docs")
print("2. Monitor specific user: python -m src.telemetry.agent --user-id U001 --api-url http://localhost:8000/api/v1/telemetry --interval 3")
print("3. View user risk profile: curl http://localhost:8000/api/users/U001/risk-profile")
print()
