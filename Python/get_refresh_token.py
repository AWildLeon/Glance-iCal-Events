import requests

# Replace with your values
CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
AUTHORIZATION_CODE = "YOUR_AUTHORIZATION_CODE"
REDIRECT_URI = "http://localhost:8075"

# Prepare the POST request
token_url = "https://oauth2.googleapis.com/token"
data = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "code": AUTHORIZATION_CODE,
    "grant_type": "authorization_code",
    "redirect_uri": REDIRECT_URI
}

# Send POST request to get the refresh token
response = requests.post(token_url, data=data)

# Check the response
if response.status_code == 200:
    print("Successfully received tokens:")
    print(response.json())
else:
    print("Error:", response.status_code)
    print(response.json())
