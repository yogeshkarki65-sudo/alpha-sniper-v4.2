#!/usr/bin/env python3
"""
Print all effective ALPHA_ settings with secrets masked.
Usage: python scripts/print_settings.py | tee /tmp/alpha_settings.json
"""

import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from alpha_sniper.config.settings import Settings

def mask_secret(key: str, value: any) -> any:
    """Mask sensitive fields."""
    sensitive_fields = {
        'API_KEY', 'API_SECRET', 'TELEGRAM_BOT_TOKEN',
        'PASSWORD', 'SECRET', 'TOKEN', 'KEY'
    }

    # Check if field name contains sensitive keywords
    if any(s in key.upper() for s in sensitive_fields):
        if isinstance(value, str) and len(value) > 0:
            # Show first 4 chars + masked
            if len(value) <= 4:
                return "***"
            return value[:4] + "***" + ("*" * (len(value) - 4))
        return "***MASKED***"

    return value

def main():
    try:
        # Load settings
        settings = Settings()

        # Convert to dict
        settings_dict = {}
        for field_name in settings.model_fields.keys():
            value = getattr(settings, field_name)
            masked_value = mask_secret(field_name, value)
            settings_dict[field_name] = masked_value

        # Output as JSON
        output = {
            "status": "success",
            "timestamp": __import__('time').strftime("%Y-%m-%d %H:%M:%S UTC", __import__('time').gmtime()),
            "settings": settings_dict
        }

        print(json.dumps(output, indent=2, default=str))

    except Exception as e:
        output = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }
        print(json.dumps(output, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    main()
