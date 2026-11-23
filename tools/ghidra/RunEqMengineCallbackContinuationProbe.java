import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.emulate.BreakCallBack;
import ghidra.pcode.pcoderaw.PcodeOpRaw;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import java.io.ByteArrayInputStream;
import java.math.BigInteger;
import java.util.ArrayList;
import java.util.List;

/** Invoke the registered MEngine callback under an explicit synthetic scheduler hypothesis. */
public class RunEqMengineCallbackContinuationProbe extends GhidraScript {
    private static final long CALLBACK = 0x60010d00L;
    private static final long INIT_NEXT = 0x60051034L;
    private static final long STOP = 0x700300L;
    private static final long SHM_SERVICE = 0xbfc11cc8L;
    private static final long RAM = 0x9fc14000L;
    private static final int RAM_SIZE = 0x8000;
    private static final long STACK = RAM + RAM_SIZE - 0x100;
    private static final long SHM_RETURN = 0x9fc16000L;
    private static final int MAX_STEPS = 30000;

    private Address addr(long value) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value);
    }

    private long reg(EmulatorHelper emu, String name) throws Exception {
        return emu.readRegister(name).longValue() & 0xffffffffL;
    }

    private void require(boolean condition, String message) throws Exception {
        if (!condition) throw new Exception(message);
    }

    @Override
    public void run() throws Exception {
        Memory memory = currentProgram.getMemory();
        MemoryBlock ram = memory.createInitializedBlock("eq_callback_continuation_ram", addr(RAM),
            new ByteArrayInputStream(new byte[RAM_SIZE]), RAM_SIZE, monitor, false);
        ram.setRead(true);
        ram.setWrite(true);
        ram.setExecute(true);

        EmulatorHelper emu = new EmulatorHelper(currentProgram);
        int steps = 0;
        int shmCalls = 0;
        List<String> boundaries = new ArrayList<>();
        boolean reachedNext = false;
        try {
            emu.registerCallOtherCallback("setISAMode", new BreakCallBack() {
                @Override public boolean pcodeCallback(PcodeOpRaw op) { return true; }
            });
            emu.setContextRegister(currentProgram.getRegister("ISA_MODE"), BigInteger.ONE);
            emu.writeRegister("sp", STACK);
            emu.writeRegister("ra", STOP | 1L);
            emu.writeRegister("a0", 0);
            emu.writeRegister("a1", 0);
            emu.writeRegister("a2", 0);
            emu.writeRegister("a3", 0);
            for (int i = 0; i <= 7; i++) emu.writeRegister("s" + i, 0);
            for (int i = 0; i <= 9; i++) emu.writeRegister("t" + i, 0);
            emu.writeRegister("gp", 0);
            emu.writeRegister("pc", CALLBACK);

            for (steps = 0; steps < MAX_STEPS; steps++) {
                long pc = reg(emu, "pc");
                long target = pc & ~1L;
                if (target == INIT_NEXT) {
                    reachedNext = true;
                    break;
                }
                if (target == STOP) break;
                if (target == SHM_SERVICE) {
                    long a0 = reg(emu, "a0"), a1 = reg(emu, "a1");
                    long a2 = reg(emu, "a2"), a3 = reg(emu, "a3");
                    long ra = reg(emu, "ra");
                    boundaries.add(String.format(
                        "resident=0xbfc11cc8 args=(%08x,%08x,%08x,%08x) ra=%08x",
                        a0, a1, a2, a3, ra));
                    require(a0 == 3 && a3 == 0x49,
                        String.format("unexpected first shared-memory request: %08x,%08x,%08x,%08x", a0,a1,a2,a3));
                    shmCalls++;
                    emu.writeRegister("v0", SHM_RETURN);
                    emu.writeRegister("pc", ra & ~1L);
                    continue;
                }
                if (target >= 0xbfc00000L && target < 0xbfd00000L) {
                    boundaries.add(String.format("resident=0x%08x args=(%08x,%08x,%08x,%08x)",
                        target, reg(emu, "a0"), reg(emu, "a1"), reg(emu, "a2"), reg(emu, "a3")));
                    throw new Exception(String.format("reached unmodeled resident boundary 0x%08x", target));
                }
                if (!emu.step(monitor))
                    throw new Exception(String.format("stopped at 0x%08x: %s", pc, emu.getLastError()));
            }

            require(reachedNext, String.format(
                "callback did not reach FUN_60051034; pc=0x%08x steps=%d",
                reg(emu, "pc") & ~1L, steps));
            require(shmCalls == 1, "expected one intercepted synthetic shared-memory call");
            println(String.format(
                "EQ MENGINE CALLBACK CONTINUATION PASS steps=%d callback=0x%08x next=0x%08x shm_calls=%d shm_return=0x%08x invocation=scheduler-hypothesis resident_effects=synthetic",
                steps, CALLBACK, INIT_NEXT, shmCalls, SHM_RETURN));
            for (String boundary : boundaries) println("EQ MENGINE CALLBACK BOUNDARY " + boundary);
        } finally {
            emu.dispose();
        }
    }
}
