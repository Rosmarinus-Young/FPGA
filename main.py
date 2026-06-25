from amaranth import *
from amaranth.back import verilog
from VGATiming import VGATiming
from XADCModule import XADCModule
from RAM import RAM
class VGADemo(Elaboratable):
    """
    基础 VGA 显示 Demo：
    - 左侧红色
    - 中间绿色
    - 右侧蓝色
    - 每 64 像素画一条白色网格线
    """

    def __init__(self):
        self.vga_hsync = Signal()
        self.vga_vsync = Signal()

        # 假设 VGA DAC 每个颜色 4 bit
        self.vga_r = Signal(4)
        self.vga_g = Signal(4)
        self.vga_b = Signal(4)
        self.rst = Signal()
        self.clk = Signal()

        self.vauxp1 = Signal()
        self.vauxn1 = Signal()

    def elaborate(self, platform):
        m = Module()

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

        timing = VGATiming()
        m.submodules.timing = timing


        xadc = XADCModule(clk = self.clk, vauxp1 = self.vauxp1, vauxn1 = self.vauxn1)
        m.submodules.xadc = xadc

        my_ram = RAM(xadc_value = xadc.adc_value, vga_x = timing.x, r_en = timing.visible)
        m.submodules.my_ram = my_ram


        r = Signal(4)
        g = Signal(4)
        b = Signal(4)

        # 网格线：每 64 像素一条
        grid = Signal()
        m.d.comb += grid.eq((timing.x[0:6] == 0) | (timing.y[0:6] == 0))

        # 默认黑屏
        m.d.comb += [
            r.eq(0),
            g.eq(0),
            b.eq(0),
        ]

        with m.If(timing.visible):
            with m.If(timing.x == my_ram.w_addr):
                m.d.comb += [
                    r.eq(0),
                    g.eq(0xF),
                    b.eq(0),
                ]
            with m.Elif(grid):
                m.d.comb += [
                    r.eq(0xF),
                    g.eq(0xF),
                    b.eq(0xF),
                ]
            with m.Elif(timing.y == my_ram.r_data):
                m.d.comb += [
                    r.eq(0xF),
                    g.eq(0xF),
                    b.eq(0x0),
                ]
            # RGB 三色竖条
            # with m.Elif(timing.x < 213):
            #     m.d.comb += [
            #         r.eq(0xF),
            #         g.eq(0x0),
            #         b.eq(0x0),
            #     ]
            #
            # with m.Elif(timing.x < 426):
            #     m.d.comb += [
            #         r.eq(0x0),
            #         g.eq(0xF),
            #         b.eq(0x0),
            #     ]
            #
            # with m.Else():
            #     m.d.comb += [
            #         r.eq(0x0),
            #         g.eq(0x0),
            #         b.eq(0xF),
            #     ]

        # 输出端口
        m.d.comb += [
            self.vga_hsync.eq(timing.hsync),
            self.vga_vsync.eq(timing.vsync),
            self.vga_r.eq(r),
            self.vga_g.eq(g),
            self.vga_b.eq(b),
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
        ]
    )

    output_path = r"D:\Code\python\Vivado\top.v"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(verilog_code)

    print(f"Verilog 已生成到: {output_path}")