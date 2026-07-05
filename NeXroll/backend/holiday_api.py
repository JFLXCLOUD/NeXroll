"""
Holiday API Integration for NeXroll
Provides automatic holiday detection and scheduling using external calendar APIs
"""

import requests
import time
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class HolidayAPI:
    """
    Integrates with Nager.Date API (https://date.nager.at/)
    Free, no authentication required, supports 100+ countries
    """
    
    BASE_URL = "https://date.nager.at/api/v3"

    # Cache TTL: holiday data for a given country/year essentially never changes,
    # but we still refresh periodically rather than caching forever. A bare
    # process-lifetime cache (e.g. functools.lru_cache) would permanently store
    # whatever the FIRST call returned - including a transient network failure's
    # empty-list result - for the rest of the app's uptime. These caches instead
    # track a timestamp and, on a failed refresh, keep serving the last known-good
    # data rather than replacing it with an empty/fallback result.
    CACHE_TTL_SECONDS = 24 * 60 * 60
    _countries_cache: Dict[str, object] = {"data": None, "timestamp": 0.0}
    _holidays_cache: Dict[Tuple[str, int], Dict[str, object]] = {}

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
    # Each alias string must map to exactly one canonical holiday - having the
    # same alias (e.g. "Christmas" / "New Year") point at two different
    # canonical entries made the match depend on dict/API list ordering.
    HOLIDAY_ALIASES = {
        "Christmas Day": ["Christmas", "Xmas"],
        "Christmas Eve": ["Xmas Eve"],
        "New Year's Day": ["New Year", "New Years"],
        "New Year's Eve": ["NYE"],
        "Halloween": ["All Hallows Eve", "Samhain"],
        "Thanksgiving": ["Thanksgiving Day"],
        "Easter": ["Easter Sunday"],
        "Valentine's Day": ["Saint Valentine's Day"],
        "Independence Day": ["Fourth of July", "4th of July"],
        "Hanukkah": ["Chanukah", "Hanukah"],
        "Chinese New Year": ["Lunar New Year", "Spring Festival"],
        "Diwali": ["Deepavali", "Festival of Lights"],
        "Kwanzaa": ["Kwanza"],
    }

    # Holidays whose calendar date never actually changes, keyed by country
    # then lowercased holiday name. Nager.Date (and government calendars
    # generally) return the "observed" date instead of the real one when a
    # fixed holiday falls on a weekend - e.g. Independence Day 2026 falls on
    # a Saturday, so Nager.Date's `date` field for it is "2026-07-03" (the
    # preceding Friday), with no separate field exposing the real July 4.
    # That's correct for "which day is the office closed," but wrong for
    # "which day is the holiday" scheduling - so get_holidays() overrides the
    # date back to the true month/day for any holiday listed here. Holidays
    # that are genuinely weekday-defined (Thanksgiving, MLK Day, Easter, etc.)
    # are deliberately not listed - their API-reported date IS the actual day.
    FIXED_HOLIDAY_DATES = {
        "US": {
            "new year's day": (1, 1),
            "valentine's day": (2, 14),
            "st. patrick's day": (3, 17),
            "juneteenth national independence day": (6, 19),
            "independence day": (7, 4),
            "halloween": (10, 31),
            "veterans day": (11, 11),
            "christmas day": (12, 25),
        },
        "CA": {
            "new year's day": (1, 1),
            "valentine's day": (2, 14),
            "canada day": (7, 1),
            "halloween": (10, 31),
            "remembrance day": (11, 11),
            "christmas day": (12, 25),
            "boxing day": (12, 26),
        },
    }


    @staticmethod
    def get_available_countries() -> List[Dict[str, str]]:
        """
        Fetch list of available countries from API
        Returns: [{"countryCode": "US", "name": "United States"}, ...]
        """
        cached = HolidayAPI._countries_cache
        if cached["data"] is not None and (time.time() - cached["timestamp"]) < HolidayAPI.CACHE_TTL_SECONDS:
            return cached["data"]

        try:
            response = requests.get(f"{HolidayAPI.BASE_URL}/AvailableCountries", timeout=5)
            if response.status_code == 200:
                countries = [
                    {"countryCode": c["countryCode"], "name": c["name"]}
                    for c in response.json()
                ]
                HolidayAPI._countries_cache = {"data": countries, "timestamp": time.time()}
                return countries
            logger.warning(f"AvailableCountries API returned status {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to fetch countries from API: {e}")

        # Refresh failed - serve the last known-good data if we have any,
        # rather than permanently downgrading to the ~30-country static list.
        if cached["data"] is not None:
            return cached["data"]
        return [{"countryCode": k, "name": v} for k, v in HolidayAPI.SUPPORTED_COUNTRIES.items()]

    @staticmethod
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
            - localName: Local language name
            - countryCode: Country code
            - fixed: Boolean (if holiday is on fixed date)
            - global: Boolean (if observed nationwide)
            - type: "Public", "Bank", "School", "Authorities", "Optional", "Observance"
        """
        cache_key = (country_code, year)
        cached = HolidayAPI._holidays_cache.get(cache_key)
        if cached and (time.time() - cached["timestamp"]) < HolidayAPI.CACHE_TTL_SECONDS:
            return cached["data"]

        try:
            response = requests.get(
                f"{HolidayAPI.BASE_URL}/PublicHolidays/{year}/{country_code}",
                timeout=5
            )

            if response.status_code == 200:
                holidays = response.json()

                # Enrich with date parsing and ensure consistent field names
                fixed_dates = HolidayAPI.FIXED_HOLIDAY_DATES.get(country_code.upper(), {})
                for holiday in holidays:
                    try:
                        holiday_date = datetime.strptime(holiday["date"], "%Y-%m-%d").date()
                        holiday["month"] = holiday_date.month
                        holiday["day"] = holiday_date.day
                        holiday["date_obj"] = holiday_date
                    except Exception:
                        pass

                    # Correct known fixed-calendar holidays back to their real
                    # date if the API reported an "observed" (weekend-shifted)
                    # date instead - see FIXED_HOLIDAY_DATES above.
                    true_md = fixed_dates.get(holiday.get("name", "").lower())
                    if true_md:
                        try:
                            true_date = date(year, true_md[0], true_md[1])
                            if holiday.get("date_obj") != true_date:
                                holiday["observed_date"] = holiday["date"]
                                holiday["date"] = true_date.strftime("%Y-%m-%d")
                                holiday["month"] = true_date.month
                                holiday["day"] = true_date.day
                                holiday["date_obj"] = true_date
                            holiday["fixed"] = True
                        except ValueError:
                            pass  # e.g. Feb 29 fallback safety, shouldn't occur for this table

                    # Ensure types is an array (Nager API returns this already)
                    if "types" not in holiday:
                        holiday["types"] = ["Public"] if holiday.get("global", False) else ["Observance"]

                HolidayAPI._holidays_cache[cache_key] = {"data": holidays, "timestamp": time.time()}
                return holidays
            else:
                logger.warning(f"API returned status {response.status_code} for {country_code}/{year}")
        except Exception as e:
            logger.error(f"Failed to fetch holidays for {country_code}/{year}: {e}")

        # Refresh failed - serve the last known-good data if we have any, rather
        # than returning an empty list that would then get treated as "no
        # holidays this year" (and, upstream, as "holiday not found" for every
        # holiday-linked schedule in this country until the next successful fetch).
        if cached:
            return cached["data"]
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
        Find a specific holiday by name (supports aliases).

        Tries an exact (case-insensitive) match on name/localName first -
        this is the path used for holiday_name values already resolved via
        the Holiday Browser or an exact API name, and must be unambiguous
        (e.g. a schedule named "Christmas" must not resolve to "Christmas Eve"
        just because one happens to come first in the API's response).
        Substring matching is only used as a last-resort fallback for
        free-typed/partial names.
        """
        holidays = HolidayAPI.get_holidays(country_code, year)
        name_lower = name.lower().strip()

        # 1. Exact match on name or localName
        for holiday in holidays:
            if holiday.get("name", "").lower() == name_lower or holiday.get("localName", "").lower() == name_lower:
                return holiday

        # 2. Alias match (exact alias -> canonical name, exact match against holidays)
        for canonical_name, aliases in HolidayAPI.HOLIDAY_ALIASES.items():
            if any(alias.lower() == name_lower for alias in aliases):
                for holiday in holidays:
                    if holiday.get("name", "").lower() == canonical_name.lower():
                        return holiday

        # 3. Substring fallback (best-effort; may be ambiguous if multiple
        #    holidays share a common substring, but better than nothing for
        #    free-text search queries)
        for holiday in holidays:
            if name_lower in holiday.get("name", "").lower():
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
