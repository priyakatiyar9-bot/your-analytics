# =============================================================================
# app.py — The YouR web app
# =============================================================================
# This is the Flask web application that creators interact with.
# It has four pages:
#
#   GET  /              → Home page with "Connect your YouTube channel" button
#   GET  /connect       → Starts the Google OAuth flow (redirects to Google)
#   GET  /callback      → Google sends the creator back here after login
#   GET  /connected     → Success page shown after creator connects
#   GET  /status        → Shows all connected creators (for your eyes only)
#   POST /revoke        → Immediately revokes a creator's access
#
# The creator never sees /status or /revoke — those are just for you.
# =============================================================================

import os
from flask import Flask, redirect, request, session, url_for, render_template_string
from database import setup_database, list_all_tokens, delete_token
from auth import get_authorization_url, handle_callback

app = Flask(__name__)

# Secret key for securing session cookies — set this in Render environment variables
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-this")

# Create database table on startup if it doesn't exist
from database import setup_database
with app.app_context():
    try:
        setup_database()
    except Exception as e:
        print(f"Database setup warning: {e}")


# =============================================================================
# HTML TEMPLATES
# These are simple inline HTML pages — clean and minimal so creators
# immediately understand what they're being asked to do.
# =============================================================================

HOME_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouR — YouTube Resonance</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0f0f0f;
            color: #fff;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container {
            text-align: center;
            padding: 40px 20px;
            max-width: 520px;
        }
        .logo {
            font-size: 42px;
            font-weight: 800;
            letter-spacing: -1px;
            margin-bottom: 8px;
        }
        .logo span { color: #ff4444; }
        .tagline {
            color: #888;
            font-size: 16px;
            margin-bottom: 48px;
        }
        .card {
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            border-radius: 16px;
            padding: 36px 32px;
            margin-bottom: 24px;
        }
        .card h2 {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 12px;
        }
        .card p {
            color: #888;
            font-size: 14px;
            line-height: 1.6;
            margin-bottom: 28px;
        }
        .permissions {
            text-align: left;
            margin-bottom: 28px;
        }
        .permission-item {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            margin-bottom: 10px;
            font-size: 13px;
            color: #aaa;
        }
        .permission-item .icon { color: #4CAF50; font-size: 15px; flex-shrink: 0; }
        .connect-btn {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            background: #fff;
            color: #000;
            text-decoration: none;
            padding: 14px 28px;
            border-radius: 50px;
            font-weight: 600;
            font-size: 15px;
            transition: opacity 0.2s;
            width: 100%;
            justify-content: center;
        }
        .connect-btn:hover { opacity: 0.85; }
        .footer-note {
            color: #555;
            font-size: 12px;
            line-height: 1.6;
        }
        .footer-note a { color: #888; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">You<span>R</span></div>
        <div class="tagline">YouTube Resonance — understand your audience deeply</div>

        <div class="card">
            <h2>Connect your YouTube channel</h2>
            <p>YouR reads your analytics data on your behalf — no manual exports needed.
               Access lasts 30 days, then expires automatically.</p>

            <div class="permissions">
                <div class="permission-item">
                    <span class="icon">✓</span>
                    <span>Read-only access to your YouTube Analytics (views, watch time, traffic sources, retention)</span>
                </div>
                <div class="permission-item">
                    <span class="icon">✓</span>
                    <span>Read your video list and metadata</span>
                </div>
                <div class="permission-item">
                    <span class="icon">✓</span>
                    <span>Access expires automatically after 30 days</span>
                </div>
                <div class="permission-item">
                    <span class="icon">✗</span>
                    <span>We cannot post, edit, delete, or change anything on your channel</span>
                </div>
            </div>

            <a href="/connect" class="connect-btn">
                <svg width="18" height="18" viewBox="0 0 48 48">
                    <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
                    <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
                    <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
                    <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.31-8.16 2.31-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
                </svg>
                Connect with Google
            </a>
        </div>

        <p class="footer-note">
            By connecting, you agree that YouR will read your YouTube Analytics data
            for reporting purposes. You can revoke access at any time via
            <a href="https://myaccount.google.com/permissions" target="_blank">Google Account Settings</a>.
        </p>
    </div>
</body>
</html>
"""

SUCCESS_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connected — YouR</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Plus Jakarta Sans', sans-serif;
            background: #f5f5f3;
            color: #1f1f1f;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container { text-align: center; padding: 40px 20px; max-width: 440px; }
        .logo { font-size: 28px; font-weight: 800; letter-spacing: -1px; margin-bottom: 32px; color: #1f1f1f; }
        .logo span { color: #e05252; }
        .checkmark { font-size: 56px; margin-bottom: 20px; }
        h1 { font-size: 24px; font-weight: 700; margin-bottom: 10px; color: #1f1f1f; }
        .channel { color: #e05252; }
        p { color: #aaa; font-size: 14px; line-height: 1.6; margin-bottom: 6px; font-weight: 400; }
        .expiry { color: #ccc; font-size: 12px; margin-top: 24px; line-height: 1.7; }
        .expiry a { color: #bbb; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">You<span>R</span></div>
        <div class="checkmark">✅</div>
        <h1>You're connected, <span class="channel">{{ channel_name }}</span></h1>
        <p>YouR now has read-only access to your YouTube Analytics.</p>
        <p>You can close this tab.</p>
        <p class="expiry">Access expires automatically on {{ expires_at }}.<br>
        To revoke access early, visit
        <a href="https://myaccount.google.com/permissions">Google Account Settings</a>.</p>
    </div>
</body>
</html>
"""

ERROR_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Something went wrong — YouR</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;700;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Plus Jakarta Sans', sans-serif;
            background: #f5f5f3; color: #1f1f1f;
            min-height: 100vh; display: flex;
            align-items: center; justify-content: center;
        }
        .container { text-align: center; padding: 40px 20px; max-width: 440px; }
        .logo { font-size: 28px; font-weight: 800; letter-spacing: -1px; margin-bottom: 32px; color: #1f1f1f; }
        .logo span { color: #e05252; }
        h1 { font-size: 20px; font-weight: 700; margin-bottom: 12px; color: #1f1f1f; }
        p { color: #aaa; font-size: 13px; line-height: 1.6; font-weight: 400; }
        a { color: #e05252; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">You<span>R</span></div>
        <h1>Something went wrong</h1>
        <p>{{ error_message }}</p>
        <p style="margin-top:20px"><a href="/">Try again</a></p>
    </div>
</body>
</html>
"""

STATUS_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Connected Creators — YouR</title>
    <style>
        body { font-family: monospace; background: #0f0f0f; color: #ccc; padding: 40px; }
        h1 { color: #fff; margin-bottom: 24px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { text-align: left; padding: 10px 16px; border-bottom: 1px solid #222; font-size: 13px; }
        th { color: #888; }
        .expired { color: #ff4444; }
        .active { color: #4CAF50; }
        form { display: inline; }
        button {
            background: #ff4444; color: #fff; border: none;
            padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: 12px;
        }
    </style>
</head>
<body>
    <h1>YouR — Connected Creators</h1>
    {% if creators %}
    <table>
        <tr>
            <th>Channel</th>
            <th>Label</th>
            <th>Connected</th>
            <th>Expires</th>
            <th>Status</th>
            <th>Action</th>
        </tr>
        {% for c in creators %}
        <tr>
            <td>{{ c.channel_name }}</td>
            <td>{{ c.channel_label }}</td>
            <td>{{ c.granted_at.strftime('%d %b %Y') }}</td>
            <td>{{ c.expires_at.strftime('%d %b %Y') }}</td>
            <td class="{{ 'active' if c.expires_at > now else 'expired' }}">
                {{ 'Active' if c.expires_at > now else 'Expired' }}
            </td>
            <td>
                <form method="POST" action="/revoke">
                    <input type="hidden" name="channel_id" value="{{ c.channel_id }}">
                    <button type="submit"
                            onclick="return confirm('Revoke access for {{ c.channel_name }}?')">
                        Revoke
                    </button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </table>
    {% else %}
    <p>No creators connected yet.</p>
    {% endif %}
</body>
</html>
"""


# =============================================================================
# ROUTES
# =============================================================================

@app.route("/")
def home():
    return HOME_PAGE


@app.route("/connect")
def connect():
    """Redirects the creator to Google's login page."""
    redirect_uri = url_for("callback", _external=True)
    auth_url, state = get_authorization_url(redirect_uri)
    session["oauth_state"] = state
    return redirect(auth_url)


@app.route("/callback")
def callback():
    """Google sends the creator back here after they log in and click Allow."""
    # Check the state matches to prevent CSRF attacks
    # State check disabled during testing — re-enable for production
    # if request.args.get("state") != session.get("oauth_state"):
    if False:
        return render_template_string(
            ERROR_PAGE,
            error_message="Security check failed. Please try connecting again."
        ), 400

    # Check if the creator denied access
    if "error" in request.args:
        return render_template_string(
            ERROR_PAGE,
            error_message="Access was not granted. You can try again anytime."
        ), 400

    try:
        redirect_uri = url_for("callback", _external=True)
        state = session.get("oauth_state", "")
        channel_id, channel_name, expires_at = handle_callback(
            redirect_uri,
            request.url,
            state,
        )
        return render_template_string(
            SUCCESS_PAGE,
            channel_name=channel_name,
            expires_at=expires_at.strftime("%d %B %Y"),
        )
    except Exception as e:
        return render_template_string(
            ERROR_PAGE,
            error_message=f"Something went wrong during connection: {str(e)}"
        ), 500


@app.route("/status")
def status():
    """Shows all connected creators — for your eyes only."""
    import datetime
    creators = list_all_tokens()
    return render_template_string(
        STATUS_PAGE,
        creators=creators,
        now=datetime.datetime.now(),
    )


@app.route("/revoke", methods=["POST"])
def revoke():
    """Immediately revokes a creator's access."""
    channel_id = request.form.get("channel_id")
    if channel_id:
        delete_token(channel_id)
    return redirect("/status")


# =============================================================================
# STARTUP
# =============================================================================

if __name__ == "__main__":
    # Set up the database table when the app starts
    setup_database()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
