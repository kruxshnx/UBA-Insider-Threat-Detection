"""
Quick Setup Script for Real Employee Monitoring System
Run this to setup the complete system for demo or production use.
"""

import os
import sys
import subprocess
import yaml
from pathlib import Path

def print_header(text):
    print("\n" + "="*70)
    print(f" {text}")
    print("="*70 + "\n")

def run_command(cmd, description):
    print(f"→ {description}...")
    subprocess.run(cmd, shell=True, check=True)
    print("✓ Done\n")

def main():
    print_header("🚀 UBA Employee Monitoring System - Quick Setup")
    
    # Step 1: Check Python version
    print("→ Checking Python version...")
    if sys.version_info < (3, 9):
        print("❌ Python 3.9+ required")
        sys.exit(1)
    print("✓ Python version OK\n")
    
    # Step 2: Create virtual environment
    if not Path('.venv').exists():
        run_command("python -m venv .venv", "Creating virtual environment")
    
    # Step 3: Install dependencies
    run_command(
        ".venv\\Scripts\\pip install -r requirements.txt" if sys.platform == 'win32' 
        else ".venv/bin/pip install -r requirements.txt",
        "Installing dependencies"
    )
    
    # Step 4: Create necessary directories
    print("→ Creating directories...")
    dirs = ['data/raw', 'data/processed', 'data/risk_output', 'models/lstm', 
            'models/baseline', 'website/dist', 'data/security_output']
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
    print("✓ Directories created\n")
    
    # Step 5: Generate initial config
    print("→ Setting up configuration...")
    config = {
        'system': {
            'name': 'Employee Monitoring System',
            'version': '2.0',
            'mode': 'production'
        },
        'database': {
            'type': 'sqlite',
            'path': 'data/telemetry.db'
        },
        'monitoring': {
            'enabled': True,
            'interval_seconds': 5,
            'track_applications': True,
            'track_websites': True,
            'track_file_operations': True,
            'track_keystrokes': False,  # Privacy: disabled by default
            'track_screenshots': False   # Privacy: disabled by default
        },
        'alerting': {
            'email_notifications': False,
            'slack_webhook': None,
            'threshold_critical': 95,
            'threshold_high': 85,
            'threshold_medium': 70
        },
        'privacy': {
            'gdpr_compliant': True,
            'employee_consent_required': True,
            'data_retention_days': 30
        }
    }
    
    with open('config_company.yaml', 'w') as f:
        yaml.dump(config, f, default_flow_style=False)
    print("✓ Configuration created\n")
    
    print_header("✅ Setup Complete!")
    print("Next steps:")
    print("1. Run: python run_demo.py (for demo)")
    print("2. Or: python run_api.py (start backend)")
    print("3. Then: cd website && npm run dev (start dashboard)")
    print("\nDashboard: http://localhost:5173")
    print("API: http://localhost:8000")
    print("API Docs: http://localhost:8000/docs")

if __name__ == "__main__":
    main()
