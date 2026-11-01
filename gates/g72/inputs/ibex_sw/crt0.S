    .section .text.init
    .globl _start
_start:
    la   sp, _stack_top
    call main
    li   t0, 0x8000          /* signature: checksum */
    sw   a0, 0(t0)
    li   t1, 1
    sw   t1, 4(t0)           /* done flag at 0x8004 */
1:  j    1b
