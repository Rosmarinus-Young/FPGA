from amaranth import *

class VGADisplay(Elaboratable):
    def __init__(self, timing, vga_r, vga_g, vga_b, r_data, gain_control_knob):
        self.timing = timing
        self.r_data = r_data
        self.gain_control_knob = gain_control_knob

        self.vga_r = vga_r
        self.vga_g = vga_g
        self.vga_b = vga_b

        
    def elaborate(self, platform):
        m = Module()

        r = Signal(4)
        g = Signal(4)
        b = Signal(4)
        grid = Signal()
        display_y = Signal(12)
        diff = Signal(signed(13))
        center = (1 << 11)
        gain = Signal(12, reset = 16)

        m.d.comb += grid.eq((self.timing.x[0:6] == 0) | (self.timing.y[0:6] == 0))
        
        # r_data 为12位adc原始数据
        m.d.comb += diff.eq(self.r_data - center)
        m.d.pix += display_y.eq(240 + (diff >> 3) * (gain >> 4))

        # 默认黑屏
        m.d.comb += [
            r.eq(0),
            g.eq(0),
            b.eq(0),
        ]

        with m.If(self.gain_control_knob == 1):
            m.d.sync += gain.eq(gain + (gain >> 2))
        with m.Elif(self.gain_control_knob == 2):
            m.d.sync += gain.eq(gain - (gain >> 2))

        with m.If(gain < 4):
            m.d.sync += gain.eq(4)
        with m.If(gain > 256):
            m.d.sync += gain.eq(256)

        with m.If(self.timing.visible):
            with m.If(grid):
                m.d.comb += [
                    r.eq(0xF),
                    g.eq(0xF),
                    b.eq(0xF),
                ]
            with m.Elif(self.timing.y == display_y):
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