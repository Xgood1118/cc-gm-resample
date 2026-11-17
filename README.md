# 采样率转换与延迟补偿

一个能完成 44.1k 与 48k 互转、并把延迟补偿到样本级的重采样器

## 保留签名

- `read_wav_samples(path)`
- `write_wav_samples(path, rate, samples)`
- `resample(samples, src_rate, dst_rate)`
- `measure_delay(samples, rate, freq)`

## 自测

```
python -m pytest tests -q
python -m resample.cli data/tone.wav --to 48000 --out tone48.wav
```
