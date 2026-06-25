from amaranth import *
from amaranth.lib.memory import Memory


class RAM(Elaboratable):
    def __init__(self, xadc_value, vga_x, r_en, depth=640, width = 480, sample_period = 100000):
        self.depth = depth
        self.width = width
        self.xadc_value = xadc_value
        self.w_en = Signal()
        self.w_data = Signal(range(width))
        self.sample_period = sample_period
        self.r_addr = vga_x
        self.r_data = Signal(range(width))
        self.r_en = r_en
        self.w_addr = Signal(range(self.depth))

    def elaborate(self, platform):
        m = Module()

        m.submodules.ram = ram = Memory(
            shape=unsigned(10),
            depth=self.depth,
            init=[0] * self.depth
        )

        wr = ram.write_port(domain="sync")
        rd = ram.read_port(domain="sync")

        sample_clk = Signal(range(self.sample_period))
        with m.If(sample_clk == self.sample_period - 1):
            m.d.sync += sample_clk.eq(0)
            m.d.sync += self.w_en.eq(1)
        with m.Else():
            m.d.sync += sample_clk.eq(sample_clk + 1)
            m.d.sync += self.w_en.eq(0)

        m.d.comb += [
            wr.en.eq(self.w_en),
            wr.addr.eq(self.w_addr),
            wr.data.eq(self.xadc_value >> 3),

            rd.en.eq(self.r_en),
            rd.addr.eq(self.r_addr),
            self.r_data.eq(rd.data),
        ]

        with m.If(self.w_en):
            with m.If(self.w_addr == self.depth - 1):
                m.d.sync += self.w_addr.eq(0)
            with m.Else():
                m.d.sync += self.w_addr.eq(self.w_addr + 1)

        return m