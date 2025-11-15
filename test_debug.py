import requests
import json

# This is a quick debug script to test the API response
# Run this after starting the app locally

BASE_URL = "http://localhost:8000"

# First, login to get a token
login_response = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"email": "test@example.com", "password": "password123"}
)

if login_response.status_code == 200:
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get attended games
    attendance_response = requests.get(
        f"{BASE_URL}/api/attendance/",
        headers=headers
    )

    print("Status Code:", attendance_response.status_code)
    print("\nResponse JSON:")
    print(json.dumps(attendance_response.json(), indent=2))

    if attendance_response.status_code == 200:
        data = attendance_response.json()
        if data:
            print("\nFirst item keys:", list(data[0].keys()))
            print("\nHas game_id?", "game_id" in data[0])
            if "game_id" in data[0]:
                print("game_id value:", data[0]["game_id"])
                print("game_id type:", type(data[0]["game_id"]))
else:
    print(f"Login failed: {login_response.status_code}")
    print(login_response.text)
