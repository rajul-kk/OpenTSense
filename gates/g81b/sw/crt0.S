/* G81b start-up: vector table (only the machine timer interrupt is used), zeroed .bss, result and done flag. */
    .section .vectors, "ax"
    .option norvc
    .globl _vectors
_vectors:
    .rept 7
    j    trap_other
    .endr
    j    timer_isr                 /* entry 7: machine timer interrupt */
    .rept 24
    j    trap_other
    .endr
    .option rvc

    .section .text.init
    .globl _start
_start:
    la   sp, _stack_top
    la   t0, _bss_start
    la   t1, _bss_end
1:  bgeu t0, t1, 2f
    sw   zero, 0(t0)
    addi t0, t0, 4
    j    1b
2:  call main
    li   t0, 0x3FF00
    sw   a0, 0(t0)                 /* result: verify_benchmark (0 = correct) or the idle program's checksum */
    li   t1, 1
    sw   t1, 4(t0)                 /* done flag */
3:  j    3b

timer_isr:
    csrw mscratch, t0
    li   t0, 0x3FF0C
    sw   zero, 0(t0)               /* clear the testbench timer line */
    csrr t0, mscratch
    mret

trap_other:                        /* any other trap: report it and stop */
    li   t0, 0x3FF00
    li   t1, 0xDEAD0000
    csrr t2, mcause
    or   t1, t1, t2
    sw   t1, 0(t0)
    li   t1, 1
    sw   t1, 4(t0)
4:  j    4b
