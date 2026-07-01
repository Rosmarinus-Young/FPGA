"""
SignalGenerator - DDS-based Signal Generator for EGO1 FPGA Board
=================================================================

Target Board: EGO1 (Xilinx Artix-7 XC7A35T-1CSG324C)
DAC: DAC0832 (8-bit, single buffer mode)
System Clock: 100 MHz

Features:
  - Waveforms: Sine, Square, Triangle
  - Modulation: AM, FM, SPWM
  - Frequency range: 100 Hz ~ 10 kHz
  - Frequency resolution: ≤ 20 Hz (actual ~0.05 Hz)
  - Amplitude: ~2.5 Vpp (centered at 2.5 V, assuming 5 V Vref)
  - Algorithm: DDS (Direct Digital Synthesis) per doc/DDS.md

=== Modulation Theory (from doc/DDS.md) ===
  AM  (Amplitude Modulation):
    s_AM(t)  = A_c * [1 + m * sin(ω_m*t)] * sin(ω_c*t)
    where m ∈ [0, 1] is the modulation index.

  FM  (Frequency Modulation):
    s_FM(t)  = A_c * cos(2π*f_c*t + β * sin(2π*f_m*t))
    where β = Δf / f_m is the modulation index, Δf = peak deviation.

  SPWM (Sinusoidal Pulse Width Modulation):
    Natural-sampling comparator: sin(ω_m*t) vs triangle(ω_c*t).
    Output is a two-level digital signal with duty cycle varying
    sinusoidally at f_m.  Fundamental component at f_m with
    amplitude proportional to m_a = V_m / V_t.

=== EGO1 DAC0832 Pin Mapping ===
  DAC_D0     -> FPGA T8
  DAC_D1     -> FPGA R8
  DAC_D2     -> FPGA T6
  DAC_D3     -> FPGA R7
  DAC_D4     -> FPGA U6
  DAC_D5     -> FPGA U7
  DAC_D6     -> FPGA V9
  DAC_D7     -> FPGA U9
  DAC_BYTE2  -> FPGA R5   (ILE, active high)
  DAC_CS#    -> FPGA N6   (active low)
  DAC_WR1#   -> FPGA V6   (active low)
  DAC_WR2#   -> FPGA R6   (active low)
  DAC_XFER#  -> FPGA V7   (active low)
  SYS_CLK    -> FPGA P17  (100 MHz)
  FPGA_RESET -> FPGA P15

=== DDS Theory (from doc/DDS.md) ===
  f_out = FTW * f_clk / 2^N

  where:
    FTW  = frequency tuning word (phase increment per clock)
    f_clk = system clock frequency (100 MHz)
    N    = phase accumulator bit width

  The top A bits of the phase accumulator index into a waveform
  lookup table (LUT) pre-computed for one full period.

  DAC output code (unipolar, for D-bit DAC):
    LUT[k] = round( center + amplitude * sin(2*pi*k / 2^A) )

=== DAC0832 Single Buffer Mode ===
  ILE = 1 (High), CS/WR1/WR2/Xfer = 0 (Low)
  Data passes straight through: any change on DI[7:0] immediately
  updates the analog output (within 1 µs settling time).

=== Clock Divider ===
  System clock is divided by 128 to produce a ~781.25 kHz DAC
  update rate, well within the DAC0832's ~1 MHz max update rate
  and respecting the 1 µs settling time.
"""
from amaranth import *
import math


class SignalGenerator(Elaboratable):
    """DDS-based signal generator for EGO1 board with DAC0832.

    Generates basic waveforms (sine, square, triangle) and modulated
    signals (AM, FM, SPWM) using Direct Digital Synthesis.

    The phase accumulator runs at the DAC update rate (~781 kHz,
    derived from the 100 MHz system clock divided by 128).

    Usage
    -----
    Edit the MODE class attribute below to select the operating mode.
    For basic waveforms: set MODE = WAVEFORM_SINE / SQUARE / TRIANGLE
                         and configure FREQ_HZ.
    For modulation:      set MODE = MODE_AM / MODE_FM / MODE_SPWM
                         and configure CARRIER_FREQ, MOD_FREQ,
                         MOD_INDEX_NUM, MOD_INDEX_DEN.

    Pin Mapping (EGO1)
    ------------------
    - clk   -> P17 (100 MHz system clock)
    - rst   -> P15 (active-high reset button)
    - dac_data[0:7] -> T8, R8, T6, R7, U6, U7, V9, U9
    - dac_ile       -> R5  (must be tied to VCC if not using FPGA control)
    - dac_cs        -> N6  (must be tied to GND if not using FPGA control)
    - dac_wr1       -> V6  (must be tied to GND if not using FPGA control)
    - dac_wr2       -> R6  (must be tied to GND if not using FPGA control)
    - dac_xfer      -> V7  (must be tied to GND if not using FPGA control)
    """

    # ================================================================
    # User-configurable parameters
    # ================================================================

    # -- Mode selection --
    WAVEFORM_SINE     = 0   # Basic sine wave (uses FREQ_HZ)
    WAVEFORM_SQUARE   = 1   # Basic square wave (uses FREQ_HZ)
    WAVEFORM_TRIANGLE = 2   # Basic triangle wave (uses FREQ_HZ)
    MODE_AM           = 3   # Amplitude Modulation (uses CARRIER_FREQ + MOD_FREQ)
    MODE_FM           = 4   # Frequency Modulation (uses CARRIER_FREQ + MOD_FREQ)
    MODE_SPWM         = 5   # Sinusoidal PWM       (uses CARRIER_FREQ + MOD_FREQ)

    MODE = WAVEFORM_SINE       # <<< SELECT MODE HERE

    # -- Basic waveform parameters (used when MODE is WAVEFORM_*) --
    FREQ_HZ = 1000            # Output frequency: 100 ~ 10000 Hz

    # -- Modulation parameters (used when MODE is MODE_AM / MODE_FM / MODE_SPWM) --
    CARRIER_FREQ = 10000       # Carrier frequency (Hz)
    MOD_FREQ     = 1000        # Modulating signal frequency (Hz)

    # Modulation index — meaning depends on mode:
    #   AM:   m   = MOD_INDEX_NUM / MOD_INDEX_DEN  ∈ [0, 1]
    #         e.g. NUM=1, DEN=2  →  m = 0.5  (50% modulation depth)
    #   FM:   β   = MOD_INDEX_NUM / MOD_INDEX_DEN  (dimensionless)
    #         Δf = β * MOD_FREQ (peak frequency deviation in Hz)
    #         e.g. NUM=500, DEN=100  →  β = 5,  Δf = 2500 Hz
    #   SPWM: m_a = MOD_INDEX_NUM / MOD_INDEX_DEN  ∈ [0, 1]
    #         e.g. NUM=8, DEN=10  →  m_a = 0.8  (80% modulation)
    MOD_INDEX_NUM = 1
    MOD_INDEX_DEN = 2
    # ================================================================

    # DDS engine parameters
    F_CLK    = 100_000_000      # System clock frequency (Hz)
    DAC_DIV  = 128              # Clock divider ratio
    F_DAC    = F_CLK // DAC_DIV # DAC update rate = 781250 Hz
    N        = 24               # Phase accumulator width (bits)
    A        = 8                # LUT address width (256 entries)
    D        = 8                # DAC data width (DAC0832 is 8-bit)

    # Amplitude configuration:
    #   Vout = Vref * code / 256  (Vref = 5 V typical for DAC0832)
    #   For ~2.5 Vpp centered at 2.5 V:
    #     swing: 1.25 V ~ 3.75 V  ->  codes: 64 ~ 192
    #     center = 128 (2.5 V), peak = 64 (1.25 V)
    #   PEAK is a power of 2 so that divisions in modulation math
    #   become simple right-shifts (>> 6).
    AMP_CENTER = 128            # Code for DC offset = Vref / 2
    AMP_PEAK   = 64             # Code for 1.25 V peak swing (2^6)
    AMP_SHIFT  = 6              # log2(AMP_PEAK) for fast division

    # Frequency resolution: Δf = F_DAC / 2^N ≈ 0.047 Hz  << 20 Hz ✓

    def __init__(self, standalone=True):
        # DAC0832 data bus (8-bit)
        self.dac_data = Signal(self.D)

        # DAC0832 control signals
        self.dac_ile  = Signal()   # Input Latch Enable (active high)
        self.dac_cs   = Signal()   # Chip Select (active low)
        self.dac_wr1  = Signal()   # Write strobe 1 (active low)
        self.dac_wr2  = Signal()   # Write strobe 2 (active low)
        self.dac_xfer = Signal()   # Transfer control (active low)

        # Global signals
        self.clk = Signal()        # 100 MHz system clock
        self.rst = Signal()        # Active-high reset

        self.standalone = standalone

    # ------------------------------------------------------------------
    # Waveform LUT generators (Python pre-computation)
    # ------------------------------------------------------------------

    def _build_sine_lut(self):
        """Build unipolar sine wave LUT per DDS formula (16).

        LUT[k] = round(center + peak * sin(2*pi*k / 2^A))
        """
        lut = []
        for k in range(1 << self.A):
            phase = 2.0 * math.pi * k / (1 << self.A)
            value = self.AMP_CENTER + self.AMP_PEAK * math.sin(phase)
            code = int(round(value))
            lut.append(self._clamp(code))
        return lut

    def _build_square_lut(self):
        """Build unipolar square wave LUT (50% duty cycle)."""
        lut = []
        midpoint = (1 << self.A) // 2
        for k in range(1 << self.A):
            code = (self.AMP_CENTER + self.AMP_PEAK
                    if k < midpoint
                    else self.AMP_CENTER - self.AMP_PEAK)
            lut.append(self._clamp(code))
        return lut

    def _build_triangle_lut(self):
        """Build unipolar triangle wave LUT.

        The triangle wave is symmetric, starting at the negative peak,
        ramping up to the positive peak over the first quarter,
        then ramping down, with amplitude AMP_PEAK.
        """
        lut = []
        quarter = (1 << self.A) // 4
        for k in range(1 << self.A):
            if k < quarter:
                # [0, quarter): ramp up from 0 to 1
                norm = k / quarter
            elif k < 3 * quarter:
                # [quarter, 3*quarter): ramp down from 1 to -1
                norm = (2 * quarter - k) / quarter
            else:
                # [3*quarter, 4*quarter): ramp up from -1 to 0
                norm = (k - 4 * quarter) / quarter
            value = self.AMP_CENTER + self.AMP_PEAK * norm
            code = int(round(value))
            lut.append(self._clamp(code))
        return lut

    @staticmethod
    def _clamp(code):
        return max(0, min(255, code))

    # ------------------------------------------------------------------
    # Signed waveform LUT generators (for modulation modes)
    # Values are in [-AMP_PEAK, +AMP_PEAK], centred at zero.
    # ------------------------------------------------------------------

    def _build_signed_sine_lut(self):
        """Build signed sine wave LUT, range [-AMP_PEAK, +AMP_PEAK].

        LUT[k] = round(peak * sin(2*pi*k / 2^A))
        """
        lut = []
        for k in range(1 << self.A):
            phase = 2.0 * math.pi * k / (1 << self.A)
            code = int(round(self.AMP_PEAK * math.sin(phase)))
            lut.append(code)  # may be negative
        return lut

    def _build_signed_triangle_lut(self):
        """Build signed triangle wave LUT, range [-AMP_PEAK, +AMP_PEAK].

        Symmetric triangle: rises from 0 to +peak in first quarter,
        falls from +peak to -peak over the middle two quarters,
        rises from -peak back to 0 in the last quarter.
        """
        lut = []
        quarter = (1 << self.A) // 4
        for k in range(1 << self.A):
            if k < quarter:
                norm = k / quarter           #  0 → +1
            elif k < 3 * quarter:
                norm = (2 * quarter - k) / quarter  # +1 → -1
            else:
                norm = (k - 4 * quarter) / quarter  # -1 →  0
            code = int(round(self.AMP_PEAK * norm))
            lut.append(code)
        return lut

    # ------------------------------------------------------------------
    # Hardware elaboration
    # ------------------------------------------------------------------

    def elaborate(self, platform) -> Module:
        m = Module()

        # -- Tie sync domain clock and reset to top-level ports --
        if self.standalone:
            m.domains.sync = ClockDomain("sync")
            m.d.comb += [
                ClockSignal("sync").eq(self.clk),
                ResetSignal("sync").eq(self.rst),
            ]

        # -- DAC0832 single buffer mode --
        # ILE=HIGH, CS/WR1/WR2/XFER=LOW: data on dac_data appears
        # directly at the analog output (after settling time).
        m.d.comb += [
            self.dac_ile.eq(1),
            self.dac_cs.eq(0),
            self.dac_wr1.eq(0),
            self.dac_wr2.eq(0),
            self.dac_xfer.eq(0),
        ]

        # -- Clock divider for DAC update rate --
        # SPWM 需要更快的 DAC 更新率来减少方波边沿的斜坡。
        # DAC0832 settling time = 1 µs (typ), 所以 1 MHz 是理论极限。
        # 基础波形/AM/FM: 128 分频 → 781 kHz  (1.28 µs 周期, 有余量)
        # SPWM:           100 分频 →   1 MHz  (1.00 µs 周期, 刚好匹配 settling time)
        if self.MODE == self.MODE_SPWM:
            dac_div = 100
        else:
            dac_div = self.DAC_DIV
        f_dac = self.F_CLK // dac_div

        clk_div_cnt = Signal(range(dac_div))
        dac_tick    = Signal()

        with m.If(self.rst):
            m.d.sync += clk_div_cnt.eq(0)
        with m.Else():
            m.d.sync += clk_div_cnt.eq(clk_div_cnt + 1)
            with m.If(clk_div_cnt == dac_div - 1):
                m.d.sync += clk_div_cnt.eq(0)

        m.d.comb += dac_tick.eq(clk_div_cnt == 0)

        # -- Fixed-point modulation index (pre-computed in Python) --
        # m_fixed = int( (NUM/DEN) * 2^12 ), 12 fractional bits.
        m_fixed_val = int((self.MOD_INDEX_NUM / self.MOD_INDEX_DEN)
                          * (1 << 12) + 0.5)

        # ================================================================
        # Branch 1: Basic waveforms (Sine, Square, Triangle)
        # ================================================================
        if self.MODE in (self.WAVEFORM_SINE,
                         self.WAVEFORM_SQUARE,
                         self.WAVEFORM_TRIANGLE):

            ftw_value = int(self.FREQ_HZ * (1 << self.N) / self.F_DAC)
            ftw = Signal(self.N, reset=ftw_value)

            if self.MODE == self.WAVEFORM_SINE:
                lut_values = self._build_sine_lut()
            elif self.MODE == self.WAVEFORM_SQUARE:
                lut_values = self._build_square_lut()
            elif self.MODE == self.WAVEFORM_TRIANGLE:
                lut_values = self._build_triangle_lut()
            else:
                lut_values = self._build_sine_lut()

            phase_acc = Signal(self.N)
            with m.If(self.rst):
                m.d.sync += phase_acc.eq(0)
            with m.Elif(dac_tick):
                m.d.sync += phase_acc.eq(phase_acc + ftw)

            lut_addr = Signal(self.A)
            m.d.comb += lut_addr.eq(phase_acc[-self.A:])

            lut = Array(Const(v, unsigned(self.D)) for v in lut_values)
            with m.If(dac_tick):
                m.d.sync += self.dac_data.eq(lut[lut_addr])

        # ================================================================
        # Branch 2: AM — Amplitude Modulation  (DDS.md eq.27)
        #
        #   Modulation signal (基带 / 调制信号):
        #     m(t) = A_m * cos(2π * f_m * t)                              (eq.20)
        #     where A_m = m * A_c  (调制信号幅度由调制指数 m 和载波幅度决定)
        #
        #   Carrier signal (载波):
        #     c(t) = A_c * cos(2π * f_c * t)                              (eq.21)
        #
        #   Modulated signal (已调信号):
        #     s_AM(t) = A_c * [1 + m * cos(2π * f_m * t)] * cos(2π * f_c * t)  (eq.27)
        #
        #   调制指数 (modulation index):
        #     m = MOD_INDEX_NUM / MOD_INDEX_DEN  ∈ [0, 1]                (eq.25)
        #     当 m=0: 纯载波; 0<m≤1: 正常调制; m>1: 过调制(失真)
        #
        #   包络 (envelope) 的幅度变化:
        #     A_env(t) = A_c * [1 + m * cos(2π * f_m * t)]
        #     包络峰值: A_c * (1 + m)   包络谷值: A_c * (1 - m)
        #     包络振幅 (调制信号的有效幅度) = m * A_c = m * AMP_PEAK 码
        #
        #   Hardware implementation:
        #     展开: s_AM = A_c*cos(ω_c*t) + m*A_c*cos(ω_m*t)*cos(ω_c*t)
        #     LUT:  cos(ω_c*t) → carrier_sin ∈ [-64, 64]
        #           cos(ω_m*t) → mod_sin     ∈ [-64, 64]
        #     DAC = center + carrier_sin
        #                 + (m_fixed * mod_sin * carrier_sin) >> (AMP_SHIFT + 12)
        #     where m_fixed = int(m * 2^12), 共 18-bit 右移除法定点缩放
        # ================================================================
        elif self.MODE == self.MODE_AM:

            carrier_ftw_val = int(self.CARRIER_FREQ * (1 << self.N) / self.F_DAC)
            mod_ftw_val     = int(self.MOD_FREQ     * (1 << self.N) / self.F_DAC)

            carrier_ftw = Signal(self.N, reset=carrier_ftw_val)
            mod_ftw     = Signal(self.N, reset=mod_ftw_val)

            # Signed sine LUT for both carrier and modulating signal
            signed_vals = self._build_signed_sine_lut()
            signed_lut = Array(Const(v, signed(8)) for v in signed_vals)

            # Two independent phase accumulators
            carrier_phase = Signal(self.N)
            mod_phase     = Signal(self.N)

            with m.If(self.rst):
                m.d.sync += [carrier_phase.eq(0), mod_phase.eq(0)]
            with m.Elif(dac_tick):
                m.d.sync += [
                    carrier_phase.eq(carrier_phase + carrier_ftw),
                    mod_phase.eq(mod_phase + mod_ftw),
                ]

            carrier_addr = Signal(self.A)
            mod_addr     = Signal(self.A)
            m.d.comb += [
                carrier_addr.eq(carrier_phase[-self.A:]),
                mod_addr.eq(mod_phase[-self.A:]),
            ]

            carrier_sin = Signal(signed(8))
            mod_sin     = Signal(signed(8))
            m.d.comb += [
                carrier_sin.eq(signed_lut[carrier_addr]),
                mod_sin.eq(signed_lut[mod_addr]),
            ]

            # AM computation:
            #   dac = center + carrier_sin
            #       + (m_fixed * mod_sin * carrier_sin) >> (AMP_SHIFT + 12)
            product   = Signal(signed(24))
            modulated = Signal(signed(16))
            am_signed = Signal(signed(9))

            m.d.comb += [
                product.eq(m_fixed_val * mod_sin * carrier_sin),
                modulated.eq(product >> (self.AMP_SHIFT + 12)),
                am_signed.eq(carrier_sin + modulated),
            ]

            dac_raw = Signal(signed(10))
            m.d.comb += dac_raw.eq(self.AMP_CENTER + am_signed)

            with m.If(dac_tick):
                with m.If(dac_raw > 255):
                    m.d.sync += self.dac_data.eq(255)
                with m.Elif(dac_raw < 0):
                    m.d.sync += self.dac_data.eq(0)
                with m.Else():
                    m.d.sync += self.dac_data.eq(dac_raw[:8])

        # ================================================================
        # Branch 3: FM — Frequency Modulation  (DDS.md eq.34)
        #
        #   Modulation signal (调制信号):
        #     m(t) = A_m * cos(2π * f_m * t)                              (eq.20)
        #
        #   Instantaneous frequency (瞬时频率):
        #     f_i(t) = f_c + k_f * m(t) = f_c + Δf * cos(2π * f_m * t)  (eq.28)
        #     where k_f = frequency sensitivity (Hz/V)
        #           Δf  = k_f * A_m = β * f_m  (峰值频偏, peak deviation)
        #
        #   Modulation index (调制指数):
        #     β = MOD_INDEX_NUM / MOD_INDEX_DEN = Δf / f_m                (eq.33)
        #     β 的单位是弧度, 表示最大相位偏移量
        #
        #   Modulated signal (已调信号):
        #     s_FM(t) = A_c * cos( 2π*f_c*t + β * sin(2π*f_m*t) )        (eq.34)
        #
        #     总瞬时相位: θ_i(t) = 2π*f_c*t + β*sin(2π*f_m*t)           (eq.30)
        #     相位偏移量:  Δθ(t)   = β * sin(2π*f_m*t)                   (eq.32)
        #
        #   Hardware implementation:
        #     瞬时频率 → 瞬时 FTW:
        #       ftw_inst = carrier_ftw + ftw_delta
        #       where carrier_ftw = f_c * 2^N / F_DAC
        #             ftw_delta   = (ftw_dev * mod_sin) >> AMP_SHIFT
        #             ftw_dev     = Δf  * 2^N / F_DAC  (频偏 → FTW 偏差)
        #             mod_sin     ∈ [-64, 64]  (来自有符号正弦 LUT)
        #
        #     >> AMP_SHIFT 将 mod_sin 归一化到 [-1, 1], 再乘以 ftw_dev
        #
        #     载波相位累加器每 tick 加 ftw_inst (而非固定 ftw),
        #     然后用载波 LUT (无符号正弦) 查表输出恒定幅度的 DAC 码.
        #
        #     DAC 输出幅度恒定 = AMP_PEAK = 64 码 (1.25V),
        #     调制信息全部在频率变化中.
        # ================================================================
        elif self.MODE == self.MODE_FM:

            carrier_ftw_val = int(self.CARRIER_FREQ * (1 << self.N) / self.F_DAC)
            mod_ftw_val     = int(self.MOD_FREQ     * (1 << self.N) / self.F_DAC)

            # Peak frequency deviation & corresponding FTW deviation
            delta_f    = (self.MOD_INDEX_NUM / self.MOD_INDEX_DEN) * self.MOD_FREQ
            ftw_dev_val = int(delta_f * (1 << self.N) / self.F_DAC)

            carrier_ftw = Signal(self.N, reset=carrier_ftw_val)
            mod_ftw     = Signal(self.N, reset=mod_ftw_val)

            # Signed sine LUT for modulating signal
            signed_vals = self._build_signed_sine_lut()
            signed_lut  = Array(Const(v, signed(8)) for v in signed_vals)

            # Unsigned sine LUT for carrier (DAC output)
            carrier_vals = self._build_sine_lut()
            carrier_lut  = Array(Const(v, unsigned(self.D)) for v in carrier_vals)

            # Phase accumulators
            carrier_phase = Signal(self.N)
            mod_phase     = Signal(self.N)

            with m.If(self.rst):
                m.d.sync += [carrier_phase.eq(0), mod_phase.eq(0)]
            with m.Elif(dac_tick):
                # Modulating phase advances at constant rate
                m.d.sync += mod_phase.eq(mod_phase + mod_ftw)

            # Modulating signal
            mod_addr = Signal(self.A)
            mod_sin  = Signal(signed(8))
            m.d.comb += [
                mod_addr.eq(mod_phase[-self.A:]),
                mod_sin.eq(signed_lut[mod_addr]),
            ]

            # Instantaneous FTW = carrier_ftw + (ftw_dev * mod_sin) >> AMP_SHIFT
            ftw_delta = Signal(signed(self.N))
            ftw_inst  = Signal(self.N)

            m.d.comb += [
                ftw_delta.eq((ftw_dev_val * mod_sin) >> self.AMP_SHIFT),
                ftw_inst.eq(carrier_ftw + ftw_delta),
            ]

            # Carrier phase advances with modulated FTW each DAC tick
            with m.If(dac_tick):
                m.d.sync += carrier_phase.eq(carrier_phase + ftw_inst)

            carrier_addr = Signal(self.A)
            m.d.comb += carrier_addr.eq(carrier_phase[-self.A:])

            with m.If(dac_tick):
                m.d.sync += self.dac_data.eq(carrier_lut[carrier_addr])

        # ================================================================
        # Branch 4: SPWM — Sinusoidal Pulse Width Modulation  (DDS.md eq.46)
        #
        #   Modulation wave (调制波, 正弦):
        #     v_m(t) = V_m * cos(ω_m * t)                                 (eq.35)
        #     where V_m = m_a * V_t  (调制波幅值)
        #           ω_m = 2π * f_m
        #
        #   Carrier wave (载波, 双极性三角波):
        #     v_tri(t) = (2*V_t/π) * arcsin(sin(ω_c*t + π/2))            (eq.37)
        #     where V_t = 三角波峰值, ω_c = 2π * f_c
        #
        #   Amplitude modulation ratio (幅值调制比):
        #     m_a = MOD_INDEX_NUM / MOD_INDEX_DEN = V_m / V_t  ∈ [0, 1]  (eq.38)
        #
        #   Frequency modulation ratio (频率调制比 / 载波比):
        #     m_f = f_c / f_m  (应为整数以保证同步 PWM)                   (eq.39)
        #
        #   Comparator (比较器):
        #     v_an(t) = V_dc/2 * sgn( v_m(t) - v_tri(t) )                (eq.44)
        #     当 v_m > v_tri: 输出 HIGH (上桥臂导通)
        #     当 v_m < v_tri: 输出 LOW  (下桥臂导通)
        #
        #   Spectrum (频谱, eq.46):
        #     基波分量:  (V_dc/2) * m_a * cos(ω_m * t)    ← 频率 f_m
        #     载波谐波:  在 n*f_c 处 (n 为奇数), 幅度由 J_0 决定
        #     边带谐波:  在 n*f_c ± k*f_m 处, 幅度由 J_k 决定
        #     (n+k) 为奇数时边带非零 (双极性调制的特征)
        #
        #   Hardware implementation:
        #     mod_sin   = signed_sine_LUT[mod_phase_addr]     ∈ [-64, 64]
        #     tri_value = signed_triangle_LUT[carrier_phase_addr] ∈ [-64, 64]
        #
        #     mod_scaled = (m_fixed * mod_sin) >> 12  ← 将 m_a 乘入调制波
        #     comparator: mod_scaled > tri_value ? HIGH : LOW
        #
        #     HIGH = AMP_CENTER + AMP_PEAK = 192  (对应 +V_dc/2)
        #     LOW  = AMP_CENTER - AMP_PEAK = 64   (对应 -V_dc/2)
        #
        #     DAC 输出为两电平数字脉冲序列,
        #     经外部 LPF 滤波后恢复频率为 f_m 的正弦基波.
        # ================================================================
        elif self.MODE == self.MODE_SPWM:

            carrier_ftw_val = int(self.CARRIER_FREQ * (1 << self.N) / f_dac)
            mod_ftw_val     = int(self.MOD_FREQ     * (1 << self.N) / f_dac)

            carrier_ftw = Signal(self.N, reset=carrier_ftw_val)
            mod_ftw     = Signal(self.N, reset=mod_ftw_val)

            # Signed sine LUT (modulating wave)
            sine_vals = self._build_signed_sine_lut()
            sine_lut  = Array(Const(v, signed(8)) for v in sine_vals)

            # Signed triangle LUT (carrier wave)
            tri_vals = self._build_signed_triangle_lut()
            tri_lut  = Array(Const(v, signed(8)) for v in tri_vals)

            # Phase accumulators
            carrier_phase = Signal(self.N)  # triangle carrier
            mod_phase     = Signal(self.N)  # modulating sine

            with m.If(self.rst):
                m.d.sync += [carrier_phase.eq(0), mod_phase.eq(0)]
            with m.Elif(dac_tick):
                m.d.sync += [
                    carrier_phase.eq(carrier_phase + carrier_ftw),
                    mod_phase.eq(mod_phase + mod_ftw),
                ]

            carrier_addr = Signal(self.A)
            mod_addr     = Signal(self.A)
            m.d.comb += [
                carrier_addr.eq(carrier_phase[-self.A:]),
                mod_addr.eq(mod_phase[-self.A:]),
            ]

            tri_value = Signal(signed(8))
            mod_sin   = Signal(signed(8))
            m.d.comb += [
                tri_value.eq(tri_lut[carrier_addr]),
                mod_sin.eq(sine_lut[mod_addr]),
            ]

            # Scale modulating signal by modulation index m_a
            #   mod_scaled = (m_fixed * mod_sin) >> 12
            mod_scaled = Signal(signed(8))
            m.d.comb += mod_scaled.eq(
                (m_fixed_val * mod_sin) >> 12)

            # Comparator: mod_scaled > tri_value → HIGH, else LOW
            hi_code = self.AMP_CENTER + self.AMP_PEAK  # 192
            lo_code = self.AMP_CENTER - self.AMP_PEAK  #  64

            with m.If(dac_tick):
                with m.If(mod_scaled > tri_value):
                    m.d.sync += self.dac_data.eq(hi_code)
                with m.Else():
                    m.d.sync += self.dac_data.eq(lo_code)

        # ================================================================
        # Fallback (unknown mode) — output mid-scale as a safe default
        # ================================================================
        else:
            with m.If(dac_tick):
                m.d.sync += self.dac_data.eq(self.AMP_CENTER)

        return m
