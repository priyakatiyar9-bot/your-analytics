# =============================================================================
# auth.py — Handles login and access management
# =============================================================================
# What this file does:
#   1. Opens a browser window for the channel owner to log in with Google
#      and grant this tool read-only access to their YouTube Analytics data.
#   2. Saves the resulting token locally so the script can run again
#      without asking the creator to log in every time.
#   3. Automatically enforces a 30-day expiry — after that, the token is
#      deleted and the creator would need to log in again.
#   4. Provides a revoke_access() function to immediately delete a creator's
#      stored token if they want to cut off access early.
#
# Nothing in here stores or sends data anywhere — it only manages the local
# token file on your own machine.
# =============================================================================

import os
import json
import datetime

from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import googleapiclient.discovery

from config import CLIENT_SECRET_FILE, TOKENS_DIR, ACCESS_DURATION_DAYS

# These are the two permissions the tool requests from the creator:
#   yt-analytics.readonly  → read their YouTube Analytics data
#   youtube.readonly       → read their video list and metadata
SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def get_authenticated_services(channel_label="default"):
    """
    Authenticates with Google and returns two API service objects:
      - youtube          → for YouTube Data API (video list, metadata, duration)
      - youtube_analytics → for YouTube Analytics API (views, retention, traffic, etc.)

    channel_label:
      A short nickname for this channel, used to name the token file.
      Examples: "test_channel", "creator_jane", "channel_2"
      Use the same label each time you run for the same creator — it's how
      the tool knows which stored token to use.

    Returns (youtube, youtube_analytics) — two service objects.
    Returns (None, None) if access has expired or something went wrong.
    """

    # Make sure the tokens folder exists
    os.makedirs(TOKENS_DIR, exist_ok=True)
    token_file = os.path.join(TOKENS_DIR, f"{channel_label}.json")

    creds = None

    # --- Check if we already have a saved token for this channel ---
    if os.path.exists(token_file):
        with open(token_file, "r") as f:
            token_data = json.load(f)

        # Check the 30-day expiry
        expires_at = datetime.datetime.fromisoformat(token_data["expires_at"])
        if datetime.datetime.now() > expires_at:
            print(f"\n⏰  Access for '{channel_label}' expired on "
                  f"{expires_at.strftime('%d %b %Y')}.")
            print("    The creator needs to log in again to re-grant access.")
            print("    Run the script and they will be prompted automatically.\n")
            os.remove(token_file)
            return None, None

        # Load stored credentials
        cred_info = token_data["credentials"]
        creds = Credentials(
            token=cred_info["token"],
            refresh_token=cred_info["refresh_token"],
            token_uri=cred_info["token_uri"],
            client_id=cred_info["client_id"],
            client_secret=cred_info["client_secret"],
            scopes=cred_info["scopes"],
        )

        days_left = (expires_at - datetime.datetime.now()).days
        print(f"\n✅  Using saved access for '{channel_label}'.")
        print(f"    Access expires in {days_left} day(s) on "
              f"{expires_at.strftime('%d %b %Y')}.\n")

    # --- If no valid token, start the OAuth login flow ---
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Token exists but just needs a refresh — no browser needed
            creds.refresh(Request())
        else:
            # No token at all — open browser for the creator to log in
            print(f"\n🔐  No saved access found for '{channel_label}'.")
            print(f"    A browser window will open for the creator to log in.")
            print(f"    Access will last {ACCESS_DURATION_DAYS} days, "
                  f"then expire automatically.\n")

            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save the token with timestamps
        granted_at = datetime.datetime.now()
        expires_at = granted_at + datetime.timedelta(days=ACCESS_DURATION_DAYS)

        token_data = {
            "channel_label": channel_label,
            "granted_at": granted_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "credentials": {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": list(creds.scopes),
            },
        }

        with open(token_file, "w") as f:
            json.dump(token_data, f, indent=2)

        print(f"\n✅  Access granted and saved for '{channel_label}'.")
        print(f"    Access will automatically expire on "
              f"{expires_at.strftime('%d %b %Y')}.\n")

    # Build and return the two API service objects
    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=creds
    )
    youtube_analytics = googleapiclient.discovery.build(
        "youtubeAnalytics", "v2", credentials=creds
    )

    return youtube, youtube_analytics


def revoke_access(channel_label="default"):
    """
    Immediately deletes the stored token for a channel.

    After calling this, the script can no longer access that channel's data
    until the creator logs in again and re-grants access.

    Note: this only deletes the local token file. If the creator also wants
    to fully revoke the app's permission on Google's side, they can go to:
    https://myaccount.google.com/permissions
    and remove "YouTube Analytics Tool" from the list.
    """
    token_file = os.path.join(TOKENS_DIR, f"{channel_label}.json")
    if os.path.exists(token_file):
        os.remove(token_file)
        print(f"\n✅  Access for '{channel_label}' has been revoked.")
        print(f"    The token file has been deleted from this machine.")
        print(f"    To fully remove app permissions on Google's side, visit:")
        print(f"    https://myaccount.google.com/permissions\n")
    else:
        print(f"\n⚠️   No stored token found for '{channel_label}'. Nothing to revoke.\n")


def get_channel_id(youtube):
    """
    Returns the authenticated channel's ID (e.g. "UCxxxxxxxxxxxxxxxx").
    Used internally by the fetch scripts.
    """
    response = youtube.channels().list(part="id,snippet", mine=True).execute()
    if not response.get("items"):
        raise Exception("Could not find a YouTube channel for this account.")
    channel = response["items"][0]
    channel_id = channel["id"]
    channel_name = channel["snippet"]["title"]
    print(f"📺  Channel found: '{channel_name}' (ID: {channel_id})\n")
    return channel_id
