import re
import smtplib
import dns.resolver
import logging
from functools import lru_cache

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    filename="email_service.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

# Syntax Check
def is_syntax_valid(email):
    return EMAIL_REGEX.match(email) is not None

@lru_cache(maxsize=1000)
def is_domain_valid_cached(domain):
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 3
        resolver.lifetime = 3
        answers = resolver.resolve(domain, 'MX')
        logging.info("Domain %s Has MX Records: %s", domain, [r.exchange.to_text() for r in answers])
        return True
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        logging.warning("Domain %s Is Invalid", domain)
        return False
    except Exception as e:
        logging.error("Error While Checking Domain %s: %s", domain, str(e))
        return False

def check_email_server(email):
    try:
        domain = email.split('@')[1]
        if not is_domain_valid_cached(domain):
            return False

        mx_records = dns.resolver.resolve(domain, 'MX')
        mx_record = mx_records[0].exchange.to_text()
        with smtplib.SMTP(mx_record, timeout=5) as smtp:
            smtp.helo()
            smtp.mail("test@example.com")
            code, _ = smtp.rcpt(email)
            return code == 250
    except Exception as e:
        logging.error("Error While Validating Email Server %s: %s", email, str(e))
        return False

def verify_email(email):
    if not is_syntax_valid(email):
        return "syntax"
    if not is_domain_valid_cached(email.split('@')[1]):
        return "domain"
    if not check_email_server(email):
        return "server"
    return "valid"
