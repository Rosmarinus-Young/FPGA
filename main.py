from amaranth import *
from amaranth.back import verilog
from VGATiming import VGATiming
from XADCModule import XADCModule
from VGADisplay import VGADisplay
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

        my_ram = RAM(xadc_value = xadc.adc_value, vga_x = timing.x, r_en = timing.visible)
        m.submodules.my_ram = my_ram

        vga_display = VGADisplay(timing = timing, ram = my_ram, vga_r = self.vga_r, vga_g = self.vga_g, vga_b = self.vga_b)
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
        ]
    )

    output_path = r"top.v"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(verilog_code)

    print(f"Verilog 已生成到: {output_path}")