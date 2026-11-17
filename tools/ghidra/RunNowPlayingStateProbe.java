// Execute selected real music.ap now-playing state branches with temporary
// RAM-backed state and a traced UI dispatcher. This is a trace-only probe.
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
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class RunNowPlayingStateProbe extends GhidraScript {
    private static final long ENTRY = 0x40154ddcL;
    private static final long STOP = 0x700300L;
    private static final long STUBS = 0x700000L;
    private static final long RAM = 0x10000000L;
    private static final long FLAGS = RAM + 0x100;
    private static final long UI_STATE = RAM + 0x200;
    private static final long PLAY_STATE = RAM + 0x300;
    private static final long STACK = RAM + 0x3000;

    private Address addr(long value) throws Exception {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value);
    }

    private void putWord(Memory memory, long address, long value) throws Exception {
        memory.setBytes(addr(address), new byte[] {
            (byte)value, (byte)(value >>> 8), (byte)(value >>> 16), (byte)(value >>> 24)
        });
    }

    private void putHalf(Memory memory, long address, int value) throws Exception {
        memory.setBytes(addr(address), new byte[] {(byte)value, (byte)(value >>> 8)});
    }

    private void putByte(Memory memory, long address, int value) throws Exception {
        memory.setBytes(addr(address), new byte[] {(byte)value});
    }

    private void expectWord(Memory memory, long address, long expected) throws Exception {
        byte[] b = new byte[4];
        memory.getBytes(addr(address), b);
        long actual = (b[0] & 0xffL) | ((b[1] & 0xffL) << 8)
            | ((b[2] & 0xffL) << 16) | ((b[3] & 0xffL) << 24);
        if (actual != (expected & 0xffffffffL)) {
            throw new Exception(String.format("literal 0x%08x: expected 0x%08x, got 0x%08x",
                address, expected, actual));
        }
    }

    private void ramBlock(Memory memory) throws Exception {
        MemoryBlock block = memory.createInitializedBlock(
            "now_playing_state_probe_ram", addr(RAM),
            new ByteArrayInputStream(new byte[0x4000]), 0x4000, monitor, false);
        block.setRead(true); block.setWrite(true); block.setExecute(true);
    }

    private String hex(long value) {
        return String.format("0x%08x", value & 0xffffffffL);
    }

    private int dispatchId(EmulatorHelper emu) throws Exception {
        long a0 = emu.readRegister("a0").longValue() & 0xffffffffL;
        if (a0 < STACK - 0x100 || a0 >= STACK + 0x100) return (int)(a0 & 0xffff);
        byte[] b = emu.readMemory(addr(a0), 2);
        return (b[0] & 0xff) | ((b[1] & 0xff) << 8);
    }

    private String dispatchSummary(EmulatorHelper emu) throws Exception {
        long a0 = emu.readRegister("a0").longValue() & 0xffffffffL;
        long a1 = emu.readRegister("a1").longValue() & 0xffffffffL;
        long a2 = emu.readRegister("a2").longValue() & 0xffffffffL;
        long a3 = emu.readRegister("a3").longValue() & 0xffffffffL;
        return String.format("id=%s a0=%s a1=%s a2=%s a3=%s",
            hex(dispatchId(emu)), hex(a0), hex(a1), hex(a2), hex(a3));
    }

    private int[] expectedIds(String mode) {
        if ("initial".equals(mode)) return new int[] {0x18c3, 0, 0x39e7, 0, 0x18c3, 0, 0x1002};
        if ("metadata".equals(mode)) return new int[] {0x1002, 0x2005};
        if ("transport".equals(mode)) return new int[] {0x1002, 0x1004, 0x1003};
        if ("status-low".equals(mode)) return new int[] {0x1002, 0x1000};
        if ("status-high".equals(mode)) return new int[] {0x1002, 0x1001};
        throw new IllegalArgumentException("unknown mode " + mode);
    }

    private int flagFor(String mode) {
        if ("initial".equals(mode)) return 0x001;
        if ("metadata".equals(mode)) return 0x100;
        if ("transport".equals(mode)) return 0x020;
        if ("status-low".equals(mode)) return 0x200;
        if ("status-high".equals(mode)) return 0x800;
        throw new IllegalArgumentException("unknown mode " + mode);
    }

    private void runCase(Memory memory, String mode, byte[] stubs) throws Exception {
        memory.setBytes(addr(RAM), new byte[0x4000]);
        int flag = flagFor(mode);
        putWord(memory, FLAGS, flag);
        putWord(memory, UI_STATE + 0x19, 0);
        putByte(memory, UI_STATE + 0x0e, 0);
        putByte(memory, PLAY_STATE, 2);
        putByte(memory, PLAY_STATE + 2, 1);

        // Each case runs in the same Ghidra program, so restore the original
        // literal-pool values before applying this case's RAM redirects.
        putWord(memory, 0x40155324L, 0xbfc16405L);
        putWord(memory, 0x40155334L, 0x9fc15418L);
        putWord(memory, 0x4015533cL, 0x9fc156f4L);
        putWord(memory, 0x4015534cL, 0x9fc156ccL);
        putWord(memory, 0x40155340L, 0xbfc16535L);
        expectWord(memory, 0x40155324L, 0xbfc16405L);
        expectWord(memory, 0x40155334L, 0x9fc15418L);
        expectWord(memory, 0x4015533cL, 0x9fc156f4L);
        expectWord(memory, 0x4015534cL, 0x9fc156ccL);
        expectWord(memory, 0x40155340L, 0xbfc16535L);
        putWord(memory, 0x40155324L, STUBS + 1);
        putWord(memory, 0x40155334L, FLAGS);
        putWord(memory, 0x4015533cL, UI_STATE);
        putWord(memory, 0x4015534cL, PLAY_STATE);
        putWord(memory, 0x40155340L, STUBS + 0x21);

        EmulatorHelper emu = new EmulatorHelper(currentProgram);
        List<String> events = new ArrayList<>();
        List<Integer> ids = new ArrayList<>();
        try {
            emu.registerCallOtherCallback("setISAMode", new BreakCallBack() {
                @Override public boolean pcodeCallback(PcodeOpRaw op) { return true; }
            });
            Register isa = currentProgram.getRegister("ISA_MODE");
            emu.setContextRegister(isa, BigInteger.ONE);
            emu.writeRegister("sp", STACK);
            emu.writeRegister("ra", STOP | 1L);
            emu.writeRegister("a0", FLAGS);
            emu.writeRegister("a1", 0);
            emu.writeRegister("a2", 0);
            emu.writeRegister("a3", 0);
            emu.writeRegister("s1", 0);
            emu.writeRegister("pc", ENTRY);

            for (int steps = 0; steps < 100000; steps++) {
                long pc = emu.readRegister("pc").longValue() & 0xffffffffL;
                long base = pc & ~1L;
                if (base == STOP) {
                    int[] expected = expectedIds(mode);
                    int[] actual = new int[ids.size()];
                    for (int i = 0; i < ids.size(); i++) actual[i] = ids.get(i);
                    if (!Arrays.equals(actual, expected)) {
                        throw new Exception(mode + " IDs=" + Arrays.toString(actual)
                            + " expected=" + Arrays.toString(expected));
                    }
                    println(String.format("NOW PLAYING STATE DYNAMIC PASS mode=%s flag=0x%x steps=%d dispatches=%d",
                        mode, flag, steps, events.size()));
                    for (String event : events) println("  " + event);
                    return;
                }
                if (base == STUBS) {
                    ids.add(dispatchId(emu));
                    events.add(dispatchSummary(emu));
                    emu.writeRegister("v0", 1);
                    long ra = emu.readRegister("ra").longValue() & 0xffffffffL;
                    emu.writeRegister("pc", ra & ~1L);
                    continue;
                }
                if (!emu.step(monitor)) {
                    throw new Exception(mode + " stopped at " + hex(pc) + ": " + emu.getLastError());
                }
            }
            throw new Exception(mode + " exceeded step limit at "
                + hex(emu.readRegister("pc").longValue()));
        } finally {
            emu.dispose();
        }
    }

    @Override
    public void run() throws Exception {
        if (getScriptArgs().length < 1) {
            throw new Exception("usage: RunNowPlayingStateProbe.java STUBS.BIN [mode ...]");
        }
        Memory memory = currentProgram.getMemory();
        byte[] stubs = Files.readAllBytes(Paths.get(getScriptArgs()[0]));
        MemoryBlock stubBlock = memory.createInitializedBlock(
            "now_playing_state_probe_stubs", addr(STUBS),
            new ByteArrayInputStream(stubs), stubs.length, monitor, false);
        stubBlock.setRead(true); stubBlock.setWrite(false); stubBlock.setExecute(true);
        ramBlock(memory);
        List<String> modes = new ArrayList<>();
        if (getScriptArgs().length == 1 || "all".equals(getScriptArgs()[1])) {
            modes.addAll(Arrays.asList("initial", "metadata", "transport", "status-low", "status-high"));
        } else {
            modes.addAll(Arrays.asList(getScriptArgs()).subList(1, getScriptArgs().length));
        }
        for (String mode : modes) runCase(memory, mode, stubs);
    }
}
