# ORCA cocotb test Makefile
#
# Default (full chip via tb.v):   make -B
# Unit suites:                    make -B UNIT=fabric|fault|eval|es
# Gate level (TT CI):             make -B GATES=yes

SIM ?= icarus
FST ?= -fst
TOPLEVEL_LANG ?= verilog

RTL_DIR = $(PWD)/../src

RTL_SOURCES = orca_pkg.sv fabric_cell.sv fabric.sv prng.sv genome_store.sv \
              ser_cmd.sv settle_sensor.sv eval_engine.sv es_controller.sv tt_um_orca.sv \
              orca_art_stub.sv

UNIT ?=

ifeq ($(GATES),yes)

# Gate level simulation (netlist copied in by the TT GDS action workflow):
SIM_BUILD        = sim_build/gl
COMPILE_ARGS    += -DGL_TEST -DFUNCTIONAL -DUSE_POWER_PINS -DSIM -DUNIT_DELAY=\#1
VERILOG_SOURCES += $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog/primitives.v
VERILOG_SOURCES += $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog/sky130_fd_sc_hd.v
VERILOG_SOURCES += $(PWD)/../src/orca_art_stub.sv
VERILOG_SOURCES += $(PWD)/gate_level_netlist.v
VERILOG_SOURCES += $(PWD)/tb.v
TOPLEVEL = tb
COCOTB_TEST_MODULES ?= test_reset,test_serial,test_evolution_e2e

else ifeq ($(UNIT),)

# Full-chip RTL simulation:
SIM_BUILD        = sim_build/rtl
VERILOG_SOURCES += $(addprefix $(RTL_DIR)/,$(RTL_SOURCES))
VERILOG_SOURCES += $(PWD)/tb.v
TOPLEVEL = tb
COCOTB_TEST_MODULES ?= test_reset,test_serial,test_evolution_e2e

else

# Unit simulation (fabric standalone or an SV harness around a block):
SIM_BUILD        = sim_build/$(UNIT)
VERILOG_SOURCES += $(addprefix $(RTL_DIR)/,$(RTL_SOURCES))
VERILOG_SOURCES += $(PWD)/harness/eval_harness.sv $(PWD)/harness/es_harness.sv
TOPLEVEL = $(if $(filter $(UNIT),fabric fault),fabric,$(if $(filter $(UNIT),eval),eval_harness,es_harness))
COCOTB_TEST_MODULES = test_$(UNIT)

endif

# Make the golden model importable from test modules:
export PYTHONPATH := $(PWD)/..:$(PYTHONPATH)

# include cocotb's make rules to take care of the simulator setup
include $(shell cocotb-config --makefiles)/Makefile.sim
