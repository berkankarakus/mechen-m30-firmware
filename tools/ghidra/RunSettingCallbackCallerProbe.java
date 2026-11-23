import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.emulate.BreakCallBack;
import ghidra.pcode.pcoderaw.PcodeOpRaw;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import java.io.ByteArrayInputStream;
import java.math.BigInteger;

/** Follow the real setting AP initializer to the callback-slot writer. */
public class RunSettingCallbackCallerProbe extends GhidraScript {
    private static final long ENTRY = 0x40054f78L;
    private static final long WRITER = 0x48494600L;
    private static final long SERVICE_A = 0x48414600L;
    private static final long SERVICE_B = 0x4845476cL;
    private static final long RAM = 0x9fc14000L;
    private static final long STACK = 0x9fc1bf00L;
    private static final long STOP = 0x700300L;

    private Address addr(long value) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value);
    }

    private long reg(EmulatorHelper emu, String name) throws Exception {
        return emu.readRegister(name).longValue() & 0xffffffffL;
    }

    private long word(EmulatorHelper emu, long at) throws Exception {
        byte[] b = emu.readMemory(addr(at), 4);
        return (b[0] & 255L) | ((b[1] & 255L) << 8)
            | ((b[2] & 255L) << 16) | ((b[3] & 255L) << 24);
    }

    private void require(boolean condition, String message) throws Exception {
        if (!condition) throw new Exception(message);
    }

    @Override
    public void run() throws Exception {
        Memory memory = currentProgram.getMemory();
        var ram = memory.createInitializedBlock("setting_callback_caller_ram", addr(RAM),
            new ByteArrayInputStream(new byte[0x8000]), 0x8000, monitor, false);
        ram.setRead(true);
        ram.setWrite(true);
        ram.setExecute(true);
        EmulatorHelper emu = new EmulatorHelper(currentProgram);
        int first = 0, second = 0, steps = 0;
        try {
            emu.registerCallOtherCallback("setISAMode", new BreakCallBack() {
                @Override public boolean pcodeCallback(PcodeOpRaw op) { return true; }
            });
            emu.setContextRegister(currentProgram.getRegister("ISA_MODE"), BigInteger.ONE);
            emu.writeRegister("sp", STACK);
            emu.writeRegister("ra", STOP | 1L);
            emu.writeRegister("pc", ENTRY);
            for (; steps < 5000; steps++) {
                long pc = reg(emu, "pc") & ~1L;
                if (pc == WRITER) {
                    require(first == 1 && second == 1, "writer reached without expected services");
                    require(reg(emu, "a0") == 0x40054d79L,
                        String.format("wrong callback argument: 0x%08x", reg(emu, "a0")));
                    println(String.format(
                        "SETTING CALLBACK CALLER PASS steps=%d caller=0x%08x writer=0x%08x callback=0x%08x descriptor-slot=0x%08x first-service=synthetic-1 second-service=synthetic-0",
                        steps, ENTRY, WRITER, reg(emu, "a0"), word(emu, 0x9fc15600L)));
                    return;
                }
                if (pc == SERVICE_A || pc == SERVICE_B) {
                    long a0 = reg(emu, "a0"), a1 = reg(emu, "a1");
                    long ra = reg(emu, "ra");
                    if (pc == SERVICE_A) {
                        require(first++ == 0 && a0 == 4 && a1 == 1,
                            "unexpected first service arguments");
                        emu.writeRegister("v0", 1);
                    } else {
                        require(second++ == 0 && a0 == 0x9fc15518L && a1 == 5,
                            "unexpected second service arguments");
                        emu.writeRegister("v0", 0);
                    }
                    emu.writeRegister("pc", ra & ~1L);
                    continue;
                }
                require(pc != STOP, "initializer returned before callback writer");
                if (!emu.step(monitor))
                    throw new Exception(String.format("caller stopped at 0x%08x: %s",
                        pc, emu.getLastError()));
            }
            throw new Exception("callback writer not reached before step limit");
        } finally {
            emu.dispose();
        }
    }
}
