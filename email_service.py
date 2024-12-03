import re
import smtplib
import dns.resolver
import logging

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    filename="email_service.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Syntax Check
def is_syntax_valid(email):
    """
    Validate Email Syntax Using Regex.
    """
    regex = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return re.match(regex, email) is not None

# Domain Check
def is_domain_valid(email):
    try:
        domain = email.split('@')[1]
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5
        answers = resolver.resolve(domain, 'MX')
        logging.info("Domain %s Has MX Records: %s", domain, [r.exchange.to_text() for r in answers])
        return True
    except dns.resolver.NoAnswer:
        logging.warning("Domain %s Does Not Have MX Records", domain)
        return False
    except dns.resolver.NXDOMAIN:
        logging.warning("Domain %s Does Not Exist", domain)
        return False
    except Exception as e:
        logging.error("Error While Checking Domain %s: %s", domain, str(e))
        return False

# SMTP Server Check
def check_email_server(email):
    try:
        domain = email.split('@')[1]
        mx_records = dns.resolver.resolve(domain, 'MX')
        mx_record = mx_records[0].exchange.to_text()
        logging.info("Found MX Record For Domain %s: %s", domain, mx_record)

        with smtplib.SMTP(mx_record) as smtp:
            smtp.set_debuglevel(0)
            smtp.helo()
            smtp.mail("test@example.com")
            code, _ = smtp.rcpt(email)
            success = code == 250
            logging.info("SMTP Server Response For Email %s: %s", email, "Success" if success else "Failed")
            return success
    except Exception as e:
        logging.error("Error While Validating Email Server %s: %s", email, str(e))
        return False

# Full Email Validation
def verify_email(email):
    """
    Perform Full Validation Of Email: Syntax, Domain, SMTP.
    """
    if not is_syntax_valid(email):
        return "syntax"
    if not is_domain_valid(email):
        return "domain"
    if not check_email_server(email):
        return "server"
    return "valid"
