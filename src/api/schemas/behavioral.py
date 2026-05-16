"""
Pydantic schemas for Behavioral Biometrics API.

This module defines request/response models for:
- Behavioral signature endpoints
- Entropy mapping results
- Work integrity metrics
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


# =============================================================================
# MOUSE DYNAMICS SCHEMAS
# =============================================================================

class MouseDynamics(BaseModel):
    """Mouse dynamics features for a user session."""
    velocity_mean: float = Field(..., description="Mean mouse velocity (pixels/sec)")
    velocity_std: float = Field(..., description="Velocity standard deviation")
    tortuosity_index: float = Field(..., description="Mouse path tortuosity (1=direct, >1=erratic)")
    activity_ratio: float = Field(..., description="Ratio of time mouse is moving")
    click_rate: Optional[float] = Field(None, description="Clicks per minute")
    
    model_config = {
        "json_schema_extra": {
            "examples": [{
                "velocity_mean": 245.3,
                "velocity_std": 89.2,
                "tortuosity_index": 1.8,
                "activity_ratio": 0.67,
                "click_rate": 42.5,
            }]
        }
    }


# =============================================================================
# KEYSTROKE DYNAMICS SCHEMAS
# =============================================================================

class KeystrokeDynamics(BaseModel):
    """Keystroke dynamics features for a user session."""
    flight_time_mean: float = Field(..., description="Mean flight time between keys (ms)")
    flight_time_std: float = Field(..., description="Flight time standard deviation")
    dwell_time_mean: float = Field(..., description="Mean key dwell time (ms)")
    dwell_time_std: float = Field(..., description="Dwell time standard deviation")
    typing_speed_wpm: float = Field(..., description="Typing speed (words per minute)")
    rhythm_consistency: float = Field(..., description="Rhythm consistency score (0-1)")
    
    model_config = {
        "json_schema_extra": {
            "examples": [{
                "flight_time_mean": 120.5,
                "flight_time_std": 45.2,
                "dwell_time_mean": 85.3,
                "dwell_time_std": 22.1,
                "typing_speed_wpm": 65.0,
                "rhythm_consistency": 0.82,
            }]
        }
    }


# =============================================================================
# WORK INTEGRITY SCHEMAS
# =============================================================================

class WorkIntegrityMetrics(BaseModel):
    """Work integrity and productivity monitoring metrics."""
    productive_app_ratio: float = Field(..., description="Ratio of time in productive apps")
    idle_time_ratio: float = Field(..., description="Ratio of idle time")
    non_work_http_ratio: float = Field(..., description="Ratio of non-work HTTP usage")
    file_op_velocity: float = Field(..., description="File operations per minute")
    anomalous_velocity_score: float = Field(..., description="Anomalous velocity score (0-1)")
    after_hours_ratio: float = Field(..., description="Ratio of after-hours activity")
    
    model_config = {
        "json_schema_extra": {
            "examples": [{
                "productive_app_ratio": 0.78,
                "idle_time_ratio": 0.12,
                "non_work_http_ratio": 0.08,
                "file_op_velocity": 3.2,
                "anomalous_velocity_score": 0.15,
                "after_hours_ratio": 0.05,
            }]
        }
    }


# =============================================================================
# ENTROPY MAPPING SCHEMAS
# =============================================================================

class SessionEntropy(BaseModel):
    """Session entropy metrics for behavioral analysis."""
    activity_entropy: float = Field(..., description="Shannon entropy over activity types")
    app_entropy: float = Field(..., description="Application category entropy")
    domain_entropy: float = Field(..., description="Domain/URL diversity entropy")
    temporal_entropy: float = Field(..., description="Time-of-day pattern entropy")
    composite_entropy: float = Field(..., description="Weighted composite entropy")
    entropy_percentile: float = Field(..., description="Percentile rank vs baseline (0-100)")
    risk_interpretation: str = Field(..., description="Risk level: Low/Medium/High/Critical")
    
    model_config = {
        "json_schema_extra": {
            "examples": [{
                "activity_entropy": 0.45,
                "app_entropy": 0.32,
                "domain_entropy": 0.28,
                "temporal_entropy": 0.15,
                "composite_entropy": 0.35,
                "entropy_percentile": 72.5,
                "risk_interpretation": "Medium",
            }]
        }
    }


# =============================================================================
# BEHAVIORAL SIGNATURE SCHEMAS
# =============================================================================

class BehavioralSignature(BaseModel):
    """
    Complete behavioral signature for a user session.
    
    Combines mouse dynamics, keystroke patterns, work integrity,
    and session entropy into unified behavioral profile.
    """
    user_id: str = Field(..., description="User identifier")
    session_id: str = Field(..., description="Session identifier")
    timestamp: datetime = Field(..., description="Session timestamp")
    
    # Mouse dynamics
    mouse_dynamics: Optional[MouseDynamics] = None
    
    # Keystroke dynamics
    keystroke_dynamics: Optional[KeystrokeDynamics] = None
    
    # Work integrity
    work_integrity: Optional[WorkIntegrityMetrics] = None
    
    # Session entropy
    session_entropy: Optional[SessionEntropy] = None
    
    # Composite behavioral score
    behavioral_risk_score: float = Field(..., description="Composite behavioral risk (0-100)")
    anomaly_score: float = Field(..., description="Overall anomaly score (0-1)")
    
    # Baseline comparison
    baseline_deviation: float = Field(..., description="Deviation from 30-day baseline")
    
    model_config = {
        "json_schema_extra": {
            "examples": [{
                "user_id": "U105",
                "session_id": "sess_abc123",
                "timestamp": "2025-01-15T14:30:00",
                "behavioral_risk_score": 67.5,
                "anomaly_score": 0.72,
                "baseline_deviation": 2.3,
            }]
        }
    }


class BehavioralSignatureResponse(BaseModel):
    """Response for behavioral signature query."""
    signature: BehavioralSignature
    historical_comparison: Optional[Dict] = Field(
        None, 
        description="Comparison with historical patterns"
    )
    risk_factors: List[str] = Field(
        default_factory=list, 
        description="Identified risk factors"
    )
    recommendations: List[str] = Field(
        default_factory=list, 
        description="Recommended actions"
    )


# =============================================================================
# BASELINE COMPARISON SCHEMAS
# =============================================================================

class BaselineComparison(BaseModel):
    """Comparison of current behavior against historical baseline."""
    user_id: str = Field(..., description="User identifier")
    baseline_period_days: int = Field(..., description="Baseline window (days)")
    
    # Mouse comparison
    mouse_velocity_delta: float = Field(..., description="Deviation in mouse velocity")
    mouse_tortuosity_delta: float = Field(..., description="Deviation in tortuosity")
    
    # Keystroke comparison
    flight_time_delta: float = Field(..., description="Deviation in flight time")
    typing_speed_delta: float = Field(..., description="Deviation in typing speed")
    
    # Entropy comparison
    entropy_delta: float = Field(..., description="Deviation in composite entropy")
    
    # Overall
    overall_deviation_score: float = Field(..., description="Overall deviation (0-1)")
    is_anomalous: bool = Field(..., description="Whether behavior is anomalous")
    
    model_config = {
        "json_schema_extra": {
            "examples": [{
                "user_id": "U105",
                "baseline_period_days": 30,
                "mouse_velocity_delta": 0.23,
                "mouse_tortuosity_delta": 0.45,
                "flight_time_delta": -0.12,
                "typing_speed_delta": 0.08,
                "entropy_delta": 0.35,
                "overall_deviation_score": 0.68,
                "is_anomalous": True,
            }]
        }
    }


# =============================================================================
# TIME SERIES DATA FOR VISUALIZATION
# =============================================================================

class BehavioralTimeSeriesPoint(BaseModel):
    """Single point in behavioral time series."""
    timestamp: datetime
    mouse_tortuosity: float
    keystroke_flight: float
    activity_entropy: float
    productivity_ratio: float
    risk_score: float


class BehavioralTimeSeries(BaseModel):
    """Time series data for behavioral visualization."""
    user_id: str
    start_time: datetime
    end_time: datetime
    points: List[BehavioralTimeSeriesPoint]
    baseline_mean: float
    baseline_std: float
    anomaly_threshold: float


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class BehavioralAnalysisRequest(BaseModel):
    """Request for behavioral analysis."""
    user_id: str = Field(..., description="User to analyze")
    session_start: Optional[datetime] = Field(None, description="Session start time")
    session_end: Optional[datetime] = Field(None, description="Session end time")
    include_historical: bool = Field(True, description="Include historical comparison")
    baseline_days: int = Field(30, description="Baseline window (days)")


class TelemetryStreamRequest(BaseModel):
    """Request for streaming telemetry data."""
    user_id: str
    start_time: datetime
    end_time: datetime
    features: List[str] = Field(
        default_factory=lambda: ["mouse", "keystroke", "productivity"],
        description="Features to include"
    )
