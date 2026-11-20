// Execute the extracted MIPS16 setup routine with explicit, synthetic ROM
// returns. The probe observes call arguments; it does not model the ROM helper.
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

public class RunNorBootSetupProbe extends GhidraScript {
    private static final long ENTRY = 0xbfc32a48L;
    private static final long ROM_GATE = 0xbfc10a6cL;
    private static final long ROM_COPY_CANDIDATE = 0xbfc108d8L;
    private static final long STOP = 0x00701000L;
    private static final long DESCRIPTOR = 0xbfc10124L;
    private static final long OUTPUT = 0x9fc12000L;
    private static final int MAX_STEPS = 2000;

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
        byte[] bytes = {
            (byte)value, (byte)(value >>> 8), (byte)(value >>> 16), (byte)(value >>> 24)
        };
        memory.setBytes(addr(address), bytes);
    }

    private long word(EmulatorHelper emu, long address) throws Exception {
        byte[] bytes = emu.readMemory(addr(address), 4);
        return (bytes[0] & 0xffL) | ((bytes[1] & 0xffL) << 8)
            | ((bytes[2] & 0xffL) << 16) | ((bytes[3] & 0xffL) << 24);
    }

    private long reg(EmulatorHelper emu, String name) throws Exception {
        return emu.readRegister(name).longValue() & 0xffffffffL;
    }

    @Override
    public void run() throws Exception {
        Memory memory = currentProgram.getMemory();
        mapRam(memory, "norboot_setup_synthetic_rom_table", 0xbfc02600L, 0x100);
        mapRam(memory, "norboot_setup_synthetic_ram", 0x9fc12000L, 0x1000);
        mapRam(memory, "norboot_setup_synthetic_descriptor", 0xbfc10100L, 0x100);
        mapRam(memory, "norboot_setup_synthetic_stack", 0x9fc20000L, 0x2000);

        putWord(memory, 0xbfc02608L, 0x11223344L);
        putWord(memory, 0xbfc0260cL, 0x55667788L);
        putWord(memory, 0xbfc02610L, 0x99aabbccL);
        putWord(memory, 0xbfc02618L, 0xddeeff00L);
        putWord(memory, 0xbfc10120L, 0x12345678L);
        for (int offset = 0; offset < 20; offset += 4)
            putWord(memory, DESCRIPTOR + offset, 0xccccccccL);

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
            emu.writeRegister("sp", 0x9fc21000L);
            emu.writeRegister("ra", STOP | 1L);
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
                if (pc == ROM_GATE || pc == ROM_COPY_CANDIDATE) {
                    calls.add(String.format("target=0x%08x args=%08x,%08x,%08x",
                        pc, reg(emu, "a0"), reg(emu, "a1"), reg(emu, "a2")));
                    long ra = reg(emu, "ra");
                    emu.writeRegister("v0", 0);
                    emu.writeRegister("pc", ra & ~1L);
                    continue;
                }
                if (!emu.step(monitor))
                    throw new Exception(String.format("p-code stopped at 0x%08x: %s",
                        pc, emu.getLastError()));
            }

            require(stopped, "setup routine did not return within the step limit");
            require(calls.size() == 3, "unexpected ROM-call count: " + calls);
            require(calls.get(0).startsWith("target=0xbfc10a6c "),
                "first call was not the ROM gate: " + calls.get(0));
            require(calls.get(1).equals(
                "target=0xbfc108d8 args=9fc12000,bfc10124,00000014"),
                "first setup-helper arguments differ: " + calls.get(1));
            require(calls.get(2).equals(
                "target=0xbfc108d8 args=9fc12014,bfc10138,00000020"),
                "second setup-helper arguments differ: " + calls.get(2));
            require(word(emu, DESCRIPTOR) == 0xbfc08da1L
                    && word(emu, DESCRIPTOR + 4) == 0x55667788L
                    && word(emu, DESCRIPTOR + 8) == 0x99aabbccL
                    && word(emu, DESCRIPTOR + 12) == 0xbfc08f3dL
                    && word(emu, DESCRIPTOR + 16) == 0xccccccccL,
                "setup descriptor writes mismatch");
            require(word(emu, OUTPUT + 0x200) == 0xddeeff00L
                    && word(emu, OUTPUT + 0x204) == 0x12345678L,
                "setup output metadata writes mismatch");
            for (String call : calls) println("NORBOOT ROM EDGE " + call);
            println(String.format(
                "NORBOOT SETUP P-CODE PASS entry=0x%08x steps=%d synthetic-rom-returns=3 copy-semantics=not-modeled",
                ENTRY, steps));
        }
        finally {
            emu.dispose();
        }
    }
}
