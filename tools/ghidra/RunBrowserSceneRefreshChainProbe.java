// Execute the real resident browser-scene caller and the AP scene loop through
// its refresh callback. Only external service callbacks are RAM-stubbed.
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
import java.util.HashMap;
import java.util.Map;

public class RunBrowserSceneRefreshChainProbe extends GhidraScript {
    private static final long ENTRY = 0xbfc16600L;
    private static final long SCENE = 0x40cd4e00L;
    private static final long STOP = 0x700300L;
    private static final long RAM = 0x10000000L;
    private static final long STATE = RAM + 0x100L;
    private static final long FSEL = RAM + 0x300L;
    private static final long CONTROL = RAM + 0x500L;
    private static final long PATH_INFO = STATE + 8;
    private static final long LIST_STATE = RAM + 0x400L;
    private static final long MODE_VALUE = RAM + 0x480L;
    private static final long ENTRIES = RAM + 0x600L;
    private static final long STUB_BASE = RAM + 0x4000L;
    private static final long STACK = RAM + 0x7000L;
    private static final int ROWS = 7;

    private static final int NOOP = 1;
    private static final int INIT = 2;
    private static final int FIRST_PREDICATE = 3;
    private static final int READY = 4;
    private static final int ROW = 5;
    private static final int FINISH = 6;
    private static final int RESET_STATE = 7;
    private static final int LIST_UPDATE_A = 8;
    private static final int LIST_UPDATE_B = 9;

    private final Map<Long, Integer> stubs = new HashMap<>();
    private int rowCalls;
    private int readyCalls;
    private int initCalls;
    private int resetCalls;
    private int listUpdateACalls;
    private int listUpdateBCalls;
    private long sceneReturn;
    private long sceneContext;

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

    private long word(EmulatorHelper emu, long address) throws Exception {
        byte[] bytes = emu.readMemory(addr(address), 4);
        return (bytes[0] & 0xffL) | ((bytes[1] & 0xffL) << 8)
            | ((bytes[2] & 0xffL) << 16) | ((bytes[3] & 0xffL) << 24);
    }

    private void ramBlock(Memory memory, String name, long base, int size) throws Exception {
        MemoryBlock block = memory.createInitializedBlock(name, addr(base),
            new ByteArrayInputStream(new byte[size]), size, monitor, false);
        block.setRead(true);
        block.setWrite(true);
        block.setExecute(true);
    }

    private long stub(int id) {
        long address = STUB_BASE + id * 0x20L;
        stubs.put(address, id);
        return address | 1L;
    }

    private void redirect(Memory memory, long literal, int id) throws Exception {
        putWord(memory, literal, stub(id));
    }

    private void installStubs(Memory memory) throws Exception {
        redirect(memory, 0x40cd5010L, NOOP);
        redirect(memory, 0x40cd501cL, NOOP);
        redirect(memory, 0x40cd5028L, INIT);
        redirect(memory, 0x40cd502cL, NOOP);
        redirect(memory, 0x40cd503cL, NOOP);
        redirect(memory, 0x40cd5044L, NOOP);
        redirect(memory, 0x40cd504cL, NOOP);
        redirect(memory, 0x40cd5050L, NOOP);
        redirect(memory, 0x40cd5054L, NOOP);
        redirect(memory, 0x40cd5164L, FIRST_PREDICATE);
        redirect(memory, 0x40cd5174L, FINISH);
        putWord(memory, 0x9fc15580L, stub(READY));
        redirect(memory, 0x40cd5180L, NOOP);
        redirect(memory, 0x40cd5200L, RESET_STATE);
        redirect(memory, 0x40cd5210L, LIST_UPDATE_A);
        redirect(memory, 0x40cd5214L, LIST_UPDATE_B);
        putWord(memory, 0x40cd5020L, CONTROL);
        putWord(memory, 0x40cd5024L, ENTRIES);
        putWord(memory, 0x40cd5040L, ENTRIES);
        putWord(memory, 0x40cd52ccL, MODE_VALUE);
        putWord(memory, 0x40cd52d0L, LIST_STATE);
        putWord(memory, 0x40cd52d4L, ENTRIES);
        redirect(memory, 0x40cd52d8L, ROW);
        redirect(memory, 0x40cd52dcL, NOOP);
        redirect(memory, 0x40cd53a0L, NOOP);
    }

    private void handleStub(EmulatorHelper emu, Memory memory, int id) throws Exception {
        long a0 = emu.readRegister("a0").longValue() & 0xffffffffL;
        long a1 = emu.readRegister("a1").longValue() & 0xffffffffL;
        long a2 = emu.readRegister("a2").longValue() & 0xffffffffL;
        long ra = emu.readRegister("ra").longValue() & 0xffffffffL;
        long result = 0;
        if (id == INIT) {
            initCalls++;
            if (a0 != CONTROL || a1 != ENTRIES || a2 != FSEL) {
                throw new Exception(String.format("scene init ABI mismatch a0=0x%08x a1=0x%08x a2=0x%08x", a0, a1, a2));
            }
        } else if (id == FIRST_PREDICATE) {
            result = 0;
        } else if (id == FINISH) {
            result = 1;
        } else if (id == READY) {
            readyCalls++;
            result = readyCalls == 1 ? 0xffff8014L : 1L;
        } else if (id == ROW) {
            int expectedIndex = rowCalls;
            if (a0 != ENTRIES + expectedIndex * 0xcL || a1 != LIST_STATE
                || a2 != expectedIndex || expectedIndex >= ROWS) {
                throw new Exception(String.format(
                    "refresh row ABI mismatch call=%d a0=0x%08x a1=0x%08x a2=0x%08x control+8=%d control+10=%d list+2=%d control+0x14=%d ready=%d init=%d reset=%d updateA=%d updateB=%d",
                    rowCalls, a0, a1, a2, word(emu, CONTROL + 8) & 0xffffL,
                    word(emu, CONTROL + 10) & 0xffffL, word(emu, LIST_STATE + 2) & 0xffffL,
                    word(emu, CONTROL + 0x14) & 0xffL, readyCalls, initCalls, resetCalls,
                    listUpdateACalls, listUpdateBCalls));
            }
            rowCalls++;
            result = 1;
        } else if (id == RESET_STATE) {
            resetCalls++;
            if (a0 != 0x9fc1561cL || a1 != CONTROL || a2 != 0x18L) {
                throw new Exception(String.format(
                    "state-init ABI mismatch a0=0x%08x a1=0x%08x a2=0x%08x", a0, a1, a2));
            }
            // The real service copies/initializes the 0x18-byte list state;
            // seed a bounded seven-row window in its synthetic replacement.
            putHalf(memory, a1 + 8, 1);
            putHalf(memory, a1 + 10, ROWS);
        } else if (id == LIST_UPDATE_A) {
            listUpdateACalls++;
        } else if (id == LIST_UPDATE_B) {
            listUpdateBCalls++;
        }
        emu.writeRegister("v0", result);
        emu.writeRegister("pc", ra & ~1L);
    }

    @Override
    public void run() throws Exception {
        Memory memory = currentProgram.getMemory();
        ramBlock(memory, "browser_scene_chain_ram", RAM, 0x8000);
        ramBlock(memory, "browser_scene_chain_guest_ram", 0x9fc10000L, 0x30000);
        putWord(memory, 0xbfc166e8L, FSEL);
        putWord(memory, 0xbfc166ecL, 0);
        installStubs(memory);
        putWord(memory, 0x9fc1a1d2L, 1);
        putByte(memory, PATH_INFO, 0xff);
        putByte(memory, PATH_INFO + 1, 1);
        putWord(memory, PATH_INFO + 8, 0); // initialized by the real resident scene caller
        putHalf(memory, LIST_STATE + 2, ROWS);
        // Seed only the synthetic visible window. The real service that fills
        // these bounds is outside the extracted firmware and remains stubbed.
        putHalf(memory, CONTROL + 8, 1);
        putHalf(memory, CONTROL + 10, ROWS);
        putWord(memory, 0x9fc15580L, stub(READY));
        putWord(memory, 0x9fc15598L, 0);
        putByte(memory, 0x9fc1559dL, 0);
        putHalf(memory, MODE_VALUE, 0);
        putByte(memory, FSEL, 0);
        putByte(memory, FSEL + 4, 0);

        EmulatorHelper emu = new EmulatorHelper(currentProgram);
        int guestSteps = 0;
        try {
            emu.registerCallOtherCallback("setISAMode", new BreakCallBack() {
                @Override public boolean pcodeCallback(PcodeOpRaw op) { return true; }
            });
            emu.writeRegister("sp", STACK);
            emu.writeRegister("ra", STOP | 1L);
            emu.writeRegister("s1", STATE);
            emu.writeRegister("t8", 0);
            emu.writeRegister("a0", 0);
            emu.writeRegister("a1", 0);
            emu.writeRegister("a2", 0);
            emu.writeRegister("a3", 0);
            Register isa = currentProgram.getRegister("ISA_MODE");
            emu.setContextRegister(isa, BigInteger.ONE);
            emu.writeRegister("pc", ENTRY);

            for (int steps = 0; steps < 200000; steps++) {
                long pc = emu.readRegister("pc").longValue() & 0xffffffffL;
                long base = pc & ~1L;
                if (base == SCENE) {
                    long a0 = emu.readRegister("a0").longValue() & 0xffffffffL;
                    long a1 = emu.readRegister("a1").longValue() & 0xffffffffL;
                    long a2 = emu.readRegister("a2").longValue() & 0xffffffffL;
                    sceneReturn = emu.readRegister("ra").longValue() & 0xffffffffL;
                    if (a0 != 0x6000L || a1 != FSEL || a2 != PATH_INFO
                        || word(emu, a2 + 8) != STATE + 24) {
                        throw new Exception(String.format(
                            "scene entry ABI mismatch a0=0x%08x a1=0x%08x a2=0x%08x ctx=0x%08x",
                            a0, a1, a2, word(emu, a2 + 8)));
                    }
                    sceneContext = word(emu, a2 + 8);
                }
                if (sceneReturn != 0 && base == (sceneReturn & ~1L)) {
                    if (rowCalls != ROWS || readyCalls != 2 || initCalls != 1 || resetCalls != 1) {
                        throw new Exception(String.format(
                            "chain incomplete row-calls=%d ready-calls=%d init-calls=%d reset-calls=%d", rowCalls, readyCalls, initCalls, resetCalls));
                    }
                    println(String.format(
                        "BROWSER SCENE REFRESH CHAIN PASS loop-iterations=%d guest-steps=%d scene=0x%08x refresh=0x40cd5218 context=0x%08x rows=%d indices=0..%d",
                        steps, guestSteps, SCENE, sceneContext, rowCalls, ROWS - 1));
                    return;
                }
                Integer id = stubs.get(base);
                if (id != null) {
                    handleStub(emu, memory, id);
                    continue;
                }
                if (!emu.step(monitor)) {
                    throw new Exception(String.format("execution stopped at 0x%08x: %s", pc, emu.getLastError()));
                }
                guestSteps++;
            }
            throw new Exception("scene chain exceeded step limit at 0x"
                + Long.toHexString(emu.readRegister("pc").longValue()));
        } finally {
            emu.dispose();
        }
    }

    private void putByte(Memory memory, long address, int value) throws Exception {
        memory.setBytes(addr(address), new byte[] {(byte)value});
    }
}
