from amaranth import *

class XADCModule(Elaboratable):
    def __init__(self, clk, vauxp10, vauxn10, vauxp2, vauxn2):
        self.clk = clk
        self.vauxp10 = vauxp10
        self.vauxn10 = vauxn10
        self.vauxp2 = vauxp2
        self.vauxn2 = vauxn2

        self.adc_ch0_value = Signal(12)   # VAUXP10
        self.adc_ch0_ready = Signal()
        self.adc_ch1_value = Signal(12)   # VAUXP2
        self.adc_ch1_ready = Signal()

    def elaborate(self, platform):
        m = Module()

        xadc_data = Signal(16)
        drdy = Signal()
        eoc = Signal()
        daddr = Signal(7, reset=0x1A)
        channel = Signal(reset=0)

        m.submodules.u_xadc = Instance(
            "xadc_wiz_0",

            i_daddr_in=daddr,
            i_dclk_in=self.clk,
            i_den_in=eoc,
            i_di_in=Const(0, 16),
            i_dwe_in=Const(0, 1),
            i_reset_in=Const(0, 1),

            i_vauxp10=self.vauxp10,
            i_vauxn10=self.vauxn10,
            i_vauxp2=self.vauxp2,
            i_vauxn2=self.vauxn2,

            o_do_out=xadc_data,
            o_drdy_out=drdy,
            o_eoc_out=eoc,

            i_vp_in=Const(0, 1),
            i_vn_in=Const(0, 1),
        )

        # drdy 时根据 channel 标志存入对应通道
        with m.If(drdy):
            with m.If(~channel):
                m.d.sync += [
                    self.adc_ch0_value.eq(xadc_data[4:16]),
                    self.adc_ch0_ready.eq(1),
                ]
            with m.Else():
                m.d.sync += [
                    self.adc_ch1_value.eq(xadc_data[4:16]),
                    self.adc_ch1_ready.eq(1),
                ]
            m.d.sync += channel.eq(~channel)

        # eoc 后立即切换 daddr，为下一次转换准备
        with m.If(eoc):
            m.d.sync += daddr.eq(Mux(channel, 0x1A, 0x12))

        # ready 信号单周期脉冲
        with m.If(self.adc_ch0_ready):
            m.d.sync += self.adc_ch0_ready.eq(0)
        with m.If(self.adc_ch1_ready):
            m.d.sync += self.adc_ch1_ready.eq(0)

        return m
