"""Standalone data models for Glooko API responses."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict


@dataclass
class BolusEntry:
    """A single insulin bolus delivery from the pump."""
    timestamp: datetime
    units: float
    carbs_input: Optional[float] = None
    insulin_on_board: Optional[float] = None
    blood_glucose_input: Optional[int] = None
    blood_glucose_source: Optional[str] = None
    correction_units: Optional[float] = None
    carb_units: Optional[float] = None
    is_manual: bool = False
    device_name: Optional[str] = None


@dataclass
class PumpStatistics:
    """Pump mode and insulin statistics from Glooko."""
    mode: Optional[str] = None  # 'auto', 'manual', 'limited'
    auto_percentage: float = 0.0
    manual_percentage: float = 0.0
    limited_percentage: float = 0.0
    hypo_protect_percentage: float = 0.0
    total_insulin_per_day: Optional[float] = None
    basal_percentage: Optional[float] = None
    bolus_percentage: Optional[float] = None
    average_bg: Optional[float] = None
    in_range_percentage: Optional[float] = None
    carbs_per_day: Optional[float] = None


@dataclass
class DeviceInfo:
    """Connected device information."""
    name: str
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    device_type: Optional[str] = None  # 'pump', 'cgm', etc.
    last_sync: Optional[datetime] = None
    properties: Dict = field(default_factory=dict)
