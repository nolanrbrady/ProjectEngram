"""
Configuration and constants for Project Engram.
"""

ENGRAM_DIR = ".engram"
LOCK_FILE = "engram.lock"

CATEGORIES = ["decisions", "patterns", "context", "journal", "notes"]
REGIONS = ["hippocampus", "cortex", "amygdala"]

REGION_WEIGHTS = {"hippocampus": 0.55, "cortex": 1.0, "amygdala": 1.2}
IMPORTANCE_WEIGHTS = {"critical": 1.3, "high": 1.1, "normal": 1.0, "low": 0.9}
RETENTION_WEIGHTS = {"reference": 1.1, "ephemeral": 0.85, "log": 0.75, "deprecated": 0.2}

DEFAULT_IMPORTANCE = "normal"
DEFAULT_RETENTION = "ephemeral"
DEFAULT_STRENGTH_FLOOR = 0.2

# Promotion heuristics
DEFAULT_PROMOTION_RECALLS = 3
DEFAULT_PROMOTION_IMPORTANCE = {"high", "critical"}
DEFAULT_PROMOTION_RETENTION = {"reference"}
