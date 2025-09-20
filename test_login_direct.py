#!/usr/bin/env python3
"""
Direct test of EDSL login function behavior in IPython environment.
This simulates the notebook environment and monitors display calls.
"""

import sys
import io
from unittest.mock import Mock, patch, MagicMock
import time
import threading


class MockIPythonKernel:
    """Mock IPython kernel to simulate notebook environment"""
    def __init__(self):
        self.kernel = Mock()
        self.kernel.session = Mock()
        self.display_calls = []
        self.javascript_calls = []
        self.clear_output_calls = []
        
    def mock_display(self, obj):
        """Mock display function that captures calls"""
        from IPython.display import Javascript
        
        if isinstance(obj, Javascript):
            self.javascript_calls.append(obj.data)
            print(f"📱 JavaScript call: {obj.data[:100]}...")
        else:
            self.display_calls.append(str(obj))
            print(f"🖥️  Display call: {str(obj)[:100]}...")
    
    def mock_clear_output(self, wait=False):
        """Mock clear_output function"""
        self.clear_output_calls.append({'wait': wait})
        print(f"🧹 Clear output called (wait={wait})")


def test_login_function():
    """Test the login function with mocked IPython environment"""
    print("🧪 Testing EDSL login function behavior")
    print("=" * 60)
    
    # Create mock IPython environment
    mock_ipython = MockIPythonKernel()
    
    # Patch IPython components
    patches = [
        patch('IPython.get_ipython', return_value=mock_ipython),
        patch('IPython.display.display', side_effect=mock_ipython.mock_display),
        patch('IPython.display.clear_output', side_effect=mock_ipython.mock_clear_output),
    ]
    
    with patch('IPython.get_ipython', return_value=mock_ipython), \
         patch('IPython.display.display', side_effect=mock_ipython.mock_display), \
         patch('IPython.display.clear_output', side_effect=mock_ipython.mock_clear_output):
        
        try:
            # Import the login function
            from edsl import login, _is_notebook_environment, _update_notebook_status
            
            print(f"📊 Notebook environment detected: {_is_notebook_environment()}")
            
            # Test the status update function directly first
            print("\n🔧 Testing status update function...")
            print("Before status update")
            _update_notebook_status("Test message 1")
            _update_notebook_status("Test message 2") 
            _update_notebook_status("Test message 3")
            print("After status updates")
            
            # Count how many display calls were made
            print(f"\n📈 Display function called {len(mock_ipython.display_calls)} times")
            print(f"📈 JavaScript function called {len(mock_ipython.javascript_calls)} times")
            print(f"📈 Clear output called {len(mock_ipython.clear_output_calls)} times")
            
            # Show details of calls
            for i, call in enumerate(mock_ipython.javascript_calls):
                print(f"  JS Call {i+1}: {call[:200]}...")
            
            # Test with timeout to simulate polling behavior
            print(f"\n⚡ Testing login with 5-second timeout...")
            print("IMPORTANT: Watch for repeated display calls during polling!")
            
            start_time = time.time()
            
            # Capture stdout to see if there are prints
            old_stdout = sys.stdout
            captured_output = io.StringIO()
            sys.stdout = captured_output
            
            try:
                # This should timeout after 5 seconds
                login(timeout=5)
            except Exception as e:
                print(f"Login exception (expected): {e}")
            finally:
                sys.stdout = old_stdout
                
            end_time = time.time()
            print(f"⏱️  Login test took {end_time - start_time:.1f} seconds")
            
            # Check captured output for any print statements
            captured_text = captured_output.getvalue()
            print(f"📝 Captured stdout output: {repr(captured_text)}")
            
            # Final summary
            print(f"\n📊 FINAL RESULTS:")
            print(f"   Total display calls: {len(mock_ipython.display_calls)}")
            print(f"   Total JavaScript calls: {len(mock_ipython.javascript_calls)}")  
            print(f"   Total clear output calls: {len(mock_ipython.clear_output_calls)}")
            
            if len(mock_ipython.javascript_calls) > 10:
                print("⚠️  HIGH NUMBER OF JAVASCRIPT CALLS - This would cause newlines!")
            elif len(mock_ipython.javascript_calls) <= 3:
                print("✅ LOW NUMBER OF JAVASCRIPT CALLS - Should be clean!")
            else:
                print("⚠️  MODERATE NUMBER OF JAVASCRIPT CALLS - May cause some newlines")
                
        except Exception as e:
            print(f"❌ Test error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    test_login_function()