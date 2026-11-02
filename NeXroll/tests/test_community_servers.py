from backend import community_servers as cs

# servers.json as Typical Nerds published it on 2026-11-01.
SERVERS = [
    {"id": "uk-norwich-1", "name": "UK Server (Fast)",
     "location": {"country": "United Kingdom", "countryCode": "GB", "city": "Norwich"},
     "baseUrl": "https://prerolls.uk", "status": "active", "provider": "EUGameHost"},
    {"id": "uk-newcastle-1", "name": "Home Server (Slow)",
     "location": {"country": "United Kingdom", "countryCode": "GB", "city": "Newcastle Upon Tyne"},
     "baseUrl": "https://home.prerolls.uk", "status": "active", "provider": "TypicalNerds.co.uk"},
]


class _Resp:
    def __init__(self, status, payload=None, error=None):
        self.ok = 200 <= status < 300
        self.status_code = status
        self._payload = payload
        self._error = error

    def json(self):
        if self._error:
            raise self._error
        return self._payload


def test_default_is_the_first_active_server():
    assert cs.default_url(SERVERS) == "https://prerolls.uk"
    later = [dict(SERVERS[0], status="offline"), SERVERS[1]]
    assert cs.default_url(later) == "https://home.prerolls.uk"
    # None marked active: any server with a baseUrl.
    assert cs.default_url([dict(SERVERS[1], status="maintenance")]) == "https://home.prerolls.uk"
    assert cs.default_url(None) is None
    assert cs.default_url([{"name": "no url"}]) is None


def test_nothing_saved_uses_the_default_or_the_fallback():
    assert cs.effective(None, SERVERS) == ("https://prerolls.uk", None)
    assert cs.effective("", None) == (cs.FALLBACK_URL, None)


def test_a_listed_server_that_was_picked_is_used():
    assert cs.effective("https://home.prerolls.uk/", SERVERS) == ("https://home.prerolls.uk", None)
    assert cs.effective("https://HOME.prerolls.uk", SERVERS) == ("https://HOME.prerolls.uk", None)


def test_retired_prerolls_uk_servers_are_set_aside_for_the_default():
    assert cs.effective("https://usa.prerolls.uk", SERVERS) == ("https://prerolls.uk", "https://usa.prerolls.uk")
    # uk.prerolls.uk only redirects to prerolls.uk now.
    assert cs.effective("https://uk.prerolls.uk/", SERVERS) == ("https://prerolls.uk", "https://uk.prerolls.uk")


def test_a_retired_server_is_kept_when_the_list_cannot_be_fetched():
    assert cs.effective("https://usa.prerolls.uk", None) == ("https://usa.prerolls.uk", None)
    assert cs.effective("https://usa.prerolls.uk", []) == ("https://usa.prerolls.uk", None)


def test_a_server_marked_offline_is_set_aside_until_it_is_active_again():
    offline = [SERVERS[0], dict(SERVERS[1], status="offline")]
    assert cs.effective("https://home.prerolls.uk", offline) == ("https://prerolls.uk", "https://home.prerolls.uk")
    assert cs.effective("https://home.prerolls.uk", SERVERS) == ("https://home.prerolls.uk", None)


def test_custom_mirrors_on_other_hosts_are_always_used():
    for url in ("https://prerolls.example.com", "http://192.168.1.20:8080", "https://notprerolls.uk"):
        assert cs.effective(url, SERVERS) == (url, None)


def test_is_official_matches_prerolls_uk_and_its_subdomains_only():
    assert cs.is_official("https://prerolls.uk")
    assert cs.is_official("https://home.prerolls.uk/")
    assert cs.is_official("HTTPS://USA.PREROLLS.UK")
    assert not cs.is_official("https://notprerolls.uk")
    assert not cs.is_official("https://prerolls.uk.example.com")
    assert not cs.is_official("")
    assert not cs.is_official("not a url")


def test_same_server_ignores_case_slashes_and_default_ports():
    assert cs.same_server("https://Prerolls.uk/", "https://prerolls.uk")
    assert not cs.same_server("https://prerolls.uk", "https://home.prerolls.uk")
    assert not cs.same_server("https://prerolls.uk", "http://prerolls.uk")
    assert not cs.same_server("", "")
    assert cs.find("https://home.prerolls.uk/", SERVERS)["name"] == "Home Server (Slow)"
    assert cs.find("https://usa.prerolls.uk", SERVERS) is None


def _main_with(delay):
    return [{**SERVERS[0], "anti-spam": delay}]


def test_download_delay_comes_from_the_server_in_use():
    # "anti-spam" as Typical Nerds added it on the evening of 2026-11-01: strings.
    published = [{**SERVERS[0], "anti-spam": "2"}, {**SERVERS[1], "anti-spam": "5"}]
    assert cs.download_delay("https://prerolls.uk", published) == 2.0
    assert cs.download_delay("https://home.prerolls.uk/", published) == 5.0
    assert cs.download_delay("https://prerolls.uk", _main_with(10)) == 10.0
    assert cs.download_delay("https://prerolls.uk", _main_with(" 1.5 ")) == 1.5
    assert cs.download_delay("https://prerolls.uk", _main_with("0")) == 0.0


def test_download_delay_defaults_to_five_seconds_and_stays_in_range():
    # The list as it was earlier on 2026-11-01, before the field.
    assert cs.download_delay("https://prerolls.uk", SERVERS) == cs.DEFAULT_DOWNLOAD_DELAY == 5.0
    # Custom mirrors and a list that couldn't be fetched.
    assert cs.download_delay("https://prerolls.example.com", _main_with("1")) == 5.0
    assert cs.download_delay("https://prerolls.uk", None) == 5.0
    for bad in (None, "", "fast", "2s", True, [], float("nan"), "nan"):
        assert cs.download_delay("https://prerolls.uk", _main_with(bad)) == 5.0
    assert cs.download_delay("https://prerolls.uk", _main_with("-3")) == 0.0
    assert cs.download_delay("https://prerolls.uk", _main_with("3600")) == cs.MAX_DOWNLOAD_DELAY


def test_fetch_tries_the_home_server_copy_when_the_main_one_fails():
    calls = []

    def get(url, timeout, headers):
        calls.append((url, headers.get("User-Agent")))
        if url.startswith("https://prerolls.uk"):
            raise ConnectionError("down")
        return _Resp(200, {"servers": SERVERS})

    servers, source = cs.fetch(get, {"User-Agent": "NeXRoll/test"})
    assert servers == SERVERS
    assert source == "https://home.prerolls.uk/servers.json"
    assert [c[0] for c in calls] == list(cs.SERVERS_JSON_URLS)
    assert all(ua == "NeXRoll/test" for _, ua in calls)


def test_fetch_skips_errors_bad_json_and_empty_lists():
    answers = iter([_Resp(503), _Resp(200, error=ValueError("not json"))])
    assert cs.fetch(lambda url, timeout, headers: next(answers), {}) == (None, None)

    answers = iter([_Resp(200, {"servers": []}), _Resp(200, {"servers": SERVERS})])
    servers, source = cs.fetch(lambda url, timeout, headers: next(answers), {})
    assert servers == SERVERS and source == cs.SERVERS_JSON_URLS[1]

    assert cs.parse({"servers": [{"name": "no url"}]}) is None
    assert cs.parse(["not", "a", "dict"]) is None
