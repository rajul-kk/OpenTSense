/* G81b idle program: 10 x (20,000 cycles of a G30 kernel, then 20,000 cycles asleep in wfi, woken by the
   testbench timer). Phase markers: 2k = compute k starts, 2k+1 = sleep k starts. Returns a checksum
   checked against idle_host.py. Kernel: G30's k_crc (bitwise CRC-32 over 96 bytes), NPASS passes per
   compute phase; NPASS is fixed in the dry run so that a compute phase lasts about 20,000 cycles. */
typedef unsigned int u32;
#define TBREG(o) (*(volatile u32 *)(0x3FF00 + (o)))
#define PHASES 10
#ifndef NPASS
#define NPASS 1
#endif
#define SLEEP 20000u
static volatile u32 buf[96];
static u32 crc_pass(u32 crc) {
    for (int i = 0; i < 96; i++) { crc ^= buf[i]; for (int b = 0; b < 8; b++) crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u))); }
    return crc;
}
u32 main(void) {
    for (int i = 0; i < 96; i++) buf[i] = (i * 37 + 11) & 0xff;
    __asm__ volatile ("csrs mie, %0" :: "r"(1u << 7));          /* machine timer interrupt enable */
    __asm__ volatile ("csrsi mstatus, 8");                      /* global interrupt enable */
    u32 crc = 0xffffffffu, passes = 0;
    for (int p = 0; p < PHASES; p++) {
        TBREG(0x18) = 2 * p;
        for (int n = 0; n < NPASS; n++) { crc = crc_pass(crc); passes++; }
        TBREG(0x18) = 2 * p + 1;
        TBREG(0x08) = SLEEP;                                    /* timer fires SLEEP cycles from now */
        __asm__ volatile ("wfi");
    }
    TBREG(0x18) = 2 * PHASES;
    return ~crc ^ passes;
}
