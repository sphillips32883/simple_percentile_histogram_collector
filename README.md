# simple_percentile_histogram_collector

A fixed-bucket histogram collector that computes approximate percentiles (p50, p95, p99) from a stream of latency samples using t-digest-style centroid merging.

## Usage

```python
from simple_percentile_histogram_collector import PercentileHistogramCollector

collector = PercentileHistogramCollector()

for latency in [12.5, 18.3, 15.0, 22.1, 19.8, 14.2, 30.0, 17.5]:
    collector.add(latency)

p50 = collector.percentile(0.50)
p95 = collector.percentile(0.95)
p99 = collector.percentile(0.99)

print(f"count={collector.count} min={collector.min} max={collector.max}")
print(f"p50={p50:.2f} p95={p95:.2f} p99={p99:.2f}")
```

The class also exposes `merge(other)` to combine two collectors.

## Why this exists

Production telemetry needs p95/p99 latency figures from high-volume sample streams, but storing every sample is expensive. This library keeps memory bounded: it maintains at most `bucket_count` centroids (default 1000) and merges the closest pair when the cap is exceeded. Insert is O(log n) in the common case; compaction is O(n log n) but runs only when the centroid count exceeds the cap.

The trade-off: percentiles are approximate. For uniformly distributed latency data in the ranges seen in practice, error stays under a few percent. For pathological distributions (e.g., a massive spike at one value with everything else spread out), accuracy degrades. If you need exact percentiles, sort all samples instead.

## The awkward edge

`min` and `max` return the mean of the leftmost and rightmost centroid, not the true extreme sample values. When a single outlier lands far from all other samples it becomes its own centroid and the value is preserved, but when outliers cluster near a boundary they may merge and the reported min/max drifts slightly. Use a dedicated extremes tracker if you need exact extrema.
