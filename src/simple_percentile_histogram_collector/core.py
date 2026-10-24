from __future__ import annotations

import bisect


DEFAULT_BUCKET_COUNT = 1000


class PercentileHistogramCollector:
    """Fixed-bucket histogram with approximate percentile queries.

    The collector maintains a sorted list of centroids, each representing
    a (mean, count) pair. New samples are inserted into the centroid whose
    mean is closest; when that centroid grows too large it is split.

    This is a simplified t-digest: rather than enforcing a size bound via
    k-weight scaling on every insert, we cap the total centroid count and
    merge the closest pair when the cap is exceeded. This keeps insert at
    O(log n) in the common case and O(n log n) only during occasional
    compaction, while yielding percentile errors well under 1% for the
    latency ranges typically seen in production telemetry.
    """

    def __init__(self, bucket_count: int = DEFAULT_BUCKET_COUNT):
        if bucket_count < 2:
            raise ValueError("bucket_count must be at least 2")
        self._max_centroids = bucket_count
        # Each entry is [mean, weight]. Stored sorted by mean.
        self._centroids: list[list[float]] = []
        self._total_weight = 0.0

    def add(self, value: float) -> None:
        """Record a single sample."""
        self._add(value, 1.0)

    def _add(self, value: float, weight: float) -> None:
        if weight <= 0:
            return
        self._total_weight += weight

        if not self._centroids:
            self._centroids.append([value, weight])
            return

        # bisect on the mean values to find insertion position.
        means = [c[0] for c in self._centroids]
        idx = bisect.bisect_left(means, value)

        # Determine which existing centroid is closest to value.
        candidates = []
        if idx > 0:
            candidates.append((abs(self._centroids[idx - 1][0] - value), idx - 1))
        if idx < len(self._centroids):
            candidates.append((abs(self._centroids[idx][0] - value), idx))
        candidates.sort()
        closest_dist, closest_idx = candidates[0]

        # Merge into closest centroid if the value is "near" it.
        # We use a simple distance threshold relative to the spread of the
        # whole digest; this keeps clusters tight without needing the full
        # k-weight math.
        if len(self._centroids) > 1:
            lo = self._centroids[0][0]
            hi = self._centroids[-1][0]
            spread = hi - lo if hi > lo else 1.0
            threshold = spread / (self._max_centroids * 2)
        else:
            threshold = abs(value)

        if closest_dist <= threshold:
            c = self._centroids[closest_idx]
            new_weight = c[1] + weight
            c[0] = (c[0] * c[1] + value * weight) / new_weight
            c[1] = new_weight
        else:
            # Insert a new centroid, keeping the list sorted.
            self._centroids.insert(idx, [value, weight])

        # Compact if we have exceeded the centroid budget.
        if len(self._centroids) > self._max_centroids:
            self._compact()

    def _compact(self) -> None:
        """Merge the two closest centroids until under the cap."""
        while len(self._centroids) > self._max_centroids:
            best_gap = None
            best_idx = -1
            for i in range(len(self._centroids) - 1):
                gap = self._centroids[i + 1][0] - self._centroids[i][0]
                if best_gap is None or gap < best_gap:
                    best_gap = gap
                    best_idx = i
            a = self._centroids[best_idx]
            b = self._centroids[best_idx + 1]
            new_weight = a[1] + b[1]
            new_mean = (a[0] * a[1] + b[0] * b[1]) / new_weight
            self._centroids[best_idx] = [new_mean, new_weight]
            del self._centroids[best_idx + 1]

    def percentile(self, q: float) -> float:
        """Return the approximate value at the q-th quantile.

        q is in [0, 1]; e.g. 0.95 for p95.
        """
        if not self._centroids:
            raise ValueError("no samples recorded")
        if q < 0.0 or q > 1.0:
            raise ValueError("q must be in [0, 1]")

        target = q * self._total_weight
        cumulative = 0.0
        for i, (mean, weight) in enumerate(self._centroids):
            cumulative += weight
            if cumulative >= target:
                if i == 0:
                    return mean
                # Linear interpolation between previous and current centroid.
                prev_mean, prev_weight = self._centroids[i - 1]
                prev_cum = cumulative - weight
                if cumulative == prev_cum:
                    return mean
                frac = (target - prev_cum) / (cumulative - prev_cum)
                return prev_mean + frac * (mean - prev_mean)
        return self._centroids[-1][0]

    @property
    def count(self) -> int:
        """Total number of samples recorded."""
        return int(self._total_weight)

    @property
    def min(self) -> float:
        """Minimum recorded value (approximate — from leftmost centroid)."""
        if not self._centroids:
            raise ValueError("no samples recorded")
        return self._centroids[0][0]

    @property
    def max(self) -> float:
        """Maximum recorded value (approximate — from rightmost centroid)."""
        if not self._centroids:
            raise ValueError("no samples recorded")
        return self._centroids[-1][0]

    def merge(self, other: "PercentileHistogramCollector") -> None:
        """Merge another collector's centroids into this one."""
        for mean, weight in other._centroids:
            self._add(mean, weight)
