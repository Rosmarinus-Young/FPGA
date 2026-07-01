# ================================================================
# EGO1 SignalGenerator — XDC Pin Constraints
# ================================================================

# 100 MHz system clock
set_property PACKAGE_PIN P17 [get_ports clk]
set_property IOSTANDARD LVCMOS33 [get_ports clk]
create_clock -period 10.000 -name sys_clk [get_ports clk]

# Reset button (active high)
set_property PACKAGE_PIN P15 [get_ports rst]
set_property IOSTANDARD LVCMOS33 [get_ports rst]

# DAC0832 data bus [DAC_D0 .. DAC_D7]
set_property PACKAGE_PIN T8  [get_ports {dac_data[0]}]
set_property PACKAGE_PIN R8  [get_ports {dac_data[1]}]
set_property PACKAGE_PIN T6  [get_ports {dac_data[2]}]
set_property PACKAGE_PIN R7  [get_ports {dac_data[3]}]
set_property PACKAGE_PIN U6  [get_ports {dac_data[4]}]
set_property PACKAGE_PIN U7  [get_ports {dac_data[5]}]
set_property PACKAGE_PIN V9  [get_ports {dac_data[6]}]
set_property PACKAGE_PIN U9  [get_ports {dac_data[7]}]

set_property IOSTANDARD LVCMOS33 [get_ports {dac_data[*]}]

# DAC0832 control signals
set_property PACKAGE_PIN R5  [get_ports dac_ile]   ;# DAC_BYTE2
set_property PACKAGE_PIN N6  [get_ports dac_cs]    ;# DAC_CS#
set_property PACKAGE_PIN V6  [get_ports dac_wr1]   ;# DAC_WR1#
set_property PACKAGE_PIN R6  [get_ports dac_wr2]   ;# DAC_WR2#
set_property PACKAGE_PIN V7  [get_ports dac_xfer]  ;# DAC_XFER#

set_property IOSTANDARD LVCMOS33 [get_ports dac_ile]
set_property IOSTANDARD LVCMOS33 [get_ports dac_cs]
set_property IOSTANDARD LVCMOS33 [get_ports dac_wr1]
set_property IOSTANDARD LVCMOS33 [get_ports dac_wr2]
set_property IOSTANDARD LVCMOS33 [get_ports dac_xfer]
