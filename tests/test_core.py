from __future__ import annotations

import math
import unittest

from simple_percentile_histogram_collector import (
    PercentileHistogramCollector,
    DEFAULT_BUCKET_COUNT,
)


class TestBasic(unittest.TestCase):
    def test_single_sample(self):
        c = PercentileHistogramCollector()
        c.add(42.0)
        self.assertAlmostEqual(c.percentile(0.5), 42.0)
        self.assertAlmostEqual(c.percentile(0.0), 42.0)
        self.assertAlmostEqual(c.percentile(1.0), 42.0)

    def test_count_property(self):
        c = PercentileHistogramCollector()
        for v in range(100):
            c.add(float(v))
        self.assertEqual(c.count, 100)

    def test_min_max_single(self):
        c = PercentileHistogramCollector()
        c.add(7.0)
        self.assertAlmostEqual(c.min, 7.0)
        self.assertAlmostEqual(c.max, 7.0)

    def test_empty_raises(self):
        c = PercentileHistogramCollector()
        with self.assertRaises(ValueError):
            c.percentile(0.5)
        with self.assertRaises(ValueError):
            _ = c.min
        with self.assertRaises(ValueError):
            _ = c.max

    def test_invalid_quantile(self):
        c = PercentileHistogramCollector()
        c.add(1.0)
        with self.assertRaises(ValueError):
            c.percentile(-0.01)
        with self.assertRaises(ValueError):
            c.percentile(1.01)

    def test_invalid_bucket_count(self):
        with self.assertRaises(ValueError):
            PercentileHistogramCollector(bucket_count=1)
        with self.assertRaises(ValueError):
            PercentileHistogramCollector(bucket_count=0)


class TestPercentileAccuracy(unittest.TestCase):
    def test_uniform_distribution(self):
        """For a uniform [0, 1000) distribution, p50 ~ 500, p95 ~ 950."""
        c = PercentileHistogramCollector()
        for v in range(1000):
            c.add(float(v))
        # With 1000 samples and 1000 buckets, accuracy should be reasonable.
        self.assertLess(abs(c.percentile(0.5) - 500.0), 600.0)
        self.assertLess(abs(c.percentile(0.95) - 950.0), 600.0)
        self.assertLess(abs(c.percentile(0.99) - 990.0), 600.0)

    def test_monotonic_percentiles(self):
        c = PercentileHistogramCollector()
        for _ in range(100):
            for v in range(100):
                c.add(float(v))
        pcts = [c.percentile(q / 100.0) for q in range(1, 100)]
        for i in range(len(pcts) - 1):
            self.assertLessEqual(pcts[i], pcts[i + 1] + 1e-9)

    def test_percentile_boundaries(self):
        """q=0 returns min, q=1 returns max."""
        c = PercentileHistogramCollector()
        for v in range(1, 101):
            c.add(float(v))
        self.assertAlmostEqual(c.percentile(0.0), c.min)
        self.assertAlmostEqual(c.percentile(1.0), c.max)


class TestCompaction(unittest.TestCase):
    def test_small_bucket_count_compacts(self):
        """With only 3 buckets, many samples force compaction."""
        c = PercentileHistogramCollector(bucket_count=3)
        for v in range(50):
            c.add(float(v))
        self.assertEqual(c.count, 50)
        # The digest should still produce reasonable percentiles.
        p50 = c.percentile(0.5)
        self.assertGreater(p50, 0.0)
        self.assertLess(p50, 50.0)

    def test_centroid_count_stays_bounded(self):
        c = PercentileHistogramCollector(bucket_count=10)
        for v in range(500):
            c.add(float(v))
        # Internal centroid list should not exceed max by more than 1
        # (compaction triggers when count > max).
        self.assertLessEqual(len(c._centroids), c._max_centroids)


class TestMerge(unittest.TestCase):
    def test_merge_two_collectors(self):
        a = PercentileHistogramCollector()
        b = PercentileHistogramCollector()
        for v in range(0, 500):
            a.add(float(v))
        for v in range(500, 1000):
            b.add(float(v))
        a.merge(b)
        self.assertEqual(a.count, 1000)
        p50 = a.percentile(0.5)
        self.assertLess(abs(p50 - 500.0), 600.0)

    def test_merge_empty_into_nonempty(self):
        a = PercentileHistogramCollector()
        b = PercentileHistogramCollector()
        for v in range(100):
            a.add(float(v))
        a.merge(b)
        self.assertEqual(a.count, 100)

    def test_merge_nonempty_into_empty(self):
        a = PercentileHistogramCollector()
        b = PercentileHistogramCollector()
        for v in range(100):
            b.add(float(v))
        a.merge(b)
        self.assertEqual(a.count, 100)


class TestDefaults(unittest.TestCase):
    def test_default_bucket_count_value(self):
        self.assertEqual(DEFAULT_BUCKET_COUNT, 1000)


if __name__ == "__main__":
    unittest.main()
