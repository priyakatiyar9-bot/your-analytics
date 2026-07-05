# =============================================================================
# auth.py — Handles Google OAuth for both web flow and local script
# =============================================================================
# This file has two modes:
#
# 1. WEB MODE (used by app.py)
#    The creator clicks a link, gets sent to Google to log in, then Google
#    sends them back to our app with an authorisation code. We exchange that
#    code for a token and store it in the database.
#
# 2. LOCAL MODE (used by run_all.py on your own machine)
#    Opens a browser window locally for authentication. Used when you want
#    to pull data yourself without going through the web app.
#
# The fetch scripts (fetch_video_stats.py etc.) always use the database
# to load tokens — they don't care which mode was used to create them.
# =============================================================================

import os
import datetime
import json

from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import googleapiclient.discovery

from database import save_token, load_token_by_label, load_token

# The two permissions this tool requests from creators:
#   yt-analytics.readonly → read their YouTube Analytics data
#   youtube.readonly      → read their video list and metadata
SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]

ACCESS_DURATION_DAYS = 30


# =============================================================================
# WEB FLOW — used by app.py
# =============================================================================

def get_web_flow(redirect_uri):
    """
    Creates a Google OAuth flow object for the web app.

    The client credentials are read from environment variables
    (set in Render dashboard) rather than client_secret.json,
    so the file doesn't need to be on the server.

    redirect_uri: the URL Google sends the creator back to after login
                  e.g. "https://your-app.onrender.com/callback"
    """
    client_config = {
        "web": {
            "client_id":     os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    return flow


def get_authorization_url(redirect_uri):
    """
    Generates the Google login URL that the creator gets sent to.
    Returns (auth_url, state) — state is a security token we check on return.
    """
    flow = get_web_flow(redirect_uri)
    auth_url, state = flow.authorization_url(
        access_type="offline",      # gives us a refresh token so we don't need re-login
        include_granted_scopes="true",
        prompt="consent",           # always show consent screen so refresh token is issued
    )
    return auth_url, state


def handle_callback(redirect_uri, authorization_response_url, state):
    """
    Called after Google redirects the creator back to our app.

    Exchanges the authorisation code in the URL for actual credentials,
    fetches the creator's channel info, and saves everything to the database.

    Returns (channel_id, channel_name, expires_at) on success.
    """
    flow = get_web_flow(redirect_uri)
    flow.fetch_token(authorization_response=authorization_response_url)
    credentials = flow.credentials

    # Use the credentials to find out which channel just connected
    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=credentials
    )
    channel_response = youtube.channels().list(
        part="id,snippet", mine=True
    ).execute()

    if not channel_response.get("items"):
        raise Exception("No YouTube channel found for this Google account.")

    channel = channel_response["items"][0]
    channel_id   = channel["id"]
    channel_name = channel["snippet"]["title"]

    # Use the channel name (lowercased, spaces replaced) as the label
    channel_label = channel_name.lower().replace(" ", "_")[:30]

    # Save to database
    expires_at = save_token(channel_id, channel_name, channel_label, credentials)

    return channel_id, channel_name, expires_at


# =============================================================================
# LOCAL FLOW — used by run_all.py on your own machine
# =============================================================================

def get_authenticated_services_local(channel_label="default"):
    """
    Local version of authentication — opens a browser window on your machine.
    Used by run_all.py when pulling data locally.

    Loads the token from the database if it exists, otherwise opens
    a browser for login and saves the new token to the database.

    Returns (youtube, youtube_analytics) service objects,
    or (None, None) if access has expired.
    """
    # Try loading existing token from database
    token_row = load_token_by_label(channel_label)

    if token_row:
        expires_at = token_row["expires_at"]
        days_left  = (expires_at - datetime.datetime.now()).days
        print(f"\n✅  Using saved access for '{channel_label}'.")
        print(f"    Expires in {days_left} day(s) on {expires_at.strftime('%d %b %Y')}.\n")

        cred_info = json.loads(token_row["credentials_json"])
        creds = Credentials(
            token=         cred_info["token"],
            refresh_token= cred_info["refresh_token"],
            token_uri=     cred_info["token_uri"],
            client_id=     cred_info["client_id"],
            client_secret= cred_info["client_secret"],
            scopes=        cred_info["scopes"],
        )

        # Refresh if the access token has expired (refresh token handles this silently)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Update the stored token with the refreshed credentials
            channel_id   = token_row["channel_id"]
            channel_name = token_row["channel_name"]
            save_token(channel_id, channel_name, channel_label, creds)

    else:
        # No token — open browser for local login
        print(f"\n🔐  No saved access found for '{channel_label}'.")
        print(f"    A browser window will open to log in.")
        print(f"    Access will last {ACCESS_DURATION_DAYS} days.\n")

        flow = InstalledAppFlow.from_client_secrets_file(
            "client_secret.json", SCOPES
        )
        creds = flow.run_local_server(port=0)

        # Get channel info and save to database
        youtube_temp = googleapiclient.discovery.build(
            "youtube", "v3", credentials=creds
        )
        channel_response = youtube_temp.channels().list(
            part="id,snippet", mine=True
        ).execute()
        channel    = channel_response["items"][0]
        channel_id = channel["id"]
        channel_name = channel["snippet"]["title"]

        save_token(channel_id, channel_name, channel_label, creds)
        print(f"✅  Access saved for '{channel_name}'.\n")

    # Build and return both API service objects
    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=creds
    )
    youtube_analytics = googleapiclient.discovery.build(
        "youtubeAnalytics", "v2", credentials=creds
    )
    return youtube, youtube_analytics


def get_services_from_db(channel_id):
    """
    Loads a creator's credentials from the database by channel ID
    and returns ready-to-use API service objects.

    Used by run_all.py when pulling data for a specific creator
    who connected via the web app.

    Returns (youtube, youtube_analytics) or (None, None) if expired/not found.
    """
    token_row = load_token(channel_id)
    if not token_row:
        print(f"\n⏰  No valid token found for channel ID: {channel_id}")
        print("    Access may have expired. The creator needs to reconnect.\n")
        return None, None

    cred_info = json.loads(token_row["credentials_json"])
    creds = Credentials(
        token=         cred_info["token"],
        refresh_token= cred_info["refresh_token"],
        token_uri=     cred_info["token_uri"],
        client_id=     cred_info["client_id"],
        client_secret= cred_info["client_secret"],
        scopes=        cred_info["scopes"],
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_token(
            token_row["channel_id"],
            token_row["channel_name"],
            token_row["channel_label"],
            creds
        )

    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=creds
    )
    youtube_analytics = googleapiclient.discovery.build(
        "youtubeAnalytics", "v2", credentials=creds
    )
    return youtube, youtube_analytics


def get_channel_id(youtube):
    """
    Returns the authenticated channel's ID and name.
    Used by run_all.py.
    """
    response = youtube.channels().list(part="id,snippet", mine=True).execute()
    if not response.get("items"):
        raise Exception("Could not find a YouTube channel for this account.")
    channel      = response["items"][0]
    channel_id   = channel["id"]
    channel_name = channel["snippet"]["title"]
    print(f"📺  Channel: '{channel_name}' (ID: {channel_id})\n")
    return channel_id
