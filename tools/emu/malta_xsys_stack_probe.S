.set noreorder
.set noat
.set mips32r2

.macro UART_PUTC value
    # Malta CBUS 16550 uses regshift=3: LSR is data base + (5 << 3).
    lui     $t0, 0xbf00
    ori     $t0, $t0, 0x0928
.Luart_ready\@:
    lbu     $t2, 0($t0)
    andi    $t2, $t2, 0x20
    beqz    $t2, .Luart_ready\@
    nop
    lui     $t0, 0xbf00
    ori     $t0, $t0, 0x0900
    addiu   $t1, $zero, \value
    sb      $t1, 0($t0)
.endm

.section .reset, "ax", @progbits
.globl _start
_start:
    j       probe_main
    nop

.section .text, "ax", @progbits
.globl probe_main
probe_main:
    # Below threshold: the extracted code must switch stacks and preserve SP.
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5b6d # 0x8001a493, extracted stack counter
    sb      $zero, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5b6b # 0x8001a495, extracted stack index
    sb      $zero, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x66d0 # 0x80019930, extracted ROM-side counter
    sb      $zero, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5760 # 0x8001a8a0, redirected stack-top pointer
    lui     $t1, 0x8001
    ori     $t1, $t1, 0xc000
    sw      $t1, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x4004 # 0x8001bffc, alternate-stack save slot
    lui     $t1, 0xcccc
    ori     $t1, $t1, 0xcccc
    sw      $t1, 0($t0)
    lui     $sp, 0x8001
    ori     $sp, $sp, 0x1fff
    move    $s0, $sp
    jal     0xbfc340a4
    nop

    lui     $t0, 0x8001
    ori     $t0, $t0, 0xbffc
    bne     $sp, $t0, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x4004
    lw      $t1, 0($t0)
    bne     $t1, $s0, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5760
    lw      $t1, 0($t0)
    lui     $t2, 0x8001
    ori     $t2, $t2, 0xbf48
    bne     $t1, $t2, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5b6d
    lbu     $t1, 0($t0)
    addiu   $t2, $zero, 1
    bne     $t1, $t2, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x66d0
    lbu     $t1, 0($t0)
    addiu   $t2, $zero, 1
    bne     $t1, $t2, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5b6b # index byte 0x8001a495 remains zero
    lbu     $t1, 0($t0)
    bnez    $t1, probe_fail
    nop

    # Equality is deliberately an alternate-stack case (strict unsigned test).
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5b6d
    sb      $zero, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5b6b
    sb      $zero, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x66d0
    sb      $zero, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5760
    lui     $t1, 0x8001
    ori     $t1, $t1, 0xc000
    sw      $t1, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x4004
    lui     $t1, 0xcccc
    ori     $t1, $t1, 0xcccc
    sw      $t1, 0($t0)
    lui     $sp, 0x8001
    ori     $sp, $sp, 0x2000
    move    $s0, $sp
    jal     0xbfc340a4
    nop
    lui     $t0, 0x8001
    ori     $t0, $t0, 0xbffc
    bne     $sp, $t0, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x4004
    lw      $t1, 0($t0)
    bne     $t1, $s0, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5760
    lw      $t1, 0($t0)
    lui     $t2, 0x8001
    ori     $t2, $t2, 0xbf48
    bne     $t1, $t2, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5b6d
    lbu     $t1, 0($t0)
    addiu   $t2, $zero, 1
    bne     $t1, $t2, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x66d0
    lbu     $t1, 0($t0)
    addiu   $t2, $zero, 1
    bne     $t1, $t2, probe_fail
    nop

    # Above threshold: direct path leaves stack state and its canary untouched.
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5b6d
    sb      $zero, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5b6b
    sb      $zero, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x66d0
    sb      $zero, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5760
    lui     $t1, 0x8001
    ori     $t1, $t1, 0xc000
    sw      $t1, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x4004
    lui     $t1, 0xcccc
    ori     $t1, $t1, 0xcccc
    sw      $t1, 0($t0)
    lui     $sp, 0x8001
    ori     $sp, $sp, 0x2001
    move    $s0, $sp
    jal     0xbfc340a4
    nop
    bne     $sp, $s0, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x4004
    lw      $t1, 0($t0)
    lui     $t2, 0xcccc
    ori     $t2, $t2, 0xcccc
    bne     $t1, $t2, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5760
    lw      $t1, 0($t0)
    lui     $t2, 0x8001
    ori     $t2, $t2, 0xc000
    bne     $t1, $t2, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5b6d
    lbu     $t1, 0($t0)
    bnez    $t1, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x66d0
    lbu     $t1, 0($t0)
    bnez    $t1, probe_fail
    nop

    # Index one must read table[1], whose limit deliberately differs from [0].
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5b6d
    sb      $zero, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x66d0
    sb      $zero, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5760
    lui     $t1, 0x8001
    ori     $t1, $t1, 0xc000
    sw      $t1, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x4004
    lui     $t1, 0xcccc
    ori     $t1, $t1, 0xcccc
    sw      $t1, 0($t0)
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5b6b
    addiu   $t1, $zero, 1
    sb      $t1, 0($t0)
    lui     $sp, 0x8001
    ori     $sp, $sp, 0x1000
    move    $s0, $sp
    jal     0xbfc340a4
    nop
    bne     $sp, $s0, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x4004
    lw      $t1, 0($t0)
    lui     $t2, 0xcccc
    ori     $t2, $t2, 0xcccc
    bne     $t1, $t2, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5760
    lw      $t1, 0($t0)
    lui     $t2, 0x8001
    ori     $t2, $t2, 0xc000
    bne     $t1, $t2, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5b6d
    lbu     $t1, 0($t0)
    bnez    $t1, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x66d0
    lbu     $t1, 0($t0)
    bnez    $t1, probe_fail
    nop
    lui     $t0, 0x8002
    addiu   $t0, $t0, -0x5b6b
    lbu     $t1, 0($t0)
    addiu   $t2, $zero, 1
    bne     $t1, $t2, probe_fail
    nop

    UART_PUTC 0x50
    UART_PUTC 0x41
    UART_PUTC 0x53
    UART_PUTC 0x53
    j       probe_halt
    nop

probe_fail:
    UART_PUTC 0x46
    UART_PUTC 0x41
    UART_PUTC 0x49
    UART_PUTC 0x4c
probe_halt:
    j       probe_halt
    nop

.section .boundary, "ax", @progbits
.globl probe_rom_boundary
probe_rom_boundary:
    jr      $ra
    nop
