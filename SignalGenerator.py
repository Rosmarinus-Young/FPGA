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
  - Button control: 5 push buttons for runtime mode selection

=== Button Mapping (EGO1 S0–S4) ===
  btn_sine     -> S0 (R11)  : WAVEFORM_SINE
  btn_square   -> S1 (R17)  : WAVEFORM_SQUARE
  btn_triangle -> S2 (R15)  : WAVEFORM_TRIANGLE
  btn_am       -> S3 (V1)   : MODE_AM
  btn_fm       -> S4 (U4)   : MODE_FM

  Each button is debounced (~10 ms) and edge-detected.
  Pressing a button switches the runtime mode register immediately.
  The module parameter MODE sets the power-on / reset default mode.

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
    Edit the MODE class attribute below to select the power-on default.
    For basic waveforms: set MODE = WAVEFORM_SINE / SQUARE / TRIANGLE
                         and configure FREQ_HZ.
    For modulation:      set MODE = MODE_AM / MODE_FM / MODE_SPWM
                         and configure CARRIER_FREQ, MOD_FREQ,
                         MOD_INDEX_NUM, MOD_INDEX_DEN.

    At runtime, press the 5 push buttons (EGO1 S0–S4) to switch modes:
      S0 → Sine   S1 → Square   S2 → Triangle   S3 → AM   S4 → FM

    Pin Mapping (EGO1)
    ------------------
    - clk         -> P17 (100 MHz system clock)
    - rst         -> P15 (active-high reset button)
    - btn_sine    -> R11 (S0)
    - btn_square  -> R17 (S1)
    - btn_triangle -> R15 (S2)
    - btn_am      -> V1  (S3)
    - btn_fm      -> U4  (S4)
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

    MODE = WAVEFORM_SINE       # <<< SELECT DEFAULT MODE HERE (power-on / reset)

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

    # Button debounce threshold: BTN_THRESHOLD / F_CLK = hold time
    # 1_000_000 / 100 MHz = 10 ms minimum press duration
    BTN_THRESHOLD = 1_000_000

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

        # Button inputs (EGO1 push buttons S0–S4)
        self.btn_sine     = Signal()   # S0 → WAVEFORM_SINE
        self.btn_square   = Signal()   # S1 → WAVEFORM_SQUARE
        self.btn_triangle = Signal()   # S2 → WAVEFORM_TRIANGLE
        self.btn_am       = Signal()   # S3 → MODE_AM
        self.btn_fm       = Signal()   # S4 → MODE_FM

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
    # Button debounce helper
    # ------------------------------------------------------------------

    def _add_button_debounce(self, m, btn_input, name):
        """Add a debounce + edge-detect circuit for one button.

        Returns a Signal that pulses high for one cycle when the button
        press is confirmed (held ≥ BTN_THRESHOLD cycles ≈ 10 ms).
        """
        # Synchronize the asynchronous button input
        btn_sync = Signal(name=f"{name}_sync")
        m.d.sync += btn_sync.eq(btn_input)

        # Debounce counter: counts while button is high, resets when low
        cnt = Signal(range(self.BTN_THRESHOLD + 1), name=f"{name}_cnt")
        with m.If(btn_sync):
            with m.If(cnt < self.BTN_THRESHOLD):
                m.d.sync += cnt.eq(cnt + 1)
        with m.Else():
            m.d.sync += cnt.eq(0)

        # Stable signal: asserted when counter saturates
        btn_stable = Signal(name=f"{name}_stable")
        m.d.comb += btn_stable.eq(cnt >= self.BTN_THRESHOLD)

        # Rising-edge detector → single-cycle pulse
        btn_stable_prev = Signal(name=f"{name}_prev")
        m.d.sync += btn_stable_prev.eq(btn_stable)

        btn_pulse = Signal(name=f"{name}_pulse")
        m.d.comb += btn_pulse.eq(btn_stable & ~btn_stable_prev)

        return btn_pulse

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

        # ================================================================
        # Button debounce — one circuit per button, producing single-cycle
        # pulses on confirmed press.
        # ================================================================
        pulse_sine     = self._add_button_debounce(m, self.btn_sine,     "sine")
        pulse_square   = self._add_button_debounce(m, self.btn_square,   "square")
        pulse_triangle = self._add_button_debounce(m, self.btn_triangle, "triangle")
        pulse_am       = self._add_button_debounce(m, self.btn_am,       "am")
        pulse_fm       = self._add_button_debounce(m, self.btn_fm,       "fm")

        # ================================================================
        # Runtime mode register
        #
        # 3-bit register reset to the PYTHON-level MODE constant.
        # On a debounced button pulse the mode switches immediately.
        # ================================================================
        mode = Signal(3, reset=self.MODE)

        with m.If(pulse_sine):
            m.d.sync += mode.eq(self.WAVEFORM_SINE)
        with m.Elif(pulse_square):
            m.d.sync += mode.eq(self.WAVEFORM_SQUARE)
        with m.Elif(pulse_triangle):
            m.d.sync += mode.eq(self.WAVEFORM_TRIANGLE)
        with m.Elif(pulse_am):
            m.d.sync += mode.eq(self.MODE_AM)
        with m.Elif(pulse_fm):
            m.d.sync += mode.eq(self.MODE_FM)

        # ================================================================
        # Clock divider for DAC update rate
        #
        # SPWM needs a faster update rate (1 MHz) to reduce slope on
        # square-wave edges; other modes use 781 kHz.  The divisor is
        # selected combinatorially based on the runtime mode.
        # ================================================================
        dac_div = Signal(8)
        m.d.comb += dac_div.eq(Mux(mode == self.MODE_SPWM, 100,
                                   self.DAC_DIV))
        f_dac = self.F_CLK // self.DAC_DIV  # nominal, used for FTW calc

        clk_div_cnt = Signal(range(max(self.DAC_DIV, 100)))
        dac_tick    = Signal()

        with m.If(self.rst):
            m.d.sync += clk_div_cnt.eq(0)
        with m.Else():
            m.d.sync += clk_div_cnt.eq(clk_div_cnt + 1)
            with m.If(clk_div_cnt + 1 == dac_div):
                m.d.sync += clk_div_cnt.eq(0)

        m.d.comb += dac_tick.eq(clk_div_cnt == 0)

        # ================================================================
        # Fixed-point modulation index (pre-computed in Python)
        # m_fixed = int( (NUM/DEN) * 2^12 ), 12 fractional bits.
        # ================================================================
        m_fixed_val = int((self.MOD_INDEX_NUM / self.MOD_INDEX_DEN)
                          * (1 << 12) + 0.5)

        # ================================================================
        # Build all LUTs (Python pre-computation)
        # ================================================================
        sine_lut_vals     = self._build_sine_lut()
        square_lut_vals   = self._build_square_lut()
        triangle_lut_vals = self._build_triangle_lut()
        signed_sine_vals  = self._build_signed_sine_lut()
        signed_tri_vals   = self._build_signed_triangle_lut()

        # ================================================================
        # Branch 1: Basic Waveforms (Sine, Square, Triangle)
        #
        # Always elaborated.  The active sub-waveform is selected at
        # runtime via mode[1:0] (values 0, 1, 2).
        # Output: dac_basic_comb
        # ================================================================
        ftw_basic_val = int(self.FREQ_HZ * (1 << self.N) / self.F_DAC)
        ftw_basic = Signal(self.N, reset=ftw_basic_val)

        phase_acc_basic = Signal(self.N)
        with m.If(self.rst):
            m.d.sync += phase_acc_basic.eq(0)
        with m.Elif(dac_tick):
            m.d.sync += phase_acc_basic.eq(phase_acc_basic + ftw_basic)

        lut_addr_basic = Signal(self.A)
        m.d.comb += lut_addr_basic.eq(phase_acc_basic[-self.A:])

        # Instantiate the three LUT arrays
        sine_lut     = Array(Const(v, unsigned(self.D)) for v in sine_lut_vals)
        square_lut   = Array(Const(v, unsigned(self.D)) for v in square_lut_vals)
        triangle_lut = Array(Const(v, unsigned(self.D)) for v in triangle_lut_vals)

        # Combinatorial read from each LUT
        sine_lut_out     = Signal(unsigned(self.D))
        square_lut_out   = Signal(unsigned(self.D))
        triangle_lut_out = Signal(unsigned(self.D))
        m.d.comb += [
            sine_lut_out.eq(sine_lut[lut_addr_basic]),
            square_lut_out.eq(square_lut[lut_addr_basic]),
            triangle_lut_out.eq(triangle_lut[lut_addr_basic]),
        ]

        # Mux the three LUT outputs based on mode[1:0]
        basic_lut_mux = Signal(unsigned(self.D))
        with m.Switch(mode[:2]):
            with m.Case(self.WAVEFORM_SINE & 0b11):
                m.d.comb += basic_lut_mux.eq(sine_lut_out)
            with m.Case(self.WAVEFORM_SQUARE & 0b11):
                m.d.comb += basic_lut_mux.eq(square_lut_out)
            with m.Case(self.WAVEFORM_TRIANGLE & 0b11):
                m.d.comb += basic_lut_mux.eq(triangle_lut_out)
            with m.Default():
                m.d.comb += basic_lut_mux.eq(sine_lut_out)

        # Basic waveforms branch combinatorial output
        dac_basic_comb = Signal(8)
        m.d.comb += dac_basic_comb.eq(basic_lut_mux)

        # ================================================================
        # Branch 2: AM — Amplitude Modulation  (DDS.md eq.27)
        #
        #   s_AM(t) = A_c * [1 + m * cos(2π f_m t)] * cos(2π f_c t)
        #
        #   Hardware:
        #     DAC = center + carrier_sin
        #                 + (m_fixed * mod_sin * carrier_sin) >> (AMP_SHIFT + 12)
        #   Output: dac_am_comb
        # ================================================================
        carrier_ftw_am_val = int(self.CARRIER_FREQ * (1 << self.N) / self.F_DAC)
        mod_ftw_am_val     = int(self.MOD_FREQ     * (1 << self.N) / self.F_DAC)

        carrier_ftw_am = Signal(self.N, reset=carrier_ftw_am_val)
        mod_ftw_am     = Signal(self.N, reset=mod_ftw_am_val)

        # Signed sine LUT for both carrier and modulating signal
        signed_lut_am = Array(Const(v, signed(8)) for v in signed_sine_vals)

        # Two independent phase accumulators
        carrier_phase_am = Signal(self.N)
        mod_phase_am     = Signal(self.N)

        with m.If(self.rst):
            m.d.sync += [carrier_phase_am.eq(0), mod_phase_am.eq(0)]
        with m.Elif(dac_tick):
            m.d.sync += [
                carrier_phase_am.eq(carrier_phase_am + carrier_ftw_am),
                mod_phase_am.eq(mod_phase_am + mod_ftw_am),
            ]

        carrier_addr_am = Signal(self.A)
        mod_addr_am     = Signal(self.A)
        m.d.comb += [
            carrier_addr_am.eq(carrier_phase_am[-self.A:]),
            mod_addr_am.eq(mod_phase_am[-self.A:]),
        ]

        carrier_sin_am = Signal(signed(8))
        mod_sin_am     = Signal(signed(8))
        m.d.comb += [
            carrier_sin_am.eq(signed_lut_am[carrier_addr_am]),
            mod_sin_am.eq(signed_lut_am[mod_addr_am]),
        ]

        # AM computation:
        #   dac = center + carrier_sin
        #       + (m_fixed * mod_sin * carrier_sin) >> (AMP_SHIFT + 12)
        product_am   = Signal(signed(24))
        modulated_am = Signal(signed(16))
        am_signed    = Signal(signed(9))
        dac_raw_am   = Signal(signed(10))

        m.d.comb += [
            product_am.eq(m_fixed_val * mod_sin_am * carrier_sin_am),
            modulated_am.eq(product_am >> (self.AMP_SHIFT + 12)),
            am_signed.eq(carrier_sin_am + modulated_am),
            dac_raw_am.eq(self.AMP_CENTER + am_signed),
        ]

        # Clamp to [0, 255]
        dac_am_comb = Signal(8)
        with m.If(dac_raw_am > 255):
            m.d.comb += dac_am_comb.eq(255)
        with m.Elif(dac_raw_am < 0):
            m.d.comb += dac_am_comb.eq(0)
        with m.Else():
            m.d.comb += dac_am_comb.eq(dac_raw_am[:8])

        # ================================================================
        # Branch 3: FM — Frequency Modulation  (DDS.md eq.34)
        #
        #   s_FM(t) = A_c * cos( 2π f_c t + β * sin(2π f_m t) )
        #
        #   Hardware:
        #     ftw_inst = carrier_ftw + (ftw_dev * mod_sin) >> AMP_SHIFT
        #     Carrier phase advances with modulated FTW.
        #     Output from unsigned sine LUT (constant amplitude).
        #   Output: dac_fm_comb
        # ================================================================
        carrier_ftw_fm_val = int(self.CARRIER_FREQ * (1 << self.N) / self.F_DAC)
        mod_ftw_fm_val     = int(self.MOD_FREQ     * (1 << self.N) / self.F_DAC)

        # Peak frequency deviation & corresponding FTW deviation
        delta_f_fm  = (self.MOD_INDEX_NUM / self.MOD_INDEX_DEN) * self.MOD_FREQ
        ftw_dev_val = int(delta_f_fm * (1 << self.N) / self.F_DAC)

        carrier_ftw_fm = Signal(self.N, reset=carrier_ftw_fm_val)
        mod_ftw_fm     = Signal(self.N, reset=mod_ftw_fm_val)

        # Signed sine LUT for modulating signal
        signed_lut_fm = Array(Const(v, signed(8)) for v in signed_sine_vals)

        # Unsigned sine LUT for carrier (DAC output)
        carrier_lut_fm = Array(Const(v, unsigned(self.D)) for v in sine_lut_vals)

        # Phase accumulators
        carrier_phase_fm = Signal(self.N)
        mod_phase_fm     = Signal(self.N)

        with m.If(self.rst):
            m.d.sync += [carrier_phase_fm.eq(0), mod_phase_fm.eq(0)]
        with m.Elif(dac_tick):
            # Modulating phase advances at constant rate
            m.d.sync += mod_phase_fm.eq(mod_phase_fm + mod_ftw_fm)

        # Modulating signal
        mod_addr_fm = Signal(self.A)
        mod_sin_fm  = Signal(signed(8))
        m.d.comb += [
            mod_addr_fm.eq(mod_phase_fm[-self.A:]),
            mod_sin_fm.eq(signed_lut_fm[mod_addr_fm]),
        ]

        # Instantaneous FTW = carrier_ftw + (ftw_dev * mod_sin) >> AMP_SHIFT
        ftw_delta_fm = Signal(signed(self.N))
        ftw_inst_fm  = Signal(self.N)

        m.d.comb += [
            ftw_delta_fm.eq((ftw_dev_val * mod_sin_fm) >> self.AMP_SHIFT),
            ftw_inst_fm.eq(carrier_ftw_fm + ftw_delta_fm),
        ]

        # Carrier phase advances with modulated FTW each DAC tick
        with m.If(dac_tick):
            m.d.sync += carrier_phase_fm.eq(carrier_phase_fm + ftw_inst_fm)

        carrier_addr_fm = Signal(self.A)
        m.d.comb += carrier_addr_fm.eq(carrier_phase_fm[-self.A:])

        dac_fm_comb = Signal(8)
        m.d.comb += dac_fm_comb.eq(carrier_lut_fm[carrier_addr_fm])

        # ================================================================
        # Branch 4: SPWM — Sinusoidal Pulse Width Modulation  (DDS.md eq.46)
        #
        #   Comparator: mod_scaled > tri_value ? HIGH : LOW
        #   mod_scaled = (m_fixed * mod_sin) >> 12
        #   HIGH = 192, LOW = 64
        #   Output: dac_spwm_comb (two-level)
        # ================================================================
        carrier_ftw_spwm_val = int(self.CARRIER_FREQ * (1 << self.N) / f_dac)
        mod_ftw_spwm_val     = int(self.MOD_FREQ     * (1 << self.N) / f_dac)

        carrier_ftw_spwm = Signal(self.N, reset=carrier_ftw_spwm_val)
        mod_ftw_spwm     = Signal(self.N, reset=mod_ftw_spwm_val)

        # Signed sine LUT (modulating wave)
        sine_lut_spwm = Array(Const(v, signed(8)) for v in signed_sine_vals)

        # Signed triangle LUT (carrier wave)
        tri_lut_spwm = Array(Const(v, signed(8)) for v in signed_tri_vals)

        # Phase accumulators
        carrier_phase_spwm = Signal(self.N)  # triangle carrier
        mod_phase_spwm     = Signal(self.N)  # modulating sine

        with m.If(self.rst):
            m.d.sync += [carrier_phase_spwm.eq(0), mod_phase_spwm.eq(0)]
        with m.Elif(dac_tick):
            m.d.sync += [
                carrier_phase_spwm.eq(carrier_phase_spwm + carrier_ftw_spwm),
                mod_phase_spwm.eq(mod_phase_spwm + mod_ftw_spwm),
            ]

        carrier_addr_spwm = Signal(self.A)
        mod_addr_spwm     = Signal(self.A)
        m.d.comb += [
            carrier_addr_spwm.eq(carrier_phase_spwm[-self.A:]),
            mod_addr_spwm.eq(mod_phase_spwm[-self.A:]),
        ]

        tri_val_spwm = Signal(signed(8))
        mod_sin_spwm = Signal(signed(8))
        m.d.comb += [
            tri_val_spwm.eq(tri_lut_spwm[carrier_addr_spwm]),
            mod_sin_spwm.eq(sine_lut_spwm[mod_addr_spwm]),
        ]

        # Scale modulating signal by modulation index m_a
        #   mod_scaled = (m_fixed * mod_sin) >> 12
        mod_scaled_spwm = Signal(signed(8))
        m.d.comb += mod_scaled_spwm.eq(
            (m_fixed_val * mod_sin_spwm) >> 12)

        # Comparator: mod_scaled > tri_value → HIGH, else LOW
        hi_code = self.AMP_CENTER + self.AMP_PEAK  # 192
        lo_code = self.AMP_CENTER - self.AMP_PEAK  #  64

        dac_spwm_comb = Signal(8)
        with m.If(mod_scaled_spwm > tri_val_spwm):
            m.d.comb += dac_spwm_comb.eq(hi_code)
        with m.Else():
            m.d.comb += dac_spwm_comb.eq(lo_code)

        # ================================================================
        # Output multiplexer
        #
        # All branches compute their DAC code combinatorially.
        # A mux selects the active branch based on the runtime mode,
        # and the result is registered on dac_tick for glitch-free output.
        # ================================================================
        # Build a 6-entry mux array indexed by the 3-bit mode signal
        dac_mux = Array([
            dac_basic_comb,   # 0: WAVEFORM_SINE
            dac_basic_comb,   # 1: WAVEFORM_SQUARE  (sub-selected by mode[1:0] inside Branch 1)
            dac_basic_comb,   # 2: WAVEFORM_TRIANGLE
            dac_am_comb,      # 3: MODE_AM
            dac_fm_comb,      # 4: MODE_FM
            dac_spwm_comb,    # 5: MODE_SPWM
        ])

        with m.If(dac_tick):
            m.d.sync += self.dac_data.eq(dac_mux[mode])

        return m
