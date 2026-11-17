# 采样率转换与延迟补偿

一个能完成 44.1k 与 48k 互转、并把延迟补偿到样本级的重采样器。仅使用 Python 标准库。

## 方案

- **有理比例多相 FIR**：`fractions.Fraction` 把采样率比约成整数比 up/down
  （44100 ↔ 48000 恰好是 160/147），比例无近似误差，输出长度
  `round(N_in * dst / src)`，误差 < 1 样本。
- **抗混叠 / 抗镜像**：Blackman 窗 sinc 低通，阻带起点 = `0.5 * min(src, dst)`，
  过渡带宽 = `0.1 * min(src, dst)`，滤波器 8801 阶，阻带抑制约 73 dB。
- **延迟补偿**：线性相位 FIR 群延迟恒为 `(N-1)/2`，多相取值时把它折算进索引，
  输出与输入在时间上样本级对齐。
- **边界**：输入两端零延拓，首尾各有一段过渡区，幅度平滑升降、无突跳。

## 过渡区长度

滤波器半长（上采样域 4400 样本）折算到输入/输出采样率：

| 转换方向 | 首/尾过渡区（输出样本） | 折合输入样本 |
|---|---|---|
| 44100 → 48000 | 30 | 27.5 |
| 48000 → 44100 | 28 | 29.9 |

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

## 实测结果（`data/tone.wav` → `tone48.wav`）

| 指标 | 数值 |
|---|---|
| 输入采样数 | 44100 @ 44100 Hz |
| 输出采样数 | 48000 @ 48000 Hz |
| 滤波器延迟 | 27 样本（@44100 Hz，`measure_delay` 实测，与解析值 (55-1)/2 一致） |
| 补偿后相位差 | 0.000000°（440 Hz，中段最小二乘拟合） |
| 折返抑制 | 73.5 dB（阻带 [22050, 3528000] Hz 采样最差响应） |
| 输出一致性 | 两次运行逐字节一致（16 位单声道 WAV） |
