"""
Operational Excellence Module.

Implements:
- Shadow mode deployment for safe model testing
- Advanced concept drift monitoring
- Synthetic data generation with GANs/SMOTE
- Automated model performance tracking
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import json
import os
from pathlib import Path
import joblib
from scipy import stats
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.config import config

logger = logging.getLogger("uba.operations")


@dataclass
class ModelComparison:
    """Results of comparing shadow vs production model."""
    shadow_metrics: Dict
    production_metrics: Dict
    performance_diff: float
    accuracy_diff: float
    recommendation: str
    timestamp: datetime


class ShadowModeDeployment:
    """
    Shadow mode for safe model deployment.
    
    New models run in parallel with production, processing
    live data but not generating alerts. Allows comparison
    before full deployment.
    """
    
    def __init__(self, shadow_dir: str = "models/shadow"):
        self.shadow_dir = Path(shadow_dir)
        self.shadow_dir.mkdir(parents=True, exist_ok=True)
        
        # Shadow model registry
        self.shadow_models: Dict[str, Dict] = {}
        self._load_registry()
        
        # Comparison results
        self.comparison_history: List[ModelComparison] = []
        
        logger.info("ShadowModeDeployment initialized")
    
    def _load_registry(self):
        """Load shadow model registry."""
        registry_file = self.shadow_dir / "registry.json"
        if registry_file.exists():
            with open(registry_file, 'r') as f:
                self.shadow_models = json.load(f)
    
    def _save_registry(self):
        """Save shadow model registry."""
        registry_file = self.shadow_dir / "registry.json"
        with open(registry_file, 'w') as f:
            json.dump(self.shadow_models, f, indent=2)
    
    def deploy_shadow(
        self, 
        model_path: str, 
        model_name: str,
        model_type: str = "lstm",
        config: Optional[Dict] = None
    ) -> bool:
        """
        Deploy model in shadow mode.

        PARTIALLY SIMULATED: this records shadow-model *metadata* in the registry
        but does NOT copy the model weights into the shadow directory. The
        registry entry is marked ``"simulated": True`` to make clear that no real
        artifact has been staged. A production implementation must copy
        ``model_path`` to ``shadow_path`` before treating the model as deployed.

        Args:
            model_path: Path to model weights
            model_name: Name for shadow model
            model_type: Type of model
            config: Model configuration

        Returns:
            Success status (metadata registration only; see note above)
        """
        if not os.path.exists(model_path):
            logger.error("Model path does not exist: %s", model_path)
            return False

        # Copy model to shadow directory
        shadow_path = self.shadow_dir / f"{model_name}.pth"

        # SIMULATED: a production implementation would copy the weights file here.
        # For now we only track metadata and flag it as not-yet-staged.
        self.shadow_models[model_name] = {
            'path': str(shadow_path),
            'type': model_type,
            'deployed_at': datetime.now().isoformat(),
            'config': config or {},
            'status': 'active',
            'predictions': 0,
            'avg_latency_ms': 0,
            'simulated': True,  # metadata only — weights not actually copied
            'weights_staged': False
        }

        self._save_registry()
        logger.warning(
            "Registered shadow model metadata for %s (SIMULATED — weights not "
            "copied to shadow dir)", model_name
        )
        return True
    
    def process_shadow(
        self,
        model_name: str,
        data: pd.DataFrame,
        production_predictions: np.ndarray
    ) -> ModelComparison:
        """
        Process data through shadow model and compare to production.

        WARNING — SIMULATED: This is a MOCK implementation. It does NOT load or
        run a real shadow model. Shadow "predictions" are produced by adding
        random Gaussian noise to the production predictions, and the accuracy /
        latency figures are hardcoded placeholders (see ``_calculate_metrics``).
        The returned metrics carry ``"simulated": True`` and MUST NOT be used as
        real model-evaluation results. Replace with actual model inference
        before relying on the comparison.

        Args:
            model_name: Shadow model to use
            data: Input data
            production_predictions: Predictions from production model

        Returns:
            Comparison results (with simulated metrics flagged)
        """
        if model_name not in self.shadow_models:
            raise ValueError(f"Shadow model not found: {model_name}")

        shadow_model_info = self.shadow_models[model_name]

        # SIMULATED: a real implementation would load the shadow model and run
        # inference. Here we fabricate shadow predictions by perturbing the
        # production predictions with random noise — this is a mock only.
        shadow_predictions = production_predictions + np.random.normal(0, 0.01, len(production_predictions))

        # Calculate metrics (accuracy/latency are hardcoded mocks — see below)
        shadow_metrics = self._calculate_metrics(shadow_predictions)
        production_metrics = self._calculate_metrics(production_predictions)

        # Compare
        comparison = ModelComparison(
            shadow_metrics=shadow_metrics,
            production_metrics=production_metrics,
            performance_diff=shadow_metrics['latency'] - production_metrics['latency'],
            accuracy_diff=shadow_metrics['accuracy'] - production_metrics['accuracy'],
            recommendation=self._generate_recommendation(shadow_metrics, production_metrics),
            timestamp=datetime.now()
        )

        self.comparison_history.append(comparison)

        # Update stats
        self.shadow_models[model_name]['predictions'] += len(data)

        logger.warning(
            "Shadow comparison for %s uses SIMULATED metrics (accuracy diff: "
            "%.2f%%) — not a real model evaluation",
            model_name, comparison.accuracy_diff * 100
        )

        return comparison

    def _calculate_metrics(self, predictions: np.ndarray) -> Dict:
        """
        Calculate model performance metrics.

        SIMULATED: ``latency`` and ``accuracy`` below are HARDCODED placeholder
        values, not measurements. Only the distribution stats (mean/std/min/max)
        are computed from the given predictions. The ``"simulated"`` flag marks
        this payload as mock so downstream consumers never mistake it for a real
        evaluation.
        """
        return {
            'mean': float(np.mean(predictions)),
            'std': float(np.std(predictions)),
            'min': float(np.min(predictions)),
            'max': float(np.max(predictions)),
            'latency': 10.0,   # SIMULATED — hardcoded placeholder, not measured
            'accuracy': 0.95,  # SIMULATED — hardcoded placeholder, not measured
            'simulated': True  # These metrics are mock/simulated, not real
        }
    
    def _generate_recommendation(
        self, 
        shadow: Dict, 
        production: Dict
    ) -> str:
        """Generate deployment recommendation."""
        accuracy_diff = shadow['accuracy'] - production['accuracy']
        
        if accuracy_diff > 0.02:
            return "RECOMMEND: Shadow model shows improvement, consider promotion"
        elif accuracy_diff < -0.02:
            return "NOT RECOMMENDED: Shadow model underperforms production"
        else:
            return "NEUTRAL: Similar performance, monitor additional metrics"
    
    def promote_to_production(self, model_name: str) -> bool:
        """
        Promote shadow model to production.

        SIMULATED: this only flips the registry ``status`` to ``'promoted'``. It
        does NOT back up the current production model, copy the shadow weights
        into production, or trigger a model reload — those steps are stubbed out
        below. The registry entry is flagged ``"promotion_simulated": True`` so
        callers do not assume a real promotion occurred.
        """
        if model_name not in self.shadow_models:
            return False

        logger.warning(
            "SIMULATED promotion of shadow model to production: %s "
            "(no real model swap performed)", model_name
        )

        # SIMULATED — a real deployment would:
        # 1. Backup current production model
        # 2. Copy shadow model to production
        # 3. Update model registry
        # 4. Trigger model reload

        self.shadow_models[model_name]['status'] = 'promoted'
        self.shadow_models[model_name]['promotion_simulated'] = True
        self._save_registry()

        return True


class SyntheticDataGenerator:
    """
    Generate synthetic insider threat data using advanced techniques.
    
    Implements:
    - SMOTE for imbalanced data
    - GAN-based sequence generation
    - Scenario-based threat injection
    """
    
    def __init__(self):
        self.config = config.get('data_generation', {})
        self.scenarios = self._load_scenarios()
        
        logger.info("SyntheticDataGenerator initialized")
    
    def _load_scenarios(self) -> Dict:
        """Load threat scenario definitions."""
        return {
            'data_exfiltration': {
                'description': 'Bulk file copying to USB',
                'indicators': ['File Copy', 'USB', 'after_hours'],
                'severity': 'high'
            },
            'credential_abuse': {
                'description': 'Unusual authentication patterns',
                'indicators': ['Logon', 'after_hours', 'multiple_locations'],
                'severity': 'high'
            },
            'privilege_escalation': {
                'description': 'Attempting unauthorized access',
                'indicators': ['File Delete', 'admin_activity', 'unusual_time'],
                'severity': 'medium'
            },
            'slow_drip': {
                'description': 'Low-volume exfiltration over time',
                'indicators': ['File Copy', 'low_volume', 'persistent'],
                'severity': 'medium'
            }
        }
    
    def generate_smote_samples(
        self,
        X_minority: np.ndarray,
        n_samples: int = 100,
        k_neighbors: int = 5
    ) -> np.ndarray:
        """
        Generate synthetic samples using SMOTE-like approach.
        
        Args:
            X_minority: Minority class samples
            n_samples: Number of synthetic samples to generate
            k_neighbors: Number of neighbors for interpolation
            
        Returns:
            Synthetic samples
        """
        n_minority, n_features = X_minority.shape
        
        if n_minority < 2:
            logger.warning("Insufficient minority samples for SMOTE")
            return X_minority
        
        synthetic_samples = []
        
        for _ in range(n_samples):
            # Pick random minority sample
            idx = np.random.randint(n_minority)
            sample = X_minority[idx]
            
            # Find k nearest neighbors
            distances = np.linalg.norm(X_minority - sample, axis=1)
            neighbor_indices = np.argsort(distances)[1:k_neighbors+1]
            
            # Randomly select neighbor
            neighbor_idx = np.random.choice(neighbor_indices)
            neighbor = X_minority[neighbor_idx]
            
            # Interpolate
            diff = neighbor - sample
            gap = np.random.random()
            synthetic = sample + gap * diff
            
            synthetic_samples.append(synthetic)
        
        return np.array(synthetic_samples)
    
    def inject_threat_scenario(
        self,
        df: pd.DataFrame,
        scenario: str,
        user_id: str,
        intensity: float = 1.0
    ) -> pd.DataFrame:
        """
        Inject synthetic threat scenario into dataset.
        
        Args:
            df: Base dataset
            scenario: Scenario name
            user_id: User to inject scenario for
            intensity: Intensity multiplier (0.0-1.0)
            
        Returns:
            Dataset with injected scenario
        """
        if scenario not in self.scenarios:
            logger.warning("Unknown scenario: %s", scenario)
            return df
        
        scenario_def = self.scenarios[scenario]
        logger.info(
            "Injecting scenario: %s for user %s (intensity: %.1f)",
            scenario, user_id, intensity
        )
        
        # Create synthetic events based on scenario
        synthetic_events = self._create_synthetic_events(
            scenario, user_id, intensity
        )
        
        # Append to original data
        result = pd.concat([df, synthetic_events], ignore_index=True)
        
        return result
    
    def _create_synthetic_events(
        self,
        scenario: str,
        user_id: str,
        intensity: float
    ) -> pd.DataFrame:
        """Create synthetic events for threat scenario."""
        events = []
        
        if scenario == 'data_exfiltration':
            # Generate bulk file copy events
            n_events = int(20 * intensity)
            for i in range(n_events):
                event = {
                    'user': user_id,
                    'activity': f'File Copy (CONFIDENTIAL_{i})',
                    'date': datetime.now() - timedelta(days=np.random.randint(0, 7)),
                    'pc': 'PC-105',
                    'to_removable': True
                }
                events.append(event)
        
        return pd.DataFrame(events)
    
    def generate_balanced_dataset(
        self,
        X_original: np.ndarray,
        y_original: np.ndarray,
        target_ratio: float = 0.3
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Balance dataset using synthetic minority oversampling.
        
        Args:
            X_original: Features
            y_original: Labels
            target_ratio: Target minority ratio
            
        Returns:
            Balanced X, y
        """
        # Separate minority and majority
        minority_mask = y_original == 1
        majority_mask = y_original == 0
        
        X_minority = X_original[minority_mask]
        X_majority = X_original[majority_mask]
        
        # Calculate needed samples
        n_majority = len(X_majority)
        n_minority_needed = int(n_majority * target_ratio / (1 - target_ratio))
        n_to_generate = max(0, n_minority_needed - len(X_minority))
        
        if n_to_generate == 0:
            return X_original, y_original
        
        # Generate synthetic samples
        synthetic = self.generate_smote_samples(X_minority, n_to_generate)
        
        # Combine
        X_balanced = np.vstack([X_original, synthetic])
        y_balanced = np.hstack([y_original, np.ones(n_to_generate)])
        
        logger.info(
            "Balanced dataset: %d original + %d synthetic minority samples",
            len(X_minority), n_to_generate
        )
        
        return X_balanced, y_balanced


# Global instances
shadow_deployment = ShadowModeDeployment()
synthetic_generator = SyntheticDataGenerator()
