/* MIPS32 entry and synthetic scroll state for the real MIPS16 bank probe. */
	.set	mips32
	.set	noreorder
	.text
	.globl	_start
	.ent	_start
_start:
	/* Match RunScrollProbe.java's deterministic stack origin. */
	lui	$sp, 0x1000
	ori	$sp, $sp, 0x3000
	/* a0 = event/style word, a1 = two-word scroll context */
	ori	$a0, $zero, 0
	lui	$a1, 0x1000
	ori	$a1, $a1, 0x2200
	/* Enter the MIPS32 trampoline; it performs the ISA-changing JALX. */
	lui	$t9, 0x40d5
	ori	$t9, $t9, 0x0000
	jalr	$t9
	nop
	/* Preserve the complete firmware short status for the host-side check. */
	lui	$t0, 0x1000
	ori	$t0, $t0, 0x3ff4
	sw	$v0, 0($t0)
	/* Write the little-endian status word, then exit successfully. */
	ori	$a0, $zero, 1
	lui	$a1, 0x1000
	ori	$a1, $a1, 0x3ff4
	ori	$a2, $zero, 4
	ori	$v0, $zero, 4004
	syscall
	nop
	ori	$a0, $zero, 0
	ori	$v0, $zero, 4001
	syscall
	nop
	.end	_start

	/*
	 * A MIPS32 jalr does not change ISA mode in QEMU.  The real bank entry is
	 * MIPS16, so use the architectural JALX instruction from the same 256 MiB
	 * region and preserve the caller's return address separately.  This is a
	 * probe trampoline, not a firmware patch.
	 */
	.section .trampoline,"ax"
	.set	mips32
	.set	noreorder
	.globl	mips32_trampoline
	.ent	mips32_trampoline
mips32_trampoline:
	/* Do not borrow a callee-saved register: the bank uses s0 as state. */
	lui	$t0, 0x1000
	ori	$t0, $t0, 0x3ff0
	sw	$ra, 0($t0)
	/* Match the isolated Ghidra harness: the bank receives a null t9. */
	addu	$t9, $zero, $zero
	jalx	0x40d54f2c
	nop
	lw	$t0, 0($t0)
	jr	$t0
	nop
	.end	mips32_trampoline

	.section .ram,"aw"
	.org	0x0000
	/* state at 0x10002000; entries pointer is at +0x0c */
	.space	6
	.byte	3, 0, 0, 0
	.space	3
	.word	0x10002100
	.space	0x10
	/* Ghidra's zero-page read chain: state+0x94 resolves to zero. */
	.org	0x94
	.word	0x10003fdc
	.org	0x100
	/* first 0x18-byte entry: style 0x2005, x=190, y=40 */
	.half	0x2005
	.space	2
	.half	190
	.space	2
	.half	40
	.space	0x12
	/* context at 0x10002200: state pointer, status byte */
	.org	0x200
	.word	0x10002000
	.word	3
	.space	0x100

	.section .trampoline_ram,"aw"
	.word	0

	.section .probe_result,"aw"
	.word	0

	.section .probe_stack,"aw"
	/*
	 * Ghidra's harness maps a readable zero page. Linux-user QEMU refuses to
	 * map guest address zero, so seed the equivalent nullable chain in the
	 * deterministic stack instead; the renderer still observes zero data.
	 */
	.space	0x7b0
	.word	0x10002088
	.space	0x1000 - 0x7b4

	.section .probe_zero_shim,"aw"
	.word	0
	.space	0x0c
	.word	0x10003fdc
