from amaranth import *

class WaveControl(Elaboratable):
    def __init__(self, adc_value, adc_ready, period, get_period_over, sample_period_control_knob):
        self.adc_value = adc_value
        self.adc_ready = adc_ready
        self.period = period
        self.get_period_over = get_period_over
        self.sample_period_control_knob = sample_period_control_knob
        self.w_en = Signal()
        self.w_addr = Signal(12, init = 0)
        self.w_data = Signal(12)
        self.sample_period = Signal(32, init = 100000)

    def elaborate(self, platform):
        m = Module()
    
        x_limit = 640

        period_cnt = Signal(32, init = 0)
        period_overflow = Signal(1, init = 0)

        sample_clk = Signal(32, init = 0)

        with m.If(period_cnt == self.period - 1):
            m.d.sync += [
                period_cnt.eq(0),
                period_overflow.eq(1)
            ]
        with m.Else():
            m.d.sync += [
                period_cnt.eq(period_cnt + 1),
                period_overflow.eq(0)
            ]

        with m.If(sample_clk == self.sample_period - 1):
            m.d.sync += [
                sample_clk.eq(0),
                self.w_addr.eq(self.w_addr + 1),
            ]
        with m.Else():
            m.d.sync += sample_clk.eq(sample_clk + 1)

        with m.If(self.w_addr >= x_limit):
            with m.If(period_overflow):
                m.d.sync += self.w_addr.eq(0)
            with m.Else():
                m.d.sync += self.w_addr.eq(x_limit)

        with m.Elif(self.adc_ready):
            m.d.sync += [
                self.w_en.eq(1),
                self.w_data.eq(self.adc_value)
            ]
        
        with m.If(self.w_en):
            m.d.sync += self.w_en.eq(0)

        with m.If(self.get_period_over):
            m.d.sync += self.sample_period.eq(self.period >> 7)

        with m.If(self.sample_period_control_knob == 1):
            m.d.sync += self.sample_period.eq(self.sample_period + (self.sample_period >> 4))
        with m.Elif(self.sample_period_control_knob == 2):
            m.d.sync += self.sample_period.eq(self.sample_period - (self.sample_period >> 4))

        return m