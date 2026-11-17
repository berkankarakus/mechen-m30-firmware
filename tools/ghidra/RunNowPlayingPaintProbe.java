// Execute the real music.ap now-playing paint entry with RAM-backed state and
// intercept its UI dispatcher. This is a trace-only p-code probe: it does not
// patch an AP or generate a flashable image.
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
import java.util.List;

public class RunNowPlayingPaintProbe extends GhidraScript {
    private static final long ENTRY = 0x40154ddcL;
    private static final long STOP = 0x700300L;
    private static final long STUBS = 0x700000L;
    private static final long RAM = 0x10000000L;
    private static final long FLAGS = RAM + 0x100;
    private static final long STACK = RAM + 0x3000;

    private Address addr(long value) throws Exception {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value);
    }

    private void putWord(Memory memory, long address, long value) throws Exception {
        memory.setBytes(addr(address), new byte[] {
            (byte)value, (byte)(value >>> 8), (byte)(value >>> 16), (byte)(value >>> 24)
        });
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
            "now_playing_paint_probe_ram", addr(RAM),
            new ByteArrayInputStream(new byte[0x4000]), 0x4000, monitor, false);
        block.setRead(true);
        block.setWrite(true);
        block.setExecute(true);
    }

    private String hex(long value) {
        return String.format("0x%08x", value & 0xffffffffL);
    }

    private String dispatchSummary(EmulatorHelper emu) throws Exception {
        long a0 = emu.readRegister("a0").longValue() & 0xffffffffL;
        long a1 = emu.readRegister("a1").longValue() & 0xffffffffL;
        long a2 = emu.readRegister("a2").longValue() & 0xffffffffL;
        long a3 = emu.readRegister("a3").longValue() & 0xffffffffL;
        return String.format("a0=%s a1=%s a2=%s a3=%s", hex(a0), hex(a1), hex(a2), hex(a3));
    }

    @Override
    public void run() throws Exception {
        if (getScriptArgs().length != 1) {
            throw new Exception("usage: RunNowPlayingPaintProbe.java STUBS.BIN");
        }
        Memory memory = currentProgram.getMemory();
        byte[] stubs = Files.readAllBytes(Paths.get(getScriptArgs()[0]));
        MemoryBlock stubBlock = memory.createInitializedBlock(
            "now_playing_paint_probe_stubs", addr(STUBS),
            new ByteArrayInputStream(stubs), stubs.length, monitor, false);
        stubBlock.setRead(true); stubBlock.setWrite(false); stubBlock.setExecute(true);
        ramBlock(memory);
        memory.setBytes(addr(RAM), new byte[0x4000]);

        // Only two literal-pool values are redirected. The dispatcher is the
        // known MIPS16 stub at 0x700001; the state flags are a zeroed RAM word.
        expectWord(memory, 0x40155324L, 0xbfc16405L);
        expectWord(memory, 0x40155334L, 0x9fc15418L);
        putWord(memory, 0x40155324L, STUBS + 1);
        putWord(memory, 0x40155334L, FLAGS);
        // Bit 0 is the initial-paint request: it draws the three fixed bands,
        // then the default artwork control through the common state path.
        putWord(memory, FLAGS, 1);

        EmulatorHelper emu = new EmulatorHelper(currentProgram);
        List<String> events = new ArrayList<>();
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
                    if (events.size() != 7) {
                        throw new Exception("paint dispatch count=" + events.size()
                            + " expected=7 events=" + events);
                    }
                    println("NOW PLAYING PAINT DYNAMIC PASS steps=" + steps
                        + " dispatches=" + events.size());
                    for (String event : events) println("  " + event);
                    return;
                }
                if (base == STUBS) {
                    events.add(dispatchSummary(emu));
                    emu.writeRegister("v0", 1);
                    long ra = emu.readRegister("ra").longValue() & 0xffffffffL;
                    emu.writeRegister("pc", ra & ~1L);
                    continue;
                }
                if (!emu.step(monitor)) {
                    throw new Exception("emulator stopped at " + hex(pc) + ": " + emu.getLastError());
                }
            }
            throw new Exception("step limit reached at "
                + hex(emu.readRegister("pc").longValue()));
        } finally {
            emu.dispose();
        }
    }
}
