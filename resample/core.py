# -*- coding: utf-8 -*-
"""采样率转换与延迟补偿"""



def read_wav_samples(path):
    """读 16 位单声道 WAV，返回(采样率, 采样列表)"""
    raise NotImplementedError("read_wav_samples 尚未实现")


def write_wav_samples(path, rate, samples):
    """写 16 位单声道 WAV"""
    raise NotImplementedError("write_wav_samples 尚未实现")


def resample(samples, src_rate, dst_rate):
    """重采样"""
    raise NotImplementedError("resample 尚未实现")


def measure_delay(samples, rate, freq):
    """测当前滤波器链的延迟样本数"""
    raise NotImplementedError("measure_delay 尚未实现")

