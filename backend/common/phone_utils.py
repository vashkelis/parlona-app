"""Phone number normalization utilities."""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def normalize_phone_e164(raw_phone: str, default_country: str = "US") -> Optional[str]:
    """
    Normalize a phone number to E.164 format.
    
    E.164 format: +[country code][subscriber number]
    Example: +14155552671
    
    Steps:
    1. Trim whitespace
    2. Replace ++ with +
    3. Remove spaces, dashes, parentheses, dots
    4. Handle leading zeros and country codes
    5. Add + prefix if missing
    
    Args:
        raw_phone: Raw phone number string
        default_country: Default country code (default: US = +1)
        
    Returns:
        Normalized E.164 phone number or None if invalid
    """
    if not raw_phone:
        return None
    
    # Step 1: Trim whitespace
    phone = raw_phone.strip()
    
    if not phone:
        return None
    
    # Step 2: Replace ++ with +
    phone = phone.replace("++", "+")
    
    # Step 3: Remove spaces, dashes, parentheses, dots
    phone = re.sub(r'[\s\-\(\)\.]', '', phone)
    
    # Extract digits and leading +
    if phone.startswith('+'):
        # Keep the + and extract digits
        digits = ''.join(c for c in phone[1:] if c.isdigit())
        phone = '+' + digits
    else:
        # Extract only digits
        digits = ''.join(c for c in phone if c.isdigit())
        phone = digits
    
    if not phone or (phone.startswith('+') and len(phone) == 1):
        return None
    
    # Step 4-5: Handle country codes
    if phone.startswith('+'):
        # Already has + prefix, validate length
        if len(phone) < 8:  # Minimum E.164 length (country + area + number)
            logger.warning("Phone number too short: %s", raw_phone)
            return None
        if len(phone) > 16:  # Maximum E.164 length
            logger.warning("Phone number too long: %s", raw_phone)
            return None
        return phone
    
    # No + prefix - need to add country code
    if default_country == "US":
        # US phone numbers
        if len(phone) == 10:
            # Standard US format: 4155552671 -> +14155552671
            return f"+1{phone}"
        elif len(phone) == 11 and phone.startswith('1'):
            # Already has 1 prefix: 14155552671 -> +14155552671
            return f"+{phone}"
        elif len(phone) == 11 and not phone.startswith('1'):
            # Foreign number without +, assume it's complete
            return f"+{phone}"
        elif len(phone) > 11:
            # Likely already has country code
            return f"+{phone}"
        else:
            logger.warning("Invalid US phone number length: %s", raw_phone)
            return None
    else:
        # For other countries, assume the number is complete
        # and just add the + prefix
        if 8 <= len(phone) <= 15:
            return f"+{phone}"
        else:
            logger.warning("Invalid phone number length: %s", raw_phone)
            return None


def normalize_email(raw_email: str) -> Optional[str]:
    """
    Normalize an email address.
    
    Steps:
    1. Trim whitespace
    2. Convert to lowercase
    3. Basic validation
    
    Args:
        raw_email: Raw email string
        
    Returns:
        Normalized email or None if invalid
    """
    if not raw_email:
        return None
    
    email = raw_email.strip().lower()
    
    # Basic email validation
    if '@' not in email or '.' not in email.split('@')[-1]:
        logger.warning("Invalid email format: %s", raw_email)
        return None
    
    return email
