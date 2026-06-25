from amaranth import *

class XADCModule(Elaboratable):
    def __init__(self, clk, vauxp1, vauxn1):
        self.clk = clk

        self.vauxp1 = vauxp1
        self.vauxn1 = vauxn1
        self.adc_value = Signal(12)
        self.adc_ready = Signal()

    def elaborate(self, platform):
        m = Module()

        xadc_data = Signal(16)
        drdy = Signal()
        eoc = Signal()

        m.submodules.u_xadc = Instance(
            "xadc_wiz_0",

            i_daddr_in=Const(0x11, 7),
            i_dclk_in=self.clk,
            i_den_in=eoc,
            i_di_in=Const(0, 16),
            i_dwe_in=Const(0, 1),
            i_reset_in=Const(0, 1),

            i_vauxp1=self.vauxp1,
            i_vauxn1=self.vauxn1,

            o_do_out=xadc_data,
            o_drdy_out=drdy,
            o_eoc_out=eoc,

            i_vp_in=Const(0, 1),
            i_vn_in=Const(0, 1),
        )

        with m.If(drdy):
            m.d.sync += [
                self.adc_value.eq(xadc_data[4:16]),
                self.adc_ready.eq(1),
            ]
        
        with m.Else():
            m.d.sync += self.adc_ready.eq(0)

        return m
