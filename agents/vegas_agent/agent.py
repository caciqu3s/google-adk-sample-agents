import datetime
import os
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Optional, Dict
from google.adk.agents import Agent
import requests
from dotenv import load_dotenv
from google.adk.tools import agent_tool
from .google_search_agent.agent import google_search_agent
from .google_maps_agent.agent import get_agent_async as get_google_maps_agent_async
import asyncio

# Load environment variables from root directory
root_dir = Path(__file__).resolve().parent.parent
load_dotenv(root_dir / '.env')

# Google Maps Weather API configuration
WEATHER_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')

# Ticketmaster API configuration
TM_API_KEY = os.getenv('TICKETMASTER_API_KEY')
TM_BASE_URL = 'https://app.ticketmaster.com/discovery/v2'

VEGAS_LOCATION = {
    "lat": 36.1699,
    "lng": -115.1398,
    "formatted_address": "Las Vegas, NV, USA",
    "timezone_id": "America/Los_Angeles"
}

def format_datetime(dt: datetime.datetime) -> dict:
    """Helper function to format datetime objects consistently.
    
    Args:
        dt (datetime.datetime): Datetime object to format
        
    Returns:
        dict: Formatted datetime strings
    """
    return {
        "iso": dt.isoformat(),
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%I:%M %p"),
        "datetime": dt.strftime("%B %d, %Y at %I:%M %p %Z"),
        "day_name": dt.strftime("%A"),
        "day": dt.strftime("%d"),
        "month": dt.strftime("%B"),
        "year": dt.strftime("%Y"),
        "hour": dt.hour,
        "is_today": dt.date() == datetime.datetime.now().date(),
        "relative_day": "today" if dt.date() == datetime.datetime.now().date() else (
            "tomorrow" if dt.date() == (datetime.datetime.now() + datetime.timedelta(days=1)).date() else
            "yesterday" if dt.date() == (datetime.datetime.now() - datetime.timedelta(days=1)).date() else
            None
        )
    }

def parse_time_expression(expression: str) -> Dict[str, str]:
    """Parse natural time expressions into start and end dates.
    
    Args:
        expression (str): Natural time expression (e.g., 'this weekend', 'next week')
        
    Returns:
        Dict[str, str]: Dictionary with start_date and end_date in YYYY-MM-DD format
    """
    # Get current time in Vegas
    current_time = datetime.datetime.now(ZoneInfo(VEGAS_LOCATION["timezone_id"]))
    
    # Convert expression to lowercase for easier matching
    expression = expression.lower().strip()
    
    # Initialize dates
    start_date = current_time
    end_date = None
    
    # Handle common time expressions
    if "tonight" in expression:
        # Set start time to current time and end time to end of day
        start_date = current_time
        end_date = current_time.replace(hour=23, minute=59, second=59)
    elif "today" in expression:
        end_date = start_date.replace(hour=23, minute=59, second=59)
    elif "tomorrow" in expression:
        start_date = current_time + datetime.timedelta(days=1)
        start_date = start_date.replace(hour=0, minute=0, second=0)
        end_date = start_date.replace(hour=23, minute=59, second=59)
    elif "this week" in expression:
        # Start from today, end on Sunday
        end_date = start_date + datetime.timedelta(days=(6 - start_date.weekday()))
        end_date = end_date.replace(hour=23, minute=59, second=59)
    elif "next week" in expression:
        # Start from next Monday
        days_until_monday = (7 - start_date.weekday()) % 7
        start_date = start_date + datetime.timedelta(days=days_until_monday)
        start_date = start_date.replace(hour=0, minute=0, second=0)
        end_date = start_date + datetime.timedelta(days=6)
        end_date = end_date.replace(hour=23, minute=59, second=59)
    elif "weekend" in expression:
        if "next" in expression:
            # Next weekend
            days_until_saturday = (5 - start_date.weekday()) % 7 + 7
            start_date = start_date + datetime.timedelta(days=days_until_saturday)
        else:
            # This weekend
            days_until_saturday = (5 - start_date.weekday()) % 7
            start_date = start_date + datetime.timedelta(days=days_until_saturday)
        start_date = start_date.replace(hour=0, minute=0, second=0)
        end_date = start_date + datetime.timedelta(days=1)
        end_date = end_date.replace(hour=23, minute=59, second=59)
    elif any(day in expression for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
        day_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        for day, day_num in day_map.items():
            if day in expression:
                days_until = (day_num - start_date.weekday()) % 7
                if "next" in expression:
                    days_until += 7
                start_date = start_date + datetime.timedelta(days=days_until)
                start_date = start_date.replace(hour=0, minute=0, second=0)
                end_date = start_date.replace(hour=23, minute=59, second=59)
                break
    
    # Format dates as strings with timezone consideration
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d") if end_date else None
    
    return {"start_date": start_str, "end_date": end_str}

def format_event_category(category: str) -> str:
    """Get appropriate emoji for event category.
    
    Args:
        category (str): Event category name
        
    Returns:
        str: Category with emoji
    """
    category_emojis = {
        "music": "🎵",
        "sports": "🏆",
        "arts": "🎨",
        "theatre": "🎭",
        "family": "👨‍👩‍👧‍👦",
        "comedy": "😂",
        "magic": "✨",
        "food": "🍽️",
        "exhibition": "🖼️",
        "experience": "🎯",
        "motorsports": "🏎️",
        "racing": "🏁",
        "aquarium": "🐠",
        "immersive": "🌟",
        "battle": "⚔️",
        "brunch": "🍳",
        "default": "🎪"
    }
    
    # Convert to lowercase for matching
    category = category.lower()
    
    # Find matching emoji
    for key, emoji in category_emojis.items():
        if key in category:
            return f"{emoji} {category.title()}"
    
    return f"{category_emojis['default']} {category.title()}"

def format_venue_type(venue: str) -> str:
    """Get appropriate emoji for venue type.
    
    Args:
        venue (str): Venue name
        
    Returns:
        str: Venue with emoji
    """
    venue_emojis = {
        "arena": "🏟️",
        "theater": "🎭",
        "theatre": "🎭",
        "stadium": "🏟️",
        "speedway": "🏎️",
        "garden": "🌳",
        "hall": "🏛️",
        "center": "🎪",
        "room": "🎵",
        "lounge": "🎵",
        "club": "🎉",
        "casino": "🎰",
        "sphere": "🌐",
        "park": "🌳",
        "default": "📍"
    }
    
    # Convert to lowercase for matching
    venue = venue.lower()
    
    # Find matching emoji
    for key, emoji in venue_emojis.items():
        if key in venue:
            return f"{emoji} {venue}"
    
    return f"{venue_emojis['default']} {venue}"

def get_time() -> dict:
    """Get current time in Las Vegas."""
    try:
        # Get current time in Vegas timezone directly
        current_time = datetime.datetime.now(ZoneInfo(VEGAS_LOCATION["timezone_id"]))
        
        # Format the time data
        formatted_time = format_datetime(current_time)
        
        # Create a detailed report
        report = (
            f"Current time in Las Vegas:\n"
            f"🗓️ {formatted_time['day_name']}, {formatted_time['month']} {formatted_time['day']}, {formatted_time['year']}\n"
            f"⏰ {formatted_time['time']} {current_time.tzname()}"
        )
        
        return {
            "status": "success",
            "time": formatted_time,
            "report": report
        }
    
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error getting time data: {str(e)}"
        }

def get_weather() -> dict:
    """Get current weather in Las Vegas."""
    try:
        # Get weather data from Google Maps Weather API
        weather_url = "https://weather.googleapis.com/v1/forecast/days:lookup"
        params = {
            "key": WEATHER_API_KEY,
            "location.latitude": VEGAS_LOCATION["lat"],
            "location.longitude": VEGAS_LOCATION["lng"],
            "days": 1
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
            f"Current weather in Las Vegas:\n"
            f"🌡️ Temperature: {temp_c:.1f}°C ({temp_f:.1f}°F)\n"
            f"🌤️ Conditions: {description}\n"
            f"💧 Humidity: {humidity}%\n"
        )
        
        return {"status": "success", "report": report}
    
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error getting weather data: {str(e)}"
        }

async def get_events(category: Optional[str] = None, start_date: Optional[str] = None, 
               end_date: Optional[str] = None, time_expression: Optional[str] = None, 
               size: Optional[int] = 20, include_images: bool = True,
               venue: Optional[str] = None) -> dict:
    """Get events in Las Vegas using Ticketmaster Discovery API.
    
    Args:
        category (Optional[str], optional): Event category (music, sports, arts, etc.)
        start_date (Optional[str], optional): Start date in YYYY-MM-DD format
        end_date (Optional[str], optional): End date in YYYY-MM-DD format
        time_expression (Optional[str], optional): Natural time expression (e.g., 'this weekend')
        size (Optional[int], optional): Number of events to return (default: 20, max: 100)
        include_images (bool, optional): Whether to include event images. Defaults to True.
        venue (Optional[str], optional): Filter events by venue name
    
    Returns:
        dict: Status and events data or error message
    """
    try:
        # Parse time expression if provided
        if time_expression:
            dates = parse_time_expression(time_expression)
            start_date = dates["start_date"] or start_date
            end_date = dates["end_date"] or end_date

        # Get current time in Vegas timezone
        current_time = datetime.datetime.now(ZoneInfo(VEGAS_LOCATION["timezone_id"]))

        # Get Ticketmaster events
        params = {
            'apikey': TM_API_KEY,
            'city': 'Las Vegas',
            'stateCode': 'NV',
            'sort': 'date,asc',
            'size': size,
            'includePictures': 'yes'
        }

        # Add venue filter if provided
        if venue:
            params['keyword'] = venue

        # Add date filters
        if start_date:
            start_datetime = f"{start_date}T{current_time.strftime('%H:%M:%S')}"
            params['startDateTime'] = f"{start_datetime}Z"
        else:
            params['startDateTime'] = current_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        if end_date:
            end_datetime = f"{end_date}T23:59:59"
            params['endDateTime'] = f"{end_datetime}Z"

        # Add category filter if provided
        if category:
            params['classificationName'] = category

        # Make API request
        response = requests.get(f"{TM_BASE_URL}/events", params=params)
        
        if response.status_code != 200:
            return {
                "status": "error",
                "error_message": f"Ticketmaster API error: {response.status_code}"
            }

        data = response.json()
        if '_embedded' not in data or 'events' not in data['_embedded']:
            return {
                "status": "success",
                "events": [],
                "report": "No events found matching your criteria."
            }

        events = []
        for event in data['_embedded']['events']:
            try:
                # Get venue information
                venues = event.get('_embedded', {}).get('venues', [])
                venue_names = [venue['name'] for venue in venues if 'name' in venue]
                venue_str = ' & '.join(venue_names)
                
                # Format venue with emoji
                formatted_venue = format_venue_type(venue_str)
                
                # Get event time
                start = event.get('dates', {}).get('start', {})
                local_date = start.get('localDate', '')
                local_time = start.get('localTime', '00:00:00')
                
                event_datetime_str = f"{local_date}T{local_time}"
                event_time = datetime.datetime.fromisoformat(event_datetime_str)
                vegas_time = event_time.astimezone(ZoneInfo(VEGAS_LOCATION["timezone_id"]))
                
                # Get price ranges
                price_info = ""
                price_range = None
                if 'priceRanges' in event:
                    ranges = event['priceRanges']
                    min_price = min(r.get('min', 0) for r in ranges)
                    max_price = max(r.get('max', 0) for r in ranges)
                    price_info = f"💰 Tickets: ${min_price:.2f} - ${max_price:.2f}"
                    price_range = {"min": min_price, "max": max_price}
                
                # Get status
                status = event.get('dates', {}).get('status', {}).get('code', '')
                
                # Get images if requested
                images = []
                if include_images:
                    event_images = event.get('images', [])
                    # Filter for medium-sized images
                    medium_images = [
                        img for img in event_images
                        if img.get('width', 0) >= 640 and img.get('width', 0) <= 800
                        and img.get('ratio', '') == '16_9'
                    ]
                    images = medium_images[:2] if medium_images else event_images[:2]
                
                # Create event data
                event_data = {
                    "name": event['name'],
                    "venue": formatted_venue,
                    "datetime": format_datetime(vegas_time),
                    "status": status,
                    "price_range": price_range,
                    "price_info": price_info,
                    "url": event.get('url', ''),
                    "images": images,
                    "source": "Ticketmaster",
                    "type": format_event_category(
                        event.get('classifications', [{}])[0].get('segment', {}).get('name', 'Event')
                    )
                }
                events.append(event_data)
                
            except Exception as e:
                print(f"Error processing event: {str(e)}")
                continue

        # Sort events by date
        events.sort(key=lambda x: x['datetime']['date'])
        
        # Create the report
        if time_expression:
            intro = f"✨ Here's what's happening {time_expression} in Vegas! 🎲\n\n"
        elif start_date == end_date:
            date_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            if date_obj.date() == datetime.datetime.now().date():
                intro = "🌟 Check out what's happening in Vegas today! 🎰\n\n"
            else:
                intro = f"🌟 Here's what's happening in Vegas on {date_obj.strftime('%A, %B %d')}! 🎰\n\n"
        else:
            intro = "✨ Here are some exciting events coming up in Vegas! 🎲\n\n"
        
        report = intro
        
        # Group events by type
        event_types = {}
        for event in events:
            event_type = event.get('type', 'Other Events')
            if event_type not in event_types:
                event_types[event_type] = []
            event_types[event_type].append(event)
        
        # Generate report by type
        for event_type, type_events in event_types.items():
            report += f"\n{event_type}:\n"
            for event in type_events:
                report += f"🎯 {event['name']}\n"
                report += f"📍 {event['venue']}\n"
                report += f"📅 {event['datetime']['datetime']}\n"
                
                if event.get('status'):
                    status_emoji = "🟢" if event['status'].lower() == "onsale" else "🔴" if event['status'].lower() == "offsale" else "🟡"
                    report += f"{status_emoji} Status: {event['status']}\n"
                
                if event.get('price_info'):
                    report += f"{event['price_info']}\n"
                
                report += f"🎫 More info: {event['url']}\n\n"
        
        return {
            "status": "success",
            "events": events[:size] if size else events,
            "report": report
        }
        
    except Exception as e:
        print(f"Error in get_events: {str(e)}")
        return {
            "status": "error",
            "error_message": f"Error getting events data: {str(e)}"
        }

async def initialize_agent():
    """Initializes all agents, including the async ones."""
    # Capture both the agent and the exit_stack
    google_maps_agent, maps_exit_stack = await get_google_maps_agent_async()

    # Define the root agent *inside* this async function
    agent_instance = Agent(
        name="vegas_events_agent",
        model="gemini-2.0-flash",
        description=(
            "I am your Las Vegas Events Assistant, specialized in providing contextually relevant event recommendations "
            "based on real-time conditions and user preferences. My capabilities include:\n\n"
            "1. Smart Event Recommendations:\n"
            "   - Weather-aware event suggestions (indoor/outdoor based on conditions)\n"
            "   - Time-appropriate activity recommendations\n"
            "   - Seasonal and special event awareness\n"
            "   - Venue-specific considerations\n\n"
            "2. Time Intelligence (get_time):\n"
            "   - Real-time Las Vegas time tracking\n"
            "   - Time zone management for event planning\n"
            "   - Business hours consideration\n"
            "   - Peak/off-peak time awareness\n\n"
            "3. Weather Integration (get_weather):\n"
            "   - Current temperature and conditions\n"
            "   - Weather-based activity recommendations\n"
            "   - Indoor/outdoor event filtering\n"
            "   - Weather advisories consideration\n\n"
            "4. Event Discovery (get_events):\n"
            "   - Category-based search (entertainment, sports, arts)\n"
            "   - Time-flexible search ('tonight', 'this weekend')\n"
            "   - Venue-specific event lookup\n"
            "   - Price and availability tracking\n\n"
            "5. Location Services:\n"
            "   - Venue information via Google Maps\n"
            "   - Distance and travel time estimation\n"
            "   - Area-specific event recommendations\n"
            "   - Parking and accessibility information"
        ),
        instruction=(
            "Follow this systematic approach for event recommendations:\n\n"
            "1. Initial Context Gathering:\n"
            "   - Check current time (get_time) to understand timing context\n"
            "   - Review weather conditions (get_weather) for activity suitability\n"
            "   - Consider seasonal factors and special events\n\n"
            "2. Weather-Based Decision Flow:\n"
            "   - For temperatures > 95°F (35°C):\n"
            "     * Prioritize indoor venues and air-conditioned spaces\n"
            "     * Suggest water activities during daytime\n"
            "     * Recommend evening outdoor events\n"
            "   - For temperatures < 50°F (10°C):\n"
            "     * Focus on indoor entertainment\n"
            "     * Highlight heated venue options\n"
            "   - For optimal weather:\n"
            "     * Include outdoor events and activities\n"
            "     * Suggest popular outdoor venues\n\n"
            "3. Time-Based Recommendations:\n"
            "   - Morning (6 AM - 11 AM):\n"
            "     * Breakfast shows and brunches\n"
            "     * Shopping and sightseeing\n"
            "   - Afternoon (11 AM - 5 PM):\n"
            "     * Indoor shows during peak heat\n"
            "     * Pool parties in suitable weather\n"
            "   - Evening (5 PM - 10 PM):\n"
            "     * Dinner shows and performances\n"
            "     * Outdoor events in good weather\n"
            "   - Late Night (10 PM - 6 AM):\n"
            "     * Club events and lounges\n"
            "     * 24-hour venue options\n\n"
            "4. Event Search Strategy (get_events):\n"
            "   - Filter by appropriate category and time\n"
            "   - Consider indoor/outdoor based on weather\n"
            "   - Check venue suitability and accessibility\n"
            "   - Verify pricing and availability\n\n"
            "5. Response Formatting:\n"
            "   - Lead with weather-appropriate suggestions\n"
            "   - Group events by time and category\n"
            "   - Include pricing and booking details\n"
            "   - Add relevant venue information\n"
            "   - Suggest alternatives when needed\n\n"
            "6. Additional Considerations:\n"
            "   - Use Google Maps for venue details and travel planning\n"
            "   - Include backup options for weather changes\n"
            "   - Consider crowd levels at different times\n"
            "   - Check for special events or holidays"
        ),
        tools=[
            agent_tool.AgentTool(agent=google_search_agent),
            agent_tool.AgentTool(agent=google_maps_agent),
            get_time,
            get_weather,
            get_events
        ],
    )
    # Return the root agent instance and the exit_stack
    # Note: If other tools/agents also needed async init with exit_stacks,
    # they would need to be combined here (e.g., using contextlib.AsyncExitStack)
    return agent_instance, maps_exit_stack

# Assign the coroutine object directly. ADK might await this during loading.
root_agent = initialize_agent() 