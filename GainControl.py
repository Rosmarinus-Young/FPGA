from amaranth import *

class GainControl(Elaboratable):
    def __init__(self, r_data, gain_control_knob):
        self.r_data = r_data
        self.gain_control_knob = gain_control_knob
        self.display_y = Signal(12)

    def elaborate(self, platform):
        m = Module()

        diff = Signal(signed(13))
        center = (1 << 11)
        gain = Signal(12, reset = 16)

        
        # r_data 为12位adc原始数据
        m.d.comb += diff.eq(self.r_data - center)
        m.d.sync += self.display_y.eq(240 + (diff >> 3) * (gain >> 4))

        with m.If(self.gain_control_knob == 1):
            m.d.sync += gain.eq(gain + (gain >> 2))
        with m.Elif(self.gain_control_knob == 2):
            m.d.sync += gain.eq(gain - (gain >> 2))

        with m.If(gain < 4):
            m.d.sync += gain.eq(4)
        with m.If(gain > 256):
            m.d.sync += gain.eq(256)

        return m