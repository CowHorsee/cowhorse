from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


class EmailHelper:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.username = os.getenv("SMTP_USERNAME")
        self.password = os.getenv("SMTP_PASSWORD")
        self.sender_email = os.getenv("EMAIL_SENDER_ADDRESS", self.username)

        template_dir = Path(__file__).resolve().parent
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        template_name: str,
        template_data: dict | None = None,
        attachments: list[str] | None = None,
        cc_emails: list[str] | str | None = None,
        **kwargs,
    ) -> bool:
        if not all([self.username, self.password]):
            logging.error("SMTP credentials not configured.")
            return False

        try:
            # 1. Prepare data for template
            render_data = template_data.copy() if isinstance(template_data, dict) else {}
            render_data.update(kwargs)

            # 2. Render HTML body
            template = self.env.get_template(template_name)
            html_content = template.render(**render_data)

            # 3. Create message
            msg = MIMEMultipart("alternative")
            from_email = self.sender_email or "system@cowhorse.com"
            msg["From"] = from_email
            msg["To"] = recipient_email
            msg["Subject"] = subject

            all_recipients = [recipient_email]
            if cc_emails:
                if isinstance(cc_emails, list):
                    msg["Cc"] = ", ".join(cc_emails)
                    all_recipients.extend(cc_emails)
                else:
                    msg["Cc"] = cc_emails
                    all_recipients.append(cc_emails)

            # Create the plain-text alternative
            text_content = f"This is an automated notification from Team Cow Horse.\n\nSubject: {subject}\n\nPlease view this email in an HTML-compatible client to see the full details and actions."
            
            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            # 4. Handle attachments
            if attachments:
                # Wrap in mixed if attachments exist
                main_msg = MIMEMultipart("mixed")
                main_msg["From"] = msg["From"]
                main_msg["To"] = msg["To"]
                main_msg["Subject"] = msg["Subject"]
                if "Cc" in msg:
                    main_msg["Cc"] = msg["Cc"]
                main_msg.attach(msg)
                msg = main_msg

                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
                        part["Content-Disposition"] = (
                            f'attachment; filename="{os.path.basename(file_path)}"'
                        )
                        msg.attach(part)
                    else:
                        logging.warning(f"Attachment not found: {file_path}")

            context = ssl.create_default_context()
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(
                    self.smtp_server, self.smtp_port, context=context, timeout=15
                ) as server:
                    server.login(self.username, self.password)
                    server.sendmail(from_email, all_recipients, msg.as_string())
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15) as server:
                    server.starttls(context=context)
                    server.login(self.username, self.password)
                    server.sendmail(from_email, all_recipients, msg.as_string())

            logging.info(f"Email sent successfully to {recipient_email}")
            return True
        except Exception as exc:
            logging.error(f"Failed to send email: {str(exc)}")
            return False


def quick_send(
    recipient_email: str | None = None,
    subject: str | None = None,
    template_name: str = "email_templates.html",
    template_data: dict | None = None,
    **kwargs,
) -> bool:
    r_email = recipient_email or kwargs.pop("recipient_email", None)
    subj = subject or kwargs.pop("subject", "System Notification")
    t_name = template_name or kwargs.pop("template_name", "email_templates.html")

    attachments = kwargs.pop("attachments", None)
    cc_emails = kwargs.pop("cc_emails", None)

    if not r_email:
        logging.error("No recipient email provided to quick_send")
        return False

    helper = EmailHelper()
    return helper.send_email(
        recipient_email=r_email,
        subject=subj,
        template_name=t_name,
        template_data=template_data,
        attachments=attachments,
        cc_emails=cc_emails,
        **kwargs,
    )
