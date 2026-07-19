"""Serial command BFM for the ORCA CSR interface.

Bit-bangs ui_in[4]=ser_data, ui_in[5]=ser_shift, ui_in[6]=ser_exec and samples
uio_out[3]=ser_out, mirroring what the RP2040 does on the TT demo board.
"""

from cocotb.triggers import ClockCycles

# CSR map
ID          = 0x00
CTRL        = 0x01
STATUS      = 0x02
BEST_FIT    = 0x03
LAST_FIT    = 0x04
GEN_LO      = 0x05
GEN_HI      = 0x06
ACCEPTS     = 0x07
TEMP        = 0x08
SEED_LO     = 0x09
SEED_HI     = 0x0A
STUCK_EN    = 0x0B
STUCK_VAL   = 0x0C
TARGET0     = 0x0D
TARGET1     = 0x0E
GENOME_BASE = 0x10  # 0x10..0x1A used (11 x 12-bit words), 0x1B reads 0
SETTLE_TAP  = 0x1C

# CTRL bits
CTRL_SOFT_RUN       = 1 << 0
CTRL_RESET_COUNTERS = 1 << 1
CTRL_PAUSE_ACCEPT   = 1 << 2
CTRL_ERR_BUSY_W1C   = 1 << 3
CTRL_SPEED_DISABLE  = 1 << 4

# STATUS bits
STATUS_STATE_MASK = 0x7
STATUS_SOLVED     = 1 << 3
STATUS_ERR_BUSY   = 1 << 4

ID_VALUE = 0x08CA

# ES FSM states (STATUS[2:0])
ES_IDLE = 0


class SerBFM:
    """dut must expose ui_in, uio_out, clk. Other ui_in bits are preserved
    via set_pin()/the ui shadow so run/anneal levels survive serial traffic."""

    def __init__(self, dut, spacing=4):
        self.dut = dut
        self.spacing = spacing
        self.ui = 0

    async def _apply(self, value):
        self.ui = value
        self.dut.ui_in.value = value
        await ClockCycles(self.dut.clk, self.spacing)

    async def set_pin(self, bit, value):
        """Set a non-serial ui_in pin (0=run, 1=anneal_en, 2=fault_demo)."""
        await self._apply((self.ui & ~(1 << bit)) | (value << bit))

    async def _pulse(self, bit):
        await self._apply(self.ui | (1 << bit))
        await self._apply(self.ui & ~(1 << bit))

    async def _shift_bit(self, bit):
        await self._apply((self.ui & ~(1 << 4)) | (bit << 4))  # ser_data
        await self._pulse(5)                                   # ser_shift

    async def _shift_frame(self, rw, addr, data):
        frame = (rw << 23) | ((addr & 0x7F) << 16) | (data & 0xFFFF)
        for i in range(23, -1, -1):
            await self._shift_bit((frame >> i) & 1)
        await self._pulse(6)                                   # ser_exec

    async def write(self, addr, data):
        await self._shift_frame(1, addr, data)

    async def read(self, addr):
        await self._shift_frame(0, addr, 0)
        value = 0
        for _ in range(16):
            # sample ser_out before each shift pulse
            value = (value << 1) | (int(self.dut.uio_out.value) >> 3 & 1)
            await self._pulse(5)
        return value

    async def read_genome(self):
        g = 0
        for w in range(11):
            g |= (await self.read(GENOME_BASE + w) & 0xFFF) << (12 * w)
        return g

    async def write_genome(self, genome):
        for w in range(11):
            await self.write(GENOME_BASE + w, (genome >> (12 * w)) & 0xFFF)
