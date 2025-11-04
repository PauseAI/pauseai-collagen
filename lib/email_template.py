"""
Email template module for Collagen notification emails.

Generates both HTML and plain text versions of notification emails
with personalized tracking URLs.
"""

from typing import Dict, Optional
from experiments import X001_CTAS_ABOVE_COLLAGE


def get_email_variant(email: str) -> str:
    """
    Determine A/B test variant for email template.

    Currently running experiment: X001 - CTAs above collage
    - Control: Traditional layout (collage image first, verbose CTAs)
    - Treatment: Streamlined (CTAs first, collage at end, simpler language)

    Args:
        email: User's email address

    Returns:
        Variant name ("control" or "treatment")
    """
    return X001_CTAS_ABOVE_COLLAGE.get_variant(email)


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


def generate_email(campaign: str, uid: str, email: str, build_id: str, subject: Optional[str] = None, is_bootstrap_user: bool = False, variant: str = "control") -> Dict[str, str]:
    """
    Generate complete email (subject, plain text, HTML) for a user.

    Args:
        campaign: Campaign name
        uid: User UID
        email: User's email address
        build_id: Collage build ID
        subject: Optional custom subject line
        is_bootstrap_user: If True, add note about previous bootstrap email
        variant: Email variant ("control" or "treatment")

    Returns:
        Dict with keys: subject, plain, html
    """
    if subject is None:
        subject = "You're now in the Say No collage! 📸"

    urls = generate_tracking_urls(campaign, uid, email, build_id)
    text_parts = []
    html_parts = []

    # === GREETING + THANKS (both variants) ===
    text_parts.append("Hi there!")
    html_parts.append("<p>Hi there!</p>")

    if variant == "treatment":
        # Treatment: collage announcement at end of intro
        text_parts.append("Thanks for adding your face to our petition to stop the race to build superintelligent AI. You are now in a published collage.")
        html_parts.append("<p>Thanks for adding your face to our petition to stop the race to build superintelligent AI. You are now in a published collage.</p>")
    else:
        # Control: separate paragraphs
        text_parts.append("Thanks for adding your face to our petition to stop the race to build superintelligent AI.")
        html_parts.append("<p>Thanks for adding your face to our petition to stop the race to build superintelligent AI.</p>")

    # === COLLAGE ANNOUNCEMENT (control only - with image) ===
    if variant == "control":
        text_parts.append(f"You are now in the collage:\n{urls['image']}")
        html_parts.append(f'<p><strong>You are now in the collage:</strong></p>')
        html_parts.append(f'<p><img src="{urls["image"]}" alt="Say No collage featuring your photo" class="collage-image"></p>')

    # === SHARE ENCOURAGEMENT (control only, before CTAs) ===
    if variant == "control":
        text_parts.append("Please share this with your networks and encourage others to participate. Every new voice of concern matters!")
        html_parts.append("<p>Please share this with your networks and encourage others to participate. <strong>Every new voice of concern matters!</strong></p>")

    # === CTA BUTTONS (different styling per variant) ===
    if variant == "treatment":
        text_parts.append("""Please choose one of these:

✓ Keep me informed about ways to help further:
  {subscribe}

No more contact: Just validate that I signed:
  {validate}""".format(**urls))

        html_parts.append(f"""<p><strong>Please choose one of these:</strong></p>
    <div class="cta-buttons">
        <a href="{urls['subscribe']}" class="cta-primary">✓ Keep me informed about ways to help further</a>
        <a href="{urls['validate']}" class="cta-secondary">No more contact: Just validate that I signed</a>
    </div>""")
    else:
        # Control: vertical layout with "or" separator
        text_parts.append("""We would love you to:

✓ Verify your email and sign up for our newsletter and more ways to help:
  {subscribe}

or

Just verify your email (we won't use it to reach out again):
  {validate}""".format(**urls))

        html_parts.append(f"""<p>We would love you to:</p>

    <p>
        <a href="{urls['subscribe']}" class="cta-primary">✓ Verify your email and sign up for our newsletter and more ways to help</a>
    </p>

    <p style="text-align: center; margin: 20px 0;">or</p>

    <p>
        <a href="{urls['validate']}" class="cta-secondary">Just verify your email (we won't use it to reach out again)</a>
    </p>""")

    # === SOCIAL SHARING ===
    share_text = """Share on social media:
📘 Facebook: {share_facebook}
🐦 Twitter/X: {share_twitter}
💬 WhatsApp: {share_whatsapp}
💼 LinkedIn: {share_linkedin}
🔗 Reddit: {share_reddit}""".format(**urls)

    share_html = f"""<div class="social-buttons">
        <p><strong>Share {"this with your networks" if variant == "treatment" else "on social media"}:</strong></p>
        <a href="{urls['share_facebook']}" class="social-button">📘 Facebook</a>
        <a href="{urls['share_twitter']}" class="social-button">🐦 Twitter/X</a>
        <a href="{urls['share_whatsapp']}" class="social-button">💬 WhatsApp</a>
        <a href="{urls['share_linkedin']}" class="social-button">💼 LinkedIn</a>
        <a href="{urls['share_reddit']}" class="social-button">🔗 Reddit</a>
    </div>"""

    text_parts.append(share_text)
    html_parts.append(share_html)

    # === EXPLANATION (treatment only) ===
    if variant == "treatment":
        text_parts.append("About these options: 'Keep me informed' marks you as open to updates about the collage and takes you to our newsletter signup. Validation alone is also valuable - it's a standard petition step that helps us demonstrate legitimacy.")
        html_parts.append('<p class="explanation">About these options: "Keep me informed" marks you as open to updates about the collage and takes you to our newsletter signup. Validation alone is also valuable - it\'s a standard petition step that helps us demonstrate legitimacy.</p>')

    # === COLLAGE IMAGE (treatment only - moved down) ===
    if variant == "treatment":
        text_parts.append(f"Here's the collage:\n{urls['image']}")
        html_parts.append(f'<p><img src="{urls["image"]}" alt="Say No collage featuring your photo" class="collage-image"></p>')

    # === IMPACT MESSAGE (both variants) ===
    text_parts.append("As the petition grows, we'll use it in social and physical media to push politicians to take international regulatory action, and to gain further public attention and support.")
    html_parts.append('<p style="margin-top: 30px;">As the petition grows, we\'ll use it in social and physical media to push politicians to take international regulatory action, and to gain further public attention and support.</p>')

    text_parts.append("Every step you take to help increase the number of photos in the petition increases its impact. Thank you for contributing - by taking action together we can stop the race.")
    html_parts.append("<p>Every step you take to help increase the number of photos in the petition increases its impact. Thank you for contributing - by taking action together we can stop the race.</p>")

    # Signature
    text_parts.append("The PauseAI Team")
    html_parts.append("<p><strong>The PauseAI Team</strong></p>")

    # Footer
    footer_text = "This is the single automated notification we promised when you submitted your photo."
    if is_bootstrap_user:
        footer_text += " (You signed early enough you already got a placeholder email from me too: thanks again, --Anthony.)"

    text_parts.append("---\n" + footer_text)
    html_parts.append(f'<div class="footer">\n        <p>{footer_text}</p>\n    </div>')

    # Assemble final content
    plain_text = "\n\n".join(text_parts)

    # Wrap HTML with template
    html_body = "\n\n    ".join(html_parts)
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
        .cta-buttons {{
            display: flex;
            flex-wrap: wrap;
            margin: 20px 0;
        }}
        .cta-buttons a {{
            flex: 1 1 160px;
            text-align: center;
            padding: 10px 12px;
            margin: 5px;
        }}
        .explanation {{
            font-size: 14px;
            color: #666;
            margin: 20px 0;
            line-height: 1.5;
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
    {html_body}
</body>
</html>"""

    return {
        'subject': subject,
        'plain': plain_text,
        'html': html
    }
