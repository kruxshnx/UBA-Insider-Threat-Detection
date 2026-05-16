"""
Per-Role LSTM Autoencoder Training for UBA & ITD System.

This module trains separate LSTM autoencoders for each user role:
- Employee LSTM
- Admin LSTM  
- Contractor LSTM

This approach reduces false positives by learning role-specific baseline behaviors.
Also implements statistical thresholding (percentile-based).
"""

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import polars as pl
import os
import sys
from sklearn.preprocessing import StandardScaler
import joblib
import json
from typing import Dict, List, Tuple, Optional

# Add parent to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models.lstm_autoencoder import LSTMAutoencoder
from utils.config import config

# Paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
FEATURED_DATA_PATH = os.path.join(PROJECT_ROOT, "data/processed/featured_timeline.parquet")
MODEL_SAVE_DIR = os.path.join(PROJECT_ROOT, "models/lstm")
USERS_PATH = os.path.join(PROJECT_ROOT, "data/raw/users.csv")


class RoleLSTMTrainer:
    """Trains role-specific LSTM autoencoders with statistical thresholding."""
    
    def __init__(self):
        self.lstm_config = config.lstm
        self.threshold_config = config.thresholds
        
        self.seq_len = self.lstm_config.get('sequence_length', 10)
        self.hidden_dim = self.lstm_config.get('hidden_dim', 32)
        self.num_layers = self.lstm_config.get('num_layers', 2)
        self.batch_size = self.lstm_config.get('batch_size', 64)
        self.epochs = self.lstm_config.get('epochs', 10)
        self.lr = self.lstm_config.get('learning_rate', 0.001)
        
        self.threshold_method = self.threshold_config.get('method', 'percentile')
        self.threshold_percentile = self.threshold_config.get('percentile', 99.5)
        
        self.feature_cols = [
            'day_of_week',
            'far', 'eds', 'iav', 'oaf', 
            'login_entropy', 'file_count', 'email_count'
        ]
    
    def load_data(self) -> Tuple[pd.DataFrame, Dict[str, str]]:
        """Load featured timeline and user metadata."""
        print("Loading featured data...")
        
        if not os.path.exists(FEATURED_DATA_PATH):
            # Fall back to master timeline if features not yet generated
            fallback_path = os.path.join(PROJECT_ROOT, "data/processed/master_timeline.parquet")
            print(f"Featured data not found. Using {fallback_path}")
            df = pl.read_parquet(fallback_path).to_pandas()
            
            # Add basic features if missing
            if 'hour' not in df.columns:
                df['hour'] = df['date'].dt.hour
                df['day_of_week'] = df['date'].dt.dayofweek
                df['is_after_hours'] = ((df['hour'] < 7) | (df['hour'] > 20)).astype(int)
            
            # Add placeholder behavioral features
            for col in self.feature_cols:
                if col not in df.columns:
                    df[col] = 0.0
        else:
            df = pl.read_parquet(FEATURED_DATA_PATH).to_pandas()
            
        # Ensure date column exists
        if 'day' in df.columns and 'date' not in df.columns:
            df['date'] = pd.to_datetime(df['day'])
        elif 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        
        # Load user roles
        user_roles = {}
        if os.path.exists(USERS_PATH):
            users_df = pd.read_csv(USERS_PATH)
            user_roles = dict(zip(users_df['id'], users_df['role']))
        else:
            print("Warning: users.csv not found. Defaulting all to 'Employee'")
        
        return df, user_roles
    
    def create_sequences(self, df: pd.DataFrame, user_roles: Dict[str, str], role: str) -> np.ndarray:
        """Create sequences for a specific role."""
        sequences = []
        
        # Filter to users of this role
        role_users = [u for u, r in user_roles.items() if r == role]
        
        # If no role mapping, include all users for 'Employee'
        if not role_users and role == 'Employee':
            role_users = df['user'].unique().tolist()
        
        for user in role_users:
            user_data = df[df['user'] == user].sort_values('date')
            
            if len(user_data) < self.seq_len:
                continue
            
            # Extract features
            available_cols = [c for c in self.feature_cols if c in user_data.columns]
            features = user_data[available_cols].values
            
            # Create sliding windows
            for i in range(len(features) - self.seq_len + 1):
                seq = features[i:i + self.seq_len]
                sequences.append(seq)
        
        if sequences:
            return np.array(sequences)
        return np.array([]).reshape(0, self.seq_len, len(self.feature_cols))
    
    def train_role_model(self, X: np.ndarray, role: str) -> Tuple[LSTMAutoencoder, StandardScaler, Dict]:
        """Train LSTM autoencoder for a specific role."""
        print(f"\n{'='*50}")
        print(f"Training LSTM for role: {role}")
        print(f"Sequences: {len(X)}, Shape: {X.shape}")
        print(f"{'='*50}")
        
        if len(X) == 0:
            print(f"No data for role {role}. Skipping.")
            return None, None, {}
        
        # Scale features
        n_samples, seq_len, n_features = X.shape
        X_flat = X.reshape(-1, n_features)
        
        scaler = StandardScaler()
        X_scaled_flat = scaler.fit_transform(X_flat)
        X_scaled = X_scaled_flat.reshape(n_samples, seq_len, n_features)
        
        # Convert to tensor
        X_tensor = torch.FloatTensor(X_scaled)
        
        # Dataset and loader
        dataset = TensorDataset(X_tensor, X_tensor)
        dataloader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        
        # Model
        model = LSTMAutoencoder(
            input_dim=n_features,
            hidden_dim=self.hidden_dim,
            num_layers=self.num_layers
        )
        
        criterion = nn.MSELoss()
        optimizer = optim.Adam(model.parameters(), lr=self.lr)
        
        # Training loop
        model.train()
        all_losses = []
        
        for epoch in range(self.epochs):
            epoch_loss = 0
            for batch_x, batch_y in dataloader:
                optimizer.zero_grad()
                output = model(batch_x)
                loss = criterion(output, batch_y)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
            
            avg_loss = epoch_loss / len(dataloader)
            all_losses.append(avg_loss)
            print(f"  Epoch [{epoch+1}/{self.epochs}] Loss: {avg_loss:.6f}")
        
        # Calculate reconstruction errors for thresholding
        model.eval()
        with torch.no_grad():
            reconstructed = model(X_tensor)
            errors = ((X_tensor - reconstructed) ** 2).mean(dim=(1, 2)).numpy()
        
        # Statistical thresholding
        threshold = self._calculate_threshold(errors)
        
        metadata = {
            'role': role,
            'n_sequences': len(X),
            'n_features': n_features,
            'final_loss': all_losses[-1],
            'threshold': float(threshold),
            'threshold_method': self.threshold_method,
            'error_mean': float(np.mean(errors)),
            'error_std': float(np.std(errors)),
            'error_p50': float(np.percentile(errors, 50)),
            'error_p95': float(np.percentile(errors, 95)),
            'error_p99': float(np.percentile(errors, 99)),
        }
        
        print(f"  Threshold ({self.threshold_method}): {threshold:.6f}")
        print(f"  Error Stats: mean={metadata['error_mean']:.4f}, std={metadata['error_std']:.4f}")
        
        return model, scaler, metadata
    
    def _calculate_threshold(self, errors: np.ndarray) -> float:
        """Calculate anomaly threshold using configured method."""
        method = self.threshold_method
        
        if method == 'percentile':
            percentile = self.threshold_percentile
            return np.percentile(errors, percentile)
        
        elif method == 'std':
            multiplier = self.threshold_config.get('std_multiplier', 3.0)
            return np.mean(errors) + multiplier * np.std(errors)
        
        elif method == 'iqr':
            multiplier = self.threshold_config.get('iqr_multiplier', 1.5)
            q1 = np.percentile(errors, 25)
            q3 = np.percentile(errors, 75)
            iqr = q3 - q1
            return q3 + multiplier * iqr
        
        else:
            # Fallback to 99th percentile
            return np.percentile(errors, 99)
    
    def train_all_roles(self) -> Dict[str, Dict]:
        """Train models for all roles."""
        df, user_roles = self.load_data()
        
        roles = ['Employee', 'Admin', 'Contractor']
        results = {}
        
        os.makedirs(MODEL_SAVE_DIR, exist_ok=True)
        
        for role in roles:
            X = self.create_sequences(df, user_roles, role)
            
            if len(X) == 0:
                print(f"No sequences for role {role}. Skipping.")
                continue
            
            model, scaler, metadata = self.train_role_model(X, role)
            
            if model is not None:
                # Save model
                role_lower = role.lower()
                model_path = os.path.join(MODEL_SAVE_DIR, f"lstm_{role_lower}.pth")
                scaler_path = os.path.join(MODEL_SAVE_DIR, f"scaler_{role_lower}.joblib")
                metadata_path = os.path.join(MODEL_SAVE_DIR, f"metadata_{role_lower}.json")
                
                torch.save(model.state_dict(), model_path)
                joblib.dump(scaler, scaler_path)
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                print(f"  Saved: {model_path}")
                results[role] = metadata
        
        # Also train a global model for fallback
        print("\n" + "="*50)
        print("Training GLOBAL fallback model...")
        X_global = self.create_sequences(df, {u: 'Employee' for u in df['user'].unique()}, 'Employee')
        if len(X_global) > 0:
            model, scaler, metadata = self.train_role_model(X_global, 'global')
            if model:
                torch.save(model.state_dict(), os.path.join(MODEL_SAVE_DIR, "lstm_global.pth"))
                joblib.dump(scaler, os.path.join(MODEL_SAVE_DIR, "scaler_global.joblib"))
                with open(os.path.join(MODEL_SAVE_DIR, "metadata_global.json"), 'w') as f:
                    json.dump(metadata, f, indent=2)
                results['global'] = metadata
        
        # Summary
        print("\n" + "="*50)
        print("TRAINING SUMMARY")
        print("="*50)
        for role, meta in results.items():
            print(f"  {role}: {meta.get('n_sequences', 0)} sequences, "
                  f"threshold={meta.get('threshold', 0):.4f}")
        
        return results


def train_role_models():
    """Main entry point for training."""
    trainer = RoleLSTMTrainer()
    return trainer.train_all_roles()


if __name__ == "__main__":
    train_role_models()
