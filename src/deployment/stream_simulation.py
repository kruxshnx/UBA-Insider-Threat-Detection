"""
Streaming/Real-Time Simulation for UBA & ITD.

Simulates a Kafka-like event processing loop:
- Events arrive one by one (or in micro-batches)
- Sliding window scoring
- Incremental model updates
"""

import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from typing import Generator, Dict, List, Optional
from collections import deque
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from risk_engine.scoring import risk_engine
from utils.config import config

# Paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))


class EventBuffer:
    """Sliding window buffer for stream processing."""
    
    def __init__(self, window_size: int = 10):
        self.window_size = window_size
        self.buffers: Dict[str, deque] = {}  # Per-user buffers
    
    def add_event(self, user: str, event: Dict) -> List[Dict]:
        """Add event to user's buffer and return the current window."""
        if user not in self.buffers:
            self.buffers[user] = deque(maxlen=self.window_size)
        
        self.buffers[user].append(event)
        return list(self.buffers[user])
    
    def get_window(self, user: str) -> List[Dict]:
        """Get current window for a user."""
        return list(self.buffers.get(user, []))


class StreamProcessor:
    """
    Simulates streaming event processing.
    In production, this would connect to Kafka/Kinesis.
    """
    
    def __init__(self):
        self.buffer = EventBuffer(window_size=config.lstm.get('sequence_length', 10))
        self.event_count = 0
        self.alert_count = 0
        self.high_risk_count = 0
        self.start_time = None
    
    def simulate_stream(
        self,
        data_path: str,
        speed_factor: float = 100.0,
        max_events: Optional[int] = None
    ) -> Generator[Dict, None, None]:
        """
        Simulate streaming events from a CSV file.
        
        Args:
            data_path: Path to CSV with events
            speed_factor: How much faster than real-time (100 = 100x faster)
            max_events: Maximum events to process (None = all)
        
        Yields:
            Event dictionaries
        """
        import polars as pl
        
        if data_path.endswith('.parquet'):
            df = pl.read_parquet(data_path).to_pandas()
        else:
            df = pd.read_csv(data_path, parse_dates=['date'])
        
        df = df.sort_values('date').reset_index(drop=True)
        
        if max_events:
            df = df.head(max_events)
        
        prev_time = None
        
        for idx, row in df.iterrows():
            event = row.to_dict()
            
            # Simulate time delay
            if prev_time is not None and speed_factor < 1000:
                time_diff = (row['date'] - prev_time).total_seconds()
                if time_diff > 0:
                    sleep_time = time_diff / speed_factor
                    if sleep_time > 0.1:  # Cap max sleep
                        sleep_time = 0.1
                    time.sleep(sleep_time)
            
            prev_time = row['date']
            yield event
    
    def process_event(self, event: Dict) -> Dict:
        """
        Process a single event in streaming mode.
        
        Args:
            event: Event dictionary
        
        Returns:
            Enriched event with risk score and metadata
        """
        user = event.get('user', 'unknown')
        
        # Add to sliding window
        window = self.buffer.add_event(user, event)
        
        # Convert to DataFrame row for scoring
        row = pd.Series(event)
        
        # For streaming, we use a simplified anomaly score
        # In production, you'd run the LSTM on the window
        anomaly_score = self._calculate_stream_anomaly(window)
        
        # Calculate risk
        risk_score, explanation = risk_engine.calculate_risk_score(row, anomaly_score)
        
        # Check alert
        event_time = event.get('date', datetime.now())
        if isinstance(event_time, str):
            event_time = pd.to_datetime(event_time)
        
        should_alert, severity = risk_engine.alert_manager.should_generate_alert(
            user, risk_score, event_time
        )
        
        # Update stats
        self.event_count += 1
        if risk_score > 50:
            self.high_risk_count += 1
        if should_alert:
            self.alert_count += 1
        
        return {
            **event,
            'risk_score': risk_score,
            'explanation': explanation.text_explanation,
            'mitre_tactic': explanation.mitre_tactic,
            'should_alert': should_alert,
            'alert_severity': severity,
            'window_size': len(window),
        }
    
    def _calculate_stream_anomaly(self, window: List[Dict]) -> float:
        """
        Calculate anomaly score for streaming (simplified).
        
        In production, you'd:
        1. Extract features from window
        2. Run through LSTM
        3. Calculate reconstruction error
        """
        if len(window) < 2:
            return 0.0
        
        # Simple heuristic: activity velocity + after-hours factor
        recent_events = len(window)
        after_hours_count = sum(
            1 for e in window 
            if isinstance(e.get('hour'), (int, float)) and (e['hour'] < 7 or e['hour'] > 20)
        )
        
        # File copy detection
        file_copies = sum(
            1 for e in window 
            if 'Copy' in str(e.get('activity', ''))
        )
        
        # Simple anomaly proxy
        score = 0.0
        score += min(0.3, recent_events / 30)  # Activity burst
        score += 0.2 * (after_hours_count / max(1, len(window)))  # After-hours ratio
        score += 0.3 * min(1, file_copies / 5)  # File copy spike
        
        return score
    
    def run_simulation(
        self,
        data_path: str,
        max_events: int = 1000,
        print_interval: int = 100
    ) -> List[Dict]:
        """
        Run streaming simulation and return processed events.
        
        Args:
            data_path: Path to data file
            max_events: Max events to process
            print_interval: Print stats every N events
        
        Returns:
            List of processed events
        """
        self.start_time = datetime.now()
        processed = []
        
        print("="*60)
        print("STREAMING SIMULATION")
        print("="*60)
        print(f"Data source: {data_path}")
        print(f"Max events: {max_events}")
        print()
        
        for event in self.simulate_stream(data_path, speed_factor=1000, max_events=max_events):
            result = self.process_event(event)
            processed.append(result)
            
            # Print progress
            if self.event_count % print_interval == 0:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                eps = self.event_count / max(0.1, elapsed)
                print(f"[{self.event_count:5d}] Events/sec: {eps:.1f} | "
                      f"High-Risk: {self.high_risk_count} | Alerts: {self.alert_count}")
            
            # Print alerts
            if result['should_alert']:
                print(f"  🚨 ALERT [{result['alert_severity']}]: "
                      f"User {result['user']} - Risk {result['risk_score']:.1f}")
        
        # Final summary
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        print()
        print("="*60)
        print("SIMULATION COMPLETE")
        print("="*60)
        print(f"Total Events: {self.event_count}")
        print(f"Duration: {elapsed:.2f} seconds")
        print(f"Throughput: {self.event_count / elapsed:.1f} events/sec")
        print(f"High-Risk Events: {self.high_risk_count}")
        print(f"Alerts Generated: {self.alert_count}")
        
        return processed


def run_stream_simulation(max_events: int = 500):
    """Main entry point for stream simulation."""
    processor = StreamProcessor()
    
    data_path = os.path.join(PROJECT_ROOT, "data/processed/featured_timeline.parquet")
    if not os.path.exists(data_path):
        data_path = os.path.join(PROJECT_ROOT, "data/processed/master_timeline.parquet")
    
    if not os.path.exists(data_path):
        print("ERROR: No processed data found!")
        return []
    
    return processor.run_simulation(data_path, max_events=max_events)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=500, help="Max events to process")
    args = parser.parse_args()
    
    run_stream_simulation(args.events)
