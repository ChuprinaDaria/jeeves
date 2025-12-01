"""
Email Service for AI Agent
Handles email operations: sending, receiving, searching, analyzing
"""
import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service for email operations via SMTP/IMAP"""
    
    def __init__(self, client):
        """
        Initialize email service for a client
        
        Args:
            client: Client model instance with SMTP configuration
        """
        self.client = client
        self.smtp_host = client.email_smtp_host
        self.smtp_port = client.email_smtp_port
        self.smtp_use_tls = client.email_smtp_use_tls
        self.smtp_username = client.email_smtp_username
        self.smtp_password = client.email_smtp_password
        self.from_address = client.email_from_address or client.email_smtp_username
        self.from_name = client.email_from_name or client.company_name or "AI Assistant"
        
        # IMAP settings (using same credentials, common providers support IMAP)
        self.imap_host = self._get_imap_host()
        self.imap_port = 993  # Standard IMAP SSL port
    
    def _get_imap_host(self) -> Optional[str]:
        """Get IMAP host based on SMTP host"""
        if not self.smtp_host:
            return None
        
        # Map common SMTP hosts to IMAP hosts
        host_mapping = {
            'smtp.gmail.com': 'imap.gmail.com',
            'smtp-mail.outlook.com': 'outlook.office365.com',
            'smtp-mail.outlook.com': 'imap-mail.outlook.com',
            'smtp.mail.yahoo.com': 'imap.mail.yahoo.com',
            'smtp.office365.com': 'outlook.office365.com',
        }
        
        # Try direct mapping
        if self.smtp_host in host_mapping:
            return host_mapping[self.smtp_host]
        
        # Try replacing smtp with imap
        if 'smtp' in self.smtp_host:
            return self.smtp_host.replace('smtp', 'imap')
        
        return None
    
    def send_email(
        self,
        to_address: str,
        subject: str,
        body: str,
        is_html: bool = False,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> Dict[str, any]:
        """
        Send an email
        
        Args:
            to_address: Recipient email address
            subject: Email subject
            body: Email body (text or HTML)
            is_html: Whether body is HTML
            cc: CC recipients (optional)
            bcc: BCC recipients (optional)
        
        Returns:
            Dict with success status and message
        """
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_address}>"
            msg['To'] = to_address
            msg['Subject'] = subject
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            
            # Add body
            if is_html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
            
            # Connect to SMTP server
            if self.smtp_use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
            
            server.login(self.smtp_username, self.smtp_password)
            
            # Prepare recipients
            recipients = [to_address]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)
            
            # Send email
            server.sendmail(self.from_address, recipients, msg.as_string())
            server.quit()
            
            return {
                'success': True,
                'message': f'Email sent successfully to {to_address}',
                'to': to_address,
                'subject': subject
            }
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to send email: {str(e)}'
            }
    
    def get_recent_emails(
        self,
        limit: int = 10,
        folder: str = 'INBOX',
        days_back: int = 7
    ) -> List[Dict[str, any]]:
        """
        Get recent emails from inbox
        
        Args:
            limit: Maximum number of emails to retrieve
            folder: IMAP folder (default: INBOX)
            days_back: Number of days to look back
        
        Returns:
            List of email dictionaries
        """
        if not self.imap_host:
            return []
        
        try:
            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            mail.login(self.smtp_username, self.smtp_password)
            mail.select(folder)
            
            # Search for recent emails
            date_since = (datetime.now() - timedelta(days=days_back)).strftime('%d-%b-%Y')
            status, messages = mail.search(None, f'SINCE {date_since}')
            
            if status != 'OK':
                mail.close()
                mail.logout()
                return []
            
            email_ids = messages[0].split()
            
            # Get most recent emails (reverse order)
            emails = []
            for email_id in email_ids[-limit:][::-1]:
                try:
                    status, msg_data = mail.fetch(email_id, '(RFC822)')
                    if status != 'OK':
                        continue
                    
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    # Parse email
                    email_dict = self._parse_email(email_message)
                    emails.append(email_dict)
                except Exception as e:
                    logger.warning(f"Failed to parse email {email_id}: {e}")
                    continue
            
            mail.close()
            mail.logout()
            
            return emails
        except Exception as e:
            logger.error(f"Failed to get recent emails: {e}")
            return []
    
    def search_emails(
        self,
        from_address: Optional[str] = None,
        subject: Optional[str] = None,
        days_back: int = 30,
        limit: int = 20
    ) -> List[Dict[str, any]]:
        """
        Search emails by criteria
        
        Args:
            from_address: Search by sender email
            subject: Search by subject (partial match)
            days_back: Number of days to look back
            limit: Maximum number of results
        
        Returns:
            List of matching emails
        """
        if not self.imap_host:
            return []
        
        try:
            mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            mail.login(self.smtp_username, self.smtp_password)
            mail.select('INBOX')
            
            # Build search criteria
            date_since = (datetime.now() - timedelta(days=days_back)).strftime('%d-%b-%Y')
            search_criteria = [f'SINCE {date_since}']
            
            if from_address:
                search_criteria.append(f'FROM "{from_address}"')
            
            if subject:
                search_criteria.append(f'SUBJECT "{subject}"')
            
            status, messages = mail.search(None, ' '.join(search_criteria))
            
            if status != 'OK':
                mail.close()
                mail.logout()
                return []
            
            email_ids = messages[0].split()
            
            # Get emails
            emails = []
            for email_id in email_ids[-limit:][::-1]:
                try:
                    status, msg_data = mail.fetch(email_id, '(RFC822)')
                    if status != 'OK':
                        continue
                    
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    email_dict = self._parse_email(email_message)
                    
                    # Additional filtering for subject if needed
                    if subject and subject.lower() not in email_dict.get('subject', '').lower():
                        continue
                    
                    emails.append(email_dict)
                except Exception as e:
                    logger.warning(f"Failed to parse email {email_id}: {e}")
                    continue
            
            mail.close()
            mail.logout()
            
            return emails
        except Exception as e:
            logger.error(f"Failed to search emails: {e}")
            return []
    
    def analyze_recent_emails(self, days_back: int = 7) -> Dict[str, any]:
        """
        Analyze recent emails and provide summary
        
        Args:
            days_back: Number of days to analyze
        
        Returns:
            Analysis summary dictionary
        """
        emails = self.get_recent_emails(limit=50, days_back=days_back)
        
        if not emails:
            return {
                'total_emails': 0,
                'message': 'No emails found in the specified period'
            }
        
        # Analyze emails
        senders = {}
        subjects = []
        unread_count = 0
        
        for email_dict in emails:
            sender = email_dict.get('from', '')
            if sender:
                senders[sender] = senders.get(sender, 0) + 1
            
            subjects.append(email_dict.get('subject', ''))
            
            if not email_dict.get('read', True):
                unread_count += 1
        
        # Get top senders
        top_senders = sorted(senders.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'total_emails': len(emails),
            'unread_count': unread_count,
            'date_range': f'Last {days_back} days',
            'top_senders': [{'email': email, 'count': count} for email, count in top_senders],
            'recent_subjects': subjects[:10],
            'summary': f"Found {len(emails)} emails in the last {days_back} days. "
                       f"{unread_count} unread. Top sender: {top_senders[0][0] if top_senders else 'N/A'}"
        }
    
    def _parse_email(self, email_message) -> Dict[str, any]:
        """Parse email message into dictionary"""
        # Decode subject
        subject = email_message['Subject']
        if subject:
            decoded_subject = decode_header(subject)[0]
            if decoded_subject[1]:
                subject = decoded_subject[0].decode(decoded_subject[1])
            else:
                subject = decoded_subject[0] if isinstance(decoded_subject[0], str) else decoded_subject[0].decode()
        else:
            subject = '(No Subject)'
        
        # Decode from
        from_header = email_message['From']
        if from_header:
            decoded_from = decode_header(from_header)[0]
            if decoded_from[1]:
                from_address = decoded_from[0].decode(decoded_from[1])
            else:
                from_address = decoded_from[0] if isinstance(decoded_from[0], str) else decoded_from[0].decode()
        else:
            from_address = 'Unknown'
        
        # Extract email address from from_header
        import re
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', from_address)
        from_email = email_match.group(0) if email_match else from_address
        
        # Get date
        date_str = email_message['Date']
        date_obj = None
        if date_str:
            try:
                from email.utils import parsedate_to_datetime
                date_obj = parsedate_to_datetime(date_str)
            except:
                pass
        
        # Get body
        body = ''
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    try:
                        body = part.get_payload(decode=True).decode()
                        break
                    except:
                        pass
                elif content_type == 'text/html' and not body:
                    try:
                        body = part.get_payload(decode=True).decode()
                    except:
                        pass
        else:
            try:
                body = email_message.get_payload(decode=True).decode()
            except:
                pass
        
        return {
            'subject': subject,
            'from': from_email,
            'from_name': from_address,
            'to': email_message.get('To', ''),
            'date': date_obj.isoformat() if date_obj else date_str,
            'body': body[:500] + '...' if len(body) > 500 else body,  # Truncate long bodies
            'body_full': body,
            'read': True,  # Default, could be enhanced with IMAP flags
        }

