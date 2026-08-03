package orca_pkg;

/*
* DEFINED
*/

// fabric size
parameter integer FABRIC_COLS = 4;
parameter integer FABRIC_ROWS = 4;

// primary output width
parameter integer PO_WIDTH = 2;

parameter logic FAULT_EN = 1;


/*
* DERIVED
*/

parameter integer NUM_CELLS = FABRIC_COLS * FABRIC_ROWS;

parameter integer PI_WIDTH = FABRIC_ROWS;
parameter integer SEL_W    = $clog2(FABRIC_ROWS);
parameter integer LUT_BITS = 4;
parameter integer GENE_W   = LUT_BITS + 2 * SEL_W; // 8 bits per cell

// genome width: 1 gene per cell + PO selects = 16*8 + 2*2 = 132
parameter integer GENOME_SIZE = NUM_CELLS * GENE_W + PO_WIDTH * SEL_W;


/*
* TYPES
*/

//   genome[8i+3 : 8i]   lut
//   genome[8i+5 : 8i+4] sel_a
//   genome[8i+7 : 8i+6] sel_b
typedef struct packed {
  logic [SEL_W-1:0]    sel_b;
  logic [SEL_W-1:0]    sel_a;
  logic [LUT_BITS-1:0] lut;
} gene_t;

endpackage
