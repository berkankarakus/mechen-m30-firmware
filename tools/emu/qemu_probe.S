/* MIPS16 host stubs for the isolated FUN_40d54f2c smoke probe. */
	.set	mips16
	.set	noreorder
	.section .stubs,"ax"

	.org	0x00
	.globl	ui_dispatch_stub
ui_dispatch_stub:
	li	$2, 1
	jr	$31
	nop

	.org	0x20
	.globl	ui_read_status_stub
ui_read_status_stub:
	li	$2, 0
	sb	$2, 0($4)
	sb	$2, 0($5)
	li	$2, 1
	jr	$31
	nop

	.org	0x40
	.globl	ui_set_backlight_stub
ui_set_backlight_stub:
	li	$2, 1
	jr	$31
	nop

	.org	0x60
	.globl	timer_stub
timer_stub:
	li	$2, 0
	jr	$31
	nop

	.org	0x80
	.globl	key_read_begin_stub
key_read_begin_stub:
	li	$2, 1
	jr	$31
	nop

	.org	0xa0
	.globl	key_read_event_stub
key_read_event_stub:
	li	$2, 0x2906
	sh	$2, 0($5)
	li	$2, 1
	jr	$31
	nop

	.org	0xc0
	.globl	key_fallback_stub
key_fallback_stub:
	li	$2, 0
	jr	$31
	nop

	.org	0xe0
	.globl	key_poll_stub
key_poll_stub:
	li	$2, 0
	jr	$31
	nop
