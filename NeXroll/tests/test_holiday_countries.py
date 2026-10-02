"""The holiday country dropdown lists countries alphabetically by name.

Nager.Date returns them ordered by ISO code, so the dropdown showed
Switzerland (CH) among the C's and the United Kingdom (GB) among the G's.
"""

import unittest
from unittest.mock import Mock, patch

from backend.holiday_api import HolidayAPI

# A slice of Nager.Date's AvailableCountries, in its own (ISO code) order.
API_ORDER = [("CH", "Switzerland"), ("CI", "Ivory Coast"), ("DE", "Germany"), ("GB", "United Kingdom"),
             ("AX", "Åland Islands"), ("TR", "Türkiye"), ("TT", "Trinidad and Tobago"), ("CW", "Curaçao"),
             ("CU", "Cuba"), ("za", "south africa")]


class CountryOrderTests(unittest.TestCase):
    def setUp(self):
        HolidayAPI._countries_cache = {"data": None, "timestamp": 0.0}
        self.addCleanup(setattr, HolidayAPI, "_countries_cache", {"data": None, "timestamp": 0.0})

    def names(self):
        return [c["name"] for c in HolidayAPI.get_available_countries()]

    def test_api_countries_are_sorted_by_name_ignoring_accents_and_case(self):
        response = Mock(status_code=200)
        response.json.return_value = [{"countryCode": code, "name": name} for code, name in API_ORDER]
        with patch("backend.holiday_api.requests.get", return_value=response):
            self.assertEqual(self.names(), [
                "Åland Islands", "Cuba", "Curaçao", "Germany", "Ivory Coast", "south africa",
                "Switzerland", "Trinidad and Tobago", "Türkiye", "United Kingdom"])

    def test_offline_fallback_is_sorted_too(self):
        with patch("backend.holiday_api.requests.get", side_effect=OSError("offline")):
            names = self.names()
        self.assertEqual(names, sorted(names, key=str.casefold))
        self.assertEqual(len(names), len(HolidayAPI.SUPPORTED_COUNTRIES))


if __name__ == "__main__":
    unittest.main()
