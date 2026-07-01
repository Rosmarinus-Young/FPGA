# DDS

直接数字频率合成（DDS）本质是用数字方法精确控制相位，再通过查表输出波形

## 采样

以正弦信号为例，我们要生成一个频率为 $f_{\text{out}}$ 的理想正弦信号
$$
s(t) = A \sin\big(2\pi f_{\text{out}} t + \phi_0\big)
\tag{1}
$$
定义瞬时相位（单位：弧度）
$$
\Phi(t) = 2\pi f_{\text{out}} t + \phi_0
\tag{2}
$$
则
$$
\frac{d\Phi(t)}{dt} = 2\pi f_{\text{out}} = \omega_{\text{out}}
\tag{3}
$$
相位随时间线性增长，斜率为角频率 $\omega_{\text{out}} = 2\pi f_{\text{out}}$

DDS 是数字系统，使用固定时钟频率 $f_{\text{clk}}$ 对相位进行采样，时钟周期
$$
T_{\text{clk}} = \frac{1}{f_{\text{clk}}}
\tag{4}
$$
我们在每个时钟上升沿更新一次相位，设第 $n$ 个时钟周期的离散时刻为
$$
t_n = n \cdot T_{\text{clk}}, \quad n = 0,1,2,\dots
$$
则离散相位序列为
$$
\Phi[n] = \Phi(n T_{\text{clk}}) = 2\pi f_{\text{out}} \, n T_{\text{clk}} + \phi_0
\tag{5}
$$
相邻两个时刻的相位增量（步长）是常数
$$
\Delta\Phi = \Phi[n+1] - \Phi[n] = 2\pi f_{\text{out}} T_{\text{clk}} = 2\pi \frac{f_{\text{out}}}{f_{\text{clk}}}
\tag{6}
$$
为了让数字电路处理，需要把相位量化为有限位宽的整数，引入**相位累加器**

我们把完整相位周期 $2\pi$ 映射到整数范围 $0$ 到 $2^N - 1$，$N$ 为相位累加器位宽

对于一个N位的二进制累加器，每个时钟周期将内部保存的相位值 $\Phi$ 加上一个常数，记作 $M$（即**频率控制字**，Frequency Tuning Word，FTW），然后取模 $2^N$（自然溢出即可实现模运算），即
$$
\Phi(n) = \big( \Phi(n-1) + M \big) \bmod 2^N
\tag{7}
$$
定义满量程 $\Phi_{\max} = 2^N$ 对应于一个完整的正弦周期 $2\pi$ 弧度，则任意时刻的瞬时相位角为
$$
\theta(n) = 2\pi \cdot \frac{\Phi(n)}{2^N}
\tag{8}
$$
相位累加器每时钟帧增加 $M$，相当于每 $T_{clk}$ 秒增加的相位角角度为
$$
\Delta\theta = 2\pi \cdot \frac{M}{2^N}
\tag{9}
$$
由（3）式，令离散增量与连续增量相等，得
$$
\omega_{out} = \frac{\Delta\theta}{T_{clk}} = 2\pi \cdot \frac{F_{tw}}{2^N} \cdot f_{clk}
\tag{10}
$$
两边除以 $2\pi$ 得到输出频率
$$
\boxed{ f_{out} = \frac{F_{tw} \cdot f_{clk}}{2^N} }
\tag{11}
$$
根据奈奎斯特采样定理，对于一个最高频率为 $f_H$ 的连续时间信号，采样频率 $f_s$ 必须满足
$$
f_s > 2 f_H
$$
才能无失真地重建原信号，DDS中系统时钟 $f_{clk}$ 就是 DAC 的更新率，也就是采样频率 $f_s = f_{clk}$ ，所以理论上，DDS 能输出的最大正弦波频率就是 $f_{clk}/2$

## 波形查找表

累加器在 $n$ 时刻的值为
$$
\Phi[n] = \big( n \cdot M + \Phi_0 \big) \bmod 2^N
\tag{12}
$$
其中 $\Phi_0$ 是初始相位对应的整数（即**相位控制字**）

通常我们只取 $\Phi[n]$ 的高几位作为**波形查找表**（LUT）的地址，因为完整 $N$ 位做地址会要求太大的 ROM

设取高位位数为 $A$ 位（地址宽度），则地址索引
$$
\text{idx}[n] = \left\lfloor \frac{\Phi[n]}{2^{N-A}} \right\rfloor
\tag{13}
$$
我们预计算一个周期的正弦波采样值，存储在 ROM 中，希望得到原始信号为标准双极性正弦，即
$$
s(k) = \sin\!\left( \frac{2\pi k}{2^A} \right)
\tag{14}
$$
其中 $k = 0, 1, \dots, 2^A-1$ 是相位累加器截断后的索引，输出值域为 $[-1, +1]$，但是，DAC接受单极性数字码（比如 0 到 $2^D-1$，对应电压 0 到 $V_{\text{ref}}$，$D$ 即DAC分辨率），不能直接把负电压给DAC，于是添加直流偏置并乘缩放因子
$$
s_{\text{uni}}(k) = \frac{1}{2} + \frac{1}{2} \sin\!\left( \frac{2\pi k}{2^A} \right)
\tag{15}
$$
即单极性正弦公式，再把 $[0, 1]$ 的幅度线性映射到这个DAC的整数区间，得波形查找表
$$
\begin{aligned}
\text{LUT}[k] &= \text{round}\!\left( \left[ \frac{1}{2} + \frac{1}{2} \sin\!\left( \frac{2\pi k}{2^A} \right) \right] \times (2^D - 1) \right) \\
&= \text{round}\!\left( \frac{2^D - 1}{2} + \frac{2^D - 1}{2} \sin\!\left( \frac{2\pi k}{2^A} \right) \right)
\end{aligned}
\tag{16}
$$
其中$\text{round}(\cdot)$为量化取整，把连续值四舍五入变成D位整数存储到LUT

综上，DDS数字输出序列为
$$
x[n] = \text{LUT}\big[ idx(n) \big]
\tag{17}
$$
这里 $n$ 是时钟周期索引

## 滤波

DAC 在每个采样周期将 $x[n]$ 保持为常值，直到下一个时钟沿，则输出可建模为
$$
x_{DAC}(t) = \sum_{n=-\infty}^{\infty} x[n] \cdot \text{rect}\!\left( \frac{t - nT_{clk} - T_{clk}/2}{T_{clk}} \right)
\tag{18}
$$
其中矩形函数
$$
\text{rect}(t) = \begin{cases} 1, & |t| \le 1/2 \\ 0, & \text{otherwise} \end{cases}
$$
实际上我们把这种DAC的每个采样周期保持输出一恒定值的过程称作零阶保持模型（Zero-Order Hold, ZOH）

对于理想的冲激采样信号
$$
x_s(t) = \sum_{n=-\infty}^{\infty} x[n] \, \delta(t - nT)
$$
它的每个冲激的强度就是采样值，如果把 $x_s(t)$ 输入一个冲激响应为 $h(t)$​ 的系统，输出就是
$$
y(t) = x_s(t) * h(t) = \sum_{n} x[n] \int_{-\infty}^{\infty} \delta(\tau - nT) \, h(t - \tau) d\tau = \sum_{n} x[n] \, h(t - nT)
$$
比较此式与前面直接用矩形叠加的式子，若取
$$
h(t) = \text{rect}\!\left( \frac{t - T/2}{T} \right)
$$
则 $h(t - nT) = \text{rect}\!\left( \frac{t - nT - T/2}{T} \right)$，这正是我们需要的那个矩形脉冲

所以，零阶保持过程完全等价于一个冲激响应为宽度 $T$、延迟 $T/2$ 的矩形脉冲的 LTI 系统，即
$$
h_{\text{ZOH}}(t) = \text{rect}\!\left( \frac{t - T/2}{T} \right)
$$
则DAC的采样保持可由理想采样与矩形脉冲的卷积描述

理想采样信号为
$$
x_s(t) = \sum_{n} x[n] \,\delta(t - nT_{clk})
$$
其傅里叶变换为
$$
\begin{aligned}
X_s(f) &= \int_{-\infty}^{\infty} x_s(t) \, e^{-j2\pi f t} \, dt \\
&= \int_{-\infty}^{\infty} \left( \sum_{n} x[n] \, \delta(t - nT) \right) e^{-j2\pi f t} \, dt \\
&= \sum_{n} x[n] \int_{-\infty}^{\infty} \delta(t - nT) \, e^{-j2\pi f t} \, dt \\ 
&= \sum_{n=-\infty}^{\infty} x[n] \, e^{-j2\pi f n T}
\end{aligned}
$$
对于原始连续正弦时间信号 $x(t)$，其傅里叶变换记为 $X_{\text{ideal}}(f)$，根据傅里叶逆变换
$$
x[n] = x(nT) = \int_{-\infty}^{\infty} X_{\text{ideal}}(\nu) \, e^{j2\pi \nu n T} \, d\nu
$$
带入上式，得
$$
\begin{aligned}
X_s(f) &= \sum_{n} \left( \int_{-\infty}^{\infty} X_{\text{ideal}}(\nu) \, e^{j2\pi \nu n T} d\nu \right) e^{-j2\pi f n T} \\
&= \int_{-\infty}^{\infty} X_{\text{ideal}}(\nu) \left( \sum_{n} e^{-j2\pi (f - \nu) n T} \right) d\nu
\end{aligned}
$$
由于 $$p(t) = \sum_{n=-\infty}^{\infty} \delta(t - nT)$$ ， $$P(f) = \frac{1}{T} \sum_{k=-\infty}^{\infty} \delta\!\left( f - \frac{k}{T} \right)$$ ，由定义 $p(t) = \int_{-\infty}^{\infty} P(f) \, e^{j2\pi f t} \, df$ ，则
$$
\sum_n \delta(t - nT) = \int \frac{1}{T} \sum_k \delta\!\left(f - \frac{k}{T}\right) e^{j2\pi f t} df = \frac{1}{T} \sum_k e^{j2\pi (k/T) t}
$$
即
$$
\sum_{n=-\infty}^{\infty} \delta(t - nT) = \frac{1}{T} \sum_{k=-\infty}^{\infty} e^{j2\pi \frac{k}{T} t}
$$
对上式两边傅里叶变换，以 $\alpha$ 为频率变量，则
$$
\sum_{n=-\infty}^{\infty} e^{-j2\pi \alpha n T} = \frac{1}{T} \sum_{k=-\infty}^{\infty} \delta\!\left( \alpha - \frac{k}{T} \right)
$$
令 $\alpha = f - \nu$，则
$$
\sum_{n} e^{-j2\pi (f - \nu) n T} = \frac{1}{T} \sum_{k=-\infty}^{\infty} \delta\!\left( f - \nu - \frac{k}{T} \right)
$$
带回原式
$$
\begin{aligned}
X_s(f) &= \int_{-\infty}^{\infty} X_{\text{ideal}}(\nu) \left[ \frac{1}{T} \sum_{k} \delta\!\left( f - \nu - \frac{k}{T} \right) \right] d\nu \\[4pt]
&= \frac{1}{T} \sum_{k=-\infty}^{\infty} \int_{-\infty}^{\infty} X_{\text{ideal}}(\nu) \, \delta\!\left( \nu - \left( f - \frac{k}{T} \right) \right) d\nu \\
&= \frac{1}{T} \sum_{k=-\infty}^{\infty} X_{\text{ideal}}\!\left( f - \frac{k}{T} \right) \\
&=  f_{\text{clk}} \sum_{k=-\infty}^{\infty} X_{\text{ideal}}(f - k f_{\text{clk}})
\end{aligned}
$$
零阶保持相当于与一个宽度为 $T_{clk}$ 的矩形脉冲卷积
$$
h_{ZOH}(t) = \text{rect}\!\left( \frac{t - T_{clk}/2}{T_{clk}} \right)
$$
其傅里叶变换为
$$
H_{ZOH}(f) = T_{clk} \, \text{sinc}(f T_{clk}) \, e^{-j\pi f T_{clk}}
$$
因此 DAC 输出频谱为
$$
\begin{aligned}
X_{DAC}(f) &= X_s(f) \cdot H_{ZOH}(f) \\
&= T_{clk} \, \text{sinc}(f T_{clk}) \, e^{-j\pi f T_{clk}} \cdot f_{clk} \sum_{k=-\infty}^{\infty} X_{\text{ideal}}(f - k f_{clk}) \\
&=  \text{sinc}\!\left(\frac{f}{f_{clk}}\right) e^{-j\pi f / f_{clk}} \sum_{k=-\infty}^{\infty} X_{\text{ideal}}(f - k f_{clk})
\end{aligned}
\tag{19}
$$
由此可见，主信号位于 $k=0$ 项，$X_{\text{ideal}}(f)$ 乘以 $\text{sinc}(f/f_{clk})$ 包络，在 $f = f_{out}$ 处，sinc 的值约为 $\text{sinc}(f_{out}/f_{clk}) \approx 1$（当 $f_{out} \ll f_{clk}$ 时），近乎无损

镜像频率出现在 $k = \pm 1, \pm 2, \dots$ 处，即频率 $k f_{clk} \pm f_{out}$。它们被 sinc 包络衰减，但幅度依然可观，特别是在 $f_{clk} - f_{out}$ 附近

所以，需要一个截止频率 $f_c$ 满足
$$
f_{\text{out,max}} \le f_c \ll f_{\text{clk}} - f_{\text{out,max}}
$$
的LPF，保留 $f_{\text{out}}$，同时把最低频率的镜像 $f_{\text{clk}} - f_{\text{out}}$ 抑制到足够小的程度

为了在滤波器的复杂度、相位线性和成本之间平衡，工程上通常把最大输出频率限制在 $f_{\text{clk}}/4$ 甚至更低，比如取
$$
f_c \approx 1.5 \times f_{\text{out,max}}
$$
或取
$$
\quad f_c \approx 0.4\, f_{\text{clk}}
$$

## 实现

使用DDS计算波形信号，通过EGO1的DAC0832外设实现信号发生器功能，代码编辑使用python的amaranth库，见SignalGenerator.py

由EGO1用户手册，板载时钟源为100MHz

![EGO1-SysClk](markdown_img/DDS/EGO1-SysClk.png)

DAC0832芯片手册，建立时间（当改变输入的数字编码（比如从全 0 跳到全 1）后，模拟输出（电流或电压）进入并保持在最终值附近某个误差带内（通常是 ±½ LSB）所需的时间）为1us

![DAC0832-KeySpecifications](markdown_img/DDS/DAC0832-KeySpecifications.png)

则为了使DAC有稳定输出，将时钟信号128分频，得到新时钟周期约为1.28us，防止输出失真

上图 `Resolution: 8 bits ` 说明DAC0832分辨率为 8 位

我们选择 24 位相位累加器，取高 8 位，比如对正弦波而言，2^8 = 256 点量化的理论信噪比约 48 dB，对于通用信号发生器已经很好，每个采样点间隔 360°/256 = 1.4°，波形肉眼看起来连续平滑

FTW由式（11）计算得，即 `ftw_value = int(self.FREQ_HZ * (1 << self.N) / self.F_DAC)`

由手册，DAC0832为电流输出型DAC，但是EGO1已外接运放转电压，可以看出EGO1的运放接法与手册中的Figure18相同，则
$$
V_{OUT} = - \frac{D}{256} \times V_{REF}
$$
![DAC0832-Features](markdown_img/DDS/DAC0832-Features.png)

<img src="markdown_img/DDS/EGO1-DAC.png" alt="EGO1-DAC" style="zoom: 67%;" />

<img src="markdown_img/DDS/DAC0832-BasicUnipolarOutputVoltage.png" alt="DAC0832-BasicUnipolarOutputVoltage" style="zoom: 67%;" />

确定 $V_{ref}$ 即可确定输出电压大小，由原理图 $V_{ref} = 5V$ (存疑)

![EGO1-DAC0832原理图](markdown_img/DDS/EGO1-DAC0832原理图.png)

使用式（15）（16）预计算LUT，直流偏置 2.5V，又要求幅度 2V，即峰峰值 2Vpp，波形需要从 2.5V 向上摆 1V 到 3.5V ，向下摆 1V 到 1.5V ，则对应代码中偏置 128，偏移量 3.5 / 5 * 256 - 128 = 51，再通过信号函数计算LUT即可

配置CS=WR1=WR2=XFER=0，ILE=1，即下图中的”流量直通“配置，这种配置下，两个内部锁存器都变成透明的，数据线上的任何变化都会立刻反应到模拟输出端，便于调试且没有软件延迟

![DAC0832-SingleBufferedOpeartion](markdown_img/DDS/DAC0832-SingleBufferedOpeartion.png)

代码架构

| 方法/函数               | 类型            | 作用                                                         |
| ----------------------- | --------------- | ------------------------------------------------------------ |
| `_clamp(code)`          | `@staticmethod` | 将 LUT 代码值限制在 `[0, 255]` 范围内，防止量化取整越界      |
| `_build_sine_lut()`     | 实例方法        | 根据 DDS 公式 (16) 预计算 256 点单极性正弦波 LUT：$128 + 51 \times \sin(2\pi k / 256)$ |
| `_build_square_lut()`   | 实例方法        | 预计算 256 点方波 LUT：前半周期为高电平 (179)，后半周期为低电平 (77)，占空比 50% |
| `_build_triangle_lut()` | 实例方法        | 预计算 256 点三角波 LUT：从最低点线性上升到最高点再线性下降，对称三角波 |
| `__init__()`            | 构造函数        | 定义所有 I/O 端口信号：`dac_data`(8)、5 个 DAC 控制信号、`clk`、`rst` |
| `elaborate(platform)`   | 硬件描述入口    | 构建完整的数字电路：DAC 控制逻辑、时钟分频器、DDS 相位累加器、LUT 查找表、DAC 输出寄存器 |
| `__main__`              | 脚本入口        | 调用 `verilog.convert` 生成 [SignalGenerator.v](vscode-webview://0qqm7eqam3a0ouhlanc3vda01imgqt6b0a7hf215nvlr8e4p7209/SignalGenerator.v)，生成 [SignalGenerator.xdc](vscode-webview://0qqm7eqam3a0ouhlanc3vda01imgqt6b0a7hf215nvlr8e4p7209/SignalGenerator.xdc) 引脚约束，打印参数报告并验证频率范围和分辨率 |

运行结果

```powershell
(FPGA-env) PS D:\UserFiles\MyProjects\FPGAProject\FPGA> python SignalGenerator.py
========================================================
  DDS Signal Generator — EGO1 + DAC0832
========================================================
  Waveform          : sine
  Target frequency  : 1000 Hz
  Actual frequency  : 999.96 Hz
  FTW               : 21474 (0x0053E2)
  Frequency res.    : 0.05 Hz
  DAC update rate   : 781250 Hz
  Amplitude         : 2 Vpp (center 2.5 V)
  DAC mode          : single buffer
--------------------------------------------------------
  Verilog           : SignalGenerator.v
  Constraints       : SignalGenerator.xdc
========================================================
```

在Vivado中创建工程，导入生成的 `.v` 和 `.xdc` 文件，生成比特流烧进EGO1，在板载 `J2` 排针处通过示波器检验生成的模拟波形
