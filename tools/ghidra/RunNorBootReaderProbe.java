// Execute the extracted MIPS16 NOR read wrapper with synthetic external
// targets. Observe arguments only; neither helper's behavior is modeled.
import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.emulate.BreakCallBack;
import ghidra.pcode.pcoderaw.PcodeOpRaw;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.mem.Memory;
import java.io.ByteArrayInputStream;
import java.math.BigInteger;
import java.util.ArrayList;
import java.util.List;

public class RunNorBootReaderProbe extends GhidraScript {
    private static final long ENTRY = 0xbfc3292cL;
    private static final long READ_TARGET = 0x00702000L;
    private static final long ROM_TRANSFORM = 0xbfc108d8L;
    private static final long STOP = 0x00702040L;
    private static final long SCRATCH = 0x9fc27000L;
    private static final int MAX_STEPS = 1000;

    private Address addr(long value) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace()
            .getAddress(value & 0xffffffffL);
    }

    private void require(boolean condition, String message) throws Exception {
        if (!condition) throw new Exception(message);
    }

    private void mapRam(Memory memory, String name, long base, int size)
        throws Exception {
        var block = memory.createInitializedBlock(name, addr(base),
            new ByteArrayInputStream(new byte[size]), size, monitor, false);
        block.setRead(true);
        block.setWrite(true);
    }

    private void putWord(Memory memory, long address, long value) throws Exception {
        memory.setBytes(addr(address), new byte[] {
            (byte)value, (byte)(value >>> 8), (byte)(value >>> 16), (byte)(value >>> 24)
        });
    }

    private long reg(EmulatorHelper emu, String name) throws Exception {
        return emu.readRegister(name).longValue() & 0xffffffffL;
    }

    private long isaMode(EmulatorHelper emu) throws Exception {
        return emu.readRegister("ISA_MODE").longValue() & 0xffffffffL;
    }

    @Override
    public void run() throws Exception {
        Memory memory = currentProgram.getMemory();
        // The setup probe earlier in run_norboot_probe.sh creates the ROM
        // table and descriptor blocks. Map only this reader's additional RAM.
        mapRam(memory, "norboot_reader_synthetic_scratch", SCRATCH, 0x1000);
        mapRam(memory, "norboot_reader_synthetic_stack", 0x9fc30000L, 0x2000);
        // Synthetic pointer is tagged as MIPS16; native mode switching is not
        // under test because this probe intercepts setISAMode.
        putWord(memory, 0xbfc02600L, READ_TARGET | 1L);
        putWord(memory, 0xbfc10138L, 0x00002800L);

        EmulatorHelper emu = new EmulatorHelper(currentProgram);
        Register isa = currentProgram.getRegister("ISA_MODE");
        List<String> calls = new ArrayList<>();
        boolean stopped = false;
        int steps = 0;
        try {
            emu.registerCallOtherCallback("setISAMode", new BreakCallBack() {
                @Override public boolean pcodeCallback(PcodeOpRaw op) { return true; }
            });
            emu.setContextRegister(isa, BigInteger.ONE);
            emu.writeRegister("sp", 0x9fc31000L);
            emu.writeRegister("ra", STOP | 1L);
            emu.writeRegister("a0", 0x9fc13000L);
            emu.writeRegister("a1", 5);
            emu.writeRegister("a2", 0x601);
            emu.writeRegister("s0", 0);
            emu.writeRegister("s1", 0);
            emu.writeRegister("pc", ENTRY);

            for (; steps < MAX_STEPS; steps++) {
                long pc = reg(emu, "pc");
                if ((pc & 1L) != 0) {
                    pc &= ~1L;
                    emu.writeRegister("pc", pc);
                }
                if (pc == STOP) {
                    stopped = true;
                    break;
                }
                if (pc == READ_TARGET || pc == ROM_TRANSFORM) {
                    require((isaMode(emu) & 1L) == 1,
                        String.format("expected MIPS16 at synthetic edge 0x%08x, got ISA_MODE=%d",
                            pc, isaMode(emu)));
                    calls.add(String.format("target=0x%08x args=%08x,%08x,%08x",
                        pc, reg(emu, "a0"), reg(emu, "a1"), reg(emu, "a2")));
                    long ra = reg(emu, "ra");
                    emu.writeRegister("v0", 0);
                    emu.setContextRegister(isa, BigInteger.ONE);
                    emu.writeRegister("pc", ra & ~1L);
                    continue;
                }
                if (!emu.step(monitor))
                    throw new Exception(String.format("p-code stopped at 0x%08x: %s",
                        pc, emu.getLastError()));
            }

            require(stopped, "reader wrapper did not return within the step limit");
            require(calls.size() == 2, "unexpected helper-call count: " + calls);
            require(calls.get(0).equals(
                "target=0x00702000 args=00000019,9fc27000,00000004"),
                "block-reader arguments differ: " + calls.get(0));
            require(calls.get(1).equals(
                "target=0xbfc108d8 args=9fc13000,9fc27000,00000601"),
                "ROM-helper arguments differ: " + calls.get(1));
            for (String call : calls) println("NORBOOT READER EDGE " + call);
            println(String.format(
                "NORBOOT READER P-CODE PASS entry=0x%08x steps=%d synthetic-returns=2 length=0x601 rounded-blocks=4 block-size=512 helper-semantics=not-modeled",
                ENTRY, steps));
        }
        finally {
            emu.dispose();
        }
    }
}
