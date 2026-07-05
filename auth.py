# =============================================================================
# auth.py — Handles Google OAuth for both web flow and local script
# =============================================================================

import os
import datetime
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import googleapiclient.discovery
import requests as req
from urllib.parse import urlparse, parse_qs

from database import save_token, load_token_by_label, load_token

SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]

ACCESS_DURATION_DAYS = 30


def get_authorization_url(redirect_uri):
    """
    Builds the Google OAuth URL manually — no PKCE, plain OAuth2 web flow.
    Returns (auth_url, state).
    """
    import secrets
    state = secrets.token_urlsafe(32)

    params = {
        "client_id":     os.environ["GOOGLE_CLIENT_ID"],
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         " ".join(SCOPES),
        "access_type":   "offline",
        "prompt":        "consent",
        "state":         state,
    }

    from urllib.parse import urlencode
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return auth_url, state


def handle_callback(redirect_uri, authorization_response_url, state):
    """
    Exchanges the authorisation code for credentials.
    No PKCE — plain server-side OAuth2.
    """
    parsed = urlparse(authorization_response_url)
    params = parse_qs(parsed.query)
    code = params.get("code", [None])[0]

    if not code:
        raise Exception("No authorisation code found in callback URL.")

    # Exchange code for tokens
    token_response = req.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code":          code,
            "client_id":     os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "redirect_uri":  redirect_uri,
            "grant_type":    "authorization_code",
        },
    )

    token_data = token_response.json()

    if "error" in token_data:
        raise Exception(f"Token exchange failed: {token_data}")

    credentials = Credentials(
        token=         token_data["access_token"],
        refresh_token= token_data.get("refresh_token"),
        token_uri=     "https://oauth2.googleapis.com/token",
        client_id=     os.environ["GOOGLE_CLIENT_ID"],
        client_secret= os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=        SCOPES,
    )

    # Get the channel info
    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=credentials
    )
    channel_response = youtube.channels().list(
        part="id,snippet", mine=True
    ).execute()

    if not channel_response.get("items"):
        raise Exception("No YouTube channel found for this Google account.")

    channel       = channel_response["items"][0]
    channel_id    = channel["id"]
    channel_name  = channel["snippet"]["title"]
    channel_label = channel_name.lower().replace(" ", "_")[:30]

    expires_at = save_token(channel_id, channel_name, channel_label, credentials)
    return channel_id, channel_name, expires_at


def get_authenticated_services_local(channel_label="default"):
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

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_token(
                token_row["channel_id"],
                token_row["channel_name"],
                channel_label,
                creds
            )
    else:
        print(f"\n🔐  No saved access found for '{channel_label}'.")
        print(f"    A browser window will open to log in.\n")

        flow = InstalledAppFlow.from_client_secrets_file(
            "client_secret.json", SCOPES
        )
        creds = flow.run_local_server(port=0)

        youtube_temp = googleapiclient.discovery.build(
            "youtube", "v3", credentials=creds
        )
        channel_response = youtube_temp.channels().list(
            part="id,snippet", mine=True
        ).execute()
        channel      = channel_response["items"][0]
        channel_id   = channel["id"]
        channel_name = channel["snippet"]["title"]

        save_token(channel_id, channel_name, channel_label, creds)
        print(f"✅  Access saved for '{channel_name}'.\n")

    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=creds
    )
    youtube_analytics = googleapiclient.discovery.build(
        "youtubeAnalytics", "v2", credentials=creds
    )
    return youtube, youtube_analytics


def get_services_from_db(channel_id):
    token_row = load_token(channel_id)
    if not token_row:
        print(f"\n⏰  No valid token found for channel ID: {channel_id}")
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
    response = youtube.channels().list(part="id,snippet", mine=True).execute()
    if not response.get("items"):
        raise Exception("Could not find a YouTube channel for this account.")
    channel      = response["items"][0]
    channel_id   = channel["id"]
    channel_name = channel["snippet"]["title"]
    print(f"📺  Channel: '{channel_name}' (ID: {channel_id})\n")
    return channel_id
