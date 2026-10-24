"""Percentile Histogram Collector.

A fixed-bucket histogram that computes approximate percentiles (p50, p95,
p99, etc.) from a stream of latency samples using t-digest-style merging.

Public API:
    PercentileHistogramCollector  -- the collector class
    DEFAULT_BUCKET_COUNT         -- default number of buckets (1000)
"""

from .core import PercentileHistogramCollector, DEFAULT_BUCKET_COUNT

__all__ = ["PercentileHistogramCollector", "DEFAULT_BUCKET_COUNT"]
