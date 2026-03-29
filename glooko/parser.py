"""Parsers for Glooko API JSON responses into standalone models."""

import logging
from datetime import datetime
from typing import List, Optional, Dict

from .models import BolusEntry, PumpStatistics, DeviceInfo

logger = logging.getLogger(__name__)


def parse_timestamp(value) -> Optional[datetime]:
    """Parse a timestamp from Glooko API data.

    Handles ISO format strings and epoch seconds/milliseconds.

    Args:
        value: Timestamp as string, int (epoch), float, or None.

    Returns:
        datetime or None if unparseable.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        try:
            # Glooko uses epoch seconds in graph data 'x' fields
            if value > 1e12:
                return datetime.fromtimestamp(value / 1000)
            return datetime.fromtimestamp(value)
        except (ValueError, OSError):
            return None

    if isinstance(value, str):
        for fmt in (
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
        ):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(
                value.replace('Z', '+00:00')
            ).replace(tzinfo=None)
        except ValueError:
            pass

    logger.warning(f"Could not parse Glooko timestamp: {value}")
    return None


def parse_bolus_entries(graph_data: Dict) -> List[BolusEntry]:
    """Extract bolus delivery entries from Glooko graph data.

    Args:
        graph_data: Raw JSON from /api/v3/graph/data endpoint.

    Returns:
        List of BolusEntry, most recent last.
    """
    entries = []

    series = graph_data.get('series', graph_data)
    delivered_bolus = series.get('deliveredBolus', [])

    for bolus in delivered_bolus:
        try:
            timestamp = parse_timestamp(
                bolus.get('timestamp') or bolus.get('x')
            )
            if timestamp is None:
                continue

            units = (
                bolus.get('insulinDelivered')
                or bolus.get('y')
                or bolus.get('value')
            )
            if units is None or float(units) <= 0:
                continue

            entry = BolusEntry(
                timestamp=timestamp,
                units=float(units),
                carbs_input=bolus.get('carbsInput'),
                insulin_on_board=bolus.get('insulinOnBoard'),
                blood_glucose_input=bolus.get('bloodGlucoseInput'),
                blood_glucose_source=bolus.get('bloodGlucoseInputSource'),
                correction_units=bolus.get('insulinRecommendationForCorrection'),
                carb_units=bolus.get('insulinRecommendationForCarbs'),
                is_manual=bolus.get('isManual', False),
                device_name=bolus.get('deviceName'),
            )
            entries.append(entry)
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping malformed bolus entry: {e}")
            continue

    return entries


def parse_iob_from_bolus(
    graph_data: Dict, max_age_minutes: float = 30
) -> Optional[float]:
    """Extract the most recent IOB value from bolus data.

    The Omnipod 5 records `insulinOnBoard` at the time of each bolus.
    This value is only useful if the bolus is recent.

    Args:
        graph_data: Raw JSON from /api/v3/graph/data endpoint.
        max_age_minutes: Ignore IOB if the bolus is older than this.

    Returns:
        IOB in units, or None if no recent data available.
    """
    series = graph_data.get('series', graph_data)
    delivered_bolus = series.get('deliveredBolus', [])

    if not delivered_bolus:
        return None

    last_bolus = delivered_bolus[-1]
    bolus_time = parse_timestamp(
        last_bolus.get('timestamp') or last_bolus.get('x')
    )

    if bolus_time is None:
        return None

    age_minutes = (datetime.now() - bolus_time).total_seconds() / 60
    if age_minutes > max_age_minutes:
        logger.debug(
            f"Skipping stale Glooko IOB (bolus was {age_minutes:.0f} min ago)"
        )
        return None

    raw_iob = last_bolus.get('insulinOnBoard')
    if raw_iob is not None:
        return float(raw_iob)

    return None


def parse_pump_mode(statistics: Dict) -> Optional[PumpStatistics]:
    """Extract pump mode and statistics from Glooko statistics response.

    Handles Omnipod 5 flat keys (op5PumpMode*) and fallback nested formats.

    Args:
        statistics: Raw JSON from /api/v3/graph/statistics/overall endpoint.

    Returns:
        PumpStatistics or None if no pump mode data found.
    """
    # Omnipod 5 specific flat keys
    auto_pct = statistics.get('op5PumpModeAutomaticPercentage')
    manual_pct = statistics.get('op5PumpModeManualPercentage')
    limited_pct = statistics.get('op5PumpModeLimitedPercentage')
    hypo_pct = statistics.get('op5PumpModeHypoProtectPercentage')

    if auto_pct is not None or manual_pct is not None:
        auto_pct = auto_pct or 0
        manual_pct = manual_pct or 0
        limited_pct = limited_pct or 0
        hypo_pct = hypo_pct or 0

        if auto_pct >= manual_pct and auto_pct >= limited_pct:
            mode = 'auto'
        elif manual_pct >= limited_pct:
            mode = 'manual'
        else:
            mode = 'limited'

        return PumpStatistics(
            mode=mode,
            auto_percentage=auto_pct,
            manual_percentage=manual_pct,
            limited_percentage=limited_pct,
            hypo_protect_percentage=hypo_pct,
            total_insulin_per_day=statistics.get('totalInsulinPerDay'),
            basal_percentage=statistics.get('basalPercentage'),
            bolus_percentage=statistics.get('bolusPercentage'),
            average_bg=statistics.get('averageBg'),
            in_range_percentage=statistics.get('inRangePercentage'),
            carbs_per_day=statistics.get('carbsPerDay'),
        )

    # Fallback: nested pumpModes dict
    pump_modes = statistics.get('pumpModes') or statistics.get('pump_modes')
    if not pump_modes:
        return None

    if isinstance(pump_modes, dict):
        auto_pct = pump_modes.get('auto', 0) or pump_modes.get('automated', 0)
        manual_pct = pump_modes.get('manual', 0)
        limited_pct = pump_modes.get('limited', 0)

        if auto_pct >= manual_pct and auto_pct >= limited_pct:
            mode = 'auto'
        elif manual_pct >= limited_pct:
            mode = 'manual'
        else:
            mode = 'limited'

        return PumpStatistics(
            mode=mode,
            auto_percentage=auto_pct,
            manual_percentage=manual_pct,
            limited_percentage=limited_pct,
        )

    return None


def parse_devices(device_data: Dict) -> List[DeviceInfo]:
    """Extract device information from Glooko device settings response.

    Args:
        device_data: Raw JSON from /api/v3/devices_and_settings endpoint.

    Returns:
        List of DeviceInfo.
    """
    devices = []
    for dev in device_data.get('devices', []):
        last_sync = parse_timestamp(dev.get('lastSyncTimestamp'))
        devices.append(DeviceInfo(
            name=dev.get('displayName') or dev.get('shortDisplayName', 'Unknown'),
            brand=dev.get('brand'),
            model=dev.get('model'),
            serial_number=dev.get('serialNumber'),
            device_type=dev.get('type'),
            last_sync=last_sync,
            properties=dev.get('properties', {}),
        ))
    return devices
