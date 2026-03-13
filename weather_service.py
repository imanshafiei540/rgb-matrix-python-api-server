#!/usr/bin/env python3
"""
Weather Service for RGB Matrix Display
Uses Open-Meteo API (free, no API key required!)
https://open-meteo.com/
"""
import urllib.request
import urllib.parse
import json
from typing import Optional, Dict, Any

class WeatherService:
    WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    
    def __init__(self):
        self._geo_cache = {}  # Cache city -> coordinates
    
    def _geocode(self, city: str) -> Optional[Dict]:
        """Convert city name to coordinates"""
        if city.lower() in self._geo_cache:
            return self._geo_cache[city.lower()]
        
        try:
            url = f"{self.GEOCODING_URL}?name={urllib.parse.quote(city)}&count=1&language=en&format=json"
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'RGB-Matrix-Weather/1.0')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                results = data.get("results", [])
                if results:
                    loc = results[0]
                    self._geo_cache[city.lower()] = loc
                    return loc
        except Exception as e:
            print(f"[ERROR] Geocoding failed for {city}: {e}")
        return None
    
    def get_weather(self, city: str, units: str = "metric") -> Dict[str, Any]:
        """
        Get current weather for a city.
        
        Args:
            city: City name (e.g., "London", "New York", "Tokyo")
            units: "metric" (Celsius) or "imperial" (Fahrenheit)
        
        Returns:
            Weather data dict with normalized fields
        """
        # Get coordinates for city
        location = self._geocode(city)
        if not location:
            print(f"[WARN] City '{city}' not found, using mock data")
            return self._mock_weather(city)
        
        lat = location["latitude"]
        lon = location["longitude"]
        city_name = location.get("name", city)
        country = location.get("country_code", "")
        
        try:
            # Build API URL with current weather params
            temp_unit = "fahrenheit" if units == "imperial" else "celsius"
            wind_unit = "mph" if units == "imperial" else "kmh"
            
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
                "temperature_unit": temp_unit,
                "wind_speed_unit": wind_unit,
                "timezone": "auto"
            }
            url = f"{self.WEATHER_URL}?{urllib.parse.urlencode(params)}"
            
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'RGB-Matrix-Weather/1.0')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return self._normalize_weather(data, city_name, country, units)
                
        except Exception as e:
            print(f"[ERROR] Weather fetch failed: {e}")
            return self._mock_weather(city)
    
    def _normalize_weather(self, data: Dict, city: str, country: str, units: str) -> Dict[str, Any]:
        """Normalize Open-Meteo response to our format"""
        current = data.get("current", {})
        
        temp_unit = "°F" if units == "imperial" else "°C"
        
        weather_code = current.get("weather_code", 0)
        is_day = current.get("is_day", 1) == 1
        
        return {
            "city": city,
            "country": country,
            "temp": round(current.get("temperature_2m", 0)),
            "temp_unit": temp_unit,
            "feels_like": round(current.get("apparent_temperature", 0)),
            "humidity": current.get("relative_humidity_2m", 0),
            "wind_speed": round(current.get("wind_speed_10m", 0)),
            "wind_deg": current.get("wind_direction_10m", 0),
            "precipitation": current.get("precipitation", 0),
            "condition": self._wmo_to_condition(weather_code),
            "description": self._wmo_to_description(weather_code),
            "weather_code": weather_code,
            "icon_code": self._wmo_to_icon_code(weather_code, is_day),
            "is_day": is_day,
        }
    
    def _wmo_to_condition(self, code: int) -> str:
        """Convert WMO weather code to condition name"""
        if code == 0:
            return "Clear"
        elif code in (1, 2, 3):
            return "Clouds"
        elif code in (45, 48):
            return "Fog"
        elif code in (51, 53, 55, 56, 57):
            return "Drizzle"
        elif code in (61, 63, 65, 66, 67, 80, 81, 82):
            return "Rain"
        elif code in (71, 73, 75, 77, 85, 86):
            return "Snow"
        elif code in (95, 96, 99):
            return "Thunderstorm"
        return "Clear"
    
    def _wmo_to_description(self, code: int) -> str:
        """Convert WMO weather code to human description"""
        descriptions = {
            0: "clear sky",
            1: "mainly clear", 2: "partly cloudy", 3: "overcast",
            45: "fog", 48: "rime fog",
            51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
            56: "freezing drizzle", 57: "dense freezing drizzle",
            61: "slight rain", 63: "moderate rain", 65: "heavy rain",
            66: "freezing rain", 67: "heavy freezing rain",
            71: "slight snow", 73: "moderate snow", 75: "heavy snow",
            77: "snow grains",
            80: "light showers", 81: "moderate showers", 82: "violent showers",
            85: "light snow showers", 86: "heavy snow showers",
            95: "thunderstorm", 96: "thunderstorm with hail", 99: "severe thunderstorm"
        }
        return descriptions.get(code, "clear sky")
    
    def _wmo_to_icon_code(self, code: int, is_day: bool) -> str:
        """Convert WMO code to icon code (compatible with our icon system)"""
        suffix = "d" if is_day else "n"
        
        if code == 0:
            return f"01{suffix}"  # clear
        elif code in (1, 2):
            return f"02{suffix}"  # partly cloudy
        elif code == 3:
            return f"04{suffix}"  # overcast
        elif code in (45, 48):
            return f"50{suffix}"  # fog/mist
        elif code in (51, 53, 55, 56, 57):
            return f"09{suffix}"  # drizzle
        elif code in (61, 63, 65, 66, 67, 80, 81, 82):
            return f"10{suffix}"  # rain
        elif code in (71, 73, 75, 77, 85, 86):
            return f"13{suffix}"  # snow
        elif code in (95, 96, 99):
            return f"11{suffix}"  # thunderstorm
        return f"01{suffix}"
    
    def _mock_weather(self, city: str) -> Dict[str, Any]:
        """Return mock weather data when API is unavailable"""
        return {
            "city": city,
            "country": "??",
            "temp": 22,
            "temp_unit": "°C",
            "feels_like": 21,
            "humidity": 65,
            "wind_speed": 5,
            "wind_deg": 180,
            "precipitation": 0,
            "condition": "Clear",
            "description": "clear sky",
            "weather_code": 0,
            "icon_code": "01d",
            "is_day": True,
        }


# Mapping icon codes to our weather conditions
ICON_CODE_MAP = {
    "01d": "clear_day",
    "01n": "clear_night",
    "02d": "partly_cloudy_day",
    "02n": "partly_cloudy_night",
    "03d": "cloudy",
    "03n": "cloudy",
    "04d": "overcast",
    "04n": "overcast",
    "09d": "rain",
    "09n": "rain",
    "10d": "rain_day",
    "10n": "rain_night",
    "11d": "thunderstorm",
    "11n": "thunderstorm",
    "13d": "snow",
    "13n": "snow",
    "50d": "mist",
    "50n": "mist",
}

def get_condition_from_code(icon_code: str) -> str:
    """Convert icon code to our condition name"""
    return ICON_CODE_MAP.get(icon_code, "clear_day")


# Singleton instance
weather_service = WeatherService()

if __name__ == "__main__":
    # Test the service
    print("Testing Open-Meteo weather service...")
    for city in ["London", "Tokyo", "New York", "Sydney"]:
        weather = weather_service.get_weather(city)
        print(f"\n{city}:")
        print(json.dumps(weather, indent=2))
