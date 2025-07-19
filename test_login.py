import re

import requests
from bs4 import BeautifulSoup


def test_login() -> None:
    # Start a session to maintain cookies
    session = requests.Session()

    # Get the login page to extract the CSRF token
    login_page = session.get("http://localhost:5000/login")
    soup = BeautifulSoup(login_page.text, "html.parser")
    csrf_token = soup.find("input", {"name": "csrf_token"})["value"]

    # Attempt to login
    login_data = {"email": "admin@example.com", "password": "admin123", "csrf_token": csrf_token}

    login_response = session.post("http://localhost:5000/login", data=login_data)

    # Check if login was successful by getting a protected page
    devices_page = session.get("http://localhost:5000/devices")

    # Success if we get a 200 status code and not redirected to login
    if devices_page.status_code == 200 and "login" not in devices_page.url:
        print("Login successful!")
        # Check for ThermoWorks devices in the response
        if "ThermoWorks" in devices_page.text:
            print("Found ThermoWorks device data!")
            soup = BeautifulSoup(devices_page.text, "html.parser")
            devices = soup.find_all("div", class_="card")
            print(f"Number of devices found: {len(devices)}")
        else:
            print("No device data found.")
    else:
        print("Login failed!")
        print(f"Status code: {devices_page.status_code}")
        print(f"URL after login attempt: {devices_page.url}")


if __name__ == "__main__":
    test_login()
