"""
Holiday API Integration for NeXroll
Provides automatic holiday detection and scheduling using external calendar APIs
"""

import requests
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


class HolidayAPI:
    """
    Integrates with Nager.Date API (https://date.nager.at/)
    Free, no authentication required, supports 100+ countries
    """
    
    BASE_URL = "https://date.nager.at/api/v3"
    
    # Map of supported countries with their ISO codes
    SUPPORTED_COUNTRIES = {
        "US": "United States",
        "CA": "Canada",
        "GB": "United Kingdom",
        "AU": "Australia",
        "NZ": "New Zealand",
        "DE": "Germany",
        "FR": "France",
        "ES": "Spain",
        "IT": "Italy",
        "MX": "Mexico",
        "BR": "Brazil",
        "AR": "Argentina",
        "CN": "China",
        "JP": "Japan",
        "KR": "South Korea",
        "IN": "India",
        "IL": "Israel",
        "ZA": "South Africa",
        "IE": "Ireland",
        "NL": "Netherlands",
        "BE": "Belgium",
        "CH": "Switzerland",
        "AT": "Austria",
        "SE": "Sweden",
        "NO": "Norway",
        "DK": "Denmark",
        "FI": "Finland",
        "PL": "Poland",
        "RU": "Russia",
        "GR": "Greece",
        "PT": "Portugal",
        # Add more as needed
    }
    
    # Holiday name mappings for common variations
    HOLIDAY_ALIASES = {
        "Christmas Day": ["Christmas", "Xmas", "Christmas Eve"],
        "New Year's Day": ["New Year", "New Years"],
        "Halloween": ["All Hallows Eve", "Samhain"],
        "Thanksgiving": ["Thanksgiving Day"],
        "Easter": ["Easter Sunday", "Easter Monday"],
        "Valentine's Day": ["Saint Valentine's Day"],
        "Independence Day": ["Fourth of July", "4th of July"],
        "Christmas Eve": ["Christmas"],
        "New Year's Eve": ["New Year"],
        "Hanukkah": ["Chanukah", "Hanukah"],
        "Chinese New Year": ["Lunar New Year", "Spring Festival"],
        "Diwali": ["Deepavali", "Festival of Lights"],
        "Kwanzaa": ["Kwanza"],
    }
    
    @staticmethod
    @lru_cache(maxsize=32)
    def get_available_countries() -> List[Dict[str, str]]:
        """
        Fetch list of available countries from API
        Returns: [{"countryCode": "US", "name": "United States"}, ...]
        """
        try:
            response = requests.get(f"{HolidayAPI.BASE_URL}/AvailableCountries", timeout=5)
            if response.status_code == 200:
                countries = response.json()
                return [
                    {"countryCode": c["countryCode"], "name": c["name"]}
                    for c in countries
                ]
            return [{"countryCode": k, "name": v} for k, v in HolidayAPI.SUPPORTED_COUNTRIES.items()]
        except Exception as e:
            logger.error(f"Failed to fetch countries from API: {e}")
            return [{"countryCode": k, "name": v} for k, v in HolidayAPI.SUPPORTED_COUNTRIES.items()]
    
    @staticmethod
    @lru_cache(maxsize=128)
    def get_holidays(country_code: str, year: int) -> List[Dict]:
        """
        Fetch holidays for a specific country and year
        
        Args:
            country_code: ISO 3166-1 alpha-2 code (e.g., "US", "CA")
            year: Year to fetch holidays for
            
        Returns:
            List of holiday dictionaries with keys:
            - name: Holiday name
            - date: Date string (YYYY-MM-DD)
            - local_name: Local language name
            - country_code: Country code
            - fixed: Boolean (if holiday is on fixed date)
            - global: Boolean (if observed nationwide)
            - type: "Public", "Bank", "School", "Authorities", "Optional", "Observance"
        """
        try:
            response = requests.get(
                f"{HolidayAPI.BASE_URL}/PublicHolidays/{year}/{country_code}",
                timeout=5
            )
            
            if response.status_code == 200:
                holidays = response.json()
                
                # Enrich with date parsing and ensure consistent field names
                for holiday in holidays:
                    try:
                        holiday_date = datetime.strptime(holiday["date"], "%Y-%m-%d").date()
                        holiday["month"] = holiday_date.month
                        holiday["day"] = holiday_date.day
                        holiday["date_obj"] = holiday_date
                    except Exception:
                        pass
                    
                    # Ensure types is an array (Nager API returns this already)
                    if "types" not in holiday:
                        holiday["types"] = ["Public"] if holiday.get("global", False) else ["Observance"]
                
                return holidays
            else:
                logger.warning(f"API returned status {response.status_code} for {country_code}/{year}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to fetch holidays for {country_code}/{year}: {e}")
            return []
    
    @staticmethod
    def get_multi_day_holidays(country_code: str, year: int) -> List[Dict]:
        """
        Get holidays that span multiple days (like Hanukkah, Kwanzaa)
        Uses special logic and fallback data since API only returns single dates
        
        Returns: List with start_date, end_date, duration
        """
        holidays = HolidayAPI.get_holidays(country_code, year)
        multi_day = []
        
        for holiday in holidays:
            # Check if holiday is known to span multiple days
            duration_days = 1  # Default
            
            # Hanukkah (8 days)
            if "hanukkah" in holiday["name"].lower() or "chanukah" in holiday["name"].lower():
                duration_days = 8
            
            # Kwanzaa (7 days, Dec 26 - Jan 1)
            elif "kwanzaa" in holiday["name"].lower():
                duration_days = 7
            
            # Diwali (5 days)
            elif "diwali" in holiday["name"].lower() or "deepavali" in holiday["name"].lower():
                duration_days = 5
            
            # Christmas season (many regions celebrate Dec 24-26)
            elif "christmas" in holiday["name"].lower() and "eve" not in holiday["name"].lower():
                # Check if there's a Christmas Eve nearby
                duration_days = 2  # Christmas Day + Boxing Day typically
            
            if duration_days > 1 and "date_obj" in holiday:
                from datetime import timedelta
                start_date = holiday["date_obj"]
                end_date = start_date + timedelta(days=duration_days - 1)
                
                multi_day.append({
                    "name": holiday["name"],
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "start_month": start_date.month,
                    "start_day": start_date.day,
                    "end_month": end_date.month,
                    "end_day": end_date.day,
                    "duration_days": duration_days,
                    "description": f"{holiday['name']} ({duration_days} days)",
                    "type": holiday.get("type", "Public"),
                    "country_code": country_code
                })
        
        return multi_day
    
    @staticmethod
    def search_holiday_by_name(name: str, country_code: str, year: int) -> Optional[Dict]:
        """
        Find a specific holiday by name (supports aliases)
        """
        holidays = HolidayAPI.get_holidays(country_code, year)
        name_lower = name.lower()
        
        # Direct match
        for holiday in holidays:
            if name_lower in holiday["name"].lower():
                return holiday
        
        # Check aliases
        for canonical_name, aliases in HolidayAPI.HOLIDAY_ALIASES.items():
            if any(alias.lower() == name_lower for alias in aliases):
                for holiday in holidays:
                    if canonical_name.lower() in holiday["name"].lower():
                        return holiday
        
        return None
    
    @staticmethod
    def get_next_occurrence(holiday_name: str, country_code: str) -> Optional[Tuple[date, str]]:
        """
        Get the next occurrence of a holiday
        Returns: (date, description) or None
        """
        current_year = datetime.now().year
        today = date.today()
        
        # Check current year and next year
        for year in [current_year, current_year + 1]:
            holiday = HolidayAPI.search_holiday_by_name(holiday_name, country_code, year)
            if holiday and "date_obj" in holiday:
                if holiday["date_obj"] >= today:
                    return holiday["date_obj"], holiday["name"]
        
        return None
    
    @staticmethod
    def get_holidays_by_month(country_code: str, year: int, month: int) -> List[Dict]:
        """
        Get all holidays in a specific month
        """
        all_holidays = HolidayAPI.get_holidays(country_code, year)
        return [h for h in all_holidays if h.get("month") == month]
    
    @staticmethod
    def suggest_schedule_dates(holiday_name: str, country_code: str, 
                               years: List[int] = None) -> List[Dict]:
        """
        Generate schedule date suggestions for a holiday across multiple years
        Useful for creating recurring yearly schedules
        
        Returns: [{"year": 2024, "date": "2024-12-25", "month": 12, "day": 25}, ...]
        """
        if years is None:
            current_year = datetime.now().year
            years = [current_year + i for i in range(3)]  # Current + next 2 years
        
        suggestions = []
        for year in years:
            holiday = HolidayAPI.search_holiday_by_name(holiday_name, country_code, year)
            if holiday and "date_obj" in holiday:
                suggestions.append({
                    "year": year,
                    "date": holiday["date"],
                    "month": holiday["month"],
                    "day": holiday["day"],
                    "name": holiday["name"],
                    "type": holiday.get("type", "Public")
                })
        
        return suggestions
    
    @staticmethod
    def is_api_available() -> bool:
        """
        Check if the holiday API is accessible
        """
        try:
            response = requests.get(f"{HolidayAPI.BASE_URL}/AvailableCountries", timeout=3)
            return response.status_code == 200
        except Exception:
            return False


# Fallback data for common holidays (used if API is unavailable)
FALLBACK_HOLIDAYS = {
    "US": {
        "New Year's Day": {"month": 1, "day": 1, "type": "fixed"},
        "Martin Luther King Jr. Day": {"month": 1, "day": "third_monday", "type": "variable"},
        "Valentine's Day": {"month": 2, "day": 14, "type": "fixed"},
        "Presidents' Day": {"month": 2, "day": "third_monday", "type": "variable"},
        "St. Patrick's Day": {"month": 3, "day": 17, "type": "fixed"},
        "Easter": {"month": "variable", "type": "lunar"},
        "Memorial Day": {"month": 5, "day": "last_monday", "type": "variable"},
        "Independence Day": {"month": 7, "day": 4, "type": "fixed"},
        "Labor Day": {"month": 9, "day": "first_monday", "type": "variable"},
        "Halloween": {"month": 10, "day": 31, "type": "fixed"},
        "Thanksgiving": {"month": 11, "day": "fourth_thursday", "type": "variable"},
        "Christmas": {"month": 12, "day": 25, "type": "fixed"},
        "Hanukkah": {"month": "variable", "type": "lunar"},
        "Kwanzaa": {"month": 12, "day": 26, "duration": 7, "type": "fixed"},
    },
    "CA": {
        "New Year's Day": {"month": 1, "day": 1, "type": "fixed"},
        "Valentine's Day": {"month": 2, "day": 14, "type": "fixed"},
        "Easter": {"month": "variable", "type": "lunar"},
        "Victoria Day": {"month": 5, "day": "monday_before_25", "type": "variable"},
        "Canada Day": {"month": 7, "day": 1, "type": "fixed"},
        "Labour Day": {"month": 9, "day": "first_monday", "type": "variable"},
        "Thanksgiving": {"month": 10, "day": "second_monday", "type": "variable"},
        "Halloween": {"month": 10, "day": 31, "type": "fixed"},
        "Remembrance Day": {"month": 11, "day": 11, "type": "fixed"},
        "Christmas": {"month": 12, "day": 25, "type": "fixed"},
        "Boxing Day": {"month": 12, "day": 26, "type": "fixed"},
    }
}


def get_fallback_holiday(country_code: str, holiday_name: str, year: int) -> Optional[Dict]:
    """
    Get holiday data from fallback database when API is unavailable
    """
    if country_code not in FALLBACK_HOLIDAYS:
        return None
    
    holidays = FALLBACK_HOLIDAYS[country_code]
    if holiday_name not in holidays:
        return None
    
    holiday_data = holidays[holiday_name]
    
    # Handle fixed dates
    if holiday_data["type"] == "fixed":
        return {
            "name": holiday_name,
            "month": holiday_data["month"],
            "day": holiday_data["day"],
            "date": f"{year}-{holiday_data['month']:02d}-{holiday_data['day']:02d}",
            "type": "Public",
            "country_code": country_code,
            "source": "fallback"
        }
    
    # For variable dates, return None (would need complex calculation)
    return None
