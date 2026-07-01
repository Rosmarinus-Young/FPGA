# ================================================================
# EGO1 VGADemo — XDC Pin Constraints
# ================================================================

# 100 MHz system clock
set_property PACKAGE_PIN P17 [get_ports clk]
set_property IOSTANDARD LVCMOS33 [get_ports clk]
create_clock -period 10.000 -name sys_clk [get_ports clk]

# Reset button (active high)
set_property PACKAGE_PIN P15 [get_ports rst]
set_property IOSTANDARD LVCMOS33 [get_ports rst]

# ---- VGA ----
set_property PACKAGE_PIN F5  [get_ports {vga_r[0]}]
set_property PACKAGE_PIN C6  [get_ports {vga_r[1]}]
set_property PACKAGE_PIN C5  [get_ports {vga_r[2]}]
set_property PACKAGE_PIN B7  [get_ports {vga_r[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {vga_r[*]}]

set_property PACKAGE_PIN B6  [get_ports {vga_g[0]}]
set_property PACKAGE_PIN A6  [get_ports {vga_g[1]}]
set_property PACKAGE_PIN A5  [get_ports {vga_g[2]}]
set_property PACKAGE_PIN D8  [get_ports {vga_g[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {vga_g[*]}]

set_property PACKAGE_PIN C7  [get_ports {vga_b[0]}]
set_property PACKAGE_PIN E6  [get_ports {vga_b[1]}]
set_property PACKAGE_PIN E5  [get_ports {vga_b[2]}]
set_property PACKAGE_PIN E7  [get_ports {vga_b[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {vga_b[*]}]

set_property PACKAGE_PIN D7  [get_ports vga_hsync]
set_property PACKAGE_PIN C4  [get_ports vga_vsync]
set_property IOSTANDARD LVCMOS33 [get_ports vga_hsync]
set_property IOSTANDARD LVCMOS33 [get_ports vga_vsync]

# ---- Control buttons / knobs ----
set_property PACKAGE_PIN R11 [get_ports auto_button]
set_property IOSTANDARD LVCMOS33 [get_ports auto_button]

set_property PACKAGE_PIN R17 [get_ports sample_period_control_knob_A]
set_property PACKAGE_PIN R15 [get_ports sample_period_control_knob_B]
set_property IOSTANDARD LVCMOS33 [get_ports sample_period_control_knob_A]
set_property IOSTANDARD LVCMOS33 [get_ports sample_period_control_knob_B]

set_property PACKAGE_PIN V1  [get_ports display_gain_control_knob_A]
set_property PACKAGE_PIN U4  [get_ports display_gain_control_knob_B]
set_property IOSTANDARD LVCMOS33 [get_ports display_gain_control_knob_A]
set_property IOSTANDARD LVCMOS33 [get_ports display_gain_control_knob_B]

# ---- XADC analog input ----
set_property PACKAGE_PIN K9  [get_ports vauxp1]
set_property PACKAGE_PIN J9  [get_ports vauxn1]
set_property IOSTANDARD LVCMOS33 [get_ports vauxp1]
set_property IOSTANDARD LVCMOS33 [get_ports vauxn1]

# ---- DAC0832 data bus [DAC_D0 .. DAC_D7] ----
set_property PACKAGE_PIN T8  [get_ports {dac_data[0]}]
set_property PACKAGE_PIN R8  [get_ports {dac_data[1]}]
set_property PACKAGE_PIN T6  [get_ports {dac_data[2]}]
set_property PACKAGE_PIN R7  [get_ports {dac_data[3]}]
set_property PACKAGE_PIN U6  [get_ports {dac_data[4]}]
set_property PACKAGE_PIN U7  [get_ports {dac_data[5]}]
set_property PACKAGE_PIN V9  [get_ports {dac_data[6]}]
set_property PACKAGE_PIN U9  [get_ports {dac_data[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {dac_data[*]}]

# ---- DAC0832 control signals ----
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
