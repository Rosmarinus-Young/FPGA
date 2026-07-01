from VGATiming import VGATiming
from XADCModule import XADCModule
from VGADisplay import VGADisplay
from PeriodDetector import PeriodDetector
from ButtonControl import ButtonControl
from WaveControl import WaveControl
from KnobControl import KnobControl
from RangeSwitcher import RangeSwitcher
from PhaseGetter import PhaseGetter
from RAM import RAM
from amaranth import *
from GainControl import GainControl

class Scope(Elaboratable):
    def __init__(self, adc_value, adc_ready, auto_button, KEYA1, KEYA2, sample_period_control_knob_A, sample_period_control_knob_B, display_gain_control_knob_A, display_gain_control_knob_B, timing):
        self.period_detector = PeriodDetector(adc_value = adc_value, 
                                              adc_ready = adc_ready,
                                              auto_button = auto_button)

        self.range_switcher = RangeSwitcher(A0 = KEYA1, A1 = KEYA2, 
                                            wave_range = self.period_detector.wave_range)

        self.sample_period_control_knob = KnobControl(A = sample_period_control_knob_A, 
                                                      B = sample_period_control_knob_B)

        self.phase_getter = PhaseGetter(adc_value = adc_value, adc_ready = adc_ready,
                                        wave_maxn = self.period_detector.maxn,
                                        wave_minn = self.period_detector.minn,
                                        get_period_over = self.period_detector.get_period_over)

        self.wave_control = WaveControl(adc_value = adc_value, adc_ready = adc_ready, 
                                        period = self.period_detector.period, 
                                        get_period_over = self.period_detector.get_period_over,
                                        sample_period_control_knob = self.sample_period_control_knob.out,
                                        period_start = self.phase_getter.period_start)

        self.ram = RAM(r_addr = timing.x, r_en = 1, w_addr = self.wave_control.w_addr, 
                       w_data = self.wave_control.w_data, w_en = self.wave_control.w_en)

        self.display_gain_control_knob = KnobControl(A = display_gain_control_knob_A, 
                                                     B = display_gain_control_knob_B)
        
        self.gain_control = GainControl(r_data = self.ram.r_data,
                                        gain_control_knob = self.display_gain_control_knob.out,
                                        get_period_over = self.period_detector.get_period_over,
                                        maxn = self.period_detector.maxn,
                                        minn = self.period_detector.minn,
                                        mid = self.period_detector.mid)

    def elaborate(self, platform):
        m = Module()

        m.submodules.period_detector = self.period_detector

        m.submodules.range_switcher = self.range_switcher

        m.submodules.sample_period_control_knob = self.sample_period_control_knob

        m.submodules.phase_getter = self.phase_getter

        m.submodules.wave_control = self.wave_control

        m.submodules.ram = self.ram

        m.submodules.display_gain_control_knob = self.display_gain_control_knob

        m.submodules.gain_control = self.gain_control

        return m