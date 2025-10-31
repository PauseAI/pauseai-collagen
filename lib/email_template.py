"""
Email template module for Collagen notification emails.

Generates both HTML and plain text versions of notification emails
with personalized tracking URLs.
"""

from typing import Dict, Optional


# Tracking URL base (production)
TRACKING_BASE = "https://collagen.pauseai.info"

# Campaign link (where validate redirects)
CAMPAIGN_PAGE = "https://pauseai.info/if-anyone-builds-it-campaign#say-no-to-superintelligent-ai"

# Social share platforms
SOCIAL_PLATFORMS = ['facebook', 'twitter', 'whatsapp', 'linkedin', 'reddit']


def generate_tracking_urls(campaign: str, uid: str, email: str, build_id: str) -> Dict[str, str]:
    """
    Generate all tracking URLs for a user.

    Args:
        campaign: Campaign name (e.g. "sayno", "test_prototype")
        uid: User's 8-char UID from tracking database
        email: User's email address (required for subscribe URL)
        build_id: Collage build ID (e.g. "20251024T230728Z,266=19x14")

    Returns:
        Dict with keys: image, subscribe, validate, share_{platform}
    """
    from urllib.parse import quote

    urls = {
        'image': f"{TRACKING_BASE}/t/{campaign}/{uid}/{build_id}.jpg",
        'subscribe': f"{TRACKING_BASE}/t/{campaign}/{uid}/subscribe?email={quote(email)}",
        'validate': f"{TRACKING_BASE}/t/{campaign}/{uid}/validate",
    }

    # Add social share URLs
    for platform in SOCIAL_PLATFORMS:
        urls[f'share_{platform}'] = f"{TRACKING_BASE}/t/{campaign}/{uid}/share/{platform}"

    return urls


def generate_plain_text(urls: Dict[str, str], subject: Optional[str] = None) -> str:
    """
    Generate plain text email body.

    Args:
        urls: Dict of tracking URLs from generate_tracking_urls()
        subject: Optional email subject (for header)

    Returns:
        Plain text email body
    """
    text = f"""Hi there!

Thanks for adding your face to our petition to stop the race to build superintelligent AI.

You are now in the collage:
{urls['image']}

Our website hosts an updating version at:
{CAMPAIGN_PAGE}

Please share this with your networks and encourage others to participate. Every new voice of concern matters!

We would love you to:
→ Verify your email and sign up for our newsletter and more ways to help:
  {urls['subscribe']}

OR

→ Just verify your email (we won't use it to reach out again):
  {urls['validate']}

Share on social media:
→ Facebook: {urls['share_facebook']}
→ Twitter/X: {urls['share_twitter']}
→ WhatsApp: {urls['share_whatsapp']}
→ LinkedIn: {urls['share_linkedin']}
→ Reddit: {urls['share_reddit']}

As the petition grows, we'll use it in social and physical media to push politicians to take international regulatory action, and to gain further public attention and support.

Every step you take to help increase the number of photos in the petition increases its impact. Thank you for contributing - by taking action together we can stop the race.

The PauseAI Team

---
This is the single automated notification we promised when you submitted your photo.
"""
    return text.strip()


def generate_html(urls: Dict[str, str], subject: Optional[str] = None, is_bootstrap_user: bool = False) -> str:
    """
    Generate HTML email body.

    Args:
        urls: Dict of tracking URLs from generate_tracking_urls()
        subject: Optional email subject (for header)
        is_bootstrap_user: If True, add note about previous bootstrap email

    Returns:
        HTML email body
    """
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>You're in the collage!</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .collage-image {{
            width: 100%;
            max-width: 400px;
            height: auto;
            margin: 20px 0;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .cta-primary {{
            display: inline-block;
            padding: 12px 24px;
            margin: 10px 0;
            background-color: #FF9416;
            color: white !important;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
        }}
        .cta-secondary {{
            display: inline-block;
            padding: 12px 24px;
            margin: 10px 0;
            background-color: #757575;
            color: white !important;
            text-decoration: none;
            border-radius: 6px;
        }}
        .social-buttons {{
            margin: 20px 0;
        }}
        .social-button {{
            display: inline-block;
            padding: 8px 16px;
            margin: 5px;
            background-color: #424242;
            color: white !important;
            text-decoration: none;
            border-radius: 4px;
            font-size: 14px;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            font-size: 12px;
            color: #666;
        }}
        a {{
            color: #1976d2;
        }}
    </style>
</head>
<body>
    <p>Hi there!</p>

    <p>Thanks for adding your face to our petition to stop the race to build superintelligent AI.</p>

    <p><strong>You are now in the collage:</strong></p>

    <p><img src="{urls['image']}" alt="Say No collage featuring your photo" class="collage-image"></p>

    <p>Please share this with your networks and encourage others to participate. <strong>Every new voice of concern matters!</strong></p>

    <p>We would love you to:</p>

    <p>
        <a href="{urls['subscribe']}" class="cta-primary">✓ Verify your email and sign up for our newsletter and more ways to help</a>
    </p>

    <p style="text-align: center; margin: 20px 0;">or</p>

    <p>
        <a href="{urls['validate']}" class="cta-secondary">Just verify your email (we won't use it to reach out again)</a>
    </p>

    <div class="social-buttons">
        <p><strong>Share on social media:</strong></p>
        <a href="{urls['share_facebook']}" class="social-button">📘 Facebook</a>
        <a href="{urls['share_twitter']}" class="social-button">🐦 Twitter/X</a>
        <a href="{urls['share_whatsapp']}" class="social-button">💬 WhatsApp</a>
        <a href="{urls['share_linkedin']}" class="social-button">💼 LinkedIn</a>
        <a href="{urls['share_reddit']}" class="social-button">🔗 Reddit</a>
    </div>

    <p style="margin-top: 30px;">As the petition grows, we'll use it in social and physical media to push politicians to take international regulatory action, and to gain further public attention and support.</p>

    <p>Every step you take to help increase the number of photos in the petition increases its impact. Thank you for contributing - by taking action together we can stop the race.</p>

    <p><strong>The PauseAI Team</strong></p>

    <div class="footer">
        <p>This is the single automated notification we promised when you submitted your photo.{' (You signed early enough you already got a placeholder email from me too: thanks again, --Anthony.)' if is_bootstrap_user else ''}</p>
    </div>
</body>
</html>
"""
    return html.strip()


def generate_email(campaign: str, uid: str, email: str, build_id: str, subject: Optional[str] = None, is_bootstrap_user: bool = False) -> Dict[str, str]:
    """
    Generate complete email (subject, plain text, HTML) for a user.

    Args:
        campaign: Campaign name
        uid: User UID
        email: User's email address
        build_id: Collage build ID
        subject: Optional custom subject line
        is_bootstrap_user: If True, add note about previous bootstrap email

    Returns:
        Dict with keys: subject, plain, html
    """
    if subject is None:
        subject = "You're now in the Say No collage! 📸"

    urls = generate_tracking_urls(campaign, uid, email, build_id)

    return {
        'subject': subject,
        'plain': generate_plain_text(urls, subject),
        'html': generate_html(urls, subject, is_bootstrap_user)
    }
