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

        # Construct 16-bit VAUX buses — only channel 1 is used
        vauxp = Cat(Const(0, 1), self.vauxp1, Const(0, 14))
        vauxn = Cat(Const(0, 1), self.vauxn1, Const(0, 14))

        m.submodules.u_xadc = Instance(
            "XADC",
            # Sequencer: continuous mode, single channel (VAUX1), all cals
            p_INIT_40=Const(0x0000, 16),
            p_INIT_41=Const(0x20F0, 16),  # SEQ=0010 continuous, CAL=1111
            p_INIT_42=Const(0x0400, 16),  # 16-sample averaging
            p_INIT_48=Const(0x0002, 16),  # Enable VAUX1 in sequencer
            p_INIT_49=Const(0x0000, 16),

            i_DADDR=Const(0x11, 7),
            i_DCLK=self.clk,
            i_DEN=eoc,
            i_DI=Const(0, 16),
            i_DWE=Const(0),
            i_RESET=Const(0),

            i_VAUXP=vauxp,
            i_VAUXN=vauxn,

            i_VP=Const(0),
            i_VN=Const(0),

            i_CONVST=Const(0),
            i_CONVSTCLK=Const(0),

            o_DO=xadc_data,
            o_DRDY=drdy,
            o_EOC=eoc,
            o_ALM=Signal(8),
            o_BUSY=Signal(),
            o_CHANNEL=Signal(5),
            o_EOS=Signal(),
            o_OT=Signal(),
            o_MUXADDR=Signal(5),
        )

        with m.If(drdy):
            m.d.sync += [
                self.adc_value.eq(xadc_data[4:16]),
                self.adc_ready.eq(1),
            ]
        
        with m.Else():
            m.d.sync += self.adc_ready.eq(0)

        return m
