/* G30 workloads: each kernel loops long enough to fill a >= 1,500-cycle window and returns a checksum. */
typedef unsigned int u32;
#ifndef KERNEL
#define KERNEL 0
#endif
static volatile u32 buf[256];

static u32 k_matmul(void) {             /* 6x6 integer matrix multiply, repeated */
    static u32 a[36], b[36], c[36]; u32 s = 0;
    for (int i = 0; i < 36; i++) { a[i] = i * 7 + 3; b[i] = i * 5 + 1; }
    for (int r = 0; r < 4; r++) {
        for (int i = 0; i < 6; i++) for (int j = 0; j < 6; j++) {
            u32 acc = 0; for (int k = 0; k < 6; k++) acc += a[i * 6 + k] * b[k * 6 + j]; c[i * 6 + j] = acc; }
        for (int i = 0; i < 36; i++) { s ^= c[i] + r; a[i] = c[i] & 0xff; }
    }
    return s;
}
static u32 k_crc(void) {                /* bitwise CRC-32 over 96 bytes, repeated */
    u32 crc = 0xffffffffu;
    for (int i = 0; i < 96; i++) buf[i] = (i * 37 + 11) & 0xff;
    for (int r = 0; r < 3; r++)
        for (int i = 0; i < 96; i++) { crc ^= buf[i]; for (int b = 0; b < 8; b++) crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u))); }
    return ~crc;
}
static u32 k_sort(void) {               /* insertion sort of 48 words, memory heavy */
    u32 s = 0;
    for (int r = 0; r < 2; r++) {
        for (int i = 0; i < 48; i++) buf[i] = (u32)((i * 2654435761u + r) >> 7) & 0xffff;
        for (int i = 1; i < 48; i++) { u32 v = buf[i]; int j = i - 1; while (j >= 0 && buf[j] > v) { buf[j + 1] = buf[j]; j--; } buf[j + 1] = v; }
        for (int i = 0; i < 48; i++) s = s * 31 + buf[i];
    }
    return s;
}
static u32 k_idle(void) {               /* tight branch loop: near-idle datapath */
    volatile u32 n = 0; for (int i = 0; i < 1200; i++) n = n; return 0x1d1e;
}
u32 main(void) {
#if KERNEL == 0
    return k_matmul();
#elif KERNEL == 1
    return k_crc();
#elif KERNEL == 2
    return k_sort();
#elif KERNEL == 3
    return k_idle();
#else
    for (;;) __asm__ volatile ("wfi");      /* sleep: no interrupts arrive, the core clock-gates itself */
#endif
}
