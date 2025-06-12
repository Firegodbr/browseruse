import re
def normalize_canadian_number(phone):
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)

    # Remove leading '1' if it's an 11-digit number
    if digits.startswith('1') and len(digits) == 11:
        digits = digits[1:]

    # Ensure it's now exactly 10 digits
    if len(digits) != 10:
        raise ValueError("Invalid Canadian phone number")

    return digits