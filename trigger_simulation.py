import requests
import json
import time
from bs4 import BeautifulSoup

def login_and_simulate():
    # Start a session to maintain cookies
    session = requests.Session()
    
    # Get the login page to extract the CSRF token
    login_page = session.get('http://localhost:5000/login')
    soup = BeautifulSoup(login_page.text, 'html.parser')
    csrf_token = soup.find('input', {'name': 'csrf_token'})['value']
    
    # Attempt to login
    login_data = {
        'email': 'admin@example.com',
        'password': 'admin123',
        'csrf_token': csrf_token
    }
    
    login_response = session.post('http://localhost:5000/login', data=login_data)
    
    # Check if login was successful
    if 'Login' not in login_response.text:
        print("Login successful!")
        
        # Start a simulation
        simulation_data = {
            "device_id": "mock_device_001",
            "profile": "grilling"
        }
        
        simulation_response = session.post(
            'http://localhost:5000/api/sessions/simulate', 
            json=simulation_data
        )
        
        print(f"Simulation triggered, status code: {simulation_response.status_code}")
        print(simulation_response.json())
        
        # Wait a bit for data to be generated
        print("Waiting for data to be generated...")
        time.sleep(5)
        
        # Check the monitoring data endpoint
        monitoring_data = session.get('http://localhost:5000/api/monitoring/data')
        print(f"Monitoring data status code: {monitoring_data.status_code}")
        print(json.dumps(monitoring_data.json(), indent=2))
        
        # Trigger sync
        sync_response = session.post('http://localhost:5000/sync')
        print(f"Sync triggered, status code: {sync_response.status_code}")
        
        # Wait for sync to complete
        time.sleep(2)
        
        # Check device data
        devices_response = session.get('http://localhost:5000/devices')
        soup = BeautifulSoup(devices_response.text, 'html.parser')
        device_cards = soup.find_all('div', class_='card')
        print(f"Number of device cards found: {len(device_cards)}")
        
    else:
        print("Login failed!")

if __name__ == "__main__":
    login_and_simulate()