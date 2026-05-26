def run(query: str) -> dict:
    """
    Legal: phone metadata only via phonenumbers library.
    No real-time location. No HLR lookup. No carrier tracking.
    Returns: carrier, region, line type, validity
    """
    try:
        import phonenumbers
        from phonenumbers import geocoder, carrier, number_type, PhoneNumberType

        num = phonenumbers.parse(query)
        is_valid = phonenumbers.is_valid_number(num)

        if not is_valid:
            return {
                "valid": False,
                "error": "Invalid phone number.",
                "legal_note": "Metadata only. No location tracking possible here."
            }

        ntype = number_type(num)
        type_map = {
            PhoneNumberType.MOBILE: "Mobile",
            PhoneNumberType.FIXED_LINE: "Fixed Line",
            PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed/Mobile",
            PhoneNumberType.TOLL_FREE: "Toll Free",
            PhoneNumberType.VOIP: "VoIP",
            PhoneNumberType.UNKNOWN: "Unknown",
        }

        return {
            "valid": True,
            "country_code": num.country_code,
            "national_number": str(num.national_number),
            "region": geocoder.description_for_number(num, "en"),
            "carrier": carrier.name_for_number(num, "en") or "Unknown",
            "line_type": type_map.get(ntype, "Unknown"),
            "international_format": phonenumbers.format_number(
                num, phonenumbers.PhoneNumberFormat.INTERNATIONAL
            ),
            "source": "phonenumbers library (public metadata)",
            "legal_note": (
                "Carrier and region only. "
                "Real-time location is impossible from this data. "
                "Only telecom operators and law enforcement can track live location."
            ),
        }
    except Exception as e:
        return {"error": str(e), "valid": False}
