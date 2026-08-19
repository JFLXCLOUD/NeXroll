from backend.community_filter import filter_ai_prerolls, is_ai_preroll


def test_ai_directory_is_detected_from_current_and_legacy_entries():
    assert is_ai_preroll({"path": "/AI/Clips/generated.mp4"})
    assert is_ai_preroll({"url": "https://uk.prerolls.uk/ai/_Plex/intro.mp4"})
    assert is_ai_preroll({"category": "AI"})
    assert is_ai_preroll({"is_ai": True, "path": "/Community/intro.mp4"})


def test_ai_name_outside_top_level_ai_directory_is_not_misclassified():
    assert not is_ai_preroll({"path": "/Community/Rain/intro.mp4"})
    assert not is_ai_preroll({"path": "/Community/AI Collection/intro.mp4"})


def test_ai_entries_are_excluded_by_default_and_can_be_included():
    regular = {"path": "/Community/regular.mp4"}
    generated = {"path": "/AI/generated.mp4"}

    assert filter_ai_prerolls([regular, generated]) == [regular]
    assert filter_ai_prerolls([regular, generated], include_ai=True) == [regular, generated]
