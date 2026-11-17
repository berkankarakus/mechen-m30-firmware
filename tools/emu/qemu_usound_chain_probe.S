/* Execute the real usound producer and ring consumer in one guest. */
	.set	mips32
	.set	noreorder
	.set	noat

	.section .vectors,"ax"
	.globl	general_exception
	.ent	general_exception
general_exception:
	/* The real consumer calls module 0x10 through a break-0 envelope. */
	lui	$k0, 0x8006
	ori	$k0, $k0, 0x4000
	lw	$k1, 0($k0)
	addiu	$k1, $k1, 1
	sw	$k1, 0($k0)
	lw	$k1, 4($k0)
	addu	$k1, $k1, $a2
	sw	$k1, 4($k0)
	sw	$v1, 8($k0)
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

	/* Guest RAM exception vector for the consumer's real callback. */
	lui	$k0, 0x8001
	ori	$k0, $k0, 0x1000
	mtc0	$k0, $15, 1
	nop
	mfc0	$k1, $12
	li	$t1, 0xffbfffff
	and	$k1, $k1, $t1
	mtc0	$k1, $12
	nop

	/* Producer state at 0x80060000; it writes the shared 0x6e40 ring. */	lui	$t0, 0x8006
	sw	$zero, 0($t0)
	sw	$zero, 4($t0)
	sb	$zero, 0x10($t0)
	sb	$zero, 0x24($t0)
	sb	$zero, 0x28($t0)
	sw	$zero, 0x18($t0)
	sw	$zero, 0x20($t0)
	li	$t1, 16
	sb	$t1, 8($t0)
	sb	$zero, 9($t0)
	jalx	0x80050dc4
	 nop

	/* Producer must publish exactly the 16 bytes consumed below. */	lw	$t1, 0x18($t0)
	li	$t2, 16
	bne	$t1, $t2, fail_producer
	 nop
	lw	$t1, 0x20($t0)
	bne	$t1, $t2, fail_producer
	 nop

	/* Consumer state at 0x80063000 reads the producer's shared ring. */	lui	$t0, 0x8006
	ori	$t0, $t0, 0x3000
	sw	$t2, 0($t0)
	sw	$zero, 4($t0)
	sw	$zero, 8($t0)
	sw	$zero, 0xc($t0)
	lui	$t1, 0x8006
	ori	$t1, $t1, 0x4000
	sw	$zero, 0($t1)
	sw	$zero, 4($t1)
	sw	$zero, 8($t1)
	/* a1 is the destination passed through the real callback envelope. */	lui	$a1, 0x8006
	ori	$a1, $a1, 0x5000
	/* a2 is the consumer's available/read state descriptor. */	or	$a2, $t0, $zero
	jalx	0x80051654
	 nop

	li	$t2, 16
	bne	$v0, $t2, fail_consumer
	 nop
	lw	$t1, 0($t0)
	bnez	$t1, fail_consumer
	 nop
	lw	$t1, 8($t0)
	bne	$t1, $t2, fail_consumer
	 nop
	lui	$t0, 0x8006
	ori	$t0, $t0, 0x4000
	lw	$t1, 0($t0)
	li	$t2, 1
	bne	$t1, $t2, fail_callback_count
	 nop
	lw	$t1, 8($t0)
	li	$t2, 0x10
	bne	$t1, $t2, fail_callback_module_id
	 nop

	la	$a0, pass_text
	jal	puts
	 nop
	b	halt
	 nop

fail_producer:
	la	$a0, producer_text
	b	fail
	 nop
fail_consumer:
	la	$a0, consumer_text
	b	fail
	 nop
fail_callback_count:
	la	$a0, callback_text
	b	fail
	 nop

fail_callback_module_id:
	la	$a0, module_id_text

fail:
	jal	puts
	 nop

halt:
	1:
	 b	1b
	 nop
	.end	_start

	.text
	.ent	puts
puts:
	addu	$t0, $a0, $zero
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
	.asciz	"REAL USOUND CHAIN PASS producer=16 consumer=16 module_call=1 module=0x10\r\n"
producer_text:
	.asciz	"REAL USOUND CHAIN FAIL producer\r\n"
consumer_text:
	.asciz	"REAL USOUND CHAIN FAIL consumer\r\n"
callback_text:
	.asciz	"REAL USOUND CHAIN FAIL callback\r\n"
module_id_text:
	.asciz	"REAL USOUND CHAIN FAIL module-id\r\n"

	.section .driver,"ax"
	.align	2
	.incbin	"usound_code.bin"
