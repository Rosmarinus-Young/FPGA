from amaranth import *
from amaranth.back import verilog
from VGATiming import VGATiming
from XADCModule import XADCModule
from VGADisplay import VGADisplay
from ButtonControl import ButtonControl
from Scope import Scope

from RAM import RAM

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
        self.vauxp2 = Signal()
        self.vauxn2 = Signal()


        self.auto_button = Signal()

        self.CH1_sample_period_control_knob_A = Signal()
        self.CH1_sample_period_control_knob_B = Signal()

        self.CH1_display_gain_control_knob_A = Signal()
        self.CH1_display_gain_control_knob_B = Signal()

        self.CH1_KEYA1 = Signal(init = 1)
        self.CH1_KEYA2 = Signal(init = 1)

        self.CH2_sample_period_control_knob_A = Signal()
        self.CH2_sample_period_control_knob_B = Signal()

        self.CH2_display_gain_control_knob_A = Signal()
        self.CH2_display_gain_control_knob_B = Signal()

        self.CH2_KEYA1 = Signal(init = 1)
        self.CH2_KEYA2 = Signal(init = 1)

    def elaborate(self, platform):
        m = Module()

        # 25Mhz 像素时钟

        clk_25m = Signal()

        m.submodules.dcm_25m = Instance(
            "dcm_25m",
            i_clk_in1=self.clk,
            i_reset=~self.rst,
            o_clk_out1=clk_25m,
        )

        m.domains.pix = ClockDomain("pix")
        m.d.comb += [
            ClockSignal("pix").eq(clk_25m),
            ResetSignal("pix").eq(~self.rst),
        ]

        m.domains.sync = ClockDomain("sync")
        m.d.comb += [
            ClockSignal("sync").eq(self.clk),
            ResetSignal("sync").eq(~self.rst),
        ]


        timing = VGATiming(self.vga_hsync, self.vga_vsync)
        m.submodules.timing = timing

        xadc = XADCModule(clk = self.clk, vauxp1 = self.vauxp1, vauxn1 = self.vauxn1,
                          vauxp2 = self.vauxp2, vauxn2 = self.vauxn2)
        m.submodules.xadc = xadc

        auto_button = ButtonControl(button = self.auto_button)
        m.submodules.auto_button = auto_button

        Channal1 = Scope(adc_value = xadc.adc_ch0_value, adc_ready = xadc.adc_ch0_ready,
                         auto_button = auto_button.out, 
                         KEYA1 = self.CH1_KEYA1, KEYA2 = self.CH1_KEYA2,
                         sample_period_control_knob_A = self.CH1_sample_period_control_knob_A,
                         sample_period_control_knob_B = self.CH1_sample_period_control_knob_B,
                         display_gain_control_knob_A = self.CH1_display_gain_control_knob_A,
                         display_gain_control_knob_B = self.CH1_display_gain_control_knob_B,
                         timing = timing)
        m.submodules.Channal1 = Channal1

        Channal2 = Scope(adc_value = xadc.adc_ch1_value, adc_ready = xadc.adc_ch1_ready,
                         auto_button = auto_button.out, 
                         KEYA1 = self.CH2_KEYA1, KEYA2 = self.CH2_KEYA2,
                         sample_period_control_knob_A = self.CH2_sample_period_control_knob_A,
                         sample_period_control_knob_B = self.CH2_sample_period_control_knob_B,
                         display_gain_control_knob_A = self.CH2_display_gain_control_knob_A,
                         display_gain_control_knob_B = self.CH2_display_gain_control_knob_B,
                         timing = timing)
        m.submodules.Channal2 = Channal2

        vga_display = VGADisplay(timing = timing, vga_r = self.vga_r, 
                                 vga_g = self.vga_g, vga_b = self.vga_b,
                                 CH1_display_y = Channal1.gain_control.display_y,
                                 CH2_display_y = Channal2.gain_control.display_y)
        m.submodules.vga_display = vga_display

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

            top.auto_button,

            top.vauxp1,
            top.vauxn1,
            top.CH1_sample_period_control_knob_A,
            top.CH1_sample_period_control_knob_B,
            top.CH1_display_gain_control_knob_A,
            top.CH1_display_gain_control_knob_B,
            top.CH1_KEYA1,
            top.CH1_KEYA2,

            top.vauxp2,
            top.vauxn2,
            top.CH2_sample_period_control_knob_A,
            top.CH2_sample_period_control_knob_B,
            top.CH2_display_gain_control_knob_A,
            top.CH2_display_gain_control_knob_B,
            top.CH2_KEYA1,
            top.CH2_KEYA2,
        ]
    )

    output_path = r"top.v"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(verilog_code)

    print(f"Verilog 已生成到: {output_path}")