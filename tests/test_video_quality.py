"""Output quality presets: pure checks of the FFmpeg arguments (the real render is exercised in tests/test_video.py)."""
import pytest

from modules.video.composer import Style
from modules.video.render import (DEFAULT_QUALITY, QUALITY_PROFILES, RenderError, quality_profile, video_args)


def test_default_is_the_setting_videos_had_before_the_option_existed():
    q = quality_profile(DEFAULT_QUALITY)
    assert q.size == Style().size == (1280, 720) and (q.crf, q.preset) == (20, "veryfast")
    args = video_args(q, Style().size)
    assert "-vf" not in args                                    # no rescale: the command is unchanged
    assert args == ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]


@pytest.mark.parametrize("key", list(QUALITY_PROFILES))
def test_every_preset_is_a_valid_even_16_9_size(key):
    w, h = QUALITY_PROFILES[key].size
    assert w % 2 == 0 and h % 2 == 0 and abs(w / h - 16 / 9) < 0.01      # yuv420p needs even sides; no stretching
    assert 0 <= QUALITY_PROFILES[key].crf <= 51


def test_other_sizes_rescale_at_encode_time_only():
    assert "scale=854:480:flags=lanczos" in video_args(quality_profile("draft"), (1280, 720))
    assert "scale=1920:1080:flags=lanczos" in video_args(quality_profile("high"), (1280, 720))


def test_quality_orders_picture_quality_and_size():
    d, s, h = (quality_profile(k) for k in ("draft", "standard", "high"))
    assert d.crf > s.crf > h.crf and d.size[1] < s.size[1] < h.size[1]


def test_unknown_quality_is_a_clear_error():
    with pytest.raises(RenderError, match="unknown video quality"):
        quality_profile("ultra")
