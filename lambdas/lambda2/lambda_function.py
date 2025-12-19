"""
Weather Outerwear Recommendation - Open-Meteo API
GET /api/v1/weather?city=Toronto
"""

import json
import urllib.request
import urllib.parse
import time
from datetime import datetime
from typing import Optional

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
MAX_RETRIES = 3


def log(level: str, message: str, metadata: Optional[dict] = None) -> None:
    """
    Structured logger for CloudWatch Logs.

    Args:
        level: Log level (INFO, ERROR, WARN)
        message: Log message
        metadata: Additional context dictionary
    """
    log_entry = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'level': level,
        'message': message,
        'function': 'PythonFunction'
    }
    if metadata:
        log_entry.update(metadata)
    print(json.dumps(log_entry))


def response(status_code: int, body: dict) -> dict:
    """
    Constructs API Gateway response object.

    Args:
        status_code: HTTP status code
        body: Response body dictionary

    Returns:
        API Gateway response with headers and JSON body
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def fetch_with_retry(url: str) -> dict:
    """
    Fetches URL with exponential backoff retry logic.

    Args:
        url: URL to fetch

    Returns:
        Parsed JSON response

    Raises:
        Exception: If all retry attempts fail
    """
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=10) as res:
                return json.loads(res.read().decode())
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            raise e


def get_coordinates(city: str) -> Optional[dict]:
    """
    Converts city name to GPS coordinates.

    Args:
        city: City name to geocode

    Returns:
        Dictionary with name, country, latitude, longitude or None if not found
    """
    params = urllib.parse.urlencode({"name": city, "count": 1})
    url = f"{GEOCODING_URL}?{params}"

    data = fetch_with_retry(url)

    if "results" not in data or len(data["results"]) == 0:
        return None

    result = data["results"][0]
    return {
        "name": result.get("name"),
        "country": result.get("country"),
        "latitude": result.get("latitude"),
        "longitude": result.get("longitude"),
    }


def get_weather(latitude: float, longitude: float) -> dict:
    """
    Fetches current weather conditions.

    Args:
        latitude: GPS latitude
        longitude: GPS longitude

    Returns:
        Dictionary with temperature (°C) and precipitation probability (%)
    """
    params = urllib.parse.urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,precipitation_probability",
    })
    url = f"{WEATHER_URL}?{params}"

    data = fetch_with_retry(url)

    current = data.get("current", {})
    return {
        "temperature": current.get("temperature_2m"),
        "precipitationProbability": current.get("precipitation_probability"),
    }


def get_outerwear_recommendations(
    temperature: float,
    precipitation_probability: Optional[float]
) -> list[str]:
    """
    Determines recommended outerwear based on weather conditions.

    Temperature thresholds:
    - Below 0°C: Winter coat (freezing conditions)
    - 0-10°C: Light jacket (cold but not freezing)
    - 10-16°C: Hoodie (cool weather)
    - Above 16°C: No temperature-based recommendation

    Rain protection added if precipitation probability > 40%

    Args:
        temperature: Current temperature in Celsius
        precipitation_probability: Chance of precipitation (0-100) or None

    Returns:
        List of recommended outerwear items
    """
    recommendations = []

    # Temperature-based (mutually exclusive)
    if temperature < 0:
        recommendations.append("winter coat")
    elif temperature < 10:
        recommendations.append("light jacket")
    elif temperature < 16:
        recommendations.append("hoodie")

    # Rain-based (additive)
    if precipitation_probability is not None and precipitation_probability > 40:
        recommendations.append("rain jacket")

    return recommendations


def lambda_handler(event: dict, context: object) -> dict:
    """
    Lambda handler for weather-based outerwear recommendations.

    Args:
        event: API Gateway event with queryStringParameters
        context: Lambda context with aws_request_id

    Returns:
        API Gateway response with recommendations or error
    """
    request_id = context.aws_request_id

    params = event.get("queryStringParameters") or {}
    city = params.get("city", "").strip()

    log('INFO', 'Request received', {
        'requestId': request_id,
        'city': city
    })

    try:
        # Validation
        if not city:
            return response(400, {
                "success": False,
                "error": "Missing required parameter: city",
            })
        
        if len(city) > 100:
            return response(400, {
                "success": False,
                "error": "City name too long (max 100 characters)",
            })
        
        # Geocoding
        location = get_coordinates(city)
        if not location:
            return response(404, {
                "success": False,
                "error": f"City not found: {city}",
            })
        
        # Weather
        weather = get_weather(location["latitude"], location["longitude"])

        if weather["temperature"] is None:
            return response(503, {
                "success": False,
                "error": "Weather data unavailable",
            })

        log('INFO', 'Weather API success', {
            'requestId': request_id,
            'location': f"{location['name']}, {location['country']}",
            'temperature': weather['temperature']
        })

        # Recommendations
        recommendations = get_outerwear_recommendations(
            weather["temperature"],
            weather["precipitationProbability"]
        )

        log('INFO', 'Request completed', {
            'requestId': request_id,
            'city': city,
            'recommendations': recommendations
        })

        return response(200, {
            "success": True,
            "data": {
                "location": f"{location['name']}, {location['country']}",
                "temperature": weather["temperature"],
                "precipitationProbability": weather["precipitationProbability"],
                "outerwearRecommended": recommendations,
            },
        })

    except Exception as e:
        log('ERROR', 'Request failed', {
            'requestId': request_id,
            'error': str(e),
            'city': params.get('city', 'unknown')
        })

        return response(500, {
            "success": False,
            "error": "Internal server error",
        })