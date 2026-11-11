/* G81b Embench board hooks: start/stop markers to the testbench registers. */
#include <support.h>
#define TBREG(o) (*(volatile unsigned int *)(0x3FF00 + (o)))
void initialise_board(void) {}
void __attribute__((noinline)) start_trigger(void) { TBREG(0x10) = 1; }
void __attribute__((noinline)) stop_trigger(void) { TBREG(0x14) = 1; }
