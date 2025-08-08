import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from weather import make_nws_request, format_alert, get_alerts, get_forecast


class TestWeatherAPI:
    """Test suite for weather MCP server."""

    @pytest.mark.asyncio
    async def test_make_nws_request_success(self):
        """Test successful NWS API request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"test": "data"}
        mock_response.raise_for_status.return_value = None
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await make_nws_request("https://api.weather.gov/test")
            
            assert result == {"test": "data"}
            mock_client.return_value.__aenter__.return_value.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_nws_request_error(self):
        """Test NWS API request with error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(side_effect=httpx.RequestError("Network error"))
            
            result = await make_nws_request("https://api.weather.gov/test")
            
            assert result is None

    @pytest.mark.asyncio
    async def test_make_nws_request_http_error(self):
        """Test NWS API request with HTTP error."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock())
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            
            result = await make_nws_request("https://api.weather.gov/test")
            
            assert result is None

    def test_format_alert(self):
        """Test alert formatting."""
        feature = {
            "properties": {
                "event": "Winter Storm Warning",
                "areaDesc": "Northern California",
                "severity": "Severe",
                "description": "Heavy snow expected",
                "instruction": "Avoid travel"
            }
        }
        
        result = format_alert(feature)
        
        assert "Winter Storm Warning" in result
        assert "Northern California" in result
        assert "Severe" in result
        assert "Heavy snow expected" in result
        assert "Avoid travel" in result

    def test_format_alert_missing_data(self):
        """Test alert formatting with missing data."""
        feature = {
            "properties": {}
        }
        
        result = format_alert(feature)
        
        assert "Unknown" in result
        assert "No description available" in result
        assert "No specific instructions provided" in result

    @pytest.mark.asyncio
    async def test_get_alerts_success(self):
        """Test successful alert retrieval."""
        mock_data = {
            "features": [
                {
                    "properties": {
                        "event": "Heat Advisory",
                        "areaDesc": "Los Angeles County",
                        "severity": "Minor",
                        "description": "Temperatures above 100°F",
                        "instruction": "Stay hydrated"
                    }
                }
            ]
        }
        
        with patch("weather.make_nws_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data
            
            result = await get_alerts("CA")
            
            assert "Heat Advisory" in result
            assert "Los Angeles County" in result
            mock_request.assert_called_once_with("https://api.weather.gov/alerts/active/area/CA")

    @pytest.mark.asyncio
    async def test_get_alerts_no_data(self):
        """Test alert retrieval with no data."""
        with patch("weather.make_nws_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = None
            
            result = await get_alerts("CA")
            
            assert result == "Unable to fetch alerts or no alerts found."

    @pytest.mark.asyncio
    async def test_get_alerts_no_features(self):
        """Test alert retrieval with no alerts."""
        mock_data = {"features": []}
        
        with patch("weather.make_nws_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_data
            
            result = await get_alerts("CA")
            
            assert result == "No active alerts for this state."

    @pytest.mark.asyncio
    async def test_get_forecast_success(self):
        """Test successful forecast retrieval."""
        mock_points_data = {
            "properties": {
                "forecast": "https://api.weather.gov/gridpoints/LOX/123,456/forecast"
            }
        }
        
        mock_forecast_data = {
            "properties": {
                "periods": [
                    {
                        "name": "Today",
                        "temperature": 75,
                        "temperatureUnit": "F",
                        "windSpeed": "10 mph",
                        "windDirection": "SW",
                        "detailedForecast": "Sunny and warm"
                    },
                    {
                        "name": "Tonight",
                        "temperature": 55,
                        "temperatureUnit": "F",
                        "windSpeed": "5 mph",
                        "windDirection": "W",
                        "detailedForecast": "Clear skies"
                    }
                ]
            }
        }
        
        with patch("weather.make_nws_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [mock_points_data, mock_forecast_data]
            
            result = await get_forecast(34.0522, -118.2437)
            
            assert "Today" in result
            assert "75°F" in result
            assert "Sunny and warm" in result
            assert "Tonight" in result
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_get_forecast_points_error(self):
        """Test forecast retrieval with points API error."""
        with patch("weather.make_nws_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = None
            
            result = await get_forecast(34.0522, -118.2437)
            
            assert result == "Unable to fetch forecast data for this location."

    @pytest.mark.asyncio
    async def test_get_forecast_forecast_error(self):
        """Test forecast retrieval with forecast API error."""
        mock_points_data = {
            "properties": {
                "forecast": "https://api.weather.gov/gridpoints/LOX/123,456/forecast"
            }
        }
        
        with patch("weather.make_nws_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [mock_points_data, None]
            
            result = await get_forecast(34.0522, -118.2437)
            
            assert result == "Unable to fetch detailed forecast."

    @pytest.mark.asyncio
    async def test_get_forecast_limits_periods(self):
        """Test that forecast limits to 5 periods."""
        mock_points_data = {
            "properties": {
                "forecast": "https://api.weather.gov/gridpoints/LOX/123,456/forecast"
            }
        }
        
        # Create 10 periods but expect only 5 in output
        periods = []
        for i in range(10):
            periods.append({
                "name": f"Day {i}",
                "temperature": 70 + i,
                "temperatureUnit": "F",
                "windSpeed": "10 mph",
                "windDirection": "SW",
                "detailedForecast": f"Forecast for day {i}"
            })
        
        mock_forecast_data = {
            "properties": {
                "periods": periods
            }
        }
        
        with patch("weather.make_nws_request", new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = [mock_points_data, mock_forecast_data]
            
            result = await get_forecast(34.0522, -118.2437)
            
            # Should only contain first 5 periods
            assert "Day 0" in result
            assert "Day 4" in result
            assert "Day 5" not in result
            assert "Day 9" not in result


if __name__ == "__main__":
    pytest.main([__file__])
