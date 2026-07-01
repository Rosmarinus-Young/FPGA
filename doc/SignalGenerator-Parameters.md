# SignalGenerator — User-Configurable Parameters

本文档说明 [SignalGenerator.py](../SignalGenerator.py) 中 `User-configurable parameters` 区块的全部可调参数及其含义。

---

## 目录

- [快速入口：MODE 选择器](#1-mode-选择器)
- [基础波形参数](#2-基础波形参数-freq_hz)
- [调制参数](#3-调制参数)
- [DDS 引擎参数（固定）](#4-dds-引擎参数)
- [幅度参数（固定）](#5-幅度参数)
- [参数速查表](#6-参数速查表)
- [配置示例](#7-配置示例)
- [约束与限制](#8-约束与限制)

---

## 1. MODE 选择器

```python
MODE = WAVEFORM_SINE       # <<< SELECT MODE HERE
```

`MODE` 是顶层开关，决定 SignalGenerator 的工作模式。所有合法取值如下：

| 常量 | 值 | 模式 | 关联参数 |
|---|---|---|---|
| `WAVEFORM_SINE` | `0` | 基础正弦波 | `FREQ_HZ` |
| `WAVEFORM_SQUARE` | `1` | 基础方波 | `FREQ_HZ` |
| `WAVEFORM_TRIANGLE` | `2` | 基础三角波 | `FREQ_HZ` |
| `MODE_AM` | `3` | 幅度调制 (AM) | `CARRIER_FREQ`, `MOD_FREQ`, `MOD_INDEX_*` |
| `MODE_FM` | `4` | 频率调制 (FM) | `CARRIER_FREQ`, `MOD_FREQ`, `MOD_INDEX_*` |
| `MODE_SPWM` | `5` | 正弦脉宽调制 (SPWM) | `CARRIER_FREQ`, `MOD_FREQ`, `MOD_INDEX_*` |

### 模式选择指南

```
需要纯净单频信号？
  ├── 是 → 使用 WAVEFORM_SINE / SQUARE / TRIANGLE
  └── 否 → 需要调制输出？
            ├── 信息在幅度上 → MODE_AM
            ├── 信息在频率上 → MODE_FM
            └── 需要开关量输出 → MODE_SPWM
```

---

## 2. 基础波形参数 `FREQ_HZ`

```python
FREQ_HZ = 1000            # 输出频率: 100 ~ 10000 Hz
```

| 属性 | 说明 |
|---|---|
| 生效条件 | `MODE ∈ {WAVEFORM_SINE, WAVEFORM_SQUARE, WAVEFORM_TRIANGLE}` |
| 合法范围 | 100 Hz ~ 10 000 Hz（受 DAC 更新率和抗混叠约束） |
| 实际分辨率 | Δf = F_DAC / 2^N = 781250 / 2^24 ≈ **0.047 Hz** |
| 实际精度 | 实际输出频率 = round(FREQ_HZ × 2^N / F_DAC) × F_DAC / 2^N，误差 ≤ 0.024 Hz |

> **原理**：`FREQ_HZ` 被转换为频率调谐字（FTW）：
> ```
> FTW = FREQ_HZ × 2^24 / 781250
> ```
> 相位累加器每个 DAC 时钟周期累加 FTW，相位的高 8 位索引波形查找表。

---

## 3. 调制参数

以下参数仅在 `MODE ∈ {MODE_AM, MODE_FM, MODE_SPWM}` 时生效。

### 3.1 `CARRIER_FREQ` — 载波频率

```python
CARRIER_FREQ = 5000       # 载波频率 (Hz)
```

| 模式 | 载波含义 |
|---|---|
| AM | 被调制的高频正弦波频率 `f_c` |
| FM | 中心频率（未调制时的载波频率）`f_c` |
| SPWM | 三角载波的频率（开关频率）`f_c` |

**SPWM 特别说明**：载波频率决定功率器件的开关速度。`m_f = f_c / MOD_FREQ` 应为整数以获得同步 PWM；推荐 `f_c ≥ 20 × MOD_FREQ`（即 `m_f ≥ 20`）。

### 3.2 `MOD_FREQ` — 调制信号频率

```python
MOD_FREQ = 500            # 调制信号频率 (Hz)
```

| 模式 | 调制信号含义 |
|---|---|
| AM | 包络变化频率 — 人耳听到的音调 `f_m` |
| FM | 频率摆动速率 `f_m` |
| SPWM | 目标输出正弦波的基波频率 `f_m` |

**约束**：`MOD_FREQ < CARRIER_FREQ`，工程上通常 `MOD_FREQ ≪ CARRIER_FREQ`。

### 3.3 `MOD_INDEX_NUM` / `MOD_INDEX_DEN` — 调制指数

```python
MOD_INDEX_NUM = 1         # 分子
MOD_INDEX_DEN = 2         # 分母 → 调制指数 = 1/2 = 0.5
```

调制指数以**分数形式**指定，避免了浮点舍入误差，便于精确控制。硬件内部以 12 位定点小数表示：

```
m_fixed = round( NUM / DEN × 4096 )
```

#### AM 模式 (m ∈ [0, 1])

| 参数 | 含义 |
|---|---|
| `m = NUM / DEN` | 调制深度 (modulation depth) |
| `m = 0` | 纯载波，无调制 |
| `m = 0.5` | 50% 调制 — 包络在 0.5A_c ~ 1.5A_c 之间 |
| `m = 1.0` | 100% 调制 — 包络在 0 ~ 2A_c 之间（临界不过调制） |
| `m > 1.0` | **禁止** — 过调制导致包络失真 |

调制信号：`s_AM(t) = A_c [1 + m · sin(2π f_m t)] · sin(2π f_c t)`

#### FM 模式 (β 无上限，工程上 β > 1 为宽带 FM)

| 参数 | 含义 |
|---|---|
| `β = NUM / DEN` | 调制指数 (modulation index)，单位：弧度 |
| `Δf = β × MOD_FREQ` | 峰值频偏 (peak frequency deviation)，单位：Hz |

> **示例**：`NUM=500, DEN=100, MOD_FREQ=500` → `β = 5`，`Δf = 5 × 500 = 2500 Hz`
>
> 瞬时频率在 `f_c ± 2500 Hz` 之间摆动。

调制信号：`s_FM(t) = A_c · cos( 2π f_c t + β · sin(2π f_m t) )`

#### SPWM 模式 (m_a ∈ [0, 1])

| 参数 | 含义 |
|---|---|
| `m_a = NUM / DEN` | 幅值调制比 (amplitude modulation ratio) |
| `m_a = 0` | 输出恒定为 50% 占空比方波 |
| `m_a = 0.8` | 80% 调制 — 线性调制区的典型上限 |
| `m_a = 1.0` | 100% 调制 — 线性调制区理论最大值 |

> **原理**：比较器 `sin(2π f_m t) × m_a` vs `triangle(2π f_c t)`

---

## 4. DDS 引擎参数

```python
F_CLK    = 100_000_000      # 系统时钟频率 (Hz)
DAC_DIV  = 128              # 时钟分频比
F_DAC    = F_CLK // DAC_DIV # DAC 更新率 = 781250 Hz
N        = 24               # 相位累加器位宽 (bits)
A        = 8                # 查找表地址位宽 (256 点)
D        = 8                # DAC 数据宽度 (DAC0832 为 8-bit)
```

| 参数 | 含义 | 为何取该值 |
|---|---|---|
| `F_CLK` | EGO1 板载 100 MHz 晶振 | 硬件固定，不可更改 |
| `DAC_DIV` | 128 分频 | DAC0832 建立时间 1 µs → 更新率 ≤ 1 MHz；781 kHz 留有安全余量 |
| `N` | 24 位相位累加器 | 频率分辨率 = 781250 / 2^24 ≈ 0.047 Hz，远超 20 Hz 的指标要求 |
| `A` | 8 位地址 | 256 点/周期，SNR ≈ 48 dB，波形肉眼平滑 |
| `D` | 8 位数据 | 匹配 DAC0832 分辨率 |

> **注意**：这些参数通常**不需要修改**。除非更换硬件或 DAC 型号。

---

## 5. 幅度参数

```python
AMP_CENTER = 128            # DC 偏置码 = Vref / 2 (2.5 V)
AMP_PEAK   = 64             # 峰值摆幅码 (2^6 = 64)
AMP_SHIFT  = 6              # log2(AMP_PEAK)，用于调制中的快速除法
```

### DAC 码到电压映射

```
V_OUT = - code / 256 × V_REF      (DAC0832 单极性模式)
```

| 参数 | DAC 码 | 输出电压 (Vref = 5V) |
|---|---|---|
| 最小值 | 128 − 64 = **64** | −64/256 × 5 = **−1.25 V** |
| 中心值 | **128** | −128/256 × 5 = **−2.5 V** |
| 最大值 | 128 + 64 = **192** | −192/256 × 5 = **−3.75 V** |

> EGO1 板载运放可能包含反相级，示波器上观察到的是反相后的正电压波形。峰峰值 ≈ **2.5 Vpp**（1.25 V ~ 3.75 V 或反向）。

### 为什么 PEAK = 64（2 的幂）？

调制模式中需要做 `÷ AMP_PEAK` 运算。如果 PEAK 是 2 的幂，该除法变为硬件右移（`>> AMP_SHIFT`），无需乘法器/DSP 资源。这是**以牺牲少量幅度调节精度换取硬件简洁性**的权衡。

---

## 6. 参数速查表

| 参数 | 类型 | 默认值 | 生效模式 | 合法范围 |
|---|---|---|---|---|
| `MODE` | `int` | `0` (SINE) | 全部 | 0, 1, 2, 3, 4, 5 |
| `FREQ_HZ` | `int` | `1000` | 基础波形 (0,1,2) | 100 ~ 10 000 |
| `CARRIER_FREQ` | `int` | `5000` | 调制 (3,4,5) | 100 ~ 50 000 |
| `MOD_FREQ` | `int` | `500` | 调制 (3,4,5) | 10 ~ CARRIER_FREQ/2 |
| `MOD_INDEX_NUM` | `int` | `1` | 调制 (3,4,5) | ≥ 0 |
| `MOD_INDEX_DEN` | `int` | `2` | 调制 (3,4,5) | ≥ 1 |
| `F_CLK` | `int` | `100_000_000` | 全部 | 不可更改 |
| `DAC_DIV` | `int` | `128` | 全部 | ≥ 1 |
| `N` | `int` | `24` | 全部 | ≥ 8 |
| `A` | `int` | `8` | 全部 | ≥ 4 |
| `D` | `int` | `8` | 全部 | 8 (DAC0832) |
| `AMP_CENTER` | `int` | `128` | 全部 | 0 ~ 255 |
| `AMP_PEAK` | `int` | `64` | 全部 | 1 ~ 128 |

---

## 7. 配置示例

### 示例 1：1 kHz 正弦波（最简配置）

```python
MODE    = WAVEFORM_SINE
FREQ_HZ = 1000
```

### 示例 2：AM 广播模拟

载波 5 kHz（模拟中波广播），调制信号 500 Hz（单音），50% 调制深度：

```python
MODE           = MODE_AM
CARRIER_FREQ   = 5000
MOD_FREQ       = 500
MOD_INDEX_NUM  = 1
MOD_INDEX_DEN  = 2          # m = 0.5
```

DAC 输出：幅度随 500 Hz 正弦波在 ±50% 范围摆动的 5 kHz 正弦波。

### 示例 3：FM 窄带调制

载波 10 kHz，调制信号 1 kHz，频偏 ±500 Hz：

```python
MODE           = MODE_FM
CARRIER_FREQ   = 10000
MOD_FREQ       = 1000
MOD_INDEX_NUM  = 1
MOD_INDEX_DEN  = 2          # β = 0.5, Δf = 500 Hz
```

DAC 输出：恒定幅度、频率在 9.5 ~ 10.5 kHz 之间摆动的正弦波。

### 示例 4：SPWM 逆变器驱动

调制波 50 Hz（工频），载波 20 kHz（超声频，无 audible noise），80% 调制：

```python
MODE           = MODE_SPWM
CARRIER_FREQ   = 20000
MOD_FREQ       = 50
MOD_INDEX_NUM  = 8
MOD_INDEX_DEN  = 10         # m_a = 0.8
```

DAC 输出：占空比按 50 Hz 正弦规律变化的两电平脉冲序列，经低通滤波后恢复 50 Hz 正弦波。

### 示例 5：FM 宽带广播模拟

载波 5 kHz，调制 500 Hz，频偏 ±2.5 kHz（β = 5，类似 FM 广播的宽带调制）：

```python
MODE           = MODE_FM
CARRIER_FREQ   = 5000
MOD_FREQ       = 500
MOD_INDEX_NUM  = 500
MOD_INDEX_DEN  = 100        # β = 5, Δf = 2500 Hz
```

---

## 8. 约束与限制

### 频率约束

| 约束 | 原因 |
|---|---|
| `FREQ_HZ < F_DAC / 2` | 奈奎斯特采样定理 |
| `FREQ_HZ ≤ 10 kHz` | 留出过渡带给重建滤波器；DAC 更新率 781 kHz ÷ 10 kHz ≈ 78× 过采样 |
| `CARRIER_FREQ < F_DAC / 2` | 载波也遵守奈奎斯特定理 |
| `MOD_FREQ < CARRIER_FREQ` | 调制频率应远低于载波频率 |
| SPWM: `m_f = f_c / f_m` 为整数 | 同步 PWM，消除分数次谐波 |

### 调制指数约束

| 模式 | 约束 | 超出后果 |
|---|---|---|
| AM | `0 ≤ m ≤ 1` | m > 1 → 过调制，包络检波失真，DAC 码可能裁剪 |
| FM | `β ≥ 0` | β 过大会使瞬时频率超出 [0, F_DAC/2)；实际 β ≤ 10 安全 |
| SPWM | `0 ≤ m_a ≤ 1` | m_a > 1 → 过调制，基波幅度不再线性增加，低次谐波急剧增大 |

### 硬件资源使用

| 模式 | 额外资源 (vs. 基础波形) |
|---|---|
| AM | 1 个额外相位累加器 + 3 个乘法器 + 移位器 |
| FM | 1 个额外相位累加器 + 1 个乘法器 + 移位器 |
| SPWM | 1 个额外相位累加器 + 1 个乘法器 + 比较器 |

所有乘法运算均映射到 Artix-7 的 DSP48E1 硬核（共 90 个可用），不占用 LUT 资源。

### 输出幅度约束

以默认 `AMP_CENTER=128, AMP_PEAK=64`：

| 模式 | 峰值 DAC 码范围 | 是否安全 |
|---|---|---|
| 基础波形 | [64, 192] | ✅ 始终在 [0, 255] 内 |
| AM (m=0.5) | [52, 204] | ✅ |
| AM (m=1.0) | [26, 230] | ✅ |
| FM | [64, 192] | ✅ 幅度恒定 |
| SPWM | {64, 192} | ✅ 二值输出 |

---

## 参考

- [DDS.md](DDS.md) — DDS 理论基础与调制的完整数学推导
- [DAC0830,32.pdf](DAC0830,32.pdf) — DAC0832 芯片数据手册
- [Ego1_UserManual_v2.2.pdf](Ego1_UserManual_v2.2.pdf) — EGO1 开发板用户手册
