from amaranth import *
from amaranth.lib.memory import Memory


class RAM(Elaboratable):
    def __init__(self, w_en, w_data, w_addr, r_en, r_addr):
        self.w_en = w_en
        self.w_data = w_data
        self.w_addr = w_addr
        self.r_en = r_en
        self.r_addr = r_addr

        self.r_data = Signal(10, init=0)

    def elaborate(self, platform):
        m = Module()


        m.submodules.ram = ram = Memory(
            shape=unsigned(10),
            depth=640,
            init=[0] * 640
        )

        wr = ram.write_port(domain="sync")
        rd = ram.read_port(domain="pix")

        m.d.comb += [
            wr.en.eq(self.w_en),
            wr.addr.eq(self.w_addr),
            wr.data.eq(self.w_data),

            rd.en.eq(self.r_en),
            rd.addr.eq(self.r_addr),
            self.r_data.eq(rd.data),
        ]

        return m
