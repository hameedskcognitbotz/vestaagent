import requests
import json
import os
import time

API_URL = "http://127.0.0.1:25678"
FILE_PATH = "/home/cognitbotz/vestaagent/152231341834670subhan project1.pdf"

def test_upload():
    print(f"--- Testing PDF Upload: {FILE_PATH} ---")
    with open(FILE_PATH, 'rb') as f:
        files = {'file': (os.path.basename(FILE_PATH), f, 'application/pdf')}
        data = {'project_id': 'test-subhan-project'}
        
        try:
            start_time = time.time()
            response = requests.post(f"{API_URL}/project/upload-plan", files=files, data=data)
            duration = time.time() - start_time
            
            print(f"Status Code: {response.status_code}")
            print(f"Duration: {duration:.2f}s")
            
            if response.status_code == 200:
                result = response.json()
                project = result.get('bim_state', {})
                elements = project.get('elements', [])
                
                walls = [e for e in elements if e['type'] == 'wall']
                furniture = [e for e in elements if e['type'] == 'furniture']
                
                print(f"SUCCESS!")
                print(f"Walls found: {len(walls)}")
                print(f"Furniture found: {len(furniture)}")
                print(f"Next Agent suggested: {result.get('vision_notes', 'N/A')}")
                
                # Check for errors in the log (this script can't see the terminal but it can see if BIM state is 4 walls)
                if len(walls) <= 4:
                    print("WARNING: Extracted 4 or fewer walls. This might be a mock fallback or parsing issue.")
                else:
                    print(f"Validated: Real geometry extraction successful ({len(walls)} walls).")
                    
            else:
                print(f"FAILURE: {response.text}")
                
        except Exception as e:
            print(f"Connection Error: {e}")

if __name__ == "__main__":
    # Wait for server to be ready
    print("Waiting for server to be ready...")
    for _ in range(10):
        try:
            r = requests.get(f"{API_URL}/")
            if r.status_code == 200:
                print("Server is UP!")
                break
        except:
            time.sleep(2)
    
    test_upload()
