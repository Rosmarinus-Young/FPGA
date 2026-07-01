from amaranth import *

class WaveControl(Elaboratable):
    def __init__(self, adc_value, adc_ready, period, get_period_over, sample_period_control_knob, period_start):
        self.adc_value = adc_value
        self.adc_ready = adc_ready
        self.period = period
        self.get_period_over = get_period_over
        self.sample_period_control_knob = sample_period_control_knob
        self.period_start = period_start
        self.w_en = Signal()
        self.w_addr = Signal(12, init = 0)
        self.w_data = Signal(12)
        self.sample_period = Signal(32, init = 100000)

    def elaborate(self, platform):
        m = Module()
    
        x_limit = 640

        period_cnt = Signal(32, init = 0)

        sample_clk = Signal(32, init = 0)

        with m.If(sample_clk >= self.sample_period - 1): # 到达采样周期，移动存储指针
            m.d.sync += [
                sample_clk.eq(0),
                self.w_addr.eq(self.w_addr + 1),
            ]
        with m.Else():
            m.d.sync += sample_clk.eq(sample_clk + 1)

        with m.If(self.w_addr >= x_limit):
            with m.If(self.period_start):
                m.d.sync += self.w_addr.eq(0)
            with m.Else():
                m.d.sync += self.w_addr.eq(x_limit)

        with m.Elif(self.adc_ready): # adc就绪，采样并储存
            m.d.sync += [
                self.w_en.eq(1),
                self.w_data.eq(self.adc_value)
            ]
        
        with m.If(self.w_en):
            m.d.sync += self.w_en.eq(0)

        with m.If(self.get_period_over): # 周期识别完毕，重置采样间隔
            m.d.sync += self.sample_period.eq(self.period >> 7)

        with m.If(self.sample_period_control_knob == 1): # 旋钮控制采样间隔
            m.d.sync += self.sample_period.eq(self.sample_period + (self.sample_period >> 4))
        with m.Elif(self.sample_period_control_knob == 2):
            m.d.sync += self.sample_period.eq(self.sample_period - (self.sample_period >> 4))

        return m