/* Execute the real usound.drv MIPS16 callback syscall stub under QEMU. */
	.set	mips32
	.set	noreorder
	.set	noat

	.section .vectors,"ax"
	.globl	general_exception
	.ent	general_exception
general_exception:
	/* The callback is a break-0 syscall.  Return through the interrupted RA,
	 * which is the caller continuation established by JALX/JALRC. */
	lui	$k0, 0x8006
	sw	$a0, 0($k0)
	sw	$a1, 4($k0)
	sw	$a2, 8($k0)
	sw	$a3, 0xc($k0)
	sw	$v1, 0x10($k0)
	li	$k1, 1
	sw	$k1, 0x14($k0)
	mtc0	$ra, $14
	nop
	eret
	nop
	.end	general_exception

	.text
	.globl	_start
	.ent	_start
_start:
	lui	$sp, 0x8004
	ori	$sp, $sp, 0xfff0
	/* Use a RAM-backed general exception vector instead of Malta's PROM. */
	lui	$k0, 0x8001
	mtc0	$k0, $15, 1
	nop
	mfc0	$k1, $12
	li	$t1, 0xffbfffff
	and	$k1, $k1, $t1
	mtc0	$k1, $12
	nop
	lui	$t0, 0x8006
	sw	$zero, 0($t0)
	sw	$zero, 4($t0)
	sw	$zero, 8($t0)
	sw	$zero, 0xc($t0)
	sw	$zero, 0x10($t0)
	sw	$zero, 0x14($t0)

	/* Match the callback ABI used by FUN_bfc31654: buffer, destination,
	 * byte count, and the fourth zero argument. */
	lui	$a0, 0x8003
	ori	$a0, $a0, 0x1111
	lui	$a1, 0x8003
	ori	$a1, $a1, 0x2222
	li	$a2, 0x40
	move	$a3, $zero
	/* The low bit is ISA metadata; JALX takes the aligned entry address. */
	jalx	0x800526a8
	 nop

	lw	$t1, 0x14($t0)
	li	$t2, 1
	bne	$t1, $t2, fail
	 nop
	lw	$t1, 0x10($t0)
	li	$t2, 0x10
	bne	$t1, $t2, fail
	 nop
	lw	$t1, 0($t0)
	li	$t2, 0x80031111
	bne	$t1, $t2, fail
	 nop
	lw	$t1, 4($t0)
	li	$t2, 0x80032222
	bne	$t1, $t2, fail
	 nop
	lw	$t1, 8($t0)
	li	$t2, 0x40
	bne	$t1, $t2, fail
	 nop
	lw	$t1, 0xc($t0)
	bnez	$t1, fail
	 nop

	la	$a0, pass_text
	jal	puts
	 nop
	b	halt
	 nop

fail:
	la	$a0, fail_text
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

	.section .rodata
pass_text:
	.asciz	"REAL USOUND CALLBACK PASS selector=0x10 args=4\r\n"
fail_text:
	.asciz	"REAL USOUND CALLBACK FAIL\r\n"

	.section .driver,"ax"
	.align	2
	.incbin	"usound_code.bin"
