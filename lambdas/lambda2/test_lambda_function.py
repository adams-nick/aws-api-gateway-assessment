"""
Unit tests for Weather Outerwear Recommendation Lambda
Minimal essential tests covering critical paths
"""

import unittest
from unittest.mock import patch, MagicMock
import json
from lambda_function import (
    lambda_handler,
    get_outerwear_recommendations
)


class TestWeatherLambda(unittest.TestCase):
    """Essential tests for weather Lambda function"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_context = MagicMock(aws_request_id="test-123")

    def test_missing_city_parameter(self):
        """Should return 400 when city parameter is missing"""
        event = {"queryStringParameters": {}}

        result = lambda_handler(event, self.mock_context)

        self.assertEqual(result["statusCode"], 400)
        body = json.loads(result["body"])
        self.assertFalse(body["success"])
        self.assertIn("Missing required parameter", body["error"])

    def test_city_name_too_long(self):
        """Should return 400 when city name exceeds 100 characters"""
        event = {"queryStringParameters": {"city": "A" * 101}}

        result = lambda_handler(event, self.mock_context)

        self.assertEqual(result["statusCode"], 400)
        body = json.loads(result["body"])
        self.assertIn("too long", body["error"])

    @patch('lambda_function.fetch_with_retry')
    def test_city_not_found(self, mock_fetch):
        """Should return 404 when city is not found"""
        mock_fetch.return_value = {"results": []}

        event = {"queryStringParameters": {"city": "InvalidCity999"}}
        result = lambda_handler(event, self.mock_context)

        self.assertEqual(result["statusCode"], 404)
        body = json.loads(result["body"])
        self.assertIn("City not found", body["error"])

    @patch('lambda_function.fetch_with_retry')
    def test_successful_weather_request(self, mock_fetch):
        """Should return 200 with recommendations for valid request"""
        # Mock geocoding response, then weather response
        mock_fetch.side_effect = [
            {
                "results": [{
                    "name": "Toronto",
                    "country": "Canada",
                    "latitude": 43.7,
                    "longitude": -79.42
                }]
            },
            {
                "current": {
                    "temperature_2m": -2,
                    "precipitation_probability": 10
                }
            }
        ]

        event = {"queryStringParameters": {"city": "Toronto"}}
        result = lambda_handler(event, self.mock_context)

        self.assertEqual(result["statusCode"], 200)
        body = json.loads(result["body"])
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["location"], "Toronto, Canada")
        self.assertIn("winter coat", body["data"]["outerwearRecommended"])

    def test_outerwear_winter_coat(self):
        """Should recommend winter coat for freezing temperatures"""
        recommendations = get_outerwear_recommendations(-5, 20)

        self.assertIn("winter coat", recommendations)
        self.assertEqual(len(recommendations), 1)

    def test_outerwear_light_jacket(self):
        """Should recommend light jacket for cold temperatures"""
        recommendations = get_outerwear_recommendations(5, 20)

        self.assertIn("light jacket", recommendations)

    def test_outerwear_hoodie(self):
        """Should recommend hoodie for cool temperatures"""
        recommendations = get_outerwear_recommendations(12, 20)

        self.assertIn("hoodie", recommendations)

    def test_outerwear_rain_jacket(self):
        """Should recommend rain jacket for high precipitation"""
        recommendations = get_outerwear_recommendations(15, 60)

        self.assertIn("rain jacket", recommendations)

    def test_outerwear_none_for_warm_weather(self):
        """Should recommend nothing for warm weather"""
        recommendations = get_outerwear_recommendations(20, 10)

        self.assertEqual(len(recommendations), 0)


if __name__ == '__main__':
    unittest.main()
