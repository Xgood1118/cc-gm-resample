# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import resample as mod  # noqa: E402

def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_hex(path):
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def test_resample_length():
    rate, s = resample.read_wav_samples("data/tone.wav")
    out = resample.resample(s, rate, 48000)
    ratio = 48000.0 / rate
    assert abs(len(out) - len(s) * ratio) <= 2


def test_delay_measurable():
    rate, s = resample.read_wav_samples("data/tone.wav")
    d = resample.measure_delay(s, rate, 440.0)
    assert isinstance(d, int) and d >= 0
