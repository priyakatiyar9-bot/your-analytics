# =============================================================================
# database.py — Handles all token storage in PostgreSQL
# =============================================================================
# What this file does:
#   Instead of saving tokens as local files (which get wiped when the server
#   restarts), this stores them in a proper PostgreSQL database on Render.
#
#   Think of it like a spreadsheet with one row per creator, storing:
#   - Their channel ID
#   - Their channel name
#   - When they granted access
#   - When access expires (30 days later)
#   - Their OAuth credentials (encrypted by the database)
#
#   Every other file that needs to read or write tokens talks to this file.
# =============================================================================

import os
import json
import datetime
import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection():
    """
    Opens a connection to the PostgreSQL database.
    The DATABASE_URL environment variable is set automatically by Render
    when you attach a database to your app — you don't need to set it manually.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise Exception(
            "DATABASE_URL environment variable not set. "
            "Make sure the Render database is attached to this app."
        )
    return psycopg2.connect(database_url)


def setup_database():
    """
    Creates the tokens table if it doesn't already exist.
    This runs automatically when the app starts — safe to call multiple times.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS creator_tokens (
                    id               SERIAL PRIMARY KEY,
                    channel_id       TEXT UNIQUE NOT NULL,
                    channel_name     TEXT,
                    channel_label    TEXT,
                    granted_at       TIMESTAMP NOT NULL,
                    expires_at       TIMESTAMP NOT NULL,
                    credentials_json TEXT NOT NULL
                );
            """)
        conn.commit()
        print("✅  Database table ready.")
    finally:
        conn.close()


def save_token(channel_id, channel_name, channel_label, credentials):
    """
    Saves or updates a creator's token in the database.

    If a token already exists for this channel_id, it gets replaced
    (so re-authenticating always gives a fresh 30-day window).

    credentials: a google.oauth2.credentials.Credentials object
    """
    granted_at = datetime.datetime.now()
    expires_at = granted_at + datetime.timedelta(days=30)

    # Serialise the credentials object to JSON for storage
    creds_data = {
        "token":         credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri":     credentials.token_uri,
        "client_id":     credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes":        list(credentials.scopes),
    }

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO creator_tokens
                    (channel_id, channel_name, channel_label,
                     granted_at, expires_at, credentials_json)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (channel_id) DO UPDATE SET
                    channel_name     = EXCLUDED.channel_name,
                    channel_label    = EXCLUDED.channel_label,
                    granted_at       = EXCLUDED.granted_at,
                    expires_at       = EXCLUDED.expires_at,
                    credentials_json = EXCLUDED.credentials_json;
            """, (
                channel_id,
                channel_name,
                channel_label,
                granted_at,
                expires_at,
                json.dumps(creds_data),
            ))
        conn.commit()
        print(f"✅  Token saved for channel: {channel_name} (expires {expires_at.strftime('%d %b %Y')})")
    finally:
        conn.close()

    return expires_at


def load_token(channel_id):
    """
    Loads a creator's token from the database.

    Returns a dict with all token data, or None if:
    - No token exists for this channel
    - The token has expired (expired tokens are deleted automatically)
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM creator_tokens WHERE channel_id = %s;
            """, (channel_id,))
            row = cur.fetchone()

        if not row:
            return None

        # Check expiry
        expires_at = row["expires_at"]
        if datetime.datetime.now() > expires_at:
            # Token expired — delete it and return None
            delete_token(channel_id)
            return None

        return dict(row)
    finally:
        conn.close()


def load_token_by_label(channel_label):
    """
    Loads a token by channel label (e.g. "test_channel") instead of channel ID.
    Used by run_all.py when you specify which channel to pull data for.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM creator_tokens
                WHERE channel_label = %s
                ORDER BY granted_at DESC
                LIMIT 1;
            """, (channel_label,))
            row = cur.fetchone()

        if not row:
            return None

        # Check expiry
        expires_at = row["expires_at"]
        if datetime.datetime.now() > expires_at:
            delete_token(row["channel_id"])
            return None

        return dict(row)
    finally:
        conn.close()


def delete_token(channel_id):
    """
    Deletes a creator's token from the database.
    Used for revoking access or cleaning up expired tokens.
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM creator_tokens WHERE channel_id = %s;
            """, (channel_id,))
        conn.commit()
        print(f"✅  Token deleted for channel ID: {channel_id}")
    finally:
        conn.close()


def list_all_tokens():
    """
    Returns a list of all connected creators and their access status.
    Useful for checking who has granted access and when it expires.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT channel_id, channel_name, channel_label,
                       granted_at, expires_at
                FROM creator_tokens
                ORDER BY granted_at DESC;
            """)
            rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
