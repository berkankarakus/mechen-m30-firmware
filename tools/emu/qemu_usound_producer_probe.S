/* Execute the real usound.drv software-ring producer under QEMU. */
	.set	mips32
	.set	noreorder
	.set	noat

	.text
	.globl	_start
	.ent	_start
_start:
	lui	$sp, 0x8004
	ori	$sp, $sp, 0xfff0
	lui	$t0, 0x8006

	/* State defaults: status=0, stop=0, format=direct, ready/reset=0.
	 * The real poll callback owns the status handshake.  The guest shim is
	 * deliberately a no-op, so enter with the poll-pending bit clear. */
	sw	$zero, 0($t0)
	sw	$zero, 4($t0)
	sb	$zero, 0x10($t0)
	sb	$zero, 0x24($t0)
	sb	$zero, 0x28($t0)
	sw	$zero, 0x18($t0)
	sw	$zero, 0x20($t0)

	/* First producer call: 16 bytes, linear destination. */
	li	$t1, 0x10
	sb	$t1, 8($t0)
	sb	$zero, 9($t0)
	jalx	0x80050dc4
	 nop
	lw	$t1, 0x18($t0)
	li	$t2, 0x10
	bne	$t1, $t2, fail_linear
	 nop
	lw	$t1, 0x20($t0)
	bne	$t1, $t2, fail_linear
	 nop

	/* Second call: start at 0x6e30 and force a 0x20-byte ring split. */
	li	$t1, 0x6e30
	sw	$t1, 0x18($t0)
	li	$t1, 0x20
	sb	$t1, 8($t0)
	sw	$zero, 0($t0)
	jalx	0x80050dc4
	 nop
	lw	$t1, 0x18($t0)
	li	$t2, 0x10
	bne	$t1, $t2, fail_wrap
	 nop
	lw	$t1, 0x20($t0)
	li	$t2, 0x30
	bne	$t1, $t2, fail_wrap
	 nop
	lbu	$t1, 0x24($t0)
	bnez	$t1, fail_ready
	 nop

	/* Third call: exercise the real 3-to-4 expansion path. */
	sw	$zero, 0x18($t0)
	sw	$zero, 0x20($t0)
	sw	$zero, 0x24($t0)
	li	$t1, 1
	sb	$t1, 0x10($t0)
	li	$t1, 0xaaaaaaab
	sw	$t1, 0x14($t0)
	li	$t1, 0x0c
	sb	$t1, 8($t0)
	sb	$zero, 9($t0)
	sw	$zero, 0($t0)
	jalx	0x80050dc4
	 nop
	lw	$t1, 0x18($t0)
	li	$t2, 0x10
	bne	$t1, $t2, fail_expand_write
	 nop
	lw	$t1, 0x20($t0)
	bne	$t1, $t2, fail_expand_available
	 nop
	lbu	$t1, 0x24($t0)
	bnez	$t1, fail_expand_ready
	 nop

	la	$a0, pass_text
	jal	puts
	 nop
	b	halt
	 nop

fail_linear:
	la	$a0, linear_text
	b	fail
	 nop
fail_wrap:
	la	$a0, wrap_text
	b	fail
	 nop
fail_ready:
	la	$a0, ready_text
	b	fail
	 nop
fail_expand_write:
	la	$a0, expand_write_text
	b	fail
	 nop

fail_expand_available:
	la	$a0, expand_available_text
	b	fail
	 nop
fail_expand_ready:
	la	$a0, expand_ready_text
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

	/* All peripheral/provider callbacks are deliberately no-op MIPS16 stubs. */
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
	.asciz	"REAL USOUND PRODUCER PASS function=FUN_bfc30dc4 linear=1 wrap=1 expand=1\r\n"
linear_text:
	.asciz	"REAL USOUND PRODUCER FAIL linear\r\n"
wrap_text:
	.asciz	"REAL USOUND PRODUCER FAIL wrap\r\n"
ready_text:
	.asciz	"REAL USOUND PRODUCER FAIL ready\r\n"
expand_write_text:
	.asciz	"REAL USOUND PRODUCER FAIL expand-write\r\n"
expand_available_text:
	.asciz	"REAL USOUND PRODUCER FAIL expand-available\r\n"
expand_ready_text:
	.asciz	"REAL USOUND PRODUCER FAIL expand-ready\r\n"

	.section .driver,"ax"
	.align	2
	.incbin	"usound_code.bin"
