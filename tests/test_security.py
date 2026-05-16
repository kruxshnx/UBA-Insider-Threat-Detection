import pandas as pd
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from security.engine import SecurityEngine

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../"))
RISK_REPORT_PATH = os.path.join(PROJECT_ROOT, "data/risk_output/risk_report.csv")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data/security_output")

def test_security_controls():
    print("--- Starting Phase 5.5: Security & Governance Test ---")
    
    if not os.path.exists(RISK_REPORT_PATH):
        print("Risk report not found. Please run Phase 4 first.")
        return

    df = pd.read_csv(RISK_REPORT_PATH)
    print(f"Loaded Risk Report: {len(df)} rows")
    
    sec_engine = SecurityEngine()
    
    # Scenario 1: Admin Access (Full View)
    print("\n[Access Control] Testing 'Admin' Access...")
    try:
        admin_view = sec_engine.get_view(df, "Admin")
        print("Admin View Success. Sample User ID:", admin_view['user'].iloc[0])
    except PermissionError as e:
        print("Admin Access Failed:", e)

    # Scenario 2: Analyst Access (Anonymized View)
    print("\n[Access Control] Testing 'Analyst' Access...")
    try:
        analyst_view = sec_engine.get_view(df, "Analyst")
        original_user = df['user'].iloc[0]
        masked_user = analyst_view['user'].iloc[0]
        
        print(f"Analyst View Success.")
        print(f"Original User ID: {original_user}")
        print(f"Masked User ID:   {masked_user}")
        
        if original_user != masked_user:
            print(">> PII Masking Verified: IDs are hashed.")
        else:
            print(">> PII Masking FAILED: IDs are visible!")
            
        # Save Anonymized Report
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        analyst_view.to_csv(os.path.join(OUTPUT_DIR, "anonymized_risk_report.csv"), index=False)
        print(f"Anonymized report saved to {OUTPUT_DIR}")
        
    except PermissionError as e:
        print("Analyst Access Failed:", e)

    # Scenario 3: Unauthorized Role
    print("\n[Access Control] Testing 'Guest' Access...")
    try:
        sec_engine.get_view(df, "Guest")
        print("Guest Access Success (Unexpected!)")
    except PermissionError as e:
        print("Guest Access Denied (Expected):", e)

if __name__ == "__main__":
    test_security_controls()
