from amaranth import *
from amaranth.back import verilog
from VGATiming import VGATiming
from XADCModule import XADCModule
from VGADisplay import VGADisplay
from PeriodDetector import PeriodDetector
from ButtonControl import ButtonControl
from WaveControl import WaveControl
from KnobControl import KnobControl
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

        self.auto_button = Signal()

        self.sample_period_control_knob_A = Signal()
        self.sample_period_control_knob_B = Signal()

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

        xadc = XADCModule(clk = self.clk, vauxp1 = self.vauxp1, vauxn1 = self.vauxn1)
        m.submodules.xadc = xadc

        auto_button = ButtonControl(button = self.auto_button)
        m.submodules.auto_button = auto_button

        period_detector = PeriodDetector(adc_value = xadc.adc_value, 
                                         adc_ready = xadc.adc_ready,
                                         auto_button = auto_button.out)
        m.submodules.period_detector = period_detector

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

        vga_display = VGADisplay(timing = timing, vga_r = self.vga_r, 
                                 vga_g = self.vga_g, vga_b = self.vga_b, 
                                 r_data = ram.r_data)
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
            top.vauxp1,
            top.vauxn1,
            top.auto_button,
            top.sample_period_control_knob_A,
            top.sample_period_control_knob_B,
        ]
    )

    output_path = r"top.v"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(verilog_code)

    print(f"Verilog 已生成到: {output_path}")