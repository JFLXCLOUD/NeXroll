"""Community index display titles and duplicate files (backend/community_catalog.py)."""
from backend.community_catalog import (
    clean_title, dedupe, group_versions, platform_of, strip_platform, tidy_titles,
)


# ------------------------------------------------------------------ titles

def test_upload_id_prefix_and_extension_are_removed():
    path = "/Archives/prerolls.video/x/b8507a2a08bd4acbbb71887cabc84f49.Constantin%20Film.mp4"
    assert clean_title(path) == "Constantin Film"


def test_every_video_extension_is_removed_whatever_its_case():
    assert clean_title("/C/Official%20Plex%20Alpha%2030fps.MOV") == "Official Plex Alpha 30fps"
    assert clean_title("/C/THX%20Broadway%20-%20Lossless.webm") == "THX Broadway - Lossless"


def test_apostrophes_written_as_underscores_come_back():
    assert clean_title("/C/Let_s%20All%20Go%20to%20the%20Lobby.mkv") == "Let's All Go to the Lobby"
    assert clean_title("/C/You_Wouldn_t_Download_A_Car.mp4") == "You Wouldn't Download A Car"


def test_uploader_casing_is_kept():
    assert clean_title("/C/Halloween_Pack_V08_Plex_Pre-roll.mp4") == "Halloween Pack V08 Plex Pre-roll"
    assert clean_title("/C/Fallout%2001%20Plex%20Pre-Roll%20%281080p%29.mp4") == "Fallout 01 Plex Pre-Roll (1080p)"


def test_lowercase_names_get_title_case_without_mangling_units():
    assert clean_title("/C/plex_vcr_preroll_4k_hdr_60fps.mp4") == "Plex Vcr Preroll 4K HDR 60fps"
    assert clean_title("/C/july_4th_logo_1080p.mp4") == "July 4th Logo 1080p"


def test_dots_between_words_become_spaces_but_decimals_stay():
    assert clean_title("/C/Mylivewallpapers.Com.Anime.mp4") == "Mylivewallpapers Com Anime"
    assert clean_title("/C/Alpha%2023.976fps.mov") == "Alpha 23.976fps"


def test_a_name_too_short_to_say_anything_borrows_its_folder():
    assert clean_title("/Archives/prerolls.video/Tallies/056abaf319754818b1ebcdf877e8d20a.7.mp4") == "Tallies 7"
    assert clean_title("/Community/x/Shh%20-%20Someone/Shh.mp4") == "Shh"


def test_fallback_when_there_is_no_file_name():
    assert clean_title("", "Stored Title") == "Stored Title"
    assert clean_title("/C/.mp4", "Stored Title") == "Stored Title"


def test_tidy_titles_rewrites_in_place():
    entries = [{"path": "/C/my_intro.mp4", "title": "My Intro"}, {"id": "/C/Two.mkv", "title": "Two"}]
    tidy_titles(entries)
    assert [e["title"] for e in entries] == ["My Intro", "Two"]


# -------------------------------------------------------------- duplicates

def e(path, size, category="Community"):
    return {"id": path, "path": path, "size_bytes": size, "category": category}


def test_archive_copy_is_folded_into_the_other_folder():
    archived = e("/Archives/old/intro.mp4", 1000, "Archives")
    current = e("/Community/x/intro.mp4", 1000)
    out = dedupe([archived, current])
    assert [x["path"] for x in out] == ["/Community/x/intro.mp4"]
    assert out[0]["duplicate_ids"] == ["/Archives/old/intro.mp4"]


def test_lengths_must_agree_when_known():
    a, b = e("/C/a.mp4", 1000), e("/C/b.mp4", 1000)
    assert len(dedupe([a, b], {"/C/a.mp4": 10.0, "/C/b.mp4": 12.0})) == 2
    assert len(dedupe([a, b], {"/C/a.mp4": 10.0, "/C/b.mp4": 10.01})) == 1
    assert len(dedupe([a, b], {"/C/a.mp4": 10.0})) == 1  # one length not read yet


def test_different_extension_or_size_or_no_size_is_not_a_duplicate():
    assert len(dedupe([e("/C/a.mp4", 1000), e("/C/a.mkv", 1000)])) == 2
    assert len(dedupe([e("/C/a.mp4", 1000), e("/C/b.mp4", 1001)])) == 2
    assert len(dedupe([e("/C/a.mp4", None), e("/C/b.mp4", None)])) == 2


def test_order_is_kept_and_untouched_entries_are_the_same_objects():
    first, dup, other = e("/C/one.mp4", 5), e("/C/one-copy.mp4", 5), e("/C/two.mp4", 6)
    out = dedupe([first, other, dup])
    assert [x["path"] for x in out] == ["/C/one.mp4", "/C/two.mp4"]
    assert out[1] is other
    assert "duplicate_ids" not in first  # the input dict is not modified


def test_three_copies_list_both_others():
    copies = [e("/Archives/a.mp4", 9, "Archives"), e("/Holidays/a.mp4", 9, "Holidays"), e("/Archives/b.mp4", 9, "Archives")]
    out = dedupe(copies)
    assert len(out) == 1 and out[0]["path"] == "/Holidays/a.mp4"
    assert sorted(out[0]["duplicate_ids"]) == ["/Archives/a.mp4", "/Archives/b.mp4"]


# ------------------------------------------------------- platform versions


def v(path, title, size=1, modified=0):
    return {"id": path, "path": path, "title": title, "size_bytes": size, "modified_time": modified}


def test_platform_comes_from_the_name_then_the_nearest_folder():
    assert platform_of(v("/C/X - A/X Jellyfin.mp4", "")) == "jellyfin"
    assert platform_of(v("/Community/_Emby/X - A/X.mp4", "")) == "emby"
    assert platform_of(v("/Archives/TN/Plex-2022/General/Car.mp4", "")) == "plex"
    assert platform_of(v("/Community/Bird%20Plexus%20-%20A/Bird%20Plexus.mp4", "")) is None
    assert platform_of(v("/Community/x/Intro.mp4", "")) is None


def test_side_by_side_versions_become_one_row():
    rows = group_versions([
        v("/C/Adult%20Swim%20-%20A/Adult%20Swim%20Emby%20v2.mp4", "Adult Swim Emby v2"),
        v("/C/Adult%20Swim%20-%20A/Adult%20Swim%20Plex%20v2.mp4", "Adult Swim Plex v2", modified=5),
        v("/C/Adult%20Swim%20-%20A/Adult%20Swim%20Jellyfin%20v2.mp4", "Adult Swim Jellyfin v2"),
        v("/C/Adult%20Swim%20-%20A/Adult%20Swim%20Plex.mp4", "Adult Swim Plex"),
    ])
    assert [r["title"] for r in rows] == ["Adult Swim v2", "Adult Swim Plex"]
    assert [x["platform"] for x in rows[0]["versions"]] == ["plex", "jellyfin", "emby"]
    assert rows[0]["path"].endswith("Plex%20v2.mp4")       # the row is the preferred version
    assert rows[0]["modified_time"] == 5                    # newest of its versions
    assert "versions" not in rows[1]                        # no counterpart: unchanged


def test_versions_in_sibling_platform_folders_group():
    rows = group_versions([
        v("/Community/_Plex/Sky%20-%20K/Sky%20-%20Plex.mp4", "Sky - Plex"),
        v("/Community/_Jellyfin/Sky%20-%20K/Sky%20-%20Jellyfin.mp4", "Sky - Jellyfin"),
    ])
    assert len(rows) == 1 and rows[0]["title"] == "Sky"


def test_the_users_servers_decide_which_version_leads():
    entries = [v("/C/X/X Plex.mp4", "X Plex"), v("/C/X/X Jellyfin.mp4", "X Jellyfin"), v("/C/X/X Emby.mp4", "X Emby")]
    rows = group_versions(entries, prefer=["jellyfin", "plex"])
    assert rows[0]["id"] == "/C/X/X Jellyfin.mp4"
    assert [x["platform"] for x in rows[0]["versions"]] == ["jellyfin", "plex", "emby"]
    assert group_versions(entries, prefer=["emby"])[0]["id"] == "/C/X/X Emby.mp4"


def test_different_cuts_or_a_second_file_per_platform_stay_apart():
    rows = group_versions([v("/C/G/Gravity Plex_1080p.mp4", "Gravity Plex 1080p"),
                           v("/C/G/Gravity Plex_4K.mp4", "Gravity Plex 4K")])
    assert len(rows) == 2 and not any("versions" in r for r in rows)
    rows = group_versions([v("/C/X/X Plex.mp4", "X Plex"), v("/C/X/X Plex.mkv", "X Plex"),
                           v("/C/X/X Emby.mp4", "X Emby")])
    assert len(rows) == 2 and len(rows[0]["versions"]) == 2 and rows[1]["path"] == "/C/X/X Plex.mkv"


def test_copies_of_a_version_are_carried_on_it():
    plex = dict(v("/C/X/X Plex.mp4", "X Plex"), duplicate_ids=["/Archives/X Plex.mp4"])
    rows = group_versions([plex, v("/C/X/X Emby.mp4", "X Emby")])
    assert rows[0]["versions"][0]["duplicate_ids"] == ["/Archives/X Plex.mp4"]


def test_strip_platform_tidies_what_is_left():
    assert strip_platform("Sky Showtime - Jellyfin") == "Sky Showtime"
    assert strip_platform("Aurora - Plex - Feature Presentation") == "Aurora - Feature Presentation"
    assert strip_platform("Lobby Plex (1080p)") == "Lobby (1080p)"
    assert strip_platform("Intro (Plex)") == "Intro"
    assert strip_platform("Plex") == "Plex"
