"""
CLI healthcheck module

Usage:
    python -m alpha_sniper.healthcheck

Returns:
    Exit code 0 if healthy
    Exit code 1 if unhealthy
    Exit code 2 if unknown/error
"""
from alpha_sniper.health import check_health_from_cli

if __name__ == "__main__":
    exit(check_health_from_cli())
