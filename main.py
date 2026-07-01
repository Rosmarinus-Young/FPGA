from amaranth import *
from amaranth.back import verilog
from VGATiming import VGATiming
from XADCModule import XADCModule
from VGADisplay import VGADisplay
from PeriodDetector import PeriodDetector
from ButtonControl import ButtonControl
from WaveControl import WaveControl
from KnobControl import KnobControl
from RangeSwitcher import RangeSwitcher
from RAM import RAM
from SignalGenerator import SignalGenerator

class VGADemo(Elaboratable):
    def __init__(self):
        self.vga_hsync = Signal()
        self.vga_vsync = Signal()

        self.vga_r = Signal(4)
        self.vga_g = Signal(4)
        self.vga_b = Signal(4)
        self.rst = Signal()
        self.clk = Signal()

        self.vauxp1 = Signal()
        self.vauxn1 = Signal()

        self.auto_button = Signal()

        self.sample_period_control_knob_A = Signal()
        self.sample_period_control_knob_B = Signal()

        self.display_gain_control_knob_A = Signal()
        self.display_gain_control_knob_B = Signal()

        self.KEYA1 = Signal(init = 1)
        self.KEYA1 = Signal(init = 1)

        # SignalGenerator mode-select buttons (EGO1 S0–S4)
        self.btn_sine     = Signal()   # S0 → WAVEFORM_SINE
        self.btn_square   = Signal()   # S1 → WAVEFORM_SQUARE
        self.btn_triangle = Signal()   # S2 → WAVEFORM_TRIANGLE
        self.btn_am       = Signal()   # S3 → MODE_AM
        self.btn_fm       = Signal()   # S4 → MODE_FM

        # SignalGenerator DAC0832 ports
        self.dac_data = Signal(8)
        self.dac_ile  = Signal()
        self.dac_cs   = Signal()
        self.dac_wr1  = Signal()
        self.dac_wr2  = Signal()
        self.dac_xfer = Signal()

    def elaborate(self, platform):
        m = Module()

        # MMCME2_BASE: 100 MHz -> 25 MHz pixel clock
        # f_out = f_in * CLKFBOUT_MULT_F / (CLKOUT0_DIVIDE_F * DIVCLK_DIVIDE)
        #       = 100 * 10 / (40 * 1) = 25 MHz
        clk_25m = Signal()
        clk_fb  = Signal()
        mmcm_locked = Signal()

        m.submodules.mmcm_25m = Instance(
            "MMCME2_BASE",
            p_BANDWIDTH="OPTIMIZED",
            p_CLKIN1_PERIOD=10.0,
            p_CLKFBOUT_MULT_F=10.0,
            p_CLKOUT0_DIVIDE_F=40.0,
            p_DIVCLK_DIVIDE=1,
            p_STARTUP_WAIT="FALSE",
            i_CLKIN1=self.clk,
            i_CLKFBIN=clk_fb,
            i_RST=~self.rst,
            i_PWRDWN=Const(0),
            o_CLKOUT0=clk_25m,
            o_CLKFBOUT=clk_fb,
            o_LOCKED=mmcm_locked,
        )

        m.domains.pix = ClockDomain("pix")
        m.d.comb += [
            ClockSignal("pix").eq(clk_25m),
            ResetSignal("pix").eq(~mmcm_locked | ~self.rst),
        ]

        m.domains.sync = ClockDomain("sync")
        m.d.comb += [
            ClockSignal("sync").eq(self.clk),
            ResetSignal("sync").eq(~self.rst),
        ]


        timing = VGATiming(self.vga_hsync, self.vga_vsync)
        m.submodules.timing = timing

        xadc = XADCModule(clk = self.clk, vauxp1 = self.vauxp1, vauxn1 = self.vauxn1)
        m.submodules.xadc = xadc

        auto_button = ButtonControl(button = self.auto_button)
        m.submodules.auto_button = auto_button

        period_detector = PeriodDetector(adc_value = xadc.adc_value, 
                                         adc_ready = xadc.adc_ready,
                                         auto_button = auto_button.out)
        m.submodules.period_detector = period_detector

        range_switcher = RangeSwitcher(A0 = self.KEYA1, A1 = self.KEYA1, 
                                       wave_range = period_detector.wave_range)
        m.submodules.range_switcher = range_switcher

        sample_period_control_knob = KnobControl(A = self.sample_period_control_knob_A, 
                                                 B = self.sample_period_control_knob_B)
        m.submodules.sample_period_control_knob = sample_period_control_knob

        wave_control = WaveControl(adc_value = xadc.adc_value, adc_ready = xadc.adc_ready, 
                                   period = period_detector.period, 
                                   get_period_over = period_detector.get_period_over,
                                   sample_period_control_knob = sample_period_control_knob.out)
        m.submodules.wave_control = wave_control

        ram = RAM(r_addr = timing.x, r_en = 1, w_addr = wave_control.w_addr, 
                  w_data = wave_control.w_data, w_en = wave_control.w_en)
        m.submodules.ram = ram

        display_gain_control_knob = KnobControl(A = self.display_gain_control_knob_A, 
                                                 B = self.display_gain_control_knob_B)
        m.submodules.display_gain_control_knob = display_gain_control_knob

        vga_display = VGADisplay(timing = timing, vga_r = self.vga_r,
                                 vga_g = self.vga_g, vga_b = self.vga_b,
                                 r_data = ram.r_data,
                                 gain_control_knob = display_gain_control_knob.out)
        m.submodules.vga_display = vga_display

        # Tie unused VGA control inputs to 0 (physical buttons now used
        # for SignalGenerator mode selection)
        m.d.comb += [
            self.auto_button.eq(0),
            self.sample_period_control_knob_A.eq(0),
            self.sample_period_control_knob_B.eq(0),
            self.display_gain_control_knob_A.eq(0),
            self.display_gain_control_knob_B.eq(0),
        ]

        # DDS Signal Generator (DAC0832 output)
        sg = SignalGenerator(standalone=False)
        m.submodules.signal_gen = sg
        m.d.comb += [
            sg.clk.eq(self.clk),
            sg.rst.eq(~self.rst),  # active-low button -> active-high reset
            sg.btn_sine.eq(self.btn_sine),
            sg.btn_square.eq(self.btn_square),
            sg.btn_triangle.eq(self.btn_triangle),
            sg.btn_am.eq(self.btn_am),
            sg.btn_fm.eq(self.btn_fm),
            self.dac_data.eq(sg.dac_data),
            self.dac_ile.eq(sg.dac_ile),
            self.dac_cs.eq(sg.dac_cs),
            self.dac_wr1.eq(sg.dac_wr1),
            self.dac_wr2.eq(sg.dac_wr2),
            self.dac_xfer.eq(sg.dac_xfer),
        ]

        return m


if __name__ == "__main__":
    top = VGADemo()

    verilog_code = verilog.convert(
        top,
        ports=[
            top.clk,
            top.rst,
            top.vga_hsync,
            top.vga_vsync,
            top.vga_r,
            top.vga_g,
            top.vga_b,
            top.vauxp1,
            top.vauxn1,

            # SignalGenerator mode-select buttons (EGO1 S0–S4)
            top.btn_sine,
            top.btn_square,
            top.btn_triangle,
            top.btn_am,
            top.btn_fm,

            # SignalGenerator DAC0832 ports
            top.dac_data,
            top.dac_ile,
            top.dac_cs,
            top.dac_wr1,
            top.dac_wr2,
            top.dac_xfer,
        ]
    )

    with open("top.v", "w", encoding="utf-8") as f:
        f.write(verilog_code)

    print(f"Verilog 已生成到: top.v")

    # --- Generate XDC constraints ---
    xdc_content = """\
# ================================================================
# EGO1 VGADemo — XDC Pin Constraints
# ================================================================

# 100 MHz system clock
set_property PACKAGE_PIN P17 [get_ports clk]
set_property IOSTANDARD LVCMOS33 [get_ports clk]
create_clock -period 10.000 -name sys_clk [get_ports clk]

# Reset button (active high)
set_property PACKAGE_PIN P15 [get_ports rst]
set_property IOSTANDARD LVCMOS33 [get_ports rst]

# ---- VGA ----
set_property PACKAGE_PIN F5  [get_ports {vga_r[0]}]
set_property PACKAGE_PIN C6  [get_ports {vga_r[1]}]
set_property PACKAGE_PIN C5  [get_ports {vga_r[2]}]
set_property PACKAGE_PIN B7  [get_ports {vga_r[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {vga_r[*]}]

set_property PACKAGE_PIN B6  [get_ports {vga_g[0]}]
set_property PACKAGE_PIN A6  [get_ports {vga_g[1]}]
set_property PACKAGE_PIN A5  [get_ports {vga_g[2]}]
set_property PACKAGE_PIN D8  [get_ports {vga_g[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {vga_g[*]}]

set_property PACKAGE_PIN C7  [get_ports {vga_b[0]}]
set_property PACKAGE_PIN E6  [get_ports {vga_b[1]}]
set_property PACKAGE_PIN E5  [get_ports {vga_b[2]}]
set_property PACKAGE_PIN E7  [get_ports {vga_b[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {vga_b[*]}]

set_property PACKAGE_PIN D7  [get_ports vga_hsync]
set_property PACKAGE_PIN C4  [get_ports vga_vsync]
set_property IOSTANDARD LVCMOS33 [get_ports vga_hsync]
set_property IOSTANDARD LVCMOS33 [get_ports vga_vsync]

# ---- SignalGenerator mode-select buttons (EGO1 S0–S4) ----
set_property PACKAGE_PIN R11 [get_ports btn_sine]
set_property PACKAGE_PIN R17 [get_ports btn_square]
set_property PACKAGE_PIN R15 [get_ports btn_triangle]
set_property PACKAGE_PIN V1  [get_ports btn_am]
set_property PACKAGE_PIN U4  [get_ports btn_fm]
set_property IOSTANDARD LVCMOS33 [get_ports btn_sine]
set_property IOSTANDARD LVCMOS33 [get_ports btn_square]
set_property IOSTANDARD LVCMOS33 [get_ports btn_triangle]
set_property IOSTANDARD LVCMOS33 [get_ports btn_am]
set_property IOSTANDARD LVCMOS33 [get_ports btn_fm]

# ---- XADC analog input ----
set_property PACKAGE_PIN K9  [get_ports vauxp1]
set_property PACKAGE_PIN J9  [get_ports vauxn1]
set_property IOSTANDARD LVCMOS33 [get_ports vauxp1]
set_property IOSTANDARD LVCMOS33 [get_ports vauxn1]

# ---- DAC0832 data bus [DAC_D0 .. DAC_D7] ----
set_property PACKAGE_PIN T8  [get_ports {dac_data[0]}]
set_property PACKAGE_PIN R8  [get_ports {dac_data[1]}]
set_property PACKAGE_PIN T6  [get_ports {dac_data[2]}]
set_property PACKAGE_PIN R7  [get_ports {dac_data[3]}]
set_property PACKAGE_PIN U6  [get_ports {dac_data[4]}]
set_property PACKAGE_PIN U7  [get_ports {dac_data[5]}]
set_property PACKAGE_PIN V9  [get_ports {dac_data[6]}]
set_property PACKAGE_PIN U9  [get_ports {dac_data[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {dac_data[*]}]

# ---- DAC0832 control signals ----
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
    with open("top.xdc", "w", encoding="utf-8") as f:
        f.write(xdc_content)

    print(f"XDC 已生成到: top.xdc")