from amaranth import *

class VGADisplay(Elaboratable):
    def __init__(self, timing, vga_r, vga_g, vga_b, r_data):
        self.timing = timing
        self.r_data = r_data

        self.vga_r = vga_r
        self.vga_g = vga_g
        self.vga_b = vga_b

        
    def elaborate(self, platform):
        m = Module()

        r = Signal(4)
        g = Signal(4)
        b = Signal(4)
        grid = Signal()

        m.d.comb += grid.eq((self.timing.x[0:6] == 0) | (self.timing.y[0:6] == 0))

        # 默认黑屏
        m.d.comb += [
            r.eq(0),
            g.eq(0),
            b.eq(0),
        ]

        with m.If(self.timing.visible):
            with m.If(grid):
                m.d.comb += [
                    r.eq(0xF),
                    g.eq(0xF),
                    b.eq(0xF),
                ]
            with m.Elif(self.timing.y == self.r_data):
                m.d.comb += [
                    r.eq(0xF),
                    g.eq(0xF),
                    b.eq(0x0),
                ]

        # 输出端口
        m.d.comb += [
            self.vga_r.eq(r),
            self.vga_g.eq(g),
            self.vga_b.eq(b),
        ]

        return m