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
from lstm_autoencoder import LSTMAutoencoder
import joblib

# Robust path handling
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../"))
PROCESSED_DATA_PATH = os.path.join(PROJECT_ROOT, "data/processed/master_timeline.parquet")
MODEL_SAVE_DIR = os.path.join(PROJECT_ROOT, "models/lstm")

# Config
SEQ_LEN = 10  # Window size
BATCH_SIZE = 64
HIDDEN_DIM = 32
NUM_LAYERS = 2
EPOCHS = 10         # Increased for better convergence
LEARNING_RATE = 1e-3

def create_sequences(df, seq_len):
    """
    Create sequences for LSTM.
    Groups by 'user' to ensure sequences don't cross user boundaries.
    """
    sequences = []
    
    # We assume dataframe is already sorted by date
    # Group by user
    for user, group in df.groupby('user'):
        # group is a DataFrame for one user
        # We only care about the features
        data = group.drop(columns=['user', 'date', 'id', 'source', 'pc']).values
        
        if len(data) < seq_len:
            continue
            
        # Create sliding windows
        for i in range(len(data) - seq_len + 1):
            seq = data[i:i+seq_len]
            sequences.append(seq)
            
    return np.array(sequences)

def load_and_process_data():
    if not os.path.exists(PROCESSED_DATA_PATH):
        print(f"Error: Data file not found at {PROCESSED_DATA_PATH}")
        sys.exit(1)

    print("Loading data for LSTM...")
    df_pl = pl.read_parquet(PROCESSED_DATA_PATH)
    df = df_pl.to_pandas()
    
    # Feature Engineering
    # Simple numerical encoding for now (similar to baseline)
    df['hour'] = df['date'].dt.hour
    df['day_of_week'] = df['date'].dt.dayofweek
    
    # Select features to scale
    # Ideally should include one-hot encoded 'activity' or 'source'
    # For this demo, let's include 'source' mapped to int
    source_map = {k: v for v, k in enumerate(df['source'].unique())}
    df['source_idx'] = df['source'].map(source_map)
    
    feature_cols = ['hour', 'day_of_week', 'source_idx']
    
    # Scale features
    print("Scaling features...")
    scaler = StandardScaler()
    df[feature_cols] = scaler.fit_transform(df[feature_cols])
    
    # Keep only necessary columns for sequencing
    # We need 'user' for grouping logic
    df_final = df[['user', 'date', 'id', 'source', 'pc'] + feature_cols]
    
    print(f"Creating sequences (Window={SEQ_LEN})...")
    X_seq = create_sequences(df_final, SEQ_LEN)
    print(f"Generated {len(X_seq)} sequences. Shape: {X_seq.shape}")
    
    return X_seq, scaler

def train():
    X_seq, scaler = load_and_process_data()
    
    if len(X_seq) == 0:
        print("Not enough data to create sequences!")
        return

    # Convert to Tensor
    X_tensor = torch.FloatTensor(X_seq)
    
    # Dataset & Loader
    dataset = TensorDataset(X_tensor, X_tensor) # Target is same as input (Autoencoder)
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    
    # Model
    input_dim = X_seq.shape[2]
    model = LSTMAutoencoder(input_dim=input_dim, hidden_dim=HIDDEN_DIM, num_layers=NUM_LAYERS)
    
    # Training
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)
    
    print(f"Starting training for {EPOCHS} epochs...")
    model.train()
    
    for epoch in range(EPOCHS):
        total_loss = 0
        for batch_idx, (data, target) in enumerate(dataloader):
            optimizer.zero_grad()
            output = model(data)
            loss = criterion(output, target)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
        avg_loss = total_loss / len(dataloader)
        print(f"Epoch [{epoch+1}/{EPOCHS}], Loss: {avg_loss:.4f}")
        
    # Save Model & Scaler
    os.makedirs(MODEL_SAVE_DIR, exist_ok=True)
    torch.save(model.state_dict(), os.path.join(MODEL_SAVE_DIR, "lstm_ae.pth"))
    joblib.dump(scaler, os.path.join(MODEL_SAVE_DIR, "scaler.joblib"))
    print(f"Model saved to {MODEL_SAVE_DIR}")

if __name__ == "__main__":
    train()
