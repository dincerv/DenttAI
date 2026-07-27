"""
Secure configuration validation layer.

All environment variables are validated at startup.
Hardcoded defaults are NOT allowed.
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse


class ConfigValidator:
    """Validates all required environment variables."""

    # Required secrets (must be set, no defaults)
    REQUIRED_SECRETS = {
        'JWT_SECRET': ('JWT token signing secret', 64),  # (description, min_length)
        'WHATSAPP_ACCESS_TOKEN': ('Meta WhatsApp API token', 100),
        'OPENAI_API_KEY': ('OpenAI API key', 20),
    }

    # Required URLs (must be valid)
    REQUIRED_URLS = {
        'DATABASE_URL': 'PostgreSQL connection string',
        'CELERY_BROKER_URL': 'Redis/RabbitMQ broker URL',
        'CELERY_BACKEND_URL': 'Celery result backend URL',
    }

    # Optional with secure defaults
    OPTIONAL_CONFIG = {
        'ENVIRONMENT': ('development', ['development', 'staging', 'production']),
        'JWT_ALGORITHM': ('HS256', ['HS256', 'HS512']),
        'JWT_EXPIRATION_HOURS': (24, int),
        'SERVICE_PORT': (8005, int),
        'CORS_ALLOWED_ORIGINS': ('http://localhost:3000', str),
        'LOG_LEVEL': ('INFO', ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']),
    }

    @classmethod
    def validate(cls) -> dict:
        """
        Validate all environment variables at startup.
        Raises RuntimeError if any critical config is missing.
        """
        config = {}
        errors = []

        # 1. Validate required secrets (no defaults allowed)
        for key, (description, min_len) in cls.REQUIRED_SECRETS.items():
            value = os.environ.get(key)

            if not value:
                errors.append(f"🔴 MISSING: {key} - {description}")
            elif len(value) < min_len:
                errors.append(f"🔴 TOO SHORT: {key} must be {min_len}+ chars (got {len(value)})")
            else:
                config[key] = value

        # 2. Validate required URLs
        for key, description in cls.REQUIRED_URLS.items():
            value = os.environ.get(key)

            if not value:
                errors.append(f"🔴 MISSING: {key} - {description}")
            else:
                # Basic URL validation
                try:
                    parsed = urlparse(value)
                    if not parsed.scheme or not parsed.netloc:
                        raise ValueError("Invalid URL format")
                    config[key] = value
                except Exception as e:
                    errors.append(f"🔴 INVALID URL: {key} - {str(e)}")

        # 3. Validate optional config
        for key, (default, allowed) in cls.OPTIONAL_CONFIG.items():
            value = os.environ.get(key, default)

            if isinstance(allowed, list):
                # Enum validation
                if value not in allowed:
                    errors.append(f"🟡 INVALID: {key} must be one of {allowed} (got {value})")
                else:
                    config[key] = value
            elif isinstance(allowed, type):
                # Type casting
                try:
                    config[key] = allowed(value)
                except ValueError:
                    errors.append(f"🟡 INVALID: {key} must be {allowed.__name__} (got {value})")

        # 4. If production
        if config.get('ENVIRONMENT') == 'production':
            if 'localhost' in config.get('DATABASE_URL', ''):
                errors.append("🔴 PRODUCTION: Database cannot be localhost")
            if 'localhost' in config.get('CELERY_BROKER_URL', ''):
                errors.append("🔴 PRODUCTION: Broker cannot be localhost")

        # 5. Print error report if any
        if errors:
            print("\n" + "=" * 70)
            print("❌ CONFIGURATION VALIDATION FAILED")
            print("=" * 70)
            for error in errors:
                print(error)
            print("=" * 70)
            print("\n✅ REQUIRED ENVIRONMENT VARIABLES:")
            print("  Security (no defaults):")
            for key, (desc, _) in cls.REQUIRED_SECRETS.items():
                print(f"    - {key}: {desc}")
            print("\n  URLs:")
            for key, desc in cls.REQUIRED_URLS.items():
                print(f"    - {key}: {desc}")
            print("\n  Optional (defaults available):")
            for key, (default, _) in cls.OPTIONAL_CONFIG.items():
                print(f"    - {key} (default: {default})")
            print("\n")
            sys.exit(1)

        return config


def get_config() -> dict:
    """Get validated configuration."""
    return ConfigValidator.validate()
