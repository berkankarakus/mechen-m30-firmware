/* MIPS32 entry and synthetic scroll state for the real MIPS16 bank probe. */
	.set	mips32
	.set	noreorder
	.text
	.globl	_start
	.ent	_start
_start:
	addiu	$sp, $sp, -16
	/* a0 = event/style word, a1 = two-word scroll context */
	ori	$a0, $zero, 0
	lui	$a1, 0x1000
	ori	$a1, $a1, 0x2200
	lui	$t9, 0x40d5
	ori	$t9, $t9, 0x4f2d
	jalr	$t9
	nop
	/* Exit with the firmware short status in the process exit code. */
	andi	$a0, $v0, 0xffff
	ori	$v0, $zero, 4001
	syscall
	nop
	.end	_start

	.section .ram,"aw"
	.org	0x0000
	/* state at 0x10002000; entries pointer is at +0x0c */
	.space	6
	.byte	3, 0, 0, 0
	.space	3
	.word	0x10002100
	.space	0x10
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
