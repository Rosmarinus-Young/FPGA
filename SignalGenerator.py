"""
SignalGenerator - DDS-based Signal Generator for EGO1 FPGA Board
=================================================================

Target Board: EGO1 (Xilinx Artix-7 XC7A35T-1CSG324C)
DAC: DAC0832 (8-bit, single buffer mode)
System Clock: 100 MHz

Features:
  - Waveforms: Sine, Square, Triangle
  - Frequency range: 100 Hz ~ 10 kHz
  - Frequency resolution: ≤ 20 Hz (actual ~0.05 Hz)
  - Amplitude: 2 Vpp (centered at 2.5 V, assuming 5 V Vref)
  - Algorithm: DDS (Direct Digital Synthesis) per doc/DDS.md

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
from amaranth.back import verilog
import math


class SignalGenerator(Elaboratable):
    """DDS-based signal generator for EGO1 board with DAC0832.

    Generates sine, square, or triangle wave using Direct Digital
    Synthesis. The phase accumulator runs at the DAC update rate
    (~781 kHz, derived from the 100 MHz system clock divided by 128).

    Usage
    -----
    Edit the WAVEFORM and FREQ_HZ class attributes below to select
    the desired waveform and output frequency, then run this script
    to generate the Verilog HDL file.

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
    WAVEFORM_SINE     = 0
    WAVEFORM_SQUARE   = 1
    WAVEFORM_TRIANGLE = 2

    WAVEFORM = WAVEFORM_SINE    # Select waveform type here
    FREQ_HZ  = 1000            # Output frequency: 100 ~ 10000 Hz
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
    #   For 2 Vpp centered at 2.5 V:
    #     swing: 1.5 V ~ 3.5 V  ->  codes: 77 ~ 179
    #     center = 128 (2.5 V), amplitude = 51 (1 V)
    AMP_CENTER = 128            # Code for DC offset = Vref / 2
    AMP_PEAK   = 51             # Code for 1 V peak swing

    # Frequency resolution: Δf = F_DAC / 2^N ≈ 0.047 Hz  << 20 Hz ✓

    def __init__(self):
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
    # Hardware elaboration
    # ------------------------------------------------------------------

    def elaborate(self, platform) -> Module:
        m = Module()

        # -- Tie sync domain clock and reset to top-level ports --
        # This prevents Amaranth from creating extra unnamed ports
        # (clk$8, rst$9) that would fail DRC in Vivado.
        m.domains.sync = ClockDomain("sync")
        m.d.comb += [
            ClockSignal("sync").eq(self.clk),
            ResetSignal("sync").eq(self.rst),   # RST: active-high
        ]

        # -- Frequency tuning word (FTW) --
        # The phase accumulator is advanced only on dac_tick,
        # so f_out = FTW * F_DAC / 2^N  =>  FTW = f_out * 2^N / F_DAC
        ftw_value = int(self.FREQ_HZ * (1 << self.N) / self.F_DAC)
        ftw = Signal(self.N, reset=ftw_value)

        # -- Select and build waveform LUT --
        if self.WAVEFORM == self.WAVEFORM_SINE:
            lut_values = self._build_sine_lut()
        elif self.WAVEFORM == self.WAVEFORM_SQUARE:
            lut_values = self._build_square_lut()
        elif self.WAVEFORM == self.WAVEFORM_TRIANGLE:
            lut_values = self._build_triangle_lut()
        else:
            lut_values = self._build_sine_lut()

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
        clk_div_cnt = Signal(range(self.DAC_DIV))
        dac_tick    = Signal()   # Asserted one cycle every DAC_DIV cycles

        with m.If(self.rst):
            m.d.sync += clk_div_cnt.eq(0)
        with m.Else():
            m.d.sync += clk_div_cnt.eq(clk_div_cnt + 1)
            with m.If(clk_div_cnt == self.DAC_DIV - 1):
                m.d.sync += clk_div_cnt.eq(0)

        m.d.comb += dac_tick.eq(clk_div_cnt == 0)

        # -- Phase accumulator (DDS core) --
        # Advanced only on dac_tick so that the DDS sample rate
        # equals the DAC update rate.  This gives finer frequency
        # resolution: Δf = F_DAC / 2^N ≈ 0.047 Hz.
        phase_acc = Signal(self.N)

        with m.If(self.rst):
            m.d.sync += phase_acc.eq(0)
        with m.Elif(dac_tick):
            m.d.sync += phase_acc.eq(phase_acc + ftw)

        # -- LUT address (top A bits of phase accumulator) --
        lut_addr = Signal(self.A)
        m.d.comb += lut_addr.eq(phase_acc[-self.A:])

        # -- LUT lookup --
        # Amaranth Array: combinatorial ROM indexed by lut_addr.
        lut = Array(Const(v, unsigned(self.D)) for v in lut_values)

        # DAC data is registered on the DAC tick to avoid glitching
        # the DAC0832 with intermediate phase values.
        with m.If(dac_tick):
            m.d.sync += self.dac_data.eq(lut[lut_addr])

        return m


# ======================================================================
# Main: generate Verilog and ancillary files
# ======================================================================
if __name__ == "__main__":
    top = SignalGenerator()

    # --- Generate Verilog ---
    verilog_code = verilog.convert(
        top,
        name="SignalGenerator",
        ports=[
            top.clk,
            top.rst,
            top.dac_data,
            top.dac_ile,
            top.dac_cs,
            top.dac_wr1,
            top.dac_wr2,
            top.dac_xfer,
        ],
        emit_src=True,
    )

    vlog_path = "SignalGenerator.v"
    with open(vlog_path, "w", encoding="utf-8") as f:
        f.write(verilog_code)

    # --- Generate XDC constraints ---
    xdc_content = """\
# ================================================================
# EGO1 SignalGenerator — XDC Pin Constraints
# ================================================================

# 100 MHz system clock
set_property PACKAGE_PIN P17 [get_ports clk]
set_property IOSTANDARD LVCMOS33 [get_ports clk]
create_clock -period 10.000 -name sys_clk [get_ports clk]

# Reset button (active high)
set_property PACKAGE_PIN P15 [get_ports rst]
set_property IOSTANDARD LVCMOS33 [get_ports rst]

# DAC0832 data bus [DAC_D0 .. DAC_D7]
set_property PACKAGE_PIN T8  [get_ports {dac_data[0]}]
set_property PACKAGE_PIN R8  [get_ports {dac_data[1]}]
set_property PACKAGE_PIN T6  [get_ports {dac_data[2]}]
set_property PACKAGE_PIN R7  [get_ports {dac_data[3]}]
set_property PACKAGE_PIN U6  [get_ports {dac_data[4]}]
set_property PACKAGE_PIN U7  [get_ports {dac_data[5]}]
set_property PACKAGE_PIN V9  [get_ports {dac_data[6]}]
set_property PACKAGE_PIN U9  [get_ports {dac_data[7]}]

set_property IOSTANDARD LVCMOS33 [get_ports {dac_data[*]}]

# DAC0832 control signals
set_property PACKAGE_PIN R5  [get_ports dac_ile]   ;# DAC_BYTE2
set_property PACKAGE_PIN N6  [get_ports dac_cs]    ;# DAC_CS#
set_property PACKAGE_PIN V6  [get_ports dac_wr1]   ;# DAC_WR1#
set_property PACKAGE_PIN R6  [get_ports dac_wr2]   ;# DAC_WR2#
set_property PACKAGE_PIN V7  [get_ports dac_xfer]  ;# DAC_XFER#

set_property IOSTANDARD LVCMOS33 [get_ports dac_ile]
set_property IOSTANDARD LVCMOS33 [get_ports dac_cs]
set_property IOSTANDARD LVCMOS33 [get_ports dac_wr1]
set_property IOSTANDARD LVCMOS33 [get_ports dac_wr2]
set_property IOSTANDARD LVCMOS33 [get_ports dac_xfer]
"""
    xdc_path = "SignalGenerator.xdc"
    with open(xdc_path, "w", encoding="utf-8") as f:
        f.write(xdc_content)

    # --- Report ---
    wave_names = {
        SignalGenerator.WAVEFORM_SINE:     "sine",
        SignalGenerator.WAVEFORM_SQUARE:   "square",
        SignalGenerator.WAVEFORM_TRIANGLE: "triangle",
    }
    freq_resolution = SignalGenerator.F_DAC / (1 << SignalGenerator.N)

    wave_name = wave_names.get(SignalGenerator.WAVEFORM, "unknown")
    ftw_val = int(SignalGenerator.FREQ_HZ
                  * (1 << SignalGenerator.N)
                  / SignalGenerator.F_DAC)
    actual_freq = (ftw_val * SignalGenerator.F_DAC
                   / (1 << SignalGenerator.N))

    print("=" * 56)
    print("  DDS Signal Generator — EGO1 + DAC0832")
    print("=" * 56)
    print(f"  Waveform          : {wave_name}")
    print(f"  Target frequency  : {SignalGenerator.FREQ_HZ} Hz")
    print(f"  Actual frequency  : {actual_freq:.2f} Hz")
    print(f"  FTW               : {ftw_val} (0x{ftw_val:06X})")
    print(f"  Frequency res.    : {freq_resolution:.2f} Hz")
    print(f"  DAC update rate   : {SignalGenerator.F_DAC} Hz")
    print(f"  Amplitude         : 2 Vpp (center 2.5 V)")
    print(f"  DAC mode          : single buffer")
    print("-" * 56)
    print(f"  Verilog           : {vlog_path}")
    print(f"  Constraints       : {xdc_path}")
    print("=" * 56)

    # Validate frequency range and resolution
    if not (100 <= SignalGenerator.FREQ_HZ <= 10000):
        print("  WARNING: Frequency outside specified 100–10000 Hz range!")
    if freq_resolution > 20:
        print(f"  WARNING: Resolution {freq_resolution:.2f} Hz > 20 Hz!")
