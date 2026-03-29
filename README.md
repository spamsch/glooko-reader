# glooko-reader

Unofficial Python client for the [Glooko](https://www.glooko.com/) diabetes data platform. Retrieves insulin pump data (Omnipod 5), CGM readings, and statistics via Glooko's internal web API.

**Note:** Glooko does not provide a public API. This library authenticates by replicating the browser login flow (CSRF token extraction, cookie-based sessions). It may break if Glooko changes their web application.

## Installation

```bash
pip install requests
```

Copy the `glooko/` directory into your project, or install from this repository:

```bash
pip install git+https://github.com/spamsch/glooko-reader.git
```

## Quick Start

```python
from glooko import GlookoClient, parse_bolus_entries, parse_pump_mode, parse_devices

client = GlookoClient(email="you@example.com", password="your_password")

# Fetch insulin delivery data (last 24 hours)
data = client.get_graph_data(
    start_date="2026-03-29T00:00:00.000Z",
    end_date="2026-03-29T23:59:59.999Z",
)

# Parse into structured objects
boluses = parse_bolus_entries(data)
for b in boluses:
    print(f"{b.timestamp} — {b.units}u (IOB: {b.insulin_on_board}, carbs: {b.carbs_input}g)")

# Pump mode and statistics
stats = client.get_statistics(
    start_date="2026-03-29T00:00:00.000Z",
    end_date="2026-03-29T23:59:59.999Z",
)
pump = parse_pump_mode(stats)
print(f"Pump: {pump.mode} mode, {pump.total_insulin_per_day} units/day")

# Connected devices
devices = parse_devices(client.get_device_settings())
for d in devices:
    print(f"{d.name} — last sync: {d.last_sync}")
```

## API Reference

### Client

```python
GlookoClient(email, password, session_timeout_minutes=55)
```

| Method | Returns | Description |
|--------|---------|-------------|
| `get_graph_data(start, end)` | `dict` | CGM readings + delivered bolus insulin |
| `get_statistics(start, end)` | `dict` | Overall stats, pump modes, insulin totals |
| `get_daily_data(start, end)` | `dict` | Daily CGM averages and percentile bands |
| `get_device_settings()` | `dict` | Connected devices and configuration |
| `test_connection()` | `bool` | Verify authentication works |
| `reconnect()` | `bool` | Force re-authentication |

All date parameters use ISO 8601 datetime format: `YYYY-MM-DDT00:00:00.000Z`

### Parsers

| Function | Input | Returns | Description |
|----------|-------|---------|-------------|
| `parse_bolus_entries(graph_data)` | graph/data response | `list[BolusEntry]` | Insulin bolus deliveries |
| `parse_iob_from_bolus(graph_data, max_age_minutes=30)` | graph/data response | `float` or `None` | IOB from most recent bolus (if recent enough) |
| `parse_pump_mode(statistics)` | statistics response | `PumpStatistics` or `None` | Pump mode and insulin stats |
| `parse_devices(device_data)` | device settings response | `list[DeviceInfo]` | Connected device info |
| `parse_timestamp(value)` | `str`, `int`, or `float` | `datetime` or `None` | Parse Glooko timestamp formats |

### Models

**BolusEntry** — A single insulin bolus delivery

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `datetime` | When the bolus was delivered |
| `units` | `float` | Insulin units delivered |
| `carbs_input` | `float?` | Carbs entered at bolus time |
| `insulin_on_board` | `float?` | IOB reported by pump at bolus time |
| `blood_glucose_input` | `int?` | BG reading at bolus time |
| `blood_glucose_source` | `str?` | Source of BG (`"CGM"`, etc.) |
| `correction_units` | `float?` | Insulin for correction |
| `carb_units` | `float?` | Insulin for carbs |
| `is_manual` | `bool` | Whether bolus was manually entered |
| `device_name` | `str?` | Device that delivered the bolus |

**PumpStatistics** — Pump mode and insulin statistics

| Field | Type | Description |
|-------|------|-------------|
| `mode` | `str?` | `"auto"`, `"manual"`, or `"limited"` |
| `auto_percentage` | `float` | Time in auto mode (%) |
| `manual_percentage` | `float` | Time in manual mode (%) |
| `limited_percentage` | `float` | Time in limited mode (%) |
| `total_insulin_per_day` | `float?` | Average daily insulin |
| `basal_percentage` | `float?` | Basal insulin share (%) |
| `bolus_percentage` | `float?` | Bolus insulin share (%) |
| `in_range_percentage` | `float?` | Time in range (%) |
| `carbs_per_day` | `float?` | Average daily carbs (g) |

**DeviceInfo** — Connected device

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Display name |
| `brand` | `str?` | Manufacturer |
| `model` | `str?` | Model name |
| `serial_number` | `str?` | Serial number |
| `device_type` | `str?` | `"pump"`, `"cgm"`, etc. |
| `last_sync` | `datetime?` | Last data sync time |
| `properties` | `dict` | Additional device properties |

## Authentication Details

Glooko uses a multi-step browser login flow:

1. `GET https://my.glooko.com/users/sign_in` — follows redirect to regional server (e.g., `de-fr.my.glooko.com`)
2. Extracts CSRF token from the HTML response
3. `POST` login form with email, password, and CSRF token
4. Extracts `patient_id` and `apiUrl` from the dashboard JavaScript
5. Subsequent API calls use cookie-based authentication with CORS headers

Sessions expire after ~60 minutes. The client automatically re-authenticates when the session timeout is reached or a 401 response is received.

### API Quirks

These were discovered through testing and may be useful for other implementations:

- **Date format**: Endpoints require full ISO datetime (`2026-03-29T00:00:00.000Z`), not just `YYYY-MM-DD`. Using date-only format returns HTTP 500.
- **CORS headers**: Graph and statistics endpoints require `Origin` and `Referer` headers pointing to the dashboard domain. The device settings endpoint works without them.
- **URL encoding**: The `series[]` parameter must use literal brackets. Percent-encoding (`series%5B%5D`) returns HTTP 500. This library uses `PreparedRequest.url` override to bypass Python `requests`' automatic encoding.
- **Regional routing**: Glooko routes users to regional servers (e.g., `de-fr.api.glooko.com`). The API base URL is scraped from the dashboard page after login.

## Testing

A mock client is included for testing without Glooko credentials:

```python
from glooko import MockGlookoClient, parse_bolus_entries, parse_pump_mode

client = MockGlookoClient(scenario="normal")  # or "high_basal", "manual_mode", "pod_change", "no_data"

data = client.get_graph_data("2026-03-29T00:00:00.000Z", "2026-03-29T23:59:59.999Z")
boluses = parse_bolus_entries(data)
```

## Tested With

- Insulet Omnipod 5 System (insulin pump)
- Dexcom G7 (CGM, via Omnipod 5 integration)
- Glooko EU region (`de-fr.api.glooko.com`)

## Dependencies

- Python 3.10+
- `requests`

## License

MIT
