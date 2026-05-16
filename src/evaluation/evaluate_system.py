"""
System Evaluation Module for UBA & ITD.

Calculates:
- Detection Day (how fast the threat user was caught)
- Max risk score reached
- False positives per user
- Precision / Recall
- Generates evaluation_report.md

Ground truth user and start day are read from config.yaml.
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple
from datetime import datetime
import os
import sys
import json

logger = logging.getLogger("uba.evaluation")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.config import config

# Paths
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
RISK_OUTPUT_DIR = os.path.join(PROJECT_ROOT, "data/risk_output")


class SystemEvaluator:
    """Evaluates the UBA system against known ground truth."""
    
    def __init__(self):
        self.eval_config = config.get('evaluation', {})
        self.ground_truth_user = self.eval_config.get('ground_truth_user', 'U105')
        self.ground_truth_start_day = self.eval_config.get('ground_truth_start_day', 25)
        self.alert_threshold = config.alerting.get('medium_threshold', 70)
    
    def load_risk_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load risk reports."""
        events_path = os.path.join(RISK_OUTPUT_DIR, "risk_report_events.csv")
        users_path = os.path.join(RISK_OUTPUT_DIR, "risk_report_users.csv")
        
        events_df = pd.read_csv(events_path)
        if 'date' in events_df.columns:
            events_df['date'] = pd.to_datetime(events_df['date'])
        
        users_df = pd.read_csv(users_path)
        
        return events_df, users_df
    
    def calculate_detection_metrics(self, events_df: pd.DataFrame) -> Dict:
        """Calculate detection metrics for the insider threat."""
        # Filter to ground truth user
        threat_events = events_df[events_df['user'] == self.ground_truth_user].copy()
        
        if threat_events.empty:
            return {
                'threat_user': self.ground_truth_user,
                'detected': False,
                'detection_day': None,
                'max_risk_score': 0,
                'high_risk_events': 0,
            }
        
        # Find first high-risk event
        high_risk = threat_events[threat_events['risk_score'] >= self.alert_threshold]
        
        if high_risk.empty:
            return {
                'threat_user': self.ground_truth_user,
                'detected': False,
                'detection_day': None,
                'max_risk_score': float(threat_events['risk_score'].max()),
                'high_risk_events': 0,
            }
        
        first_detection = high_risk['date'].min()
        start_date = events_df['date'].min()
        detection_day = (first_detection - start_date).days
        
        return {
            'threat_user': self.ground_truth_user,
            'detected': True,
            'detection_day': detection_day,
            'expected_start_day': self.ground_truth_start_day,
            'detection_delay': max(0, detection_day - self.ground_truth_start_day),
            'first_detection_time': str(first_detection),
            'max_risk_score': float(threat_events['risk_score'].max()),
            'high_risk_events': len(high_risk),
            'total_events': len(threat_events),
        }
    
    def calculate_precision_recall(self, events_df: pd.DataFrame) -> Dict:
        """
        Calculate precision and recall using synthetic ground truth.
        
        Ground truth assumption:
        - True positives: High-risk events from U105 after day 25
        - False positives: High-risk events from other users
        - False negatives: Low-risk events from U105 after day 25 that should be threats
        """
        start_date = events_df['date'].min()
        events_df['day'] = (events_df['date'] - start_date).dt.days
        
        # Define ground truth
        threat_mask = (
            (events_df['user'] == self.ground_truth_user) & 
            (events_df['day'] >= self.ground_truth_start_day)
        )
        
        # Predictions
        predicted_positive = events_df['risk_score'] >= self.alert_threshold
        
        # Metrics
        true_positives = (threat_mask & predicted_positive).sum()
        false_positives = (~threat_mask & predicted_positive).sum()
        false_negatives = (threat_mask & ~predicted_positive).sum()
        true_negatives = (~threat_mask & ~predicted_positive).sum()
        
        precision = true_positives / max(1, true_positives + false_positives)
        recall = true_positives / max(1, true_positives + false_negatives)
        f1 = 2 * precision * recall / max(0.001, precision + recall)
        
        return {
            'true_positives': int(true_positives),
            'false_positives': int(false_positives),
            'false_negatives': int(false_negatives),
            'true_negatives': int(true_negatives),
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1_score': round(f1, 4),
            'alert_threshold': self.alert_threshold,
        }
    
    def calculate_false_positive_rate(self, events_df: pd.DataFrame) -> Dict:
        """Calculate false positive statistics per user."""
        # Exclude ground truth user
        normal_users = events_df[events_df['user'] != self.ground_truth_user]
        
        # Count high-risk events per user
        user_fp = normal_users[normal_users['risk_score'] >= self.alert_threshold].groupby('user').size()
        
        return {
            'total_normal_users': normal_users['user'].nunique(),
            'users_with_false_positives': len(user_fp[user_fp > 0]),
            'total_false_positive_events': int(user_fp.sum()),
            'avg_fp_per_user': round(user_fp.mean(), 2) if len(user_fp) > 0 else 0,
            'max_fp_single_user': int(user_fp.max()) if len(user_fp) > 0 else 0,
            'fp_rate': round(len(user_fp[user_fp > 0]) / max(1, normal_users['user'].nunique()), 4),
        }
    
    def evaluate(self) -> Dict:
        """Run full evaluation."""
        logger.info("Loading risk data...")
        events_df, users_df = self.load_risk_data()
        
        logger.info("Calculating detection metrics...")
        detection = self.calculate_detection_metrics(events_df)
        
        logger.info("Calculating precision/recall...")
        pr_metrics = self.calculate_precision_recall(events_df)
        
        logger.info("Calculating false positive rate...")
        fp_metrics = self.calculate_false_positive_rate(events_df)
        
        # User ranking
        logger.info("Analyzing user rankings...")
        threat_rank = users_df[users_df['user'] == self.ground_truth_user].index.tolist()
        threat_rank = threat_rank[0] + 1 if threat_rank else -1
        
        results = {
            'evaluation_time': datetime.now().isoformat(),
            'detection': detection,
            'precision_recall': pr_metrics,
            'false_positives': fp_metrics,
            'user_analysis': {
                'total_users': len(users_df),
                'threat_user_rank': threat_rank,
                'top_5_users': users_df.head(5)[['user', 'total_risk_score']].to_dict('records'),
            },
            'summary': {
                'threat_detected': detection['detected'],
                'detection_delay_days': detection.get('detection_delay', 'N/A'),
                'precision': pr_metrics['precision'],
                'recall': pr_metrics['recall'],
                'f1': pr_metrics['f1_score'],
            }
        }
        
        return results
    
    def generate_report(self, results: Dict, output_path: str) -> None:
        """Generate markdown evaluation report."""
        detection = results['detection']
        pr = results['precision_recall']
        fp = results['false_positives']
        summary = results['summary']
        
        report = f"""# UBA System Evaluation Report

**Generated**: {results['evaluation_time']}

## Executive Summary

| Metric | Value |
|--------|-------|
| Threat Detected | {'✅ Yes' if summary['threat_detected'] else '❌ No'} |
| Detection Delay | {summary['detection_delay_days']} days |
| Precision | {summary['precision']:.2%} |
| Recall | {summary['recall']:.2%} |
| F1 Score | {summary['f1']:.4f} |

## Insider Threat Detection

- **Target User**: {detection['threat_user']}
- **Expected Activity Start**: Day {detection.get('expected_start_day', 'N/A')}
- **First Detection**: Day {detection.get('detection_day', 'Never')}
- **Max Risk Score**: {detection['max_risk_score']:.1f}/100
- **High-Risk Events Flagged**: {detection.get('high_risk_events', 0)}

## Precision & Recall Analysis

| Metric | Count |
|--------|-------|
| True Positives | {pr['true_positives']} |
| False Positives | {pr['false_positives']} |
| False Negatives | {pr['false_negatives']} |
| True Negatives | {pr['true_negatives']} |

**Alert Threshold**: {pr['alert_threshold']}

## False Positive Analysis

- **Normal Users**: {fp['total_normal_users']}
- **Users with False Alarms**: {fp['users_with_false_positives']}
- **Total FP Events**: {fp['total_false_positive_events']}
- **FP Rate**: {fp['fp_rate']:.2%}

## Top 5 Risky Users

| Rank | User | Risk Score |
|------|------|------------|
"""
        for i, user in enumerate(results['user_analysis']['top_5_users'], 1):
            indicator = " ⚠️" if user['user'] == detection['threat_user'] else ""
            report += f"| {i} | {user['user']}{indicator} | {user['total_risk_score']:.1f} |\n"
        
        report += f"""
## Verdict

"""
        if summary['threat_detected'] and summary['recall'] > 0.5:
            report += "✅ **System Successfully Detected Insider Threat**\n"
        elif summary['threat_detected']:
            report += "⚠️ **Partial Detection** - Low recall indicates missed events\n"
        else:
            report += "❌ **Detection Failed** - System did not flag threat user\n"
        
        with open(output_path, 'w') as f:
            f.write(report)
        
        logger.info("Report saved to %s", output_path)


def run_evaluation() -> Dict:
    """Main entry point for evaluation."""
    evaluator = SystemEvaluator()
    results = evaluator.evaluate()
    
    # Save JSON
    json_path = os.path.join(RISK_OUTPUT_DIR, "evaluation_results.json")
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Generate markdown report
    md_path = os.path.join(RISK_OUTPUT_DIR, "evaluation_report.md")
    evaluator.generate_report(results, md_path)
    
    logger.info("=" * 50)
    logger.info("EVALUATION SUMMARY")
    logger.info("Threat Detected: %s", results['summary']['threat_detected'])
    logger.info("Precision: %.2f%%", results['summary']['precision'] * 100)
    logger.info("Recall: %.2f%%", results['summary']['recall'] * 100)
    logger.info("F1 Score: %.4f", results['summary']['f1'])
    
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_evaluation()
