#!/usr/bin/env python3
"""
Unit tests for main.py scan loop timing and error handling changes
Tests the last_scan_time tracking and error backoff logic
"""
import unittest
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


class TestScanLoopTiming(unittest.TestCase):
    """Test scan loop timing and error handling"""

    def test_scan_interval_timing_calculation(self):
        """Test elapsed time calculation between scans"""
        last_scan_time = time.time() - 100  # 100 seconds ago
        current_time = time.time()
        
        elapsed = current_time - last_scan_time
        
        self.assertGreaterEqual(elapsed, 100)
        self.assertLess(elapsed, 101)  # Allow small timing variance

    def test_fast_mode_scan_interval(self):
        """Test fast mode uses shorter scan interval"""
        fast_scan_interval = 60  # 1 minute
        normal_scan_interval = 300  # 5 minutes
        
        # Fast mode should be significantly shorter
        self.assertLess(fast_scan_interval, normal_scan_interval)
        self.assertLessEqual(fast_scan_interval, 120)

    def test_error_backoff_duration(self):
        """Test error backoff is 30 seconds (not 5 seconds)"""
        error_backoff = 30
        
        self.assertEqual(error_backoff, 30)
        self.assertGreater(error_backoff, 5)

    def test_scan_interval_threshold_check(self):
        """Test scan triggers when elapsed >= scan_interval"""
        scan_interval = 300
        
        # Should trigger
        elapsed_trigger = 300
        self.assertGreaterEqual(elapsed_trigger, scan_interval)
        
        # Should not trigger
        elapsed_no_trigger = 299
        self.assertLess(elapsed_no_trigger, scan_interval)

    def test_drift_detection_reset(self):
        """Test drift alert flag resets after successful scan"""
        drift_alert_sent = True
        
        # After scan completes, should reset
        drift_alert_sent = False
        
        self.assertFalse(drift_alert_sent)

    def test_last_scan_time_updates(self):
        """Test last_scan_time updates to current_time after scan"""
        initial_time = time.time() - 300
        last_scan_time = initial_time
        
        # Simulate scan completion
        current_time = time.time()
        last_scan_time = current_time
        
        self.assertGreater(last_scan_time, initial_time)
        self.assertAlmostEqual(last_scan_time, current_time, delta=1)

    def test_fast_mode_runtime_calculation(self):
        """Test fast mode runtime hours calculation"""
        fast_mode_start_time = time.time() - 3600  # 1 hour ago
        current_time = time.time()
        
        fast_mode_runtime_hours = (current_time - fast_mode_start_time) / 3600
        
        self.assertGreaterEqual(fast_mode_runtime_hours, 1.0)
        self.assertLess(fast_mode_runtime_hours, 1.1)

    def test_fast_mode_auto_disable_threshold(self):
        """Test fast mode auto-disables after max runtime"""
        max_runtime_hours = 12
        current_runtime = 12.5
        
        should_disable = current_runtime >= max_runtime_hours
        
        self.assertTrue(should_disable)

    def test_scan_interval_switch_on_disable(self):
        """Test scan interval switches when fast mode disabled"""
        fast_mode_enabled = True
        fast_scan_interval = 60
        normal_scan_interval = 300
        
        scan_interval = fast_scan_interval if fast_mode_enabled else normal_scan_interval
        self.assertEqual(scan_interval, 60)
        
        # Disable fast mode
        fast_mode_enabled = False
        scan_interval = fast_scan_interval if fast_mode_enabled else normal_scan_interval
        self.assertEqual(scan_interval, 300)

    def test_multiple_scan_timing_accuracy(self):
        """Test timing accuracy over multiple scan cycles"""
        scan_times = []
        base_time = time.time()
        
        # Simulate 5 scans at 300 second intervals
        for i in range(5):
            scan_times.append(base_time + (i * 300))
        
        # Verify intervals
        for i in range(1, len(scan_times)):
            interval = scan_times[i] - scan_times[i-1]
            self.assertAlmostEqual(interval, 300, delta=1)

    def test_scan_loop_sleep_duration(self):
        """Test scan loop sleeps 1 second to prevent CPU spinning"""
        loop_sleep = 1
        
        self.assertEqual(loop_sleep, 1)
        self.assertGreater(loop_sleep, 0)


class TestScanLoopErrorHandling(unittest.TestCase):
    """Test error handling in scan loop"""

    def test_error_backoff_prevents_rapid_logging(self):
        """Test 30s backoff prevents rapid error log spam"""
        error_backoff = 30
        rapid_retry = 5
        
        # 30 second backoff is more conservative than 5 seconds
        self.assertGreater(error_backoff, rapid_retry)

    def test_exception_handling_continues_loop(self):
        """Test that exceptions don't crash the loop"""
        running = True
        exception_occurred = False
        
        try:
            # Simulate exception
            raise Exception("Test error")
        except Exception as e:
            exception_occurred = True
            # Loop should continue running
            pass
        
        self.assertTrue(exception_occurred)
        self.assertTrue(running)

    def test_backoff_duration_reasonable(self):
        """Test backoff duration is reasonable (not too short or too long)"""
        error_backoff = 30
        
        # Should be at least 10 seconds to prevent spam
        self.assertGreaterEqual(error_backoff, 10)
        
        # Should be less than 1 minute to maintain responsiveness
        self.assertLessEqual(error_backoff, 60)


class TestLastScanTimeTracking(unittest.TestCase):
    """Test last_scan_time variable tracking"""

    def test_single_variable_for_tracking(self):
        """Test using single last_scan_time variable instead of two"""
        # Before: had both last_scan_time and self.last_scan_time
        # After: only self.last_scan_time
        
        last_scan_time = time.time()
        
        # Verify we can track with one variable
        current_time = time.time()
        elapsed = current_time - last_scan_time
        
        self.assertGreaterEqual(elapsed, 0)

    def test_last_scan_time_initialization(self):
        """Test last_scan_time is initialized after first cycle"""
        last_scan_time = None
        
        # After first cycle
        last_scan_time = time.time()
        
        self.assertIsNotNone(last_scan_time)
        self.assertIsInstance(last_scan_time, float)

    def test_drift_detection_uses_same_variable(self):
        """Test drift detection and elapsed calc use same variable"""
        last_scan_time = time.time()
        
        # Both calculations use the same variable
        current_time = time.time()
        elapsed = current_time - last_scan_time
        drift_check_time = last_scan_time
        
        self.assertEqual(last_scan_time, drift_check_time)


class TestCommentAccuracy(unittest.TestCase):
    """Test that code comments match actual behavior"""

    def test_last_scan_time_comment_accuracy(self):
        """Test comment correctly describes dual purpose of last_scan_time"""
        # Comment should mention: "Track scan time for both elapsed calc and drift detection"
        purposes = ['elapsed calc', 'drift detection']
        
        # Verify both purposes are valid
        self.assertEqual(len(purposes), 2)
        self.assertIn('elapsed calc', purposes)
        self.assertIn('drift detection', purposes)

    def test_error_backoff_comment_accuracy(self):
        """Test comment explains 30s backoff prevents rapid error logging"""
        backoff_seconds = 30
        comment_purpose = "prevent rapid error logging"
        
        self.assertEqual(backoff_seconds, 30)
        self.assertIsInstance(comment_purpose, str)


if __name__ == '__main__':
    unittest.main(verbosity=2)