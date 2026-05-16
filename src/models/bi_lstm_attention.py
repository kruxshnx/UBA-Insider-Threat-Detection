import torch
import torch.nn as nn
import torch.nn.functional as F

class BiLSTMAttention(nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim=2, n_layers=2, dropout=0.3):
        """
        Bi-LSTM with Attention Mechanism for Insider Threat Detection.
        """
        super(BiLSTMAttention, self).__init__()
        
        self.hidden_dim = hidden_dim
        self.n_layers = n_layers
        
        # Bidirectional LSTM
        self.lstm = nn.LSTM(input_dim, hidden_dim, n_layers, 
                            bidirectional=True, dropout=dropout, batch_first=True)
        
        # Attention Layer
        # Input: (batch, seq_len, 2*hidden_dim) -> Output: (batch, seq_len, 1)
        self.attention = nn.Linear(hidden_dim * 2, 1)
        
        # Output Layer
        self.fc = nn.Linear(hidden_dim * 2, output_dim)
        
        self.dropout = nn.Dropout(dropout)
        
    def forward(self, x):
        # x: [batch, seq_len, input_dim]
        
        # LSTM output: [batch, seq_len, 2*hidden_dim]
        lstm_out, _ = self.lstm(x)
        
        # Attention weights
        attn_weights = F.softmax(self.attention(lstm_out), dim=1) # [batch, seq_len, 1]
        
        # Context vector: Weighted sum of LSTM outputs
        context_vector = torch.sum(attn_weights * lstm_out, dim=1) # [batch, 2*hidden_dim]
        
        # Classification
        out = self.fc(self.dropout(context_vector))
        
        return out, attn_weights

# Training Helper
class InsiderDataset(torch.utils.data.Dataset):
    def __init__(self, sequences, labels):
        self.sequences = sequences
        self.labels = labels
        
    def __len__(self):
        return len(self.labels)
        
    def __getitem__(self, idx):
        return torch.FloatTensor(self.sequences[idx]), torch.LongTensor([self.labels[idx]])
