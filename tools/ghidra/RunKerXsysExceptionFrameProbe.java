// Execute the real MIPS16 frame formatter with a synthetic ROM callback.
import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.emulate.BreakCallBack;
import ghidra.pcode.pcoderaw.PcodeOpRaw;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import java.io.ByteArrayInputStream;
import java.math.BigInteger;
import java.util.ArrayList;
import java.util.List;

public class RunKerXsysExceptionFrameProbe extends GhidraScript {
    private static final long ENTRY = 0xbfc344f4L;
    private static final long CALLBACK_SLOT = 0xbfc34558L;
    private static final long CALLBACK = 0x00070000L;
    private static final long CALLBACK_TAGGED = CALLBACK | 1L;
    private static final long FRAME = 0x00013dccL;
    private static final long STATUS = 0x9fc1aa5cL;
    private static final long WATCHDOG = 0xc012001cL;
    private static final long STACK_BASE = 0x9fc1b000L;
    private static final int STACK_SIZE = 0x2000;
    private static final long[] WORDS = {
        0x11223344L, 0x55667788L, 0x99aabbccL, 0xddeeff00L, 0x13579bdfL
    };

    private Address addr(long value) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value);
    }

    private void require(boolean condition, String message) throws Exception {
        if (!condition) throw new Exception(message);
    }

    private void putWord(Memory memory, long at, long value) throws Exception {
        memory.setBytes(addr(at), new byte[] {
            (byte)value, (byte)(value >>> 8), (byte)(value >>> 16), (byte)(value >>> 24)
        });
    }

    private long reg(EmulatorHelper emu, String name) throws Exception {
        return emu.readRegister(name).longValue() & 0xffffffffL;
    }

    private long readWord(EmulatorHelper emu, long at) throws Exception {
        byte[] bytes = emu.readMemory(addr(at), 4);
        return (bytes[0] & 0xffL) | ((bytes[1] & 0xffL) << 8)
            | ((bytes[2] & 0xffL) << 16) | ((bytes[3] & 0xffL) << 24);
    }

    private MemoryBlock mapRam(Memory memory, String name, long base, int size)
            throws Exception {
        MemoryBlock block = memory.createInitializedBlock(name, addr(base),
            new ByteArrayInputStream(new byte[size]), size, monitor, false);
        block.setRead(true);
        block.setWrite(true);
        return block;
    }

    private void runProfile(Memory memory, long status, long expectedWatchdog)
            throws Exception {
        for (int i = 0; i < WORDS.length; i++) putWord(memory, FRAME + i * 4L, WORDS[i]);
        putWord(memory, 0x00013dc8L, 0xcafebabeL);
        putWord(memory, 0x00013de0L, 0x0badf00dL);
        putWord(memory, STATUS, status);
        putWord(memory, WATCHDOG, 0);

        EmulatorHelper emu = new EmulatorHelper(currentProgram);
        try {
            emu.registerCallOtherCallback("setISAMode", new BreakCallBack() {
                @Override public boolean pcodeCallback(PcodeOpRaw op) { return true; }
            });
            emu.writeRegister("sp", STACK_BASE + 0x1000);
            emu.writeRegister("ra", 0x80001235L);
            emu.writeRegister("pc", ENTRY);

            List<Long> observed = new ArrayList<>();
            boolean watchdogWrite = false;
            for (int step = 0; step < 256; step++) {
                long pc = reg(emu, "pc");
                if (pc == CALLBACK) {
                    observed.add(reg(emu, "a1"));
                    require(reg(emu, "a2") == 2, "unexpected frame formatter width argument");
                    require(reg(emu, "a0") == 0xbfc3454cL,
                        "unexpected frame formatter descriptor argument");
                }
                if (!emu.step(monitor)) {
                    throw new Exception(String.format("stopped at 0x%08x: %s",
                        pc, emu.getLastError()));
                }
                if (observed.size() == WORDS.length
                        && readWord(emu, WATCHDOG) == expectedWatchdog) {
                    watchdogWrite = true;
                    break;
                }
            }

            require(observed.size() == WORDS.length, "did not observe five frame formatter calls");
            for (int i = 0; i < WORDS.length; i++) {
                require(observed.get(i) == WORDS[i], String.format(
                    "frame word %d mismatch: expected 0x%08x got 0x%08x",
                    i, WORDS[i], observed.get(i)));
            }
            require(watchdogWrite, String.format(
                "expected watchdog write 0x%08x, observed 0x%08x",
                expectedWatchdog, readWord(emu, WATCHDOG)));
            require(readWord(emu, 0x00013dc8L) == 0xcafebabeL,
                "pre-frame canary changed");
            require(readWord(emu, 0x00013de0L) == 0x0badf00dL,
                "post-frame canary changed");
            println(String.format(
                "KER XSYS EXCEPTION FRAME PROFILE PASS state=0x%08x frame-words=%d watchdog-write=0x%02x",
                status, observed.size(), expectedWatchdog));
        }
        finally {
            emu.dispose();
        }
    }

    @Override
    public void run() throws Exception {
        require(getScriptArgs().length == 1, "usage: RunKerXsysExceptionFrameProbe.java XSYS");
        byte[] input = java.nio.file.Files.readAllBytes(
            java.nio.file.Paths.get(getScriptArgs()[0]));
        require(input.length == 0x800, "unexpected ker_xsys.bin size");
        Memory memory = currentProgram.getMemory();
        MemoryBlock xsys = memory.getBlock(addr(ENTRY));
        require(xsys != null, "ker_xsys segment is not mapped");
        xsys.setWrite(true);

        mapRam(memory, "exception_frame_probe_ram", 0x00013d00L, 0x100);
        mapRam(memory, "exception_frame_probe_stack", STACK_BASE, STACK_SIZE);
        mapRam(memory, "exception_frame_probe_state", 0x9fc1aa00L, 0x100);
        mapRam(memory, "watchdog_mmio_probe", 0xc0120000L, 0x100);
        MemoryBlock callback = mapRam(memory, "synthetic_rom_callback", CALLBACK, 2);
        memory.setBytes(addr(CALLBACK), new byte[] {(byte)0xa0, (byte)0xe8}); // jrc ra
        callback.setExecute(true);
        Register isa = currentProgram.getProgramContext().getRegister("ISA_MODE");
        currentProgram.getProgramContext().setValue(isa, addr(CALLBACK), addr(CALLBACK + 1),
            BigInteger.ONE);
        require(disassemble(addr(ENTRY)), "could not disassemble MIPS16 frame function");
        require(createFunction(addr(ENTRY), null) != null,
            "could not create MIPS16 frame function");
        require(disassemble(addr(CALLBACK)), "could not disassemble synthetic callback");

        putWord(memory, CALLBACK_SLOT, CALLBACK_TAGGED);
        runProfile(memory, 0, 0x5d);
        runProfile(memory, 2, 0x69);
        println(String.format(
            "KER XSYS EXCEPTION FRAME P-CODE PASS entry=0x%08x frame=0x%08x profiles=2 callback=0x%08x synthetic-rom-callback=1",
            ENTRY, FRAME, CALLBACK_TAGGED));
    }
}
