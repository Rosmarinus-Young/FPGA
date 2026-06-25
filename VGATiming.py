from amaranth import *

class VGATiming(Elaboratable):
    """
    640x480@60Hz

    输出：
        hsync   : VGA 行同步，低有效
        vsync   : VGA 场同步，低有效
        visible : 当前像素是否位于有效显示区域
        x       : 当前像素横坐标，0~639
        y       : 当前像素纵坐标，0~479
    """

    def __init__(self):
        # 640x480@60Hz timing
        self.H_VISIBLE = 640
        self.H_FRONT   = 16
        self.H_SYNC    = 96
        self.H_BACK    = 48
        self.H_TOTAL   = self.H_VISIBLE + self.H_FRONT + self.H_SYNC + self.H_BACK

        self.V_VISIBLE = 480
        self.V_FRONT   = 10
        self.V_SYNC    = 2
        self.V_BACK    = 33
        self.V_TOTAL   = self.V_VISIBLE + self.V_FRONT + self.V_SYNC + self.V_BACK

        self.hsync   = Signal(reset=1)
        self.vsync   = Signal(reset=1)
        self.visible = Signal()

        self.x = Signal(range(self.H_TOTAL))
        self.y = Signal(range(self.V_TOTAL))

    def elaborate(self, platform):
        m = Module()

        h_cnt = Signal(range(self.H_TOTAL))
        v_cnt = Signal(range(self.V_TOTAL))

        # 水平、垂直扫描计数器
        with m.If(h_cnt == self.H_TOTAL - 1):
            m.d.pix += h_cnt.eq(0)

            with m.If(v_cnt == self.V_TOTAL - 1):
                m.d.pix += v_cnt.eq(0)
            with m.Else():
                m.d.pix += v_cnt.eq(v_cnt + 1)

        with m.Else():
            m.d.pix += h_cnt.eq(h_cnt + 1)

        # 有效显示区域
        m.d.comb += [
            self.x.eq(h_cnt),
            self.y.eq(v_cnt),
            self.visible.eq(
                (h_cnt < self.H_VISIBLE) &
                (v_cnt < self.V_VISIBLE)
            )
        ]

        # VGA 同步信号，低有效
        hsync_start = self.H_VISIBLE + self.H_FRONT
        hsync_end   = self.H_VISIBLE + self.H_FRONT + self.H_SYNC

        vsync_start = self.V_VISIBLE + self.V_FRONT
        vsync_end   = self.V_VISIBLE + self.V_FRONT + self.V_SYNC

        m.d.comb += [
            self.hsync.eq(~((h_cnt >= hsync_start) & (h_cnt < hsync_end))),
            self.vsync.eq(~((v_cnt >= vsync_start) & (v_cnt < vsync_end))),
        ]

        return m
