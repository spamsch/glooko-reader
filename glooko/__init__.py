"""Glooko API client library.

Unofficial Python client for the Glooko diabetes data platform.
Supports authentication, insulin pump data (Omnipod 5), CGM data,
and statistics retrieval.

Usage:
    from glooko import GlookoClient

    client = GlookoClient(email="user@example.com", password="pass")
    data = client.get_graph_data(
        start_date="2026-03-29T00:00:00.000Z",
        end_date="2026-03-29T23:59:59.999Z",
    )

    boluses = parse_bolus_entries(data)
    pump_mode = parse_pump_mode(statistics)
"""

from .client import GlookoClient, GlookoAuthError
from .models import BolusEntry, PumpStatistics, DeviceInfo
from .parser import (
    parse_bolus_entries,
    parse_iob_from_bolus,
    parse_pump_mode,
    parse_devices,
    parse_timestamp,
)
from .mock import MockGlookoClient

__all__ = [
    'GlookoClient',
    'GlookoAuthError',
    'MockGlookoClient',
    'BolusEntry',
    'PumpStatistics',
    'DeviceInfo',
    'parse_bolus_entries',
    'parse_iob_from_bolus',
    'parse_pump_mode',
    'parse_devices',
    'parse_timestamp',
]
