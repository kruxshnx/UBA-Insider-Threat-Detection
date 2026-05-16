"""
Multi-Frequency LSTM Autoencoder for Behavioral Telemetry.

This module extends the base LSTM Autoencoder to handle:
1. High-frequency telemetry (1Hz mouse/keyboard data)
2. Low-frequency logs (logon/logoff, file operations)
3. Multi-scale temporal fusion

Architecture:
- Separate encoders for high-freq and low-freq streams
- Attention-based fusion layer
- Shared latent space
- Reconstruction loss for anomaly detection
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger("uba.models.multi_freq_lstm")


class MultiFrequencyLSTMAutoencoder(nn.Module):
    """
    Multi-frequency LSTM Autoencoder for heterogeneous telemetry.
    
    Handles two input streams:
    1. High-frequency (1Hz): Mouse dynamics, keystroke rhythms
    2. Low-frequency (event-based): Logons, file ops, HTTP logs
    
    The architecture uses:
    - Separate encoders per frequency
    - Cross-frequency attention fusion
    - Joint reconstruction loss
    """
    
    def __init__(
        self,
        high_freq_dim: int,
        low_freq_dim: int,
        high_freq_hidden: int = 64,
        low_freq_hidden: int = 32,
        latent_dim: int = 48,
        num_layers: int = 2,
        dropout: float = 0.2,
        bidirectional: bool = True,
    ):
        super().__init__()
        
        self.high_freq_dim = high_freq_dim
        self.low_freq_dim = low_freq_dim
        self.latent_dim = latent_dim
        
        # High-frequency encoder (1Hz telemetry)
        self.high_freq_encoder = nn.LSTM(
            input_size=high_freq_dim,
            hidden_size=high_freq_hidden,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=bidirectional,
        )
        
        # Low-frequency encoder (event logs)
        self.low_freq_encoder = nn.LSTM(
            input_size=low_freq_dim,
            hidden_size=low_freq_hidden,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=bidirectional,
        )
        
        # Attention-based fusion
        fusion_input_dim = (high_freq_hidden * (2 if bidirectional else 1) + 
                           low_freq_hidden * (2 if bidirectional else 1))
        self.attention = nn.MultiheadAttention(
            embed_dim=latent_dim,
            num_heads=4,
            dropout=dropout,
            batch_first=True,
        )
        
        # Fusion network
        self.fusion_network = nn.Sequential(
            nn.Linear(fusion_input_dim, latent_dim * 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(latent_dim * 2, latent_dim),
        )
        
        # Decoders
        self.high_freq_decoder = nn.LSTM(
            input_size=latent_dim,
            hidden_size=high_freq_hidden,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=bidirectional,
        )
        
        self.low_freq_decoder = nn.LSTM(
            input_size=latent_dim,
            hidden_size=low_freq_hidden,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
            bidirectional=bidirectional,
        )
        
        # Output layers
        self.high_freq_output = nn.Linear(
            high_freq_hidden * (2 if bidirectional else 1),
            high_freq_dim
        )
        self.low_freq_output = nn.Linear(
            low_freq_hidden * (2 if bidirectional else 1),
            low_freq_dim
        )
        
        logger.info(
            "MultiFrequencyLSTMAutoencoder initialized: "
            f"high_freq_dim={high_freq_dim}, low_freq_dim={low_freq_dim}, "
            f"latent_dim={latent_dim}"
        )
    
    def forward(
        self,
        high_freq_input: torch.Tensor,
        low_freq_input: torch.Tensor,
        high_freq_lengths: Optional[torch.Tensor] = None,
        low_freq_lengths: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Forward pass through multi-frequency autoencoder.
        
        Args:
            high_freq_input: High-freq features [batch, seq_len, high_freq_dim]
            low_freq_input: Low-freq features [batch, seq_len, low_freq_dim]
            high_freq_lengths: Sequence lengths for high-freq (for padding)
            low_freq_lengths: Sequence lengths for low-freq (for padding)
        
        Returns:
            Tuple of (high_freq_reconstruction, low_freq_reconstruction, latent)
        """
        batch_size = high_freq_input.size(0)
        
        # Encode high-frequency stream
        high_encoded, high_hidden = self.high_freq_encoder(high_freq_input)
        
        # Encode low-frequency stream
        low_encoded, low_hidden = self.low_freq_encoder(low_freq_input)
        
        # Extract final hidden states
        if isinstance(high_hidden, tuple):
            high_hidden_state = high_hidden[0]  # LSTM
        else:
            high_hidden_state = high_hidden
        
        if isinstance(low_hidden, tuple):
            low_hidden_state = low_hidden[0]
        else:
            low_hidden_state = low_hidden
        
        # Flatten hidden states
        high_hidden_flat = high_hidden_state.view(batch_size, -1)
        low_hidden_flat = low_hidden_state.view(batch_size, -1)
        
        # Concatenate and fuse
        combined_hidden = torch.cat([high_hidden_flat, low_hidden_flat], dim=1)
        latent = self.fusion_network(combined_hidden)
        
        # Expand latent for decoder
        seq_len_high = high_freq_input.size(1)
        seq_len_low = low_freq_input.size(1)
        
        latent_high = latent.unsqueeze(1).repeat(1, seq_len_high, 1)
        latent_low = latent.unsqueeze(1).repeat(1, seq_len_low, 1)
        
        # Decode high-frequency
        high_decoded, _ = self.high_freq_decoder(latent_high)
        high_reconstructed = self.high_freq_output(high_decoded)
        
        # Decode low-frequency
        low_decoded, _ = self.low_freq_decoder(latent_low)
        low_reconstructed = self.low_freq_output(low_decoded)
        
        return high_reconstructed, low_reconstructed, latent
    
    def compute_anomaly_score(
        self,
        high_freq_input: torch.Tensor,
        low_freq_input: torch.Tensor,
        high_freq_target: torch.Tensor,
        low_freq_target: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Compute anomaly scores for both frequency streams.
        
        Args:
            high_freq_input: High-freq input features
            low_freq_input: Low-freq input features
            high_freq_target: High-freq target (same as input for autoencoder)
            low_freq_target: Low-freq target
            
        Returns:
            Tuple of (high_freq_anomaly_score, low_freq_anomaly_score)
        """
        high_reconstructed, low_reconstructed, _ = self.forward(
            high_freq_input, low_freq_input
        )
        
        # MSE reconstruction error per sample
        high_error = F.mse_loss(high_reconstructed, high_freq_target, reduction='none')
        low_error = F.mse_loss(low_reconstructed, low_freq_target, reduction='none')
        
        # Mean over features and sequence
        high_anomaly = high_error.mean(dim=[1, 2])
        low_anomaly = low_error.mean(dim=[1, 2])
        
        return high_anomaly, low_anomaly
    
    def get_latent_vector(
        self,
        high_freq_input: torch.Tensor,
        low_freq_input: torch.Tensor,
    ) -> torch.Tensor:
        """Extract latent representation for embeddings."""
        _, _, latent = self.forward(high_freq_input, low_freq_input)
        return latent


class TemporalFusionLayer(nn.Module):
    """
    Temporal fusion layer for combining multi-scale features.
    
    Uses learnable attention weights to combine:
    - Instantaneous features (1Hz)
    - Short-term windows (5-min aggregates)
    - Long-term context (hourly/daily)
    """
    
    def __init__(
        self,
        feature_dim: int,
        num_scales: int = 3,
        attention_heads: int = 4,
        dropout: float = 0.1,
    ):
        super().__init__()
        
        self.num_scales = num_scales
        
        # Multi-scale attention
        self.attention = nn.MultiheadAttention(
            embed_dim=feature_dim,
            num_heads=attention_heads,
            dropout=dropout,
            batch_first=True,
        )
        
        # Scale weights
        self.scale_weights = nn.Parameter(torch.ones(num_scales))
        
        # Layer norm for stability
        self.layer_norm = nn.LayerNorm(feature_dim)
        
        logger.info(f"TemporalFusionLayer initialized: scales={num_scales}")
    
    def forward(
        self,
        multi_scale_features: List[torch.Tensor],
    ) -> torch.Tensor:
        """
        Fuse multi-scale temporal features.
        
        Args:
            multi_scale_features: List of tensors at different time scales
                                 Each: [batch, seq_len, feature_dim]
        
        Returns:
            Fused features [batch, seq_len, feature_dim]
        """
        if len(multi_scale_features) != self.num_scales:
            raise ValueError(
                f"Expected {self.num_scales} scales, "
                f"got {len(multi_scale_features)}"
            )
        
        # Stack scales
        stacked = torch.stack(multi_scale_features, dim=0)  # [scales, batch, seq, dim]
        
        # Apply attention across scales
        batch_size = stacked.size(1)
        seq_len = stacked.size(2)
        feature_dim = stacked.size(3)
        
        # Reshape for attention
        reshaped = stacked.view(self.num_scales, batch_size * seq_len, feature_dim)
        
        # Self-attention over scales
        attended, _ = self.attention(
            reshaped.transpose(0, 1),
            reshaped.transpose(0, 1),
            reshaped.transpose(0, 1),
        )
        
        # Reshape back
        attended = attended.view(batch_size, seq_len, feature_dim)
        
        # Layer norm
        output = self.layer_norm(attended)
        
        return output


class HierarchicalLSTMEncoder(nn.Module):
    """
    Hierarchical LSTM encoder for multi-resolution behavioral modeling.
    
    Architecture:
    - Level 1: Raw telemetry (1Hz) -> 5-min summaries
    - Level 2: 5-min summaries -> hourly patterns
    - Level 3: Hourly patterns -> daily behavioral signature
    
    This captures behavioral patterns at multiple temporal granularities.
    """
    
    def __init__(
        self,
        input_dim: int,
        hidden_dims: List[int] = [64, 32, 16],
        num_layers_per_level: int = 1,
        dropout: float = 0.1,
    ):
        super().__init__()
        
        self.levels = len(hidden_dims)
        self.hidden_dims = hidden_dims
        
        # Build hierarchical LSTM levels
        self.level_encoders = nn.ModuleList()
        
        current_dim = input_dim
        for level_idx, hidden_dim in enumerate(hidden_dims):
            level_lstm = nn.LSTM(
                input_size=current_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers_per_level,
                batch_first=True,
                dropout=dropout if num_layers_per_level > 1 else 0.0,
                bidirectional=True,
            )
            self.level_encoders.append(level_lstm)
            current_dim = hidden_dim * 2  # Bidirectional output
        
        logger.info(f"HierarchicalLSTMEncoder initialized: levels={self.levels}")
    
    def forward(
        self,
        x: torch.Tensor,
        level: int = -1,
    ) -> torch.Tensor:
        """
        Encode at specified hierarchical level.
        
        Args:
            x: Input sequence [batch, seq_len, input_dim]
            level: Level to extract (0=finest, -1=coarsest)
        
        Returns:
            Encoded representation at specified level
        """
        current = x
        
        for lvl_idx, encoder in enumerate(self.level_encoders):
            encoded, _ = encoder(current)
            current = encoded
            
            if lvl_idx == level:
                return encoded
        
        return current


if __name__ == "__main__":
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--seq_len_high", type=int, default=300)  # 5 min @ 1Hz
    parser.add_argument("--seq_len_low", type=int, default=10)
    parser.add_argument("--high_freq_dim", type=int, default=24)
    parser.add_argument("--low_freq_dim", type=int, default=16)
    args = parser.parse_args()
    
    # Create model
    model = MultiFrequencyLSTMAutoencoder(
        high_freq_dim=args.high_freq_dim,
        low_freq_dim=args.low_freq_dim,
    )
    
    # Dummy data
    high_freq = torch.randn(args.batch_size, args.seq_len_high, args.high_freq_dim)
    low_freq = torch.randn(args.batch_size, args.seq_len_low, args.low_freq_dim)
    
    # Forward pass
    high_rec, low_rec, latent = model(high_freq, low_freq)
    
    print(f"High-freq reconstruction shape: {high_rec.shape}")
    print(f"Low-freq reconstruction shape: {low_rec.shape}")
    print(f"Latent vector shape: {latent.shape}")
