# -*- coding: utf-8 -*-
"""采样率转换与延迟补偿（仅标准库）。

实现方案：有理比例多相 FIR 重采样。

- 用 fractions.Fraction 把 src_rate -> dst_rate 约成整数比 up/down
  （44100 <-> 48000 恰好是 160/147），比例无近似误差。
- 抗混叠/抗镜像：Blackman 窗 sinc 低通，线性相位，群延迟恒为 (N-1)/2。
- 多相结构直接在输出采样点取值，并把滤波器群延迟折算进索引，
  输出与输入在时间上样本级对齐（延迟补偿）。
- 输入两端按零延拓处理，首尾各有一段约半个滤波器长度的过渡区，
  幅度平滑升降，无突跳。
"""

import math
import struct
import wave
from fractions import Fraction

__all__ = ["read_wav_samples", "write_wav_samples", "resample", "measure_delay"]

# Blackman 窗过渡带系数：过渡带宽度 ≈ 5.5 / N（归一化频率）
_BLACKMAN_TRANSITION = 5.5
# 阻带起点 = 0.5 * min(src, dst)；截止频率放在过渡带正中（0.9 * 阻带起点），
# 过渡带总宽 = 0.2 * 阻带起点
_CUTOFF_FACTOR = 0.9
_TRANSITION_FACTOR = 0.2


def read_wav_samples(path):
    """读 16 位单声道 WAV，返回(采样率, 采样列表)，采样为 [-1, 1] 浮点。"""
    with wave.open(path, "rb") as w:
        if w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("仅支持 16 位单声道 WAV")
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    count = len(raw) // 2
    ints = struct.unpack("<%dh" % count, raw[: count * 2])
    return rate, [x / 32768.0 for x in ints]


def write_wav_samples(path, rate, samples):
    """写 16 位单声道 WAV（确定性输出，两次写入逐字节一致）。"""
    pack = struct.Struct("<h").pack
    frames = bytearray()
    for s in samples:
        v = int(round(s * 32767.0))
        if v > 32767:
            v = 32767
        elif v < -32768:
            v = -32768
        frames += pack(v)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate))
        w.writeframes(bytes(frames))


def _design_lowpass(num_taps, cutoff_norm):
    """Blackman 窗 sinc 低通。num_taps 为奇数，cutoff_norm = 截止频率/采样率。"""
    mid = (num_taps - 1) // 2
    last = num_taps - 1
    taps = []
    for k in range(num_taps):
        x = k - mid
        if x == 0:
            s = 1.0
        else:
            s = math.sin(2.0 * math.pi * cutoff_norm * x) / (
                2.0 * math.pi * cutoff_norm * x
            )
        w = (
            0.42
            - 0.5 * math.cos(2.0 * math.pi * k / last)
            + 0.08 * math.cos(4.0 * math.pi * k / last)
        )
        taps.append(2.0 * cutoff_norm * s * w)
    return taps


def _resample_filter(src_rate, dst_rate):
    """设计 src_rate -> dst_rate 的多相滤波器，返回 (taps, up, down)。"""
    frac = Fraction(int(dst_rate), int(src_rate))
    up, down = frac.numerator, frac.denominator
    fs_up = src_rate * up
    f_stop = 0.5 * min(src_rate, dst_rate)
    cutoff = _CUTOFF_FACTOR * f_stop
    transition = _TRANSITION_FACTOR * f_stop
    num_taps = int(math.ceil(_BLACKMAN_TRANSITION * fs_up / transition)) | 1
    taps = _design_lowpass(num_taps, cutoff / fs_up)
    # 插值滤波器直流增益应为 up，归一化保证整链增益为 1
    gain = up / sum(taps)
    taps = [t * gain for t in taps]
    return taps, up, down


def resample(samples, src_rate, dst_rate):
    """重采样：src_rate -> dst_rate，抗混叠 + 样本级延迟补偿。

    输出长度 = round(len(samples) * dst_rate / src_rate)（误差 < 1 样本）。
    """
    xs = list(samples)
    n_in = len(xs)
    if n_in == 0 or src_rate == dst_rate:
        return xs
    taps, up, down = _resample_filter(src_rate, dst_rate)
    num_taps = len(taps)
    delay = (num_taps - 1) // 2  # 上采样域群延迟（样本）
    n_out = int(math.floor(n_in * (float(dst_rate) / float(src_rate)) + 0.5))
    last_j = (n_in - 1) * up  # 上采样域最后一个非零下标
    out = []
    for n in range(n_out):
        # 输出点 n 对应上采样域下标 t；加 delay 即把滤波器群延迟折回，
        # 使 y[n] 与输入时刻 n/dst_rate 对齐。
        t = n * down + delay
        # v[t] = sum_k taps[k] * u[t-k]，u[j] 仅在 j % up == 0 处非零
        k = max(0, t - last_j)
        k += (t % up - k) % up  # 最小的 k >= 下界 且 k ≡ t (mod up)
        k_end = min(num_taps - 1, t)
        acc = 0.0
        while k <= k_end:
            acc += taps[k] * xs[(t - k) // up]
            k += up
        out.append(acc)
    return out


def _convolve(xs, taps):
    n = len(xs)
    nt = len(taps)
    out = [0.0] * n
    for i in range(n):
        lo = max(0, i - n + 1)
        hi = min(nt - 1, i)
        acc = 0.0
        for k in range(lo, hi + 1):
            acc += taps[k] * xs[i - k]
        out[i] = acc
    return out


def _fit_phase(xs, rate, freq, start=0):
    """最小二乘拟合 A*sin(wt)+B*cos(wt)，返回相位 atan2(B, A)。

    start 为 xs[0] 在整段信号中的绝对样本下标，保证不同信号相位可比。
    """
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


def measure_delay(samples, rate, freq):
    """测当前滤波器链的延迟样本数。

    用与 resample 相同的设计规则构造该采样率下的抗混叠低通，
    对输入做最小二乘正弦拟合，比较滤波前后 freq 处相位并换算成样本数。
    输入太短无法可靠拟合时，退回线性相位 FIR 的解析群延迟 (N-1)/2。
    freq 需满足 delay < rate/freq（相位不卷绕），如 440 Hz。
    """
    xs = list(samples)
    taps, _, _ = _resample_filter(rate, rate)
    delay = (len(taps) - 1) // 2
    n = len(xs)
    if n < 64 or not 0.0 < freq < 0.4 * rate:
        return delay
    y = _convolve(xs, taps)
    m = n // 4  # 取中段，避开首尾过渡区
    seg_x = xs[m : n - m]
    seg_y = y[m : n - m]
    if len(seg_x) < 16:
        return delay
    dphi = (
        _fit_phase(seg_y, rate, freq, m) - _fit_phase(seg_x, rate, freq, m) + math.pi
    ) % (2.0 * math.pi) - math.pi
    measured = -dphi * rate / (2.0 * math.pi * freq)
    return int(round(measured))
