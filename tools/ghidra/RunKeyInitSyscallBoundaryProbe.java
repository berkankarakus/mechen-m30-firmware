// Capture the key driver's caller-side arguments at its fixed-ROM syscall trap.
import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.emulate.BreakCallBack;
import ghidra.pcode.pcoderaw.PcodeOpRaw;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import java.io.ByteArrayInputStream;
import java.math.BigInteger;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;

public class RunKeyInitSyscallBoundaryProbe extends GhidraScript {
    private static final long ENTRY = 0xbfc10008L;
    private static final long SYSCALL_TRAP = 0xbfc10004L;
    private static final long STOP = 0x700300L;
    private static final long BSS = 0x9fc14328L;
    private static final long MMIO_9 = 0xc0090000L;
    private static final long MMIO_B = 0xc00b0000L;
    private static final long STACK = 0x10003f00L;
    private static final String EXPECTED_SHA256 =
        "858d56ff19106fccb75e35552c9cecca99dce0579c7daac5dce376d742f67ba1";

    private final List<String> calls = new ArrayList<>();

    private Address address(long value) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value);
    }

    private void require(boolean condition, String message) throws Exception {
        if (!condition) {
            throw new Exception(message);
        }
    }

    private long register(EmulatorHelper emulator, String name) throws Exception {
        return emulator.readRegister(name).longValue() & 0xffffffffL;
    }

    private long word(EmulatorHelper emulator, long location) throws Exception {
        byte[] bytes = emulator.readMemory(address(location), 4);
        return (bytes[0] & 0xffL)
            | ((bytes[1] & 0xffL) << 8)
            | ((bytes[2] & 0xffL) << 16)
            | ((bytes[3] & 0xffL) << 24);
    }

    private void addBlock(
            Memory memory,
            long start,
            int size,
            String name,
            boolean executable
    ) throws Exception {
        MemoryBlock block = memory.getBlock(address(start));
        if (block == null) {
            block = memory.createInitializedBlock(
                name,
                address(start),
                new ByteArrayInputStream(new byte[size]),
                size,
                monitor,
                false
            );
        }
        block.setRead(true);
        block.setWrite(true);
        block.setExecute(executable);
    }

    private void returnFromSyntheticRom(EmulatorHelper emulator) throws Exception {
        long returnAddress = register(emulator, "ra");
        require((returnAddress & 1L) == 1L,
            String.format("syscall return address lacks MIPS16 tag: 0x%08x", returnAddress));
        emulator.writeRegister("v0", 0);
        emulator.writeRegister("pc", returnAddress & ~1L);
    }

    private void invokeInit(EmulatorHelper emulator) throws Exception {
        emulator.writeRegister("sp", STACK);
        emulator.writeRegister("ra", STOP | 1L);
        emulator.writeRegister("a0", 0);
        emulator.writeRegister("a1", 0);
        emulator.writeRegister("a2", 0);
        emulator.writeRegister("a3", 0);
        emulator.writeRegister("s0", 0);
        emulator.writeRegister("s1", 0);
        emulator.writeRegister("pc", ENTRY);

        for (int step = 0; step < 500; step++) {
            long pc = register(emulator, "pc") & ~1L;
            if (pc == STOP) {
                return;
            }

            if (pc == SYSCALL_TRAP) {
                long module = register(emulator, "v1");
                long argument0 = register(emulator, "a0");
                long argument1 = register(emulator, "a1");
                long argument2 = register(emulator, "a2");
                long argument3 = register(emulator, "a3");
                long payloadWord = argument1 >= STACK - 0x100 && argument1 < STACK + 0x100
                    ? word(emulator, argument1)
                    : 0;
                calls.add(String.format(
                    "v1_at_trap=0x%08x args=(0x%x,0x%08x,0x%x,0x%x) payload_word=0x%08x",
                    module,
                    argument0,
                    argument1,
                    argument2,
                    argument3,
                    payloadWord
                ));
                returnFromSyntheticRom(emulator);
                continue;
            }

            if (!emulator.step(monitor)) {
                throw new Exception(String.format(
                    "key init stopped at 0x%08x: %s",
                    pc,
                    emulator.getLastError()
                ));
            }
        }

        throw new Exception("key init did not return within 500 instructions");
    }

    @Override
    public void run() throws Exception {
        require(getScriptArgs().length == 1,
            "usage: RunKeyInitSyscallBoundaryProbe.java KEY.DRV");
        byte[] driver = Files.readAllBytes(Paths.get(getScriptArgs()[0]));
        String sha256 = HexFormat.of().formatHex(
            MessageDigest.getInstance("SHA-256").digest(driver)
        );
        require(EXPECTED_SHA256.equals(sha256), "key.drv SHA-256 mismatch: " + sha256);

        Memory memory = currentProgram.getMemory();
        require(memory.getBlock(address(ENTRY)) != null, "key.drv code is not mapped");
        addBlock(memory, BSS, 0xd6, "key_init_boundary_bss", false);
        addBlock(memory, MMIO_9, 0x20, "key_init_boundary_mmio_9", false);
        addBlock(memory, MMIO_B, 0x20, "key_init_boundary_mmio_b", false);
        addBlock(memory, STACK, 0x100, "key_init_boundary_stack", false);

        EmulatorHelper emulator = new EmulatorHelper(currentProgram);
        try {
            emulator.registerCallOtherCallback("setISAMode", new BreakCallBack() {
                @Override
                public boolean pcodeCallback(PcodeOpRaw op) {
                    return true;
                }
            });
            emulator.setContextRegister(currentProgram.getRegister("ISA_MODE"), BigInteger.ONE);
            invokeInit(emulator);

            require(calls.size() == 2, "expected two fixed-ROM calls, observed " + calls.size());
            require(calls.get(0).contains("args=(0x6,0x00000000,0x0,0x1a)"),
                "first initialization call arguments changed: " + calls.get(0));
            require(calls.get(1).contains("args=(0x6,0x10003ee8,0x0,0x18)"),
                "second initialization call arguments changed: " + calls.get(1));
            require(calls.get(1).endsWith("payload_word=0x20000a00"),
                "second initialization payload changed: " + calls.get(1));

            for (int index = 0; index < calls.size(); index++) {
                println("KEY INIT ROM CALL " + index + " " + calls.get(index));
            }
            println("KEY INIT SYSCALL BOUNDARY PASS calls=2 synthetic_return=0");
        }
        finally {
            emulator.dispose();
        }
    }
}
