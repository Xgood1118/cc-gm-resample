# -*- coding: utf-8 -*-
import math
import os
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import resample  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TONE = os.path.join(ROOT, "data", "tone.wav")


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_hex(path):
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def _sine(freq, rate, n, amp=0.6):
    return [amp * math.sin(2.0 * math.pi * freq * i / rate) for i in range(n)]


def _fit_phase(xs, rate, freq, start=0):
    w = 2.0 * math.pi * freq / rate
    ss = cc = sc = ys = yc = 0.0
    for i, x in enumerate(xs):
        t = start + i
        s = math.sin(w * t)
        c = math.cos(w * t)
        ss += s * s
        cc += c * c
        sc += s * c
        ys += x * s
        yc += x * c
    det = ss * cc - sc * sc
    a = (ys * cc - yc * sc) / det
    b = (yc * ss - ys * sc) / det
    return math.atan2(b, a)


def _rms(xs):
    return math.sqrt(sum(x * x for x in xs) / len(xs))


def _goertzel(xs, rate, freq):
    w = 2.0 * math.pi * freq / rate
    cw = math.cos(w)
    c = 2.0 * cw
    s1 = s2 = 0.0
    for x in xs:
        s0 = x + c * s1 - s2
        s2 = s1
        s1 = s0
    return math.hypot(s1 - s2 * cw, s2 * math.sin(w)) / len(xs)


def test_resample_length():
    rate, s = resample.read_wav_samples(TONE)
    out = resample.resample(s, rate, 48000)
    ratio = 48000.0 / rate
    assert abs(len(out) - len(s) * ratio) <= 1
    back = resample.resample(out, 48000, rate)
    assert abs(len(back) - len(s)) <= 1


def test_delay_measurable():
    rate, s = resample.read_wav_samples(TONE)
    d = resample.measure_delay(s, rate, 440.0)
    assert isinstance(d, int) and d >= 0


def test_delay_consistent_across_lengths():
    ds = set()
    for n in (2000, 8000, 44100):
        sig = _sine(440.0, 44100, n)
        ds.add(resample.measure_delay(sig, 44100, 440.0))
    assert len(ds) == 1


def test_antialias_downsample():
    # 23000 Hz 超过 44100 的奈奎斯特频率，转换后应被压到 -40 dB 以下
    rate = 48000
    sig = _sine(23000.0, rate, 24000, amp=0.8)
    out = resample.resample(sig, rate, 44100)
    mid = out[len(out) // 4 : 3 * len(out) // 4]
    assert _rms(mid) < _rms(sig) * 1e-2


def test_antiimage_upsample():
    # 上采样镜像：10000 Hz 在 44100 处的镜像 34100 Hz，
    # 折到 48000 域为 13900 Hz，应比主谱线低 40 dB 以上
    sig = _sine(10000.0, 44100, 22050)
    out = resample.resample(sig, 44100, 48000)
    mid = out[len(out) // 4 : 3 * len(out) // 4]
    main = _goertzel(mid, 48000, 10000.0)
    image = _goertzel(mid, 48000, 13900.0)
    assert image < main * 1e-2


def test_delay_compensation_phase():
    sig = _sine(440.0, 44100, 22050)
    out = resample.resample(sig, 44100, 48000)
    qi = len(sig) // 4
    qo = len(out) // 4
    ph_in = _fit_phase(sig[qi : len(sig) - qi], 44100, 440.0, qi)
    ph_out = _fit_phase(out[qo : len(out) - qo], 48000, 440.0, qo)
    diff = (ph_in - ph_out + math.pi) % (2.0 * math.pi) - math.pi
    assert abs(math.degrees(diff)) <= 1.0


def test_short_input():
    assert resample.resample([], 44100, 48000) == []
    one = resample.resample([0.5], 44100, 48000)
    assert len(one) == 1
    two = resample.resample([0.5, -0.5], 48000, 44100)
    assert len(two) == int(2 * 44100 / 48000 + 0.5)
    assert resample.measure_delay([0.1, -0.1], 44100, 440.0) >= 0


def test_no_edge_jumps():
    # 首尾过渡区应平滑升降，相邻样本不出现突跳
    sig = _sine(440.0, 44100, 22050)
    out = resample.resample(sig, 44100, 48000)
    steady = 0.6 * 2.0 * math.pi * 440.0 / 48000.0 * 1.5
    for i in range(len(out) - 1):
        assert abs(out[i + 1] - out[i]) <= steady


def test_deterministic_and_valid_wav(tmp_path):
    rate, s = resample.read_wav_samples(TONE)
    out = resample.resample(s, rate, 48000)
    assert resample.resample(s, rate, 48000) == out
    p1 = str(tmp_path / "a.wav")
    p2 = str(tmp_path / "b.wav")
    resample.write_wav_samples(p1, 48000, out)
    resample.write_wav_samples(p2, 48000, out)
    assert read_bytes(p1) == read_bytes(p2)
    with wave.open(p1) as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 48000
        assert w.getnframes() == len(out)
