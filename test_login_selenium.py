#!/usr/bin/env python3
"""
Selenium test for EDSL login function in Jupyter notebook.
This will start a Jupyter server, open the test notebook, execute the login function,
and monitor for newlines/output behavior.
"""

import time
import subprocess
import threading
import signal
import sys
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

class JupyterSeleniumTest:
    def __init__(self):
        self.jupyter_process = None
        self.driver = None
        self.jupyter_url = None
        
    def start_jupyter_server(self):
        """Start Jupyter notebook server in background"""
        print("🚀 Starting Jupyter notebook server...")
        
        # Start Jupyter with no browser and specific port
        cmd = [
            "jupyter", "notebook", 
            "--no-browser", 
            "--port=8899",
            "--NotebookApp.token=''",
            "--NotebookApp.password=''",
            "--NotebookApp.disable_check_xsrf=True"
        ]
        
        self.jupyter_process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Wait for server to start and get URL
        for line in iter(self.jupyter_process.stdout.readline, ''):
            print(f"Jupyter: {line.strip()}")
            if "http://localhost:8899" in line:
                self.jupyter_url = "http://localhost:8899"
                print(f"✅ Jupyter server ready at {self.jupyter_url}")
                break
                
        # Give it a moment to fully start
        time.sleep(3)
    
    def setup_webdriver(self):
        """Set up Chrome WebDriver"""
        print("🔧 Setting up Chrome WebDriver...")
        
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # Run in background
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.implicitly_wait(10)
        print("✅ WebDriver ready")
    
    def open_test_notebook(self):
        """Open the test notebook in Jupyter"""
        print("📓 Opening test notebook...")
        
        # Navigate to Jupyter
        self.driver.get(self.jupyter_url)
        
        # Click on the test notebook file
        notebook_link = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "test_login_notebook.ipynb"))
        )
        notebook_link.click()
        
        # Wait for notebook to load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".cell"))
        )
        print("✅ Test notebook opened")
    
    def execute_cells_and_monitor(self):
        """Execute notebook cells and monitor for output behavior"""
        print("⚡ Executing test cells...")
        
        # Get all code cells
        cells = self.driver.find_elements(By.CSS_SELECTOR, ".code_cell")
        
        for i, cell in enumerate(cells):
            print(f"\n📱 Executing cell {i+1}...")
            
            # Click on cell to select it
            cell.click()
            
            # Execute cell with Shift+Enter
            cell.send_keys(Keys.SHIFT, Keys.ENTER)
            
            # Monitor output for 15 seconds (enough time for login timeout)
            if i == 1:  # The login test cell
                print("👀 Monitoring for newlines and output behavior...")
                start_time = time.time()
                output_count = 0
                
                while time.time() - start_time < 15:
                    # Count output elements in this cell
                    try:
                        outputs = cell.find_elements(By.CSS_SELECTOR, ".output")
                        new_count = len(outputs)
                        
                        if new_count != output_count:
                            print(f"📊 Output count changed: {output_count} -> {new_count}")
                            output_count = new_count
                            
                            # Get the actual output text
                            for idx, output in enumerate(outputs):
                                output_text = output.text
                                print(f"  Output {idx+1}: {repr(output_text[:100])}")
                    
                    except Exception as e:
                        print(f"⚠️  Error checking outputs: {e}")
                    
                    time.sleep(1)
                    
                print("✅ Monitoring complete")
            else:
                # Wait a bit for other cells
                time.sleep(2)
    
    def get_final_results(self):
        """Get the final state of the notebook"""
        print("\n📋 Final notebook state:")
        
        try:
            # Get all outputs
            all_outputs = self.driver.find_elements(By.CSS_SELECTOR, ".output")
            
            print(f"Total output elements: {len(all_outputs)}")
            
            for i, output in enumerate(all_outputs):
                output_text = output.text.strip()
                if output_text:
                    print(f"Output {i+1}: {repr(output_text)}")
            
            # Check for the login interface HTML
            html_outputs = self.driver.find_elements(By.CSS_SELECTOR, ".output_html")
            print(f"HTML outputs found: {len(html_outputs)}")
            
            # Check for any JavaScript outputs
            js_outputs = self.driver.find_elements(By.CSS_SELECTOR, ".output_javascript")
            print(f"JavaScript outputs found: {len(js_outputs)}")
            
            # Look for our login interface
            login_containers = self.driver.find_elements(By.ID, "edsl-login-container")
            print(f"Login containers found: {len(login_containers)}")
            
            if login_containers:
                status_divs = self.driver.find_elements(By.ID, "edsl-status")
                print(f"Status divs found: {len(status_divs)}")
                
                for status_div in status_divs:
                    print(f"Status content: {repr(status_div.text)}")
                    
        except Exception as e:
            print(f"Error getting results: {e}")
    
    def cleanup(self):
        """Clean up resources"""
        print("🧹 Cleaning up...")
        
        if self.driver:
            self.driver.quit()
            print("✅ WebDriver closed")
        
        if self.jupyter_process:
            self.jupyter_process.terminate()
            self.jupyter_process.wait()
            print("✅ Jupyter server stopped")
    
    def run_test(self):
        """Run the complete test"""
        try:
            self.start_jupyter_server()
            self.setup_webdriver()
            self.open_test_notebook()
            self.execute_cells_and_monitor()
            self.get_final_results()
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self.cleanup()

if __name__ == "__main__":
    print("🧪 Starting EDSL Login Selenium Test")
    print("=" * 50)
    
    test = JupyterSeleniumTest()
    test.run_test()
    
    print("\n" + "=" * 50)
    print("🏁 Test completed!")