import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from jinja2 import Environment, FileSystemLoader
import logging

class EmailHelper:
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.username = os.getenv("SMTP_USERNAME")
        self.password = os.getenv("SMTP_PASSWORD")
        self.sender_email = os.getenv("EMAIL_SENDER_ADDRESS", self.username)
        
        # Setup Jinja2 environment
        template_dir = os.path.dirname(os.path.abspath(__file__))
        self.env = Environment(loader=FileSystemLoader(template_dir))
        
    def send_email(self, recipient_email, subject, template_name, template_data=None, attachments=None, cc_emails=None, **kwargs):
        """
        Sends an email using SMTP.
        Supports both template_data dict and direct keyword arguments.
        """
        if not all([self.username, self.password]):
            logging.error("SMTP credentials not configured.")
            return False

        try:
            # 1. Prepare data for template
            render_data = template_data.copy() if (template_data and isinstance(template_data, dict)) else {}
            render_data.update(kwargs) # Add any direct keyword arguments
            
            # 2. Render HTML body
            template = self.env.get_template(template_name)
            html_content = template.render(**render_data)

            # 3. Create message
            msg = MIMEMultipart()
            # Ensure sender_email fallback
            from_email = self.sender_email or "system@cowhorse.com"
            msg['From'] = from_email
            msg['To'] = recipient_email
            msg['Subject'] = subject
            
            if cc_emails:
                if isinstance(cc_emails, list):
                    msg['Cc'] = ", ".join(cc_emails)
                else:
                    msg['Cc'] = cc_emails
            
            msg.attach(MIMEText(html_content, 'html'))

            # 4. Handle attachments
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
                        part['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                        msg.attach(part)
                    else:
                        logging.warning(f"Attachment not found: {file_path}")

            # 5. Send email
            context = ssl.create_default_context()
            
            if self.smtp_port == 465:
                # SSL/TLS directly (Port 465)
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context, timeout=15) as server:
                    server.login(self.username, self.password)
                    
                    all_recipients = [recipient_email]
                    if cc_emails:
                        if isinstance(cc_emails, list):
                            all_recipients.extend(cc_emails)
                        else:
                            all_recipients.append(cc_emails)
                    
                    server.sendmail(from_email, all_recipients, msg.as_string())
            else:
                # STARTTLS (Port 587)
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15) as server:
                    server.starttls(context=context)
                    server.login(self.username, self.password)
                    
                    all_recipients = [recipient_email]
                    if cc_emails:
                        if isinstance(cc_emails, list):
                            all_recipients.extend(cc_emails)
                        else:
                            all_recipients.append(cc_emails)
                    
                    server.sendmail(from_email, all_recipients, msg.as_string())
            
            logging.info(f"Email sent successfully to {recipient_email}")
            return True

        except Exception as e:
            logging.error(f"Failed to send email: {str(e)}")
            return False

def quick_send(recipient_email=None, subject=None, template_name="email_templates.html", template_data=None, **kwargs):
    """
    Highly flexible helper for email sending. 
    Accepts explicit args or keyword arguments to suit various call sites.
    """
    # 1. Resolve core parameters from keyword args if missing
    r_email = recipient_email or kwargs.pop('recipient_email', None)
    subj = subject or kwargs.pop('subject', 'System Notification')
    t_name = template_name or kwargs.pop('template_name', 'email_templates.html')
    
    attachments = kwargs.pop('attachments', None)
    cc_emails = kwargs.pop('cc_emails', None)

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
        **kwargs
    )
