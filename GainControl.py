from amaranth import *

class GainControl(Elaboratable):
    def __init__(self, r_data, gain_control_knob, get_period_over, maxn, minn, mid):
        self.r_data = r_data
        self.gain_control_knob = gain_control_knob
        self.get_period_over = get_period_over
        self.maxn = maxn
        self.minn = minn
        self.mid = mid
        self.display_y = Signal(12)

    def elaborate(self, platform):
        m = Module()

        diff = Signal(signed(13))
        center = Signal(12, reset = 2048)
        gain = Signal(12, reset = 16)
        amp = Signal(12)

        # 峰峰值 = maxn - minn（maxn >= minn 恒成立）
        m.d.comb += amp.eq(self.maxn - self.minn)

        with m.If(self.get_period_over):
            m.d.sync += [
                center.eq(self.mid),
            ]
            # 自动增益：根据信号峰峰值选择 gain，使波形约占 300 像素
            # 公式：(amp >> 3) * (gain >> 4) ≈ 300  =>  gain ≈ 38400 / amp
            # with m.If(amp > 3000):
            #     m.d.sync += gain.eq(8)
            # with m.Elif(amp > 1500):
            #     m.d.sync += gain.eq(16)
            # with m.Elif(amp > 750):
            #     m.d.sync += gain.eq(32)
            # with m.Elif(amp > 375):
            #     m.d.sync += gain.eq(64)
            # with m.Elif(amp > 187):
            #     m.d.sync += gain.eq(128)
            # with m.Else():
            #     m.d.sync += gain.eq(256)
        
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