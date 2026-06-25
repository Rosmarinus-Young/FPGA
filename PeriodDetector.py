from amaranth import *

class PeriodDetector(Elaboratable):
    def __init__(self, adc_value, adc_ready, auto_button):
        self.value = adc_value
        self.adc_ready = adc_ready
        self.button = auto_button
        self.average = Signal(32)
        self.period = Signal(32)

    def elaborate(self, platform):
        m = Module()

        ADC_BITS = 12

        maxn = Signal(ADC_BITS + 2, init = 0)
        minn = Signal(ADC_BITS + 2, init = (1 << ADC_BITS) - 1)
        mid = Signal(ADC_BITS + 2, init = 0)
        mid_high = Signal(ADC_BITS + 2, init = 0)
        mid_low = Signal(ADC_BITS + 2, init = 0)
        timeout = Signal(32, init = 0)
        period_sum = Signal(32)
        get_period_ready = Signal()

        with m.FSM(init="normal"):
            with m.State("normal"):
                with m.If(self.button):
                    m.d.sync += [
                        maxn.eq(0),
                        minn.eq((1 << ADC_BITS) - 1),
                        timeout.eq(0),
                    ]
                    m.next = "get_average"

            with m.State("get_average"):
                with m.If(self.adc_ready):
                    m.d.sync += [
                        maxn.eq(Mux(self.value > maxn, self.value, maxn)),
                        minn.eq(Mux(self.value < minn, self.value, minn)),
                    ]
                m.d.sync += timeout.eq(timeout + 1)
                with m.If(timeout == 1000000):
                    m.d.sync += [
                        mid.eq((maxn + minn) >> 1),
                        mid_high.eq((maxn + maxn + maxn + minn) >> 2),
                        mid_low.eq((maxn + minn + minn + minn) >> 2),
                        get_period_ready.eq(0),
                        period_sum.eq(0)
                    ]
                    m.next = "get_period_down"

            with m.State("get_period_down"):
                with m.If(self.adc_ready):
                    with m.If(self.value < mid_low):
                        m.d.sync += get_period_ready.eq(1)
                        m.next = "get_period_up"
                with m.If(get_period_ready):
                        m.d.sync += period_sum.eq(period_sum + 1)

            with m.State("get_period_start"):
                with m.If(self.adc_ready):
                    


