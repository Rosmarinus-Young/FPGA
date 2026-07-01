from amaranth import *

class PeriodDetector(Elaboratable):
    def __init__(self, adc_value, adc_ready, auto_button):
        self.value = adc_value
        self.adc_ready = adc_ready
        self.button = auto_button
        self.average = Signal(32)
        self.period = Signal(32, init = 1000000)
        self.get_period_over = Signal(1, init = 0)
        self.wave_range = Signal(4, init = 1)
        # 档位分别为：1/50, 1/10, 1, 10
    def elaborate(self, platform):
        m = Module()

        ADC_BITS = 12

        maxn = Signal(ADC_BITS + 2, init = 0)
        minn = Signal(ADC_BITS + 2, init = (1 << ADC_BITS) - 1)
        mid = Signal(ADC_BITS + 2, init = 0)
        mid_high = Signal(ADC_BITS + 2, init = 0)
        mid_low = Signal(ADC_BITS + 2, init = 0)
        choose_range_timeout = Signal(32, init = 0)
        get_period_timeout = Signal(32, init = 0)
        period_sum = Signal(32, init = 0)
        period_cnt = Signal(32, init = 0)

        # 是否准备好开始统计周期时间
        get_period_ready = Signal(init = 0)
        maxn2center = Signal(ADC_BITS + 2, init = 0)
        minn2center = Signal(ADC_BITS + 2, init = 0)
        range_up_threshold = Signal(ADC_BITS + 2, init = 0)
        normal_status = Signal(init = 1)

        center = (1 << 11)

        with m.If(get_period_ready):
            m.d.sync += period_sum.eq(period_sum + 1)

        m.d.sync += [
            maxn2center.eq(Mux(maxn > center, maxn - center, center - maxn)),
            minn2center.eq(Mux(minn < center, center - minn, minn - center)),
            range_up_threshold.eq(Mux(self.wave_range == 1, center >> 3, center >> 4))
        ]

        with m.If(~normal_status):
            m.d.sync += get_period_timeout.eq(get_period_timeout + 1)
        with m.Else():
            m.d.sync += get_period_timeout.eq(0)

        with m.FSM(init="normal"):
            with m.State("normal"): # 正常运行
                with m.If(self.button):
                    m.d.sync += [
                        maxn.eq(0),
                        minn.eq((1 << ADC_BITS) - 1),
                        choose_range_timeout.eq(0),
                        self.wave_range.eq(1),
                        normal_status.eq(0)
                    ]
                    m.next = "choose_range"

            with m.State("choose_range"):
                 # 求均值
                with m.If(self.adc_ready):
                    m.d.sync += [
                        maxn.eq(Mux(self.value > maxn, self.value, maxn)),
                        minn.eq(Mux(self.value < minn, self.value, minn)),
                    ]

                with m.If(choose_range_timeout >= 50000000):
                    m.d.sync += choose_range_timeout.eq(0)
                    with m.If((self.wave_range < 4)
                              & (maxn2center < range_up_threshold)
                              & (minn2center < range_up_threshold)):
                        m.d.sync += self.wave_range.eq(self.wave_range + 1)
                    with m.Else():
                        m.next = "get_average"
                with m.Else():
                    m.d.sync += choose_range_timeout.eq(choose_range_timeout + 1)

            with m.State("get_average"):
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
                        m.next = "get_period_mid"
                with m.If(get_period_timeout >= 1000000000): # 10s
                    m.next = "over"
                
            with m.State("get_period_mid"):
                with m.If(self.adc_ready):
                    with m.If(self.value > mid):
                        m.d.sync += get_period_ready.eq(1)
                        with m.If(period_cnt <= 15):
                            m.d.sync += period_cnt.eq(period_cnt + 1)
                            m.next = "get_period_up"
                        with m.Else():
                            m.next = "over"
                with m.If(get_period_timeout >= 1000000000): # 10s
                    m.next = "over"

            with m.State("get_period_up"):
                with m.If(self.adc_ready):
                    with m.If(self.value > mid_high):
                        m.next = "get_period_down"
                with m.If(get_period_timeout >= 1000000000): # 10s
                    m.next = "over"

            with m.State("over"):
                with m.If(get_period_timeout < 1000000000): # 没有触发超时，正常退出了
                    m.d.sync += self.period.eq(period_sum >> 4)
                
                m.d.sync += [
                    self.get_period_over.eq(1),
                    get_period_ready.eq(0),
                    period_cnt.eq(0),
                    self.average.eq(mid),
                    normal_status.eq(1),
                ]
                m.next = "normal"

        with m.If(self.get_period_over):
            m.d.sync += self.get_period_over.eq(0)

        return m