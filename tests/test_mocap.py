import numpy as np
import pytest
from modules.video import mocap as M
from modules.video.mocap import J, MocapError, MocapService, clip_from_joints, retarget
from modules.video.stickman import _NUMERIC

def idx(n): return _NUMERIC.index(n)

def skeleton(r_arm=(0, -1, 0), l_arm=(0, -1, 0), r_leg=(0, -1, 0), r_shin=(0, -1, 0), lift=0.0):
    """One standing frame. Arms/legs are DIRECTIONS (x lateral, y up, z forward); segments are 0.3-0.45 m."""
    j = np.zeros((22, 3), np.float32)
    u = lambda v: np.array(v, float) / np.linalg.norm(v)
    j[J["pelvis"]] = (0, 0.9, 0)
    j[J["l_hip"]], j[J["r_hip"]] = (-0.1, 0.9, 0), (0.1, 0.9, 0)
    j[J["neck"]], j[J["head"]] = (0, 1.4, 0), (0, 1.6, 0)
    j[J["l_sho"]], j[J["r_sho"]] = (-0.2, 1.4, 0), (0.2, 1.4, 0)
    j[J["r_elb"]] = j[J["r_sho"]] + 0.3 * u(r_arm); j[J["r_wri"]] = j[J["r_elb"]] + 0.3 * u(r_arm)
    j[J["l_elb"]] = j[J["l_sho"]] + 0.3 * u(l_arm); j[J["l_wri"]] = j[J["l_elb"]] + 0.3 * u(l_arm)
    j[J["l_knee"]] = j[J["l_hip"]] + (0, -0.42, 0); j[J["l_ankle"]] = j[J["l_knee"]] + (0, -0.42, 0)
    j[J["r_knee"]] = j[J["r_hip"]] + 0.42 * u(r_leg); j[J["r_ankle"]] = j[J["r_knee"]] + 0.42 * u(r_shin)
    j[:, 1] += lift
    return j

def clip(frames): return np.stack(frames)
def row(frames, name, i=0): return retarget(clip(frames))[i][idx(name)]

def test_arm_directions_become_the_angles_of_the_rig():
    f = lambda **k: [skeleton(**k)] * 6
    assert row(f(), "sh_f") == pytest.approx(0, abs=1)
    assert row(f(r_arm=(0, 0, 1)), "sh_f") == pytest.approx(90, abs=1)          # straight forward
    assert row(f(r_arm=(0, 1, 0)), "sh_f") == pytest.approx(180, abs=1)         # straight up
    assert row(f(r_arm=(1, 0, 0)), "sh_f") == pytest.approx(90, abs=1)  # sideways counts as forward
    assert row(f(l_arm=(0, 0, 1)), "sh_b") == pytest.approx(90, abs=1)

def test_elbow_is_forearm_minus_upper_arm_and_knee_never_negative():
    bent = skeleton(r_arm=(0, 0, 1))
    bent[J["r_wri"]] = bent[J["r_elb"]] + (0, 0.3, 0)                           # forearm straight up
    assert row([bent] * 6, "el_f") == pytest.approx(90, abs=1)
    knee = row([skeleton(r_leg=(0, -1, 0.0), r_shin=(0, -1, -1))] * 6, "kn_f")  # shin swings back
    assert knee == pytest.approx(45, abs=1)
    assert row([skeleton(r_shin=(0, -1, 1))] * 6, "kn_f") == 0.0                # a knee does not bend the wrong way

def test_airborne_frames_give_negative_dy_and_standing_frames_zero():
    frames = [skeleton()] * 4 + [skeleton(lift=0.3)] * 4
    dy = retarget(clip(frames))[:, idx("dy")]
    assert dy[0] == 0.0 and dy[-1] == pytest.approx(-0.3 * M.PX_PER_M, abs=8)   # smoothing blurs the edge a little

def test_no_angle_jump_when_the_arm_swings_through_the_top():
    frames = [skeleton(r_arm=(0.1 * k - 0.5, 1, 0)) for k in range(11)]       # up, leaning from one side to the other
    sh = retarget(clip(frames))[:, idx("sh_f")]
    assert np.abs(np.diff(sh)).max() < 40 and sh.min() > 100

def test_clip_plays_pingpong_and_never_leaves_its_range():
    c = clip_from_joints("x", clip([skeleton(r_arm=(0, 0, 1))] * 3 + [skeleton(r_arm=(0, 1, 0))] * 3))
    assert c.duration == pytest.approx(5 / 20)
    p0, p_end = c.pose_at(0.0), c.pose_at(c.duration)
    assert p0.sh_f < p_end.sh_f and c.pose_at(c.duration * 2).sh_f == pytest.approx(p0.sh_f, abs=1e-6)
    assert all(min(p0.sh_f, p_end.sh_f) - 1e-6 <= c.pose_at(t / 10).sh_f <= max(p0.sh_f, p_end.sh_f) + 1e-6 for t in range(40))

@pytest.mark.parametrize("bad", [np.zeros((5, 21, 3)), np.zeros((1, 22, 3)), np.full((4, 22, 3), np.nan), np.zeros((4, 22))])
def test_wrong_shapes_are_rejected(bad):
    with pytest.raises(MocapError):
        retarget(bad)

class Prov:
    name, online = "fake", False
    def __init__(self, fail=False, none=False): self.fail, self.none, self.calls = fail, none, []
    def fetch(self, key, prompt):
        self.calls.append((key, prompt))
        if self.fail: raise MocapError("boom")
        return None if self.none else clip([skeleton()] * 4)

def test_service_caches_on_disk_and_asks_once_per_action(tmp_path):
    p = Prov(); s = MocapService(p, tmp_path)
    assert s.get("wave") and s.get("wave") and len(p.calls) == 1 and p.calls[0][1] == M.ACTION_PROMPTS["wave"]
    assert MocapService(Prov(), tmp_path).get("wave") is not None             # second run: from the cache folder
    assert s.summary()["clips"] == {"wave": "cache"}

def test_service_never_raises_and_stops_asking_after_two_failures(tmp_path):
    p = Prov(fail=True); s = MocapService(p, tmp_path)
    assert [s.get(a) for a in ("wave", "point", "think")] == [None] * 3
    assert len(p.calls) == 2 and "skipped" in s.errors[-1]
    assert MocapService(Prov(none=True), tmp_path / "n").get("wave") is None
    assert s.get("not_an_action") is None

def test_clips_for_keeps_only_what_exists(tmp_path):
    out = MocapService(Prov(), tmp_path).clips_for(["wave", "wave", "dance", "point"])
    assert list(out) == ["wave", "point"]

def test_folder_provider_reads_npy(tmp_path):
    np.save(tmp_path / "wave.npy", clip([skeleton()] * 4))
    s = MocapService(M.DirMocap(tmp_path), tmp_path / "c")
    assert s.get("wave") and s.get("point") is None

def test_every_director_action_has_a_prompt_and_gestures_use_the_right_side():
    from modules.video.mocap import ACTION_PROMPTS as A
    assert {"wave", "point", "think", "idea", "shrug", "surprised", "nod", "cheer", "jump", "talk", "idle"} <= set(A)
    assert all("right" in A[k] for k in ("wave", "point", "think"))
