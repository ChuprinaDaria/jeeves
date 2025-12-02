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
        
        logger.info(f"EmailService initialized for client {client.id}: SMTP={self.smtp_host}, IMAP={self.imap_host}")
    
    def _get_imap_host(self) -> Optional[str]:
        """Get IMAP host based on SMTP host"""
        if not self.smtp_host:
            return None
        
        smtp_host_lower = self.smtp_host.lower()
        
        # Map common SMTP hosts to IMAP hosts
        host_mapping = {
            # Gmail
            'smtp.gmail.com': 'imap.gmail.com',
            'mail.gmail.com': 'imap.gmail.com',
            # Microsoft / Outlook
            'smtp-mail.outlook.com': 'outlook.office365.com',
            'smtp.office365.com': 'outlook.office365.com',
            'smtp.live.com': 'imap-mail.outlook.com',
            'smtp-mail.live.com': 'imap-mail.outlook.com',
            # Yahoo
            'smtp.mail.yahoo.com': 'imap.mail.yahoo.com',
            'smtp.mail.yahoo.co.uk': 'imap.mail.yahoo.co.uk',
            # Zoho
            'smtp.zoho.com': 'imap.zoho.com',
            'smtp.zoho.eu': 'imap.zoho.eu',
            # ProtonMail
            'mail.protonmail.com': '127.0.0.1',  # ProtonMail використовує Bridge
            # iCloud
            'smtp.mail.me.com': 'imap.mail.me.com',
        }
        
        # Try direct mapping
        if smtp_host_lower in host_mapping:
            return host_mapping[smtp_host_lower]
        
        # Special handling for home.pl servers
        # Для home.pl IMAP використовує той самий хост що і SMTP (serwer2555348.home.pl)
        # Порт: 993 (SSL) або 143 (без SSL)
        if 'home.pl' in smtp_host_lower:
            # Для home.pl IMAP хост = SMTP хост (той самий сервер)
            # Приклади:
            # - SMTP: serwer2555348.home.pl -> IMAP: serwer2555348.home.pl
            # - SMTP: smtp.serwer2555348.home.pl -> IMAP: serwer2555348.home.pl (прибираємо smtp. префікс)
            # - SMTP: mail.serwer2555348.home.pl -> IMAP: serwer2555348.home.pl (прибираємо mail. префікс)
            
            # Прибираємо префікси smtp. або mail. якщо є
            if smtp_host_lower.startswith('smtp.'):
                imap_host = smtp_host_lower.replace('smtp.', '')
            elif smtp_host_lower.startswith('mail.'):
                imap_host = smtp_host_lower.replace('mail.', '')
            else:
                # Якщо немає префіксу - використовуємо той самий хост
                imap_host = smtp_host_lower
            
            logger.info(f"Detected home.pl server, using IMAP host: {imap_host} (same as SMTP host)")
            return imap_host
        
        # Try replacing smtp with imap
        if 'smtp' in smtp_host_lower:
            imap_host = smtp_host_lower.replace('smtp', 'imap')
            logger.info(f"Trying IMAP host by replacing smtp: {imap_host}")
            return imap_host
        
        # Try replacing mail with imap
        if 'mail' in smtp_host_lower and 'imap' not in smtp_host_lower:
            imap_host = smtp_host_lower.replace('mail', 'imap')
            logger.info(f"Trying IMAP host by replacing mail: {imap_host}")
            return imap_host
        
        # Last resort: try common patterns
        # For custom domains, try mail.domain.com or imap.domain.com
        if '.' in smtp_host_lower:
            domain_parts = smtp_host_lower.split('.')
            if len(domain_parts) >= 2:
                # Extract domain (e.g., example.com from smtp.example.com)
                domain = '.'.join(domain_parts[-2:])  # Get last 2 parts (domain.tld)
                # Try mail.domain.com
                imap_host = f"mail.{domain}"
                logger.info(f"Trying common IMAP pattern: {imap_host}")
                return imap_host
        
        logger.warning(f"Could not determine IMAP host for SMTP host: {self.smtp_host}")
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
            logger.warning(f"IMAP host not configured for SMTP host: {self.smtp_host}")
            return []
        
        try:
            logger.info(f"Connecting to IMAP server: {self.imap_host}:{self.imap_port}")
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
            error_msg = str(e)
            logger.error(f"Failed to get recent emails from {self.imap_host}: {error_msg}", exc_info=True)
            
            # Якщо помилка DNS - повертаємо порожній список, але збережемо помилку для analyze_recent_emails
            if 'Name or service not known' in error_msg or 'Errno -2' in error_msg:
                logger.warning(f"IMAP host {self.imap_host} is not accessible (DNS error). Please check IMAP configuration.")
            
            # Повертаємо порожній список, але логуємо деталі
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
    
    def analyze_recent_emails(self, days_back: int = 7, language: str = 'en') -> Dict[str, any]:
        """
        Analyze recent emails and provide summary using LLM
        
        Args:
            days_back: Number of days to analyze
            language: User's language for response (en, uk, de, fr, es, it, nl, da, ru)
        
        Returns:
            Analysis summary dictionary
        """
        emails = self.get_recent_emails(limit=50, days_back=days_back)
        
        if not emails:
            # Перевіряємо, чи проблема в IMAP хості
            if not self.imap_host:
                # Для home.pl IMAP хост = SMTP хост
                if 'home.pl' in (self.smtp_host or '').lower():
                    error_msg = f'❌ IMAP host not configured.\n\nSMTP host: {self.smtp_host}\n\nFor home.pl servers, IMAP host should be the same as SMTP host:\n- IMAP host: {self.smtp_host}\n- IMAP port: 993 (SSL) or 143 (without SSL)'
                else:
                    error_msg = f'❌ IMAP host not configured.\n\nSMTP host: {self.smtp_host}\n\nPlease configure IMAP settings for email reading.'
                return {
                    'total_emails': 0,
                    'message': error_msg,
                    'summary': error_msg,
                    'error': 'IMAP host not configured',
                    'smtp_host': self.smtp_host
                }
            else:
                # Можливо, IMAP хост не доступний або неправильний
                error_msg = f'⚠️ No emails found or IMAP connection failed.\n\nIMAP host: {self.imap_host}\nSMTP host: {self.smtp_host}\nPeriod: last {days_back} days\n\nPossible issues:\n- IMAP host is incorrect\n- IMAP server is not accessible\n- No emails in the specified period\n- IMAP credentials are incorrect'
                return {
                    'total_emails': 0,
                    'message': error_msg,
                    'summary': error_msg,
                    'imap_host': self.imap_host,
                    'smtp_host': self.smtp_host,
                    'days_back': days_back
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
        
        # Використовуємо LLM для створення саммарі мовою користувача
        try:
            from MASTER.rag.llm_client import LLMClient
            
            # Підготовка даних для LLM (беремо останні 10 листів з body)
            emails_for_summary = []
            for email_dict in emails[:10]:
                # Обрізаємо body до 500 символів для економії токенів
                body = email_dict.get('body', '')[:500]
                emails_for_summary.append({
                    'date': email_dict.get('date', ''),
                    'from': email_dict.get('from', ''),
                    'subject': email_dict.get('subject', ''),
                    'body': body if body else '(No content)'
                })
            
            # Промпт для LLM
            prompt = f"""Analyze the following {len(emails)} emails from the last {days_back} days and provide a concise summary in {language.upper()} language.

Total emails: {len(emails)}
Unread: {unread_count}
Period: last {days_back} days

Top senders:
{chr(10).join([f'- {email}: {count} emails' for email, count in top_senders[:3]])}

Recent emails (with content):
{chr(10).join([f'{i+1}. [{e["date"][:16]}] From: {e["from"]}, Subject: {e["subject"]}, Content: {e["body"][:200]}...' for i, e in enumerate(emails_for_summary)])}

Please provide a structured summary that includes:
1. Overview (total count, period, unread)
2. Main topics/categories based on email content (not just subjects)
3. Key senders
4. Important information or actions needed

Respond in {language.upper()} language. Be concise but informative."""

            llm_client = LLMClient(self.client)
            llm_response = llm_client.generate(prompt, temperature=0.3, max_tokens=500)
            
            if llm_response:
                summary_text = llm_response.strip()
            else:
                # Fallback до простого саммарі
                raise Exception("LLM response is empty")
        
        except Exception as e:
            logger.warning(f"Failed to generate LLM summary: {e}. Using fallback.")
            # Fallback до простого саммарі українською (original logic)
            summary_parts = [
                f"📧 Знайдено {len(emails)} листів за останні {days_back} днів"
            ]
            
            if unread_count > 0:
                summary_parts.append(f"📬 Непрочитаних: {unread_count}")
            
            if top_senders:
                summary_parts.append(f"\n👤 Топ відправники:")
                for email, count in top_senders[:3]:
                    summary_parts.append(f"  • {email}: {count} листів")
            
            if subjects:
                summary_parts.append(f"\n📋 Останні теми:")
                for i, subject in enumerate(subjects[:5], 1):
                    subject_short = subject[:60] + '...' if len(subject) > 60 else subject
                    summary_parts.append(f"  {i}. {subject_short}")
            
            summary_text = '\n'.join(summary_parts)
        
        return {
            'total_emails': len(emails),
            'unread_count': unread_count,
            'date_range': f'Last {days_back} days',
            'top_senders': [{'email': email, 'count': count} for email, count in top_senders],
            'recent_subjects': subjects[:10],
            'emails': emails[:10],  # Include first 10 emails for context
            'summary': summary_text
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

