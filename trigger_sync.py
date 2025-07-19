import requests
import re
from bs4 import BeautifulSoup

def login_and_sync():
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
        
        # Trigger a sync
        sync_response = session.post('http://localhost:5000/sync')
        print(f"Sync triggered, status code: {sync_response.status_code}")
        
        # Check for devices
        devices_response = session.get('http://localhost:5000/devices')
        print(f"Devices page status code: {devices_response.status_code}")
        
        # Check the monitoring data endpoint
        monitoring_data = session.get('http://localhost:5000/api/monitoring/data')
        print(f"Monitoring data status code: {monitoring_data.status_code}")
        print(monitoring_data.json())
        
    else:
        print("Login failed!")

if __name__ == "__main__":
    login_and_sync()