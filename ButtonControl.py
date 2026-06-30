from amaranth import *

class ButtonControl(Elaboratable):
    def __init__(self, button):
        self.button = button
        self.out = Signal(1, init = 0)

    def elaborate(self, platform):
        m = Module()

        status = Signal(1, init = 0)
        last_status = Signal(1, init = 0)
        cnt = Signal(32, init = 0)
        m.d.sync += [
            last_status.eq(status),
            status.eq(self.button),
        ]

        with m.FSM(init = "up"):
            with m.State("up"):
                with m.If(status == 1):
                    m.d.sync += cnt.eq(cnt + 1)
                with m.Else():
                    m.d.sync += cnt.eq(0)
                with m.If(cnt >= 1000000): # 10ms
                    m.d.sync += [
                        self.out.eq(1),
                        cnt.eq(0)
                        ]
                    m.next = "down"
            with m.State("down"):
                m.d.sync += self.out.eq(0)
                with m.If(status == 0):
                    m.d.sync += cnt.eq(cnt + 1)
                with m.Else():
                    m.d.sync += cnt.eq(0)
                with m.If(cnt >= 1000000): # 10ms
                    m.d.sync += cnt.eq(0)
                    m.next = "up"

        return m