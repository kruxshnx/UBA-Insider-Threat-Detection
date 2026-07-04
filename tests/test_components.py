import pytest
import pandas as pd
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from risk_engine.scoring import RiskScoringEngine  # alias for AdvancedRiskScoringEngine
from security.engine import SecurityEngine

class TestRiskEngine:
    def test_risk_calculation_high(self):
        engine = RiskScoringEngine()
        # Mock row: Admin user doing File Copy at night
        row = {
            'user': 'U999',
            'date': pd.Timestamp('2024-01-01 23:00:00'),
            'source': 'File',
            'activity': 'File Copy'
        }
        # Inject Admin role
        engine.user_roles['U999'] = 'Admin'
        
        # High anomaly score — returns (score, explanation) tuple
        risk, explanation = engine.calculate_risk_score(row, anomaly_score=0.8, model_type='lstm')
        
        # Expect high risk — capped at max_risk (100)
        assert risk == 100
        assert explanation.risk_score == 100
        assert len(explanation.factors) > 0

    def test_risk_calculation_low(self):
        engine = RiskScoringEngine()
        row = {
            'user': 'U999',
            'date': pd.Timestamp('2024-01-01 10:00:00'),
            'source': 'Http',
            'activity': 'Browsing'
        }
        engine.user_roles['U999'] = 'Employee'
        
        # Low anomaly score (below threshold) — returns (score, explanation) tuple
        risk, explanation = engine.calculate_risk_score(row, anomaly_score=0.05, model_type='lstm')
        
        # Should be near zero (below anomaly mean of 0.16)
        assert risk == 0
        assert explanation.primary_factor == "Normal activity"

class TestSecurityEngine:
    def test_pii_masking(self):
        sec = SecurityEngine(salt="test_salt")
        original = "User123"
        masked = sec.mask_pii(original)

        # One-way: the mask must not equal the plaintext.
        assert original != masked
        # Digest is now a 32-hex-char sha256 prefix (was 12).
        assert len(masked) == 32
        assert all(c in "0123456789abcdef" for c in masked)

        # Determinism: same salt + same input -> same digest.
        assert sec.mask_pii(original) == masked

        # Salt is configurable and actually changes the digest, so identical
        # plaintext does not map to the same token across deployments.
        other = SecurityEngine(salt="different_salt")
        assert other.mask_pii(original) != masked
        
    def test_rbac_admin(self):
        sec = SecurityEngine()
        assert sec.check_access("Admin", "view_pii") == True
        
    def test_rbac_analyst(self):
        sec = SecurityEngine()
        assert sec.check_access("Analyst", "view_pii") == False
        assert sec.check_access("Analyst", "view_anonymized_report") == True
