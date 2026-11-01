ENTRY(_start)
SECTIONS {
  . = 0x80;
  .text : { *(.text.init) *(.text*) }
  .rodata : { *(.rodata*) *(.srodata*) }
  .data : { *(.data*) *(.sdata*) }
  .bss : { *(.bss*) *(.sbss*) *(COMMON) }
  _stack_top = 0x7ff0;
}
