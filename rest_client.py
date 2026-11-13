import requests
from typing import Dict, Any, Optional
from config import FORTY_GUARD_API_KEY, FORTY_GUARD_REST_BASE, is_within_us_bounds

class FortyGuardRESTClient:
    """
    Direct REST API client for FortyGuard Temperature API endpoints.
    Base URL: https://api.fortyguard.com/v1
    """

    def __init__(self, api_key: Optional[str] = None, base_url: str = FORTY_GUARD_REST_BASE):
        self.api_key = api_key or FORTY_GUARD_API_KEY
        self.base_url = base_url

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def fetch_api_key_usage(self) -> Dict[str, Any]:
        """Fetch subscription and credit consumption from system endpoint."""
        url = f"{self.base_url}/system/fetch-api-key-usage"
        # Note: Empirical finding - requires api_key inside body
        payload = {"api_key": self.api_key}
        res = requests.post(url, headers=self.headers, json=payload, timeout=15)
        return {"status_code": res.status_code, "data": res.json() if res.status_code == 200 else res.text}

    def check_activity_status(self, activity_id: str) -> Dict[str, Any]:
        """Poll the universal status endpoint for any asynchronous activity."""
        url = f"{self.base_url}/status/{activity_id}"
        res = requests.get(url, headers=self.headers, timeout=15)
        return {"status_code": res.status_code, "data": res.json() if res.status_code == 200 else res.text}

    def submit_env_params(
        self,
        lat: float,
        lon: float,
        temperature: float,
        date_str: str,
        time_str: str = "12:00",
        filter_type: int = 1,
    ) -> Dict[str, Any]:
        """Submit point-level environmental parameters via REST."""
        if not is_within_us_bounds(lat, lon):
            return {
                "status_code": 400,
                "data": {"error": True, "message": "Location outside contiguous US bounds."},
            }

        url = f"{self.base_url}/env_params"
        payload = {
            "latitude": lat,
            "longitude": lon,
            "temperature": temperature,
            "date_time": {
                "start_date": date_str,
                "start_time": time_str,
                "filter_type": filter_type,
            },
        }
        res = requests.post(url, headers=self.headers, json=payload, timeout=20)
        return {"status_code": res.status_code, "data": res.json() if res.status_code == 200 else res.text}

    def submit_heatmap(
        self,
        polygon_aoi: Dict[str, Any],
        date_time: Dict[str, Any],
        granularity: int = 100,
        analytic_type: str = "tcm",
    ) -> Dict[str, Any]:
        """Submit a standalone heatmap request via REST."""
        url = f"{self.base_url}/heatmap"
        payload = {
            "polygon_aoi": polygon_aoi,
            "date_time": date_time,
            "granularity": granularity,
            "analytic_type": analytic_type,
        }
        res = requests.post(url, headers=self.headers, json=payload, timeout=25)
        return {"status_code": res.status_code, "data": res.json() if res.status_code == 200 else res.text}
