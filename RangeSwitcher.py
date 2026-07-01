from amaranth import *

class RangeSwitcher(Elaboratable):
    def __init__(self, A0, A1, wave_range):
        self.A0 = A0
        self.A1 = A1
        self.wave_range = wave_range

    def elaborate(self, platform):
        m = Module()

        with m.Switch(self.wave_range):
            with m.Case(4):
                m.d.sync += [
                    self.A0.eq(0),
                    self.A1.eq(0)
                ]
            with m.Case(3):
                m.d.sync += [
                    self.A0.eq(1),
                    self.A1.eq(0)
                ]
            with m.Case(2):
                m.d.sync += [
                    self.A0.eq(0),
                    self.A1.eq(1)
                ]
            with m.Case(1):
                m.d.sync += [
                    self.A0.eq(1),
                    self.A1.eq(1)
                ]
            with m.Default():
                m.d.sync += [
                    self.A0.eq(1),
                    self.A1.eq(1)
                ]
        return m