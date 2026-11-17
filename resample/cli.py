import argparse
import math

import resample as m
from resample.core import _fit_phase, _resample_filter


def _wrap_pi(x):
    return (x + math.pi) % (2.0 * math.pi) - math.pi


def _stopband_suppression_db(taps, fs_up, f_stop, points=200):
    """在阻带 [f_stop, fs_up/2] 上采样滤波器响应，返回最差抑制量（dB）。"""
    dc = sum(taps)
    worst = 0.0
    for i in range(points):
        f = f_stop + (fs_up / 2.0 - f_stop) * i / (points - 1)
        w = 2.0 * math.pi * f / fs_up
        re = im = 0.0
        for k, t in enumerate(taps):
            re += t * math.cos(w * k)
            im -= t * math.sin(w * k)
        mag = math.hypot(re, im) / dc
        if mag > worst:
            worst = mag
    return -20.0 * math.log10(worst)


def main():
    ap = argparse.ArgumentParser(description="采样率转换与延迟补偿")
    ap.add_argument("input", help="输入 16 位单声道 WAV")
    ap.add_argument("--to", type=int, required=True, help="目标采样率")
    ap.add_argument("--out", required=True, help="输出 WAV 路径")
    ap.add_argument("--freq", type=float, default=440.0, help="相位测量用正弦频率")
    a = ap.parse_args()

    rate, samples = m.read_wav_samples(a.input)
    out = m.resample(samples, rate, a.to)
    m.write_wav_samples(a.out, a.to, out)

    delay = m.measure_delay(samples, rate, a.freq)

    # 补偿后相位差：输入/输出中段同一正弦的相位（绝对时间基准）
    q_in = len(samples) // 4
    q_out = len(out) // 4
    ph_in = _fit_phase(samples[q_in : len(samples) - q_in], rate, a.freq, q_in)
    ph_out = _fit_phase(out[q_out : len(out) - q_out], a.to, a.freq, q_out)
    phase_deg = abs(math.degrees(_wrap_pi(ph_in - ph_out)))

    taps, up, _ = _resample_filter(rate, a.to)
    suppress_db = _stopband_suppression_db(
        taps, rate * up, 0.5 * min(rate, a.to)
    )

    print("输入: %d 样本 @ %d Hz" % (len(samples), rate))
    print("输出: %d 样本 @ %d Hz -> %s" % (len(out), a.to, a.out))
    print("滤波器延迟: %d 样本 (@%d Hz)" % (delay, rate))
    print("补偿后相位差: %.4f 度" % phase_deg)
    print("折返抑制: %.1f dB" % suppress_db)


if __name__ == "__main__":
    main()
