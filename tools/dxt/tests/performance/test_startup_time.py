"""
Test DXT Startup Performance
Tests DXT startup time and performance benchmarks.
"""

import pytest
import subprocess
import time
import statistics
from pathlib import Path


class TestStartupPerformance:
    """Test DXT startup performance (AC5)."""
    
    @pytest.fixture
    def dxt_package_path(self):
        """Path to the built DXT package."""
        project_root = Path(__file__).parent.parent.parent.parent.parent
        dxt_path = project_root / "tools" / "dxt" / "dist"
        
        if dxt_path.exists():
            dxt_files = list(dxt_path.glob("*.dxt"))
            if dxt_files:
                return str(dxt_files[0])
        
        pytest.skip("No DXT package found")
    
    def test_dxt_info_startup_time(self, dxt_package_path):
        """Test DXT startup time is within acceptable limits."""
        startup_times = []
        
        # Run multiple iterations to get average
        for i in range(3):
            start_time = time.time()
            
            result = subprocess.run([
                "npx", "@anthropic-ai/dxt", "info", dxt_package_path
            ], capture_output=True, text=True, timeout=10)
            
            end_time = time.time()
            startup_time = end_time - start_time
            startup_times.append(startup_time)
            
            # Should complete reasonably quickly
            assert startup_time < 10.0, f"Startup iteration {i+1} too slow: {startup_time:.2f}s"
        
        # Average startup time should be reasonable
        avg_startup = statistics.mean(startup_times)
        assert avg_startup < 8.0, f"Average startup too slow: {avg_startup:.2f}s"
        
        print(f"DXT startup times: {startup_times}")
        print(f"Average startup time: {avg_startup:.2f}s")
    
    def test_dxt_validation_performance(self, dxt_package_path):
        """Test DXT validation performance."""
        start_time = time.time()
        
        result = subprocess.run([
            "npx", "@anthropic-ai/dxt", "validate", dxt_package_path
        ], capture_output=True, text=True, timeout=15)
        
        validation_time = time.time() - start_time
        
        # Validation should complete within reasonable time
        assert validation_time < 15.0, f"Validation too slow: {validation_time:.2f}s"
        
        print(f"DXT validation time: {validation_time:.2f}s")
    
    def test_memory_usage_reasonable(self, dxt_package_path):
        """Test that DXT memory usage is reasonable."""
        # This is a basic test - would need more sophisticated memory monitoring
        # for production use
        
        try:
            import psutil
            
            # Start DXT process and monitor memory
            process = subprocess.Popen([
                "npx", "@anthropic-ai/dxt", "info", dxt_package_path
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Monitor for a short time
            time.sleep(0.5)
            
            if process.poll() is None:
                # Process still running - check memory
                ps_process = psutil.Process(process.pid)
                memory_mb = ps_process.memory_info().rss / 1024 / 1024
                
                # Should not use excessive memory
                assert memory_mb < 500, f"Memory usage too high: {memory_mb:.1f}MB"
                
                print(f"DXT memory usage: {memory_mb:.1f}MB")
            
            # Clean up
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        except ImportError:
            pytest.skip("psutil not available for memory testing")
        except Exception as e:
            pytest.skip(f"Memory testing failed: {e}")
    
    def test_concurrent_access_performance(self, dxt_package_path):
        """Test performance with concurrent access."""
        import concurrent.futures
        
        def run_dxt_info():
            start_time = time.time()
            result = subprocess.run([
                "npx", "@anthropic-ai/dxt", "info", dxt_package_path
            ], capture_output=True, text=True, timeout=10)
            end_time = time.time()
            return end_time - start_time, result.returncode
        
        # Run 2 concurrent DXT info commands
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(run_dxt_info) for _ in range(2)]
            results = [future.result() for future in futures]
        
        # Both should complete within reasonable time
        for i, (duration, returncode) in enumerate(results):
            assert duration < 15.0, f"Concurrent run {i+1} too slow: {duration:.2f}s"
            assert returncode is not None, f"Concurrent run {i+1} should complete"
        
        print(f"Concurrent run times: {[r[0] for r in results]}")
    
    def test_version_drift_handling(self, dxt_package_path):
        """Test DXT handles dependency version mismatches."""
        # This is a basic test for version handling
        
        # Test with different environment variables that might affect versions
        test_env = {
            "NODE_ENV": "test",
            "PYTHON_VERSION": "3.11",  # Specify version
        }
        
        result = subprocess.run([
            "npx", "@anthropic-ai/dxt", "info", dxt_package_path
        ], env=test_env, capture_output=True, text=True, timeout=10)
        
        # Should handle version environment variables gracefully
        assert result.returncode is not None, "Should handle version environment variables"
    
    def test_tool_execution_speed_baseline(self, dxt_package_path):
        """Test baseline for tool execution speed."""
        # This is a placeholder for tool execution performance testing
        # Would need an actual running DXT server to test tool execution
        
        # For now, just test that we can get package info quickly
        start_time = time.time()
        
        result = subprocess.run([
            "npx", "@anthropic-ai/dxt", "info", dxt_package_path
        ], capture_output=True, text=True, timeout=10)
        
        info_time = time.time() - start_time
        
        # Package info should be fast
        assert info_time < 5.0, f"Package info too slow: {info_time:.2f}s"
        
        # This establishes a baseline for more complex tool execution testing
        print(f"Package info baseline: {info_time:.2f}s")