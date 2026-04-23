from html import escape
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import EmailMultiAlternatives


PRIMARY_THEME_FALLBACK = "#F57C20"



def _brand_primary() -> str:
    return PRIMARY_THEME_FALLBACK


def _support_email() -> str:
    return "support@door2door.com"


def _from_email() -> str:
    return getattr(settings, "EMAIL_HOST_USER", "")


def _frontend_base_url() -> str:
    configured = str(getattr(settings, "FRONTEND_URL", "http://localhost:5173")).strip()
    if not configured:
        return "http://localhost:5173"
    return configured.rstrip("/")


def _frontend_url(path: str, query: dict | None = None) -> str:
    base = _frontend_base_url()
    normalized_path = "/" + path.lstrip("/")
    url = f"{base}{normalized_path}"
    if query:
        return f"{url}?{urlencode(query)}"
    return url


def _render_email_shell(*, title: str, subtitle: str, body_html: str, cta_label: str | None = None, cta_url: str | None = None) -> str:
    primary = escape(_brand_primary())
    support = escape(_support_email())

    cta_html = ""
    if cta_label and cta_url:
        cta_html = (
            '<div style="text-align:center;margin:30px 0 28px 0;">'
            f'<a href="{escape(cta_url)}" '
            'style="display:inline-block;padding:12px 24px;border-radius:8px;'
            f'background:{primary};color:#ffffff;text-decoration:none;font-weight:600;">'
            f"{escape(cta_label)}</a>"
            "</div>"
        )

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{escape(title)}</title>
</head>
<body style="margin:0;padding:24px;background:#f7f8fa;font-family:Arial,Helvetica,sans-serif;color:#1f2937;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;overflow:hidden;">
    <tr>
      <td style="background:{primary};padding:24px 24px 18px 24px;">
        <p style="margin:0;color:#fff7ed;font-size:12px;letter-spacing:.08em;text-transform:uppercase;">Door2Door</p>
        <h1 style="margin:8px 0 0 0;color:#ffffff;font-size:24px;line-height:1.3;">{escape(title)}</h1>
        <p style="margin:8px 0 0 0;color:#fff7ed;font-size:14px;line-height:1.5;">{escape(subtitle)}</p>
      </td>
    </tr>
    <tr>
            <td style="padding:26px 24px 8px 24px;">{body_html}{cta_html}</td>
    </tr>
    <tr>
      <td style="border-top:1px solid #f1f5f9;padding:16px 24px 22px 24px;color:#6b7280;font-size:12px;line-height:1.6;">
        <p style="margin:0;">Need help? Contact <a href="mailto:{support}" style="color:{primary};text-decoration:none;">{support}</a>.</p>
                <p style="margin:6px 0 0 0;">This is an automated message from Door2Door.</p>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def _send_email(subject: str, to: list[str], plain_message: str, html_message: str) -> bool:
    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=_from_email(),
            to=to,
        )
        email.attach_alternative(html_message, "text/html")
        email.send(fail_silently=False)
        return True
    except Exception as exc:
        print(f"Error sending email: {str(exc)}")
        return False


def send_provider_approval_email(courier_provider, admin_email, admin_password):
    """
    Send approval email to courier provider with admin credentials.
    """
    company_name = courier_provider.name
    login_url = _frontend_url("/courier/login")

    subject = f"Your {company_name} registration has been approved"

    body_html = f"""
<p style="margin:0 0 14px 0;">Dear {escape(company_name)} Team,</p>
<p style="margin:0 0 14px 0;">Your courier provider registration has been approved. You can now access your dashboard and start operations.</p>
<div style="border:1px solid #fed7aa;background:#fff7ed;border-radius:10px;padding:14px 16px;margin:18px 0;">
  <p style="margin:0 0 8px 0;font-weight:700;color:#9a3412;">Admin Login Credentials</p>
  <p style="margin:0 0 6px 0;"><strong>Email:</strong> {escape(admin_email)}</p>
  <p style="margin:0;"><strong>Temporary Password:</strong> {escape(admin_password)}</p>
</div>
<div style="border:1px solid #fed7aa;background:#fff7ed;border-radius:10px;padding:12px 14px;margin:16px 0 8px 0;">
    <p style="margin:0;font-size:14px;color:#9a3412;"><strong>Security reminder:</strong> Change this password immediately after first login and do not share credentials.</p>
</div>
"""

    plain_message = (
        f"Your {company_name} registration has been approved.\n\n"
        f"Admin email: {admin_email}\n"
        f"Temporary password: {admin_password}\n\n"
        "Please change the temporary password after first login.\n"
        f"Login: {login_url}\n"
    )

    html_message = _render_email_shell(
        title="Registration Approved",
        subtitle="Your courier dashboard is now ready.",
        body_html=body_html,
        cta_label="Open Courier Login",
        cta_url=login_url,
    )

    return _send_email(subject, [courier_provider.company_email], plain_message, html_message)


def send_provider_rejection_email(courier_provider, rejection_reason):
    """
    Send rejection email to courier provider with reason.
    """
    company_name = courier_provider.name
    support_email = _support_email()
    support_mailto = f"mailto:{support_email}"

    subject = f"Update on {company_name} registration"

    body_html = f"""
<p style="margin:0 0 14px 0;">Dear {escape(company_name)} Team,</p>
<p style="margin:0 0 14px 0;">Thank you for applying to Door2Door. After review, we are unable to approve your registration at this time.</p>
<div style="border:1px solid #fed7aa;background:#fff7ed;border-radius:10px;padding:14px 16px;margin:18px 0;">
    <p style="margin:0 0 6px 0;font-weight:700;color:#9a3412;">Reason</p>
  <p style="margin:0;">{escape(rejection_reason)}</p>
</div>
<p style="margin:0 0 12px 0;">You may address the issues and reapply. If anything is unclear, contact support.</p>
"""

    plain_message = (
        f"Update on {company_name} registration\n\n"
        "We are unable to approve the registration at this time.\n\n"
        f"Reason: {rejection_reason}\n\n"
        f"Contact support: {support_email}\n"
    )

    html_message = _render_email_shell(
        title="Registration Status Update",
        subtitle="Your application needs revisions before approval.",
        body_html=body_html,
        cta_label="Contact Support",
        cta_url=support_mailto,
    )

    return _send_email(subject, [courier_provider.company_email], plain_message, html_message)


def send_otp_email_service(email, otp_code):
    """
    Send OTP email for password reset or verification.
    """
    subject = "Your Door2Door verification code"

    body_html = f"""
<p style="margin:0 0 14px 0;">Use the code below to complete your verification.</p>
<div style="border:1px dashed #fdba74;background:#fff7ed;border-radius:10px;padding:18px 14px;text-align:center;margin:18px 0;">
  <p style="margin:0 0 8px 0;font-size:13px;color:#9a3412;">Verification Code</p>
  <p style="margin:0;font-size:34px;letter-spacing:8px;font-weight:700;color:#9a3412;font-family:monospace;">{escape(str(otp_code))}</p>
</div>
<div style="border:1px solid #fed7aa;background:#fff7ed;border-radius:10px;padding:12px 14px;margin:16px 0 8px 0;">
    <p style="margin:0;font-size:14px;color:#9a3412;"><strong>Security reminder:</strong> This code expires in 10 minutes. Never share your OTP.</p>
</div>
"""

    plain_message = (
        "Door2Door verification code\n\n"
        f"Your OTP is: {otp_code}\n"
        "This code expires in 10 minutes.\n"
    )

    html_message = _render_email_shell(
        title="Verification Code",
        subtitle="Use this one-time code to continue securely.",
        body_html=body_html,
    )

    return _send_email(subject, [email], plain_message, html_message)


def send_provider_invitation_email(invitation):
    """
    Send invitation email to rider or staff with registration link.
    """
    role = invitation.role
    if role == "rider":
        role_title = "Rider"
        role_display = "delivery rider"
        registration_path = getattr(
            settings, "FRONTEND_RIDER_REGISTRATION_PATH", "/rider/register"
        )
    elif role == "admin":
        role_title = "Courier Admin"
        role_display = "courier admin"
        registration_path = getattr(
            settings, "FRONTEND_STAFF_REGISTRATION_PATH", "/staff/register"
        )
    else:
        role_title = "Operations Staff"
        role_display = "operations staff"
        registration_path = getattr(
            settings, "FRONTEND_STAFF_REGISTRATION_PATH", "/staff/register"
        )

    registration_url = _frontend_url(
        registration_path,
        query={"token": invitation.invitation_token},
    )

    company_name = invitation.courier_provider.name
    expires_at = invitation.expires_at.strftime("%B %d, %Y at %I:%M %p")

    subject = f"Invitation to join {company_name} as {role_title}"

    body_html = f"""
<p style="margin:0 0 14px 0;">Hello,</p>
<p style="margin:0 0 14px 0;">You have been invited to join <strong>{escape(company_name)}</strong> as {escape(role_display)} on Door2Door.</p>
<div style="border:1px solid #fed7aa;background:#fff7ed;border-radius:10px;padding:14px 16px;margin:18px 0;">
  <p style="margin:0 0 6px 0;"><strong>Invited email:</strong> {escape(invitation.email)}</p>
  <p style="margin:0 0 6px 0;"><strong>Location:</strong> {escape(invitation.courier_provider.city)}, {escape(invitation.courier_provider.state)}</p>
  <p style="margin:0;"><strong>Expires:</strong> {escape(expires_at)}</p>
</div>
<div style="border:1px solid #fed7aa;background:#fff7ed;border-radius:10px;padding:12px 14px;margin:16px 0 8px 0;">
    <p style="margin:0;font-size:14px;color:#9a3412;"><strong>Important:</strong> This invitation link is unique to you and should not be shared.</p>
</div>
"""

    plain_message = (
        f"Invitation to join {company_name} as {role_title}\n\n"
        f"You were invited as {role_display}.\n"
        f"Expires: {expires_at}\n"
        f"Register: {registration_url}\n"
    )

    html_message = _render_email_shell(
        title="You are invited",
        subtitle="Complete your registration to join the courier team.",
        body_html=body_html,
        cta_label="Register Now",
        cta_url=registration_url,
    )

    return _send_email(subject, [invitation.email], plain_message, html_message)
