"""The centre line of a hand-drawn 走向 stroke must be smoother than the hand path it came from.

A mouse user cannot draw a straight line: the pointer arrives as a coarse, wobbly path. The course direction is
read from the tangents of this centre line, so any zigzag the extraction adds shows up as a zigzag in the
texture (the courses, and every 斜单线 line, follow it). Extraction therefore has to remove tremor, not add it.

Regression: centre_lines binned the stroke along its PCA axis into integer bins and averaged each bin. On a
1000 px stroke that returns ~1000 points, one per bin, and the bin-to-bin steps came out *rougher* than the
hand path (measured 4-5x the input's turn rate), so the texture inherited the zigzag.
"""
import cv2
import numpy as np

from stocking import guide_fields as gf


def hand_path(n, length, jitter, seed):
    """A hand-drawn line: `length` px along x, wobbling by about `jitter` px, sampled `n` times."""
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 1, n)
    y = jitter * 6 + np.sin(t * np.pi * 4) * jitter + np.sin(t * np.pi * 9 + 1.1) * jitter * 0.5 \
        + rng.normal(0, jitter * 0.25, n)
    return np.stack([t * length, y], 1)


def raster(pts, shape):
    """The stroke layer as the solver sees it: 5 px wide, one connected stroke."""
    a = np.zeros(shape, np.uint8)
    p = np.round(np.asarray(pts) * 16).astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(a, [p], False, 255, 5, cv2.LINE_8, 4)
    return a


def turn_rate(Q):
    """Total turning in degrees per 100 px of arc length. A straight line is 0; a zigzag is large."""
    if len(Q) < 3:
        return 0.0
    return float(100.0 * np.degrees(np.abs(np.diff(angles(Q))).sum()) / max(arclen(Q), 1e-9))


def angles(Q):
    """Direction of the curve at each point, unwrapped so turns accumulate instead of wrapping at +-pi."""
    T = np.gradient(Q, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
    return np.unwrap(np.arctan2(T[:, 1], T[:, 0]))


def arclen(Q):
    return float(np.r_[0, np.cumsum(np.hypot(*np.diff(Q, axis=0).T))][-1])


def zigzag(Q):
    """How sharply the curvature itself jumps between neighbouring points, in degrees per px.

    This is the number that separates the two cases the eye cares about: a smooth wave (a hand that wobbles
    gently, turn rate spread evenly over the arc) and a zigzag (corners, the turn rate spiking every few px).
    Total turning alone cannot tell them apart -- both add up to the same degrees -- so measure the spikes.
    """
    if len(Q) < 3:
        return 0.0
    a = angles(Q)
    s = np.r_[0, np.cumsum(np.hypot(*np.diff(Q, axis=0).T))]
    k = np.diff(a) / np.maximum(np.diff(s), 1e-9)              # curvature, rad per px
    return float(np.degrees(np.abs(np.diff(k)).sum()) * np.median(np.diff(s)) / max(s[-1], 1e-9) * 100)


def extracted(pts):
    """The centre line guide_fields reads the course direction from, for one hand-drawn stroke."""
    shape = (1200, 1400)
    P = np.asarray(pts, np.float64) - np.asarray(pts).min(0) + 40
    lines = gf.centre_lines(raster(P, shape), np.ones(shape, bool))
    assert lines, 'the stroke should extract to one centre line'
    return lines[0], P


def test_centre_line_is_smoother_than_the_hand_path():
    """The whole point of the extraction: tremor in, smooth out.

    Measured as curvature roughness (see zigzag), not total turning: a hand path that wanders gently is
    already acceptable, a path with corners is not, and only the second shows up here.
    """
    for jitter in (2.0, 4.0, 6.0, 8.0):
        Q, P = extracted(hand_path(60, 1000, jitter, seed=7))
        before, after = zigzag(P), zigzag(Q)
        assert after < before, (
            f'tremor {jitter} px: centre line is rougher than the hand path '
            f'({after:.2f} vs {before:.2f} deg/100px)')


def test_centre_line_does_not_add_zigzag():
    """Even on an exactly straight stroke (no tremor at all), including a slanted one whose rasterization is a pixel
    staircase, the extraction must not invent corners."""
    for deg in (0, 5, 15, 30):
        th = np.deg2rad(deg)
        t = np.linspace(0, 800, 60)
        pts = np.stack([t * np.cos(th), t * np.sin(th)], 1)
        Q, _ = extracted(pts)
        assert zigzag(Q) < 0.5, f'{deg} deg straight stroke came back with corners: {zigzag(Q):.2f} deg/100px'


def test_centre_line_keeps_the_shape_of_a_bent_stroke():
    """A stroke drawn round a bend (膝盖 ∩, including a deep one whose depth exceeds its half-width) must come back
    bent, not flattened onto its main axis.

    走向 strokes are drawn as arcs (README: 膝盖上方 ∩, 下方 ∪, and a knee stroke joining thigh to calf), and the
    PCA binning folded the far side of a deep bend into the same bin as the near side.
    """
    t = np.linspace(-1, 1, 80)
    for half_w, h_arc in ((300, 120), (60, 150)):
        arc = np.stack([t * half_w, -h_arc * (1 - t ** 2)], 1)      # a ∩
        Q, P = extracted(arc)
        assert len(Q) >= 3
        # the apex is the topmost point (image y grows downward); it must survive rather than being averaged away
        depth = max(Q[0, 1], Q[-1, 1]) - Q[:, 1].min()
        assert depth > 0.6 * h_arc, f'arc (half_w={half_w}) flattened: depth {depth:.0f} of {h_arc}'
        # and the ends must stay at the ends (unordered: the walk may start from either end)
        d0 = min(np.hypot(*(Q[0] - P[0])), np.hypot(*(Q[-1] - P[0])))
        d1 = min(np.hypot(*(Q[0] - P[-1])), np.hypot(*(Q[-1] - P[-1])))
        assert d0 < 15 and d1 < 15


def test_centre_line_keeps_its_ends():
    """The stroke spans about 80% of the region's width (README); extraction must not shorten it, even when 2D hand
    jitter leaves tiny spurs on the thinned skeleton."""
    Q, P = extracted(hand_path(60, 1000, 4.0, seed=3))
    span_in = np.hypot(*(P[-1] - P[0]))
    span_out = np.hypot(*(Q[-1] - Q[0]))
    assert span_out > 0.97 * span_in, f'stroke shrank from {span_in:.0f} to {span_out:.0f} px'
    rng = np.random.default_rng(0)
    for seed in range(30):
        t = np.linspace(0, 1, 120)
        pts = np.stack([t * 600 + rng.normal(0, 1.8, len(t)),
                        50 + np.sin(t * 6) * 8 + rng.normal(0, 1.8, len(t))], 1)
        Q, P = extracted(pts)
        assert np.hypot(*(Q[-1] - Q[0])) > 0.95 * np.hypot(*(P[-1] - P[0]))
