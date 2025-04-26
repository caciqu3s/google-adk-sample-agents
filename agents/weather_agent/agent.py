import datetime
import os
from pathlib import Path
from zoneinfo import ZoneInfo
from google.adk.agents import Agent
import googlemaps
import requests
from dotenv import load_dotenv

# Load environment variables from root directory
root_dir = Path(__file__).resolve().parent.parent
load_dotenv(root_dir / '.env')

# Initialize Google Maps client
gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))

def get_location_data(city: str) -> dict:
    """Get location data for a city using Google Maps Geocoding API.

    Args:
        city (str): Name of the city to geocode.

    Returns:
        dict: Location data including coordinates and timezone.
    """
    try:
        # Geocode the city
        geocode_result = gmaps.geocode(city)
        
        if not geocode_result:
            return {
                "status": "error",
                "error_message": f"Could not find location data for '{city}'."
            }
        
        location = geocode_result[0]
        lat = location['geometry']['location']['lat']
        lng = location['geometry']['location']['lng']
        
        # Get timezone information
        timezone_result = gmaps.timezone((lat, lng))
        
        return {
            "status": "success",
            "data": {
                "lat": lat,
                "lng": lng,
                "formatted_address": location['formatted_address'],
                "timezone_id": timezone_result['timeZoneId']
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error getting location data: {str(e)}"
        }

def get_weather(city: str) -> dict:
    """Retrieves the current weather report for a specified city using Google Maps Weather API.

    Args:
        city (str): The name of the city for which to retrieve the weather report.

    Returns:
        dict: status and result or error msg.
    """
    try:
        # First get the coordinates using Google Maps Geocoding
        location = get_location_data(city)
        
        if location["status"] == "error":
            return location
        
        # Get weather data from Google Maps Weather API
        lat = location["data"]["lat"]
        lng = location["data"]["lng"]
        
        weather_url = "https://weather.googleapis.com/v1/forecast/days:lookup"
        params = {
            "key": os.getenv('GOOGLE_MAPS_API_KEY'),
            "location.latitude": lat,
            "location.longitude": lng,
            "days": 1  # Get only today's forecast
        }
        
        response = requests.get(weather_url, params=params)
        weather_data = response.json()
        
        if response.status_code != 200:
            return {
                "status": "error",
                "error_message": f"Weather API error: {weather_data.get('error', {}).get('message', 'Unknown error')}"
            }
        
        # Get today's forecast
        today = weather_data['forecastDays'][0]
        daytime = today['daytimeForecast']
        
        # Format the weather report
        temp_c = today['maxTemperature']['degrees']
        temp_f = (temp_c * 9/5) + 32
        description = daytime['weatherCondition']['description']['text']
        humidity = daytime['relativeHumidity']
        
        report = (
            f"The weather in {location['data']['formatted_address']} is {description} "
            f"with a temperature of {temp_c:.1f}°C ({temp_f:.1f}°F) "
            f"and {humidity}% humidity."
        )
        
        return {"status": "success", "report": report}
    
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error getting weather data: {str(e)}"
        }

def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city.

    Args:
        city (str): The name of the city for which to retrieve the current time.

    Returns:
        dict: status and result or error msg.
    """
    try:
        # Get location data including timezone
        location = get_location_data(city)
        
        if location["status"] == "error":
            return location
        
        tz_identifier = location["data"]["timezone_id"]
        tz = ZoneInfo(tz_identifier)
        now = datetime.datetime.now(tz)
        
        report = (
            f'The current time in {location["data"]["formatted_address"]} '
            f'is {now.strftime("%Y-%m-%d %H:%M:%S %Z%z")}'
        )
        return {"status": "success", "report": report}
    
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error getting time data: {str(e)}"
        }

root_agent = Agent(
    name="weather_time_agent",
    model="gemini-2.0-flash-exp",
    description=(
        "Agent to answer questions about the time and weather in a city."
    ),
    instruction=(
        "I can answer your questions about the time and weather in a city."
    ),
    tools=[get_weather, get_current_time],
) 