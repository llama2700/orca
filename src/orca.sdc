# librelane's stock constraints, then one line for the settle sensor
source $::env(SCRIPTS_DIR)/base.sdc

# clk feeds the delay chain on purpose. without this sta follows clk through
# all 64 cells and the tap mux, sees the shadow launch register as a clk sink
# 30 ns late, and cts pads every other flop to match (332 delay buffers, then
# placement fell over). killing the arc through the first cell makes the chain
# plain data and leaves the shadow register unconstrained, which is what the
# design wants. set_sense -stop_propagation did not do it in this openroad.
# hold on shadow_q -> fabric -> capture is reviewed by hand, see
# TODO_delayline.md
set_disable_timing [get_cells {u_sensor.g_dly\[0\].u_dly}]
