from types import SimpleNamespace

from backend.dynamic_preroll import (
    DynamicPrerollGenerator,
    resolve_dynamic_audio_mode,
    resolve_dynamic_font_scale,
    resolve_dynamic_text_color,
    resolve_render_settings,
)


def test_resolve_render_settings_maps_user_options_to_encoder_values():
    profile = resolve_render_settings('2160p', 60, 'master')

    assert profile == {
        'resolution': '2160',
        'width': 3840,
        'height': 2160,
        'frame_rate': 60,
        'quality': 'master',
        'label': 'Master',
        'preset': 'slower',
        'crf': 12,
        'audio_bitrate': '320k',
    }


def test_resolve_render_settings_uses_safe_defaults_for_unknown_values():
    profile = resolve_render_settings('cinema', 48, 'lossless')

    assert (profile['width'], profile['height']) == (1920, 1080)
    assert profile['frame_rate'] == 30
    assert profile['quality'] == 'balanced'


def test_dynamic_font_scale_is_safely_bounded():
    assert resolve_dynamic_font_scale(0.85) == 0.85
    assert resolve_dynamic_font_scale(1.3) == 1.3
    assert resolve_dynamic_font_scale(0.2) == 0.85
    assert resolve_dynamic_font_scale(4) == 1.3
    assert resolve_dynamic_font_scale('large') == 1.0


def test_dynamic_theme_catalog_includes_motion_metadata():
    themes = DynamicPrerollGenerator.COLOR_THEMES

    assert themes['aurora_drift']['effect'] == 'aurora'
    assert themes['neon_city']['effect'] == 'cyber_grid'
    assert themes['deep_space']['featured'] is True


def test_dynamic_text_colors_and_audio_modes_use_safe_values():
    assert resolve_dynamic_text_color('#A1B2C3') == '#a1b2c3'
    assert resolve_dynamic_text_color('red') is None
    assert resolve_dynamic_text_color('color(display-p3 1 0 0)') is None
    assert resolve_dynamic_audio_mode('DEFAULT') == 'default'
    assert resolve_dynamic_audio_mode('custom') == 'custom'
    assert resolve_dynamic_audio_mode('surprise') == 'none'


def test_generate_from_image_applies_selected_render_profile(tmp_path, monkeypatch):
    generator = DynamicPrerollGenerator.__new__(DynamicPrerollGenerator)
    generator.output_dir = tmp_path
    generator.ffmpeg_path = 'ffmpeg'
    monkeypatch.setattr(generator, 'is_available', lambda: True)
    captured = {}

    def fake_run(command, **_kwargs):
        captured['command'] = command
        (tmp_path / 'studio.mp4').write_bytes(b'video')
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr('backend.dynamic_preroll.subprocess.run', fake_run)
    soundtrack = tmp_path / 'soundtrack.mp3'
    soundtrack.write_bytes(b'audio')

    result = generator.generate_from_image(
        image_data=b'png',
        output_filename='studio.mp4',
        width=3840,
        height=2160,
        frame_rate=60,
        video_preset='slower',
        video_crf=12,
        audio_bitrate='320k',
        audio_path=str(soundtrack),
    )

    command = captured['command']
    assert result == str(tmp_path / 'studio.mp4')
    assert command[command.index('-framerate') + 1] == '60'
    assert command[command.index('-preset') + 1] == 'slower'
    assert command[command.index('-crf') + 1] == '12'
    assert command[command.index('-level') + 1] == '5.2'
    assert command[command.index('-b:a') + 1] == '320k'
    assert command[command.index('-stream_loop') + 1] == '-1'
    assert 'afade=t=in' in command[command.index('-filter_complex') + 1]


def test_generate_from_video_preserves_browser_motion_and_normalizes_output(tmp_path, monkeypatch):
    generator = DynamicPrerollGenerator.__new__(DynamicPrerollGenerator)
    generator.output_dir = tmp_path
    generator.ffmpeg_path = 'ffmpeg'
    monkeypatch.setattr(generator, 'is_available', lambda: True)
    captured = {}

    def fake_run(command, **_kwargs):
        captured['command'] = command
        (tmp_path / 'motion.mp4').write_bytes(b'video')
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr('backend.dynamic_preroll.subprocess.run', fake_run)

    result = generator.generate_from_video(
        video_data=b'webm-motion',
        duration=5,
        output_filename='motion.mp4',
        width=1920,
        height=1080,
        frame_rate=30,
        video_preset='slow',
        video_crf=15,
        audio_bitrate='256k',
    )

    command = captured['command']
    filter_graph = command[command.index('-filter_complex') + 1]
    assert result == str(tmp_path / 'motion.mp4')
    assert 'scale=1920:1080:flags=lanczos' in filter_graph
    assert 'fps=30' in filter_graph
    assert 'trim=duration=5' in filter_graph
    assert 'fade=' not in filter_graph
    assert command[command.index('-preset') + 1] == 'slow'
    assert command[command.index('-crf') + 1] == '15'
    assert '-an' in command
    assert '-b:a' not in command


def test_generate_from_video_loops_and_fades_selected_soundtrack(tmp_path, monkeypatch):
    generator = DynamicPrerollGenerator.__new__(DynamicPrerollGenerator)
    generator.output_dir = tmp_path
    generator.ffmpeg_path = 'ffmpeg'
    monkeypatch.setattr(generator, 'is_available', lambda: True)
    soundtrack = tmp_path / 'custom.wav'
    soundtrack.write_bytes(b'audio')
    captured = {}

    def fake_run(command, **_kwargs):
        captured['command'] = command
        (tmp_path / 'motion-with-audio.mp4').write_bytes(b'video')
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr('backend.dynamic_preroll.subprocess.run', fake_run)

    result = generator.generate_from_video(
        video_data=b'webm-motion',
        duration=5,
        output_filename='motion-with-audio.mp4',
        audio_path=str(soundtrack),
    )

    command = captured['command']
    filter_graph = command[command.index('-filter_complex') + 1]
    assert result == str(tmp_path / 'motion-with-audio.mp4')
    assert command[command.index('-stream_loop') + 1] == '-1'
    assert str(soundtrack) in command
    assert 'atrim=duration=5' in filter_graph
    assert 'afade=t=in' in filter_graph
    assert 'afade=t=out' in filter_graph
    assert '-c:a' in command


def test_coming_soon_encoder_scales_design_canvas_with_selected_profile(tmp_path, monkeypatch):
    generator = DynamicPrerollGenerator.__new__(DynamicPrerollGenerator)
    generator.output_dir = tmp_path
    generator.ffmpeg_path = 'ffmpeg'
    monkeypatch.setattr(generator, '_get_coming_soon_audio_path', lambda **_kwargs: None)
    captured = {}

    def fake_run(command, **_kwargs):
        captured['command'] = command
        (tmp_path / 'coming-soon.mp4').write_bytes(b'video')
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr('backend.dynamic_preroll.subprocess.run', fake_run)

    result = generator._run_ffmpeg_vignette_fallback(
        'null',
        tmp_path / 'coming-soon.mp4',
        duration=2,
        width=1920,
        height=1080,
        bg_color='0x141428',
        output_width=3840,
        output_height=2160,
        frame_rate=60,
        video_preset='slower',
        video_crf=12,
        audio_bitrate='320k',
    )

    command = captured['command']
    filter_graph = command[command.index('-filter_complex') + 1]
    assert result == str(tmp_path / 'coming-soon.mp4')
    assert any('r=60' in value for value in command)
    assert 'scale=3840:2160:flags=lanczos' in filter_graph
    assert command[command.index('-preset') + 1] == 'slower'
    assert command[command.index('-crf') + 1] == '12'
    assert command[command.index('-level') + 1] == '5.2'
