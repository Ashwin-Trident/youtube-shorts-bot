from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Make sure client_secret.json is in the same folder
flow = InstalledAppFlow.from_client_secrets_file("client_secret_1.json", SCOPES)

# Opens browser automatically
creds = flow.run_local_server(port=0)

print("CLIENT_ID:", creds.client_id)
print("CLIENT_SECRET:", creds.client_secret)
print("REFRESH_TOKEN:", creds.refresh_token)