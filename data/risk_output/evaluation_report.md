# UBA System Evaluation Report

**Generated**: 2026-07-04T19:34:42.181333

## Executive Summary

| Metric | Value |
|--------|-------|
| Threat Detected | ✅ Yes |
| Detection Delay | 0 days |
| Precision | 100.00% |
| Recall | 100.00% |
| F1 Score | 1.0000 |

## Insider Threat Detection

- **Target User**: U105
- **Expected Activity Start**: Day 25
- **First Detection**: Day 25
- **Max Risk Score**: 100.0/100
- **High-Risk Events Flagged**: 6

## Precision & Recall Analysis

| Metric | Count |
|--------|-------|
| True Positives | 6 |
| False Positives | 0 |
| False Negatives | 0 |
| True Negatives | 2339 |

**Alert Threshold**: 70

## False Positive Analysis

- **Normal Users**: 99
- **Users with False Alarms**: 0
- **Total FP Events**: 0
- **FP Rate**: 0.00%

## Top 5 Risky Users

| Rank | User | Risk Score |
|------|------|------------|
| 1 | U105 ⚠️ | 146.9 |
| 2 | U180 | 70.1 |
| 3 | U169 | 63.7 |
| 4 | U134 | 34.1 |
| 5 | U107 | 30.8 |

## Verdict

✅ **System Successfully Detected Insider Threat**
