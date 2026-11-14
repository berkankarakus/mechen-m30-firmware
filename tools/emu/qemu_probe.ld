/* Filled by make_qemu_probe.py with an INCLUDE of the generated AP banks. */
ENTRY(_start)
SECTIONS
{
    . = 0x00400000;
    .text : { qemu_probe_start.o(.text) }
    . = 0x00700000;
    .stubs : { qemu_probe.o(.stubs) }
    . = 0x10002000;
    .ram : { qemu_probe_start.o(.ram) }
    INCLUDE banks.ld
    /DISCARD/ : { *(.MIPS.abiflags) *(.reginfo) *(.pdr) *(.comment) *(.gnu.attributes) *(.mdebug*) }
}
