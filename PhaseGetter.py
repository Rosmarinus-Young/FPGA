from amaranth import *

class PhaseGetter(Elaboratable):
    def __init__(self, adc_value, adc_ready, wave_maxn, wave_minn, get_period_over):
        self.adc_value = adc_value
        self.adc_ready = adc_ready
        self.wave_maxn = wave_maxn
        self.wave_minn = wave_minn
        self.get_period_over = get_period_over
        self.period_start = Signal(1, init = 0)

    def elaborate(self, platform):
        m = Module()

        maxn = Signal(12, init = 0)
        minn = Signal(12, init = (1 << 12) - 1)
        mid = Signal(12, init = 0)
        mid_high = Signal(12, init = 0)
        mid_low = Signal(12, init = 0)

        with m.If(self.get_period_over):
            m.d.sync += [
                maxn.eq(self.wave_maxn),
                minn.eq(self.wave_minn)
            ]
        with m.Elif(self.adc_ready):
            m.d.sync += [
                maxn.eq(Mux(self.adc_value > maxn, self.adc_value, maxn)),
                minn.eq(Mux(self.adc_value < minn, self.adc_value, minn))
            ]

        m.d.sync += [
            mid.eq((maxn + minn) >> 1),
            mid_high.eq((maxn + mid) >> 1),
            mid_low.eq((mid + minn) >> 1)
        ]

        with m.FSM(init = "get_period_down"):
            with m.State("get_period_down"):
                with m.If(self.adc_ready & (self.adc_value < mid_low)):
                    m.next = "get_period_mid"
            with m.State("get_period_mid"):
                with m.If(self.adc_ready & (self.adc_value > mid)):
                    m.d.sync += self.period_start.eq(1)
                    m.next = "get_period_up"
            with m.State("get_period_up"):
                with m.If(self.adc_ready & (self.adc_value > mid_high)):
                    m.next = "get_period_down"

        with m.If(self.period_start):
            m.d.sync += self.period_start.eq(0)
        return m