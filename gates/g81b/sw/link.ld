/* G81b: 256 KB memory; vectors at 0 (ibex mtvec reset = boot_addr, vectored), reset entry at 0x80;
   testbench registers in 0x3FF00-0x3FFFF are never part of the image. */
ENTRY(_start)
SECTIONS {
  . = 0x0;
  .vectors : { KEEP(*(.vectors)) }
  . = 0x80;
  .text : { *(.text.init) *(.text*) }
  .rodata : { *(.rodata*) *(.srodata*) }
  .data : { *(.data*) *(.sdata*) }
  . = ALIGN(4);
  _bss_start = .;
  .bss : { *(.bss*) *(.sbss*) *(COMMON) }
  . = ALIGN(4);
  _bss_end = .;
  _end = .;
  _stack_top = 0x3FEF0;
  ASSERT(_end < 0x3C000, "image + bss too large for 256 KB with a 16 KB stack")
}
