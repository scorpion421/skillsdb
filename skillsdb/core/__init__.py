"""
Core engine modules: database connections, model tier detection, and parallel execution.
"""

from .db import get_connection, get_thread_connection, init_db
from .detector import detect_model_tier, set_profile, get_profile
from .concurrency import get_skills_parallel, search_multi_parallel, get_cluster, benchmark_concurrency

__all__ = [
    "get_connection",
    "get_thread_connection",
    "init_db",
    "detect_model_tier",
    "set_profile",
    "get_profile",
    "get_skills_parallel",
    "search_multi_parallel",
    "get_cluster",
    "benchmark_concurrency",
]
