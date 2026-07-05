# =============================================================================
# auth.py — Handles Google OAuth for both web flow and local script
# =============================================================================

import os
import datetime
import json

from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import googleapiclient.discovery

from database import save_token, load_token_by_label, load_token

SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
]

ACCESS_DURATION_DAYS = 30


def get_client_config():
    return {
        "web": {
            "client_id":     os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
            "redirect_uris": ["https://your-analytics.onrender.com/callback"],
        }
    }


def get_web_flow(redirect_uri):
    flow = Flow.from_client_config(
        get_client_config(),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )
    return flow


def get_authorization_url(redirect_uri):
    flow = get_web_flow(redirect_uri)
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url, state


def handle_callback(redirect_uri, authorization_response_url, state):
    flow = get_web_flow(redirect_uri)

    # Fetch token without code verifier (standard web app flow)
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # allow http in dev if needed
    flow.fetch_token(
        authorization_response=authorization_response_url,
    )
    credentials = flow.credentials

    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=credentials
    )
    channel_response = youtube.channels().list(
        part="id,snippet", mine=True
    ).execute()

    if not channel_response.get("items"):
        raise Exception("No YouTube channel found for this Google account.")

    channel      = channel_response["items"][0]
    channel_id   = channel["id"]
    channel_name = channel["snippet"]["title"]
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
