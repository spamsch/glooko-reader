"""Glooko API client with web-scraping authentication.

Glooko has no public API. This client replicates the browser login flow:
1. GET login page -> follow redirect to regional URL
2. Extract CSRF token from HTML
3. POST form login with credentials
4. Extract patient ID and API base URL from dashboard HTML
5. Use cookie-authenticated session for API calls

Key API quirks discovered through testing:
- Dates must be full ISO datetime (2026-03-29T00:00:00.000Z), not YYYY-MM-DD
- Graph endpoints require Origin + Referer CORS headers
- series[] brackets must NOT be percent-encoded
"""

import logging
import re
from datetime import datetime
from typing import Optional, Dict
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

GLOOKO_BASE_URL = 'https://my.glooko.com'
GLOOKO_LOGIN_PATH = '/users/sign_in'


class GlookoAuthError(Exception):
    """Raised when Glooko authentication fails."""
    pass


class GlookoClient:
    """Client for the Glooko diabetes data platform.

    Args:
        email: Glooko account email.
        password: Glooko account password.
        session_timeout_minutes: Re-authenticate after this many minutes.
            Glooko web sessions typically expire at 60 minutes.
    """

    def __init__(self, email: str, password: str, session_timeout_minutes: int = 55):
        self.email = email
        self.password = password
        self.session_timeout_minutes = session_timeout_minutes

        self.session: Optional[requests.Session] = None
        self.patient_id: Optional[str] = None
        self.api_base: Optional[str] = None
        self.dashboard_origin: Optional[str] = None
        self.last_auth_time: Optional[datetime] = None

        self._authenticate()

    def _authenticate(self):
        """Perform the multi-step Glooko authentication flow."""
        logger.info(f"Glooko: authenticating as {self.email}")

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) '
                'Gecko/20100101 Firefox/148.0'
            ),
        })

        # Step 1: GET login page, follow redirect to regional URL
        login_url = f"{GLOOKO_BASE_URL}{GLOOKO_LOGIN_PATH}?id=login_form&locale=en-GB"
        try:
            resp = self.session.get(login_url, allow_redirects=False)
        except requests.exceptions.RequestException as e:
            raise GlookoAuthError(f"Failed to reach Glooko login page: {e}")

        regional_url = resp.headers.get('Location', login_url)
        if not regional_url.startswith('http'):
            regional_url = f"{GLOOKO_BASE_URL}{regional_url}"

        # Step 2: GET regional login page and extract CSRF token
        try:
            regional_resp = self.session.get(regional_url)
            regional_resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise GlookoAuthError(f"Failed to load regional login page: {e}")

        token_match = re.search(
            r'name="csrf-token" content="([^"]+)"', regional_resp.text
        )
        if not token_match:
            raise GlookoAuthError("Could not extract CSRF token from login page")

        csrf_token = token_match.group(1)

        # Step 3: POST login form
        try:
            auth_resp = self.session.post(
                regional_url,
                data={
                    'authenticity_token': csrf_token,
                    'user[email]': self.email,
                    'user[password]': self.password,
                    'commit': 'Log In',
                },
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Referer': regional_url,
                },
                allow_redirects=True,
            )
        except requests.exceptions.RequestException as e:
            raise GlookoAuthError(f"Login request failed: {e}")

        # Step 4: Extract patient ID and API base from dashboard HTML
        dashboard_html = auth_resp.text

        patient_match = re.search(
            r'window\.patient\s*=\s*"([^"]+)"', dashboard_html
        )
        if not patient_match:
            raise GlookoAuthError(
                "Could not extract patient ID — credentials may be invalid"
            )
        self.patient_id = patient_match.group(1)

        api_match = re.search(r"apiUrl:\s*'([^']+)'", dashboard_html)
        if api_match:
            self.api_base = api_match.group(1)
        else:
            parsed = urlparse(auth_resp.url)
            api_host = parsed.hostname.replace('my.glooko', 'api.glooko')
            self.api_base = f"{parsed.scheme}://{api_host}"

        # Store dashboard origin for CORS headers on API requests
        parsed = urlparse(auth_resp.url)
        self.dashboard_origin = f"{parsed.scheme}://{parsed.hostname}"

        self.last_auth_time = datetime.now()
        logger.info(
            f"Glooko: authenticated. patient={self.patient_id}, api={self.api_base}"
        )

    def ensure_authenticated(self):
        """Re-authenticate if session has expired."""
        if self.session is None or self.last_auth_time is None:
            self._authenticate()
            return

        elapsed = (datetime.now() - self.last_auth_time).total_seconds() / 60
        if elapsed >= self.session_timeout_minutes:
            logger.info(
                f"Glooko: session expired ({elapsed:.0f} min), re-authenticating"
            )
            self._authenticate()

    def _api_request(self, url: str, preserve_url: bool = False) -> Optional[Dict]:
        """Make an authenticated API request with automatic re-auth on 401.

        Args:
            url: Full request URL.
            preserve_url: If True, bypass requests' URL encoding to keep
                literal brackets (needed for series[] params).
        """
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': self.dashboard_origin,
            'Referer': f"{self.dashboard_origin}/",
        }

        def _do_request(request_url: str) -> requests.Response:
            if preserve_url:
                req = requests.Request(
                    'GET', request_url,
                    headers={**headers, **self.session.headers},
                )
                prepared = self.session.prepare_request(req)
                prepared.url = request_url  # Override to keep literal []
                return self.session.send(prepared, timeout=30)
            else:
                return self.session.get(request_url, headers=headers, timeout=30)

        try:
            resp = _do_request(url)
        except requests.exceptions.RequestException as e:
            logger.error(f"Glooko API request failed: {e}")
            return None

        if resp.status_code == 401:
            logger.warning("Glooko: session expired (401), re-authenticating")
            try:
                self._authenticate()
                resp = _do_request(url)
            except (GlookoAuthError, requests.exceptions.RequestException) as e:
                logger.error(f"Glooko: re-auth failed: {e}")
                return None

        if not resp.ok:
            body_preview = resp.text[:200] if resp.text else '(empty)'
            logger.error(
                f"Glooko API error {resp.status_code}: {url} — {body_preview}"
            )
            return None

        try:
            return resp.json()
        except ValueError:
            logger.error("Glooko API returned non-JSON response")
            return None

    # -- Public API methods --------------------------------------------------

    def get_graph_data(self, start_date: str, end_date: str) -> Optional[Dict]:
        """Fetch graph data including CGM readings and delivered bolus insulin.

        Args:
            start_date: ISO datetime (e.g. '2026-03-29T00:00:00.000Z').
            end_date: ISO datetime (e.g. '2026-03-29T23:59:59.999Z').

        Returns:
            Dict with 'series' and 'devices' keys, or None on failure.
            Series includes 'cgmHigh', 'cgmLow', 'cgmNormal', 'deliveredBolus'.
        """
        self.ensure_authenticated()

        query = (
            f"patient={self.patient_id}"
            f"&startDate={start_date}"
            f"&endDate={end_date}"
            f"&locale=en-GB"
            f"&insulinTooltips=true"
            f"&filterBgReadings=true"
            f"&splitByDay=false"
        )
        series = (
            "&series[]=cgmHigh"
            "&series[]=cgmLow"
            "&series[]=cgmNormal"
            "&series[]=deliveredBolus"
        )
        url = f"{self.api_base}/api/v3/graph/data?{query}{series}"
        return self._api_request(url, preserve_url=True)

    def get_statistics(self, start_date: str, end_date: str) -> Optional[Dict]:
        """Fetch overall statistics including insulin and pump mode data.

        Args:
            start_date: ISO datetime.
            end_date: ISO datetime.

        Returns:
            Dict with statistics fields, or None on failure.
        """
        self.ensure_authenticated()

        query = (
            f"patient={self.patient_id}"
            f"&startDate={start_date}"
            f"&endDate={end_date}"
            f"&egv=false"
            f"&includeInsulin=true"
            f"&includeExercise=true"
            f"&dow=monday,tuesday,wednesday,thursday,friday,saturday,sunday"
            f"&includePumpModes=true"
        )
        url = f"{self.api_base}/api/v3/graph/statistics/overall?{query}"
        return self._api_request(url)

    def get_daily_data(self, start_date: str, end_date: str) -> Optional[Dict]:
        """Fetch daily CGM averages and percentile bands.

        Args:
            start_date: ISO datetime.
            end_date: ISO datetime.

        Returns:
            Dict with daily average and percentile data, or None on failure.
        """
        self.ensure_authenticated()

        query = f"patient={self.patient_id}&startDate={start_date}&endDate={end_date}"
        series = (
            "&series[]=cgmDailyAverage"
            "&series[]=cgmDailyPercentile10To90"
            "&series[]=cgmDailyPercentile25To75"
        )
        url = f"{self.api_base}/api/v3/graph/daily_data?{query}{series}"
        return self._api_request(url, preserve_url=True)

    def get_device_settings(self) -> Optional[Dict]:
        """Fetch connected device information.

        Returns:
            Dict with 'devices' list, or None on failure.
        """
        self.ensure_authenticated()

        url = f"{self.api_base}/api/v3/devices_and_settings?patient={self.patient_id}"
        return self._api_request(url)

    def test_connection(self) -> bool:
        """Test the connection by fetching device settings."""
        try:
            self.ensure_authenticated()
            result = self.get_device_settings()
            return result is not None
        except Exception:
            return False

    def reconnect(self) -> bool:
        """Force re-authentication."""
        try:
            self._authenticate()
            return True
        except Exception:
            return False
