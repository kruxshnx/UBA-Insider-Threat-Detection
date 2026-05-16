import torch
import torch.nn as nn

class LSTMAutoencoder(nn.Module):
    def __init__(self, input_dim, hidden_dim, num_layers=1, dropout=0.0):
        super(LSTMAutoencoder, self).__init__()
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        
        # Encoder: Takes sequence of features, outputs hidden state
        self.encoder = nn.LSTM(
            input_size=input_dim, 
            hidden_size=hidden_dim, 
            num_layers=num_layers, 
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0
        )
        
        # Decoder: Takes repeated latent vector, reconstructs sequence
        # We feed the latent vector (hidden_dim) as input to the decoder at each step
        self.decoder = nn.LSTM(
            input_size=hidden_dim, 
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0
        )
        
        self.output_layer = nn.Linear(hidden_dim, input_dim)
        
    def forward(self, x):
        # x shape: [batch_size, seq_len, input_dim]
        batch_size, seq_len, _ = x.size()
        
        # --- Encoder ---
        # out: [batch, seq, hidden], (h_n, c_n)
        _, (hidden, cell) = self.encoder(x)
        
        # We take the last layer's hidden state as the latent representation
        # hidden shape: [num_layers, batch, hidden_dim]
        z = hidden[-1] # [batch, hidden_dim]
        
        # --- Decoder ---
        # Repeat z for each time step to condition the decoder
        z_repeated = z.unsqueeze(1).repeat(1, seq_len, 1) # [batch, seq_len, hidden_dim]
        
        # Run decoder
        decoder_out, _ = self.decoder(z_repeated) # [batch, seq_len, hidden_dim]
        
        # Map back to feature space
        x_hat = self.output_layer(decoder_out) # [batch, seq_len, input_dim]
        
        return x_hat

    def get_latent_vector(self, x):
        """Helper to extract embeddings."""
        _, (hidden, _) = self.encoder(x)
        return hidden[-1]
