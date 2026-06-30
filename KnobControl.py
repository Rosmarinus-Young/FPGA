from amaranth import *

class KnobControl(Elaboratable):
    def __init__(self, A, B, out):
        self.A = A
        self.B = B
        self.out = out

    def elaborate(self, platform):
        m = Module()

        stable = Signal(1, init = 0)
        status = Signal(2, init = 0)
        stable_status = Signal(2, init = 0)
        last_stable_status = Signal(2, init = 0)
        last_status = Signal(2, init = 0)
        cnt = Signal(32, init = 0)
        m.d.sync += [
            last_status.eq(status),
            status.eq((self.A << 1) + self.B),
        ]

        with m.FSM(init = "unstable"):
            with m.State("stable"):
                with m.If(status != last_status):
                    m.d.sync += cnt.eq(0)
                    m.next = "unstable"
            with m.State("unstable"):
                with m.If(status == last_status):
                    m.d.sync += cnt.eq(cnt + 1)
                with m.Else:
                    m.d.sync += cnt.eq(0)

                with m.If(cnt >= 1000000): # 10ms
                    m.d.sync += [
                        stable.eq(1),
                        stable_status.eq(status),
                    ]
                    m.next = "stable"

        with m.If(stable):
            with m.Switch(last_stable_status):
                with m.Case(0b00):
                    with m.If(stable_status == 1):
                        m.d.sync += self.out.eq(self.out + 1)
                    with m.Elif(stable_status == 2):
                        m.d.sync += self.out.eq(self.out - 1)
                with m.Case(0b01):
                    with m.If(stable_status == 3):
                        m.d.sync += self.out.eq(self.out + 1)
                    with m.Elif(stable_status == 0):
                        m.d.sync += self.out.eq(self.out - 1)
                with m.Case(0b11):
                    with m.If(stable_status == 2):
                        m.d.sync += self.out.eq(self.out + 1)
                    with m.Elif(stable_status == 1):
                        m.d.sync += self.out.eq(self.out - 1)
                with m.Case(0b10):
                    with m.If(stable_status == 0):
                        m.d.sync += self.out.eq(self.out + 1)
                    with m.Elif(stable_status == 3):
                        m.d.sync += self.out.eq(self.out - 1)
            m.d.sync += [
                stable.eq(0),
                last_stable_status.eq(stable_status),
            ]
        return m
