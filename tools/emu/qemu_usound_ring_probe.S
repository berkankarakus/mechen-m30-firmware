/* Execute the real usound.drv ring consumer with a relocated state pool. */
	.set	mips32
	.set	noreorder
	.set	noat

	.text
	.globl	_start
	.ent	_start
_start:
	lui	$sp, 0x8004
	ori	$sp, $sp, 0xfff0

	/* First call: consume 16 bytes without wrapping. */	lui	$t0, 0x8006
	ori	$t1, $zero, 16
	sw	$t1, 0($t0)
	sw	$zero, 4($t0)
	sw	$zero, 8($t0)
	sb	$zero, 0xc($t0)
	lui	$a1, 0x8003
	addiu	$a1, $a1, 0x100
	or	$a2, $t0, $zero
	jalx	0x80051654
	 nop
	li	$t1, 16
	bne	$v0, $t1, fail_first
	 nop
	lw	$t1, 0($t0)
	bnez	$t1, fail_first
	 nop
	lw	$t1, 8($t0)

	/* Second call: 32 bytes from read offset 0xff8, forcing two callbacks. */	li	$t2, 32
	sw	$t2, 0($t0)
	li	$t2, 0xff8
	sw	$t2, 8($t0)
	li	$t2, 32
	sw	$t2, 0x20($t0)
	or	$a2, $t0, 0x20
	jalx	0x80051654
	 nop
	li	$t1, 32
	bne	$v0, $t1, fail_wrap
	 nop
	lw	$t1, 0($t0)
	bnez	$t1, fail_wrap
	 nop
	lw	$t1, 8($t0)
	/* The real function resets the pointer to zero after crossing 0x1000. */	li	$t2, 0
	bne	$t1, $t2, fail_wrap
	 nop

	la	$a0, pass_text
	jal	puts
	 nop
	b	halt
	 nop

fail_first:
	la	$a0, first_text
	b	fail
	 nop
fail_wrap:
	la	$a0, wrap_text
fail:
	jal	puts
	 nop

halt:
	1:
	b	1b
	 nop
	.end	_start

	.ent	puts
puts:
	or	$t0, $a0, $zero
putc:
	lui	$t1, 0xbf00
	ori	$t1, $t1, 0x0900
	lbu	$t3, 0($t0)
	beqz	$t3, puts_done
	 nop
	sb	$t3, 0($t1)
	addiu	$t0, $t0, 1
	b	putc
	 nop
puts_done:
	jr	$ra
	 nop
	.end	puts

	/* The recovered callback is MIPS16. It is intentionally no-op here. */
	.section .callback,"ax"
	.set	mips16
	.globl	usound_callback_stub
	.ent	usound_callback_stub
usound_callback_stub:
	jr	$ra
	 nop
	.end	usound_callback_stub
	.set	mips32

	.section .rodata
pass_text:
	.asciz	"REAL USOUND RING PASS consumer=FUN_bfc31654 wrap=1 callbacks=2\r\n"
first_text:
	.asciz	"REAL USOUND RING FAIL first\r\n"
wrap_text:
	.asciz	"REAL USOUND RING FAIL wrap\r\n"

	.section .driver,"ax"
	.align	2
	.incbin	"usound_code.bin"
