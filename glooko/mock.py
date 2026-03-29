"""Mock Glooko client for testing and development."""

from datetime import datetime, timedelta
from typing import Optional, Dict


class MockGlookoClient:
    """Returns realistic Omnipod 5 data without requiring Glooko credentials.

    Scenarios:
        'normal': Typical day with a few boluses and auto-mode.
        'high_basal': High basal delivery with frequent micro-boluses.
        'manual_mode': Pump in manual mode.
        'pod_change': Recent pod change with gap in data.
        'no_data': Simulates Glooko being unreachable.
    """

    def __init__(self, scenario: str = 'normal'):
        self.scenario = scenario
        self.patient_id = 'mock-patient-123'
        self.api_base = 'https://mock.glooko.com'
        self.dashboard_origin = 'https://mock.my.glooko.com'
        self.last_auth_time = datetime.now()

    def ensure_authenticated(self):
        pass

    def get_graph_data(self, start_date: str, end_date: str) -> Optional[Dict]:
        if self.scenario == 'no_data':
            return None

        now = datetime.now()

        if self.scenario == 'normal':
            return {
                'series': {
                    'deliveredBolus': [
                        {
                            'timestamp': (now - timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                            'insulinDelivered': 2.5,
                            'y': 2.5,
                            'insulinOnBoard': 0.8,
                            'carbsInput': 30.0,
                            'bloodGlucoseInput': 165,
                            'bloodGlucoseInputSource': 'CGM',
                            'deviceName': 'Omnipod 5',
                        },
                        {
                            'timestamp': (now - timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                            'insulinDelivered': 1.0,
                            'y': 1.0,
                            'insulinOnBoard': 1.5,
                            'carbsInput': 15.0,
                            'bloodGlucoseInput': 180,
                            'bloodGlucoseInputSource': 'CGM',
                            'deviceName': 'Omnipod 5',
                        },
                        {
                            'timestamp': (now - timedelta(minutes=20)).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                            'insulinDelivered': 0.5,
                            'y': 0.5,
                            'insulinOnBoard': 1.8,
                            'carbsInput': 0,
                            'bloodGlucoseInput': 195,
                            'bloodGlucoseInputSource': 'CGM',
                            'deviceName': 'Omnipod 5',
                        },
                    ],
                },
            }

        if self.scenario == 'high_basal':
            boluses = []
            for i in range(24):
                t = now - timedelta(minutes=i * 5)
                boluses.append({
                    'timestamp': t.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                    'insulinDelivered': 0.05, 'y': 0.05,
                })
            boluses.append({
                'timestamp': (now - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                'insulinDelivered': 3.0, 'y': 3.0, 'insulinOnBoard': 3.2,
            })
            return {'series': {'deliveredBolus': boluses}}

        if self.scenario == 'pod_change':
            return {
                'series': {
                    'deliveredBolus': [{
                        'timestamp': (now - timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                        'insulinDelivered': 0.5, 'y': 0.5, 'insulinOnBoard': 0.5,
                    }],
                },
            }

        if self.scenario == 'manual_mode':
            return {
                'series': {
                    'deliveredBolus': [{
                        'timestamp': (now - timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                        'insulinDelivered': 4.0, 'y': 4.0, 'insulinOnBoard': 2.1,
                    }],
                },
            }

        return {'series': {'deliveredBolus': []}}

    def get_statistics(self, start_date: str, end_date: str) -> Optional[Dict]:
        if self.scenario == 'no_data':
            return None

        if self.scenario == 'manual_mode':
            return {
                'op5PumpModeAutomaticPercentage': 0,
                'op5PumpModeManualPercentage': 100,
                'op5PumpModeLimitedPercentage': 0,
            }

        return {
            'op5PumpModeAutomaticPercentage': 85,
            'op5PumpModeManualPercentage': 10,
            'op5PumpModeLimitedPercentage': 5,
            'totalInsulinPerDay': 22.5,
            'basalPercentage': 55,
            'bolusPercentage': 45,
        }

    def get_daily_data(self, start_date: str, end_date: str) -> Optional[Dict]:
        if self.scenario == 'no_data':
            return None
        return {'cgmDailyAverage': [], 'cgmDailyPercentile10To90': []}

    def get_device_settings(self) -> Optional[Dict]:
        if self.scenario == 'no_data':
            return None
        return {
            'devices': [{
                'displayName': 'Insulet Omnipod 5 System',
                'brand': 'Insulet',
                'model': 'Omnipod 5 System',
                'type': 'pump',
                'serialNumber': 'MOCK-OP5-001',
            }]
        }

    def test_connection(self) -> bool:
        return self.scenario != 'no_data'

    def reconnect(self) -> bool:
        return self.scenario != 'no_data'
