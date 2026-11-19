// Execute aud_dev bank-5 EQ handling and capture the module-0x10 copy ABI.
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
import java.util.Arrays;
import java.util.List;

public class RunAuddevEqCopyProbe extends GhidraScript {
    private static final long ENTRY = 0x9400L;
    private static final long STOP = 0x700300L;
    private static final long COPY_STUB = 0x10003000L;
    private static final long RAM = 0x10000000L;
    private static final long SOURCE = RAM + 0x1000;
    private static final long STATE = 0x9fc34000L;
    private static final long STACK = RAM + 0x4000;
    private static final int BANDS = 16;
    private static final List<String> calls = new ArrayList<>();

    private Address addr(long value) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value);
    }

    private long reg(EmulatorHelper emu, String name) throws Exception {
        return emu.readRegister(name).longValue() & 0xffffffffL;
    }

    private void putWord(Memory memory, long at, long value) throws Exception {
        memory.setBytes(addr(at), new byte[] {
            (byte)value, (byte)(value >>> 8), (byte)(value >>> 16), (byte)(value >>> 24)
        });
    }

    private long fileWord(byte[] bytes, int offset) {
        return (bytes[offset] & 0xffL) | ((bytes[offset + 1] & 0xffL) << 8)
            | ((bytes[offset + 2] & 0xffL) << 16) | ((bytes[offset + 3] & 0xffL) << 24);
    }

    private void require(boolean condition, String message) throws Exception {
        if (!condition) throw new Exception(message);
    }

    private int execute(EmulatorHelper emu) throws Exception {
        emu.writeRegister("sp", STACK);
        emu.writeRegister("ra", STOP | 1L);
        emu.writeRegister("a0", 1);
        emu.writeRegister("a1", SOURCE);
        emu.writeRegister("a2", 0);
        emu.writeRegister("a3", 0);
        emu.writeRegister("pc", ENTRY);
        for (int steps = 0; steps < 100000; steps++) {
            long pc = reg(emu, "pc") & ~1L;
            if (pc >= 0x9400 && pc < 0x9a00) {
                emu.setContextRegister(currentProgram.getRegister("ISA_MODE"), BigInteger.ONE);
            }
            if (pc == STOP) return steps;
            if (pc == COPY_STUB) {
                long a0 = reg(emu, "a0");
                long a1 = reg(emu, "a1");
                long a2 = reg(emu, "a2");
                long a3 = reg(emu, "a3");
                long ra = reg(emu, "ra");
                calls.add(String.format(
                    "a0=0x%08x a1=0x%08x a2=0x%08x a3=0x%08x ra=0x%08x",
                    a0, a1, a2, a3, ra
                ));
                emu.writeRegister("v0", 0);
                emu.writeRegister("pc", ra & ~1L);
                continue;
            }
            if (!emu.step(monitor)) {
                throw new Exception(String.format("stopped at 0x%08x: %s", pc, emu.getLastError()));
            }
        }
        throw new Exception("aud_dev EQ entry exceeded instruction limit");
    }

    @Override
    public void run() throws Exception {
        if (getScriptArgs().length != 1)
            throw new Exception("usage: RunAuddevEqCopyProbe.java AUD_DEV.DRV");
        byte[] driver = java.nio.file.Files.readAllBytes(
            java.nio.file.Paths.get(getScriptArgs()[0]));
        if (driver.length < 0x2500) throw new Exception("aud_dev.drv is truncated before bank 5");

        Memory memory = currentProgram.getMemory();
        MemoryBlock code = memory.getBlock(addr(ENTRY));
        if (code == null) throw new Exception("mapped bank-5 code is missing");
        byte[] mappedCode = new byte[0x600];
        memory.getBytes(addr(ENTRY), mappedCode);
        if (!Arrays.equals(mappedCode, Arrays.copyOfRange(driver, 0x1f00, 0x2500)))
            throw new Exception("loaded 0x9400 code does not match input file bank-5 candidate");
        if (fileWord(driver, 0x23fc) != 0xbfc09f59L
                || fileWord(driver, 0x23f8) != 0x9fc34000L)
            throw new Exception("candidate bank-5 pointer words do not match expected image values");
        code.setWrite(true);
        putWord(memory, 0x98fc, COPY_STUB | 1L);

        MemoryBlock ram = memory.createInitializedBlock("auddev_eq_probe_ram", addr(RAM),
            new ByteArrayInputStream(new byte[0x5000]), 0x5000, monitor, false);
        ram.setRead(true);
        ram.setWrite(true);
        ram.setExecute(true);

        MemoryBlock state = memory.createInitializedBlock("auddev_eq_probe_state", addr(STATE),
            new ByteArrayInputStream(new byte[0x200]), 0x200, monitor, false);
        state.setRead(true);
        state.setWrite(true);

        // One active EQ/DAE payload with 16 distinct 8-byte bands.  Other
        // mode flags remain zero so unrelated file/filter paths stay inactive.
        byte[] input = new byte[0x180];
        input[7] = 1;
        for (int band = 0; band < BANDS; band++) {
            for (int j = 0; j < 8; j++) input[0x10 + band * 8 + j] = (byte)(band * 8 + j + 1);
        }
        memory.setBytes(addr(SOURCE), input);

        EmulatorHelper emu = new EmulatorHelper(currentProgram);
        try {
            emu.registerCallOtherCallback("setISAMode", new BreakCallBack() {
                @Override public boolean pcodeCallback(PcodeOpRaw op) { return true; }
            });
            emu.setContextRegister(currentProgram.getRegister("ISA_MODE"), BigInteger.ONE);
            int steps = execute(emu);
            require(calls.size() == BANDS, "expected 16 module-0x10 calls, got " + calls.size());
            for (int band = 0; band < BANDS; band++) {
                String expected = String.format(
                    "a0=0x%08x a1=0x%08x a2=0x00000008 a3=0x00000000",
                    STATE + 0x94 + band * 8L, SOURCE + 0x10 + band * 8L
                );
                require(calls.get(band).startsWith(expected),
                    "band " + band + " call mismatch: " + calls.get(band));
                println(String.format("AUDDEV EQ COPY band=%02d %s", band, calls.get(band)));
            }
            println(String.format(
                "AUDDEV EQ COPY P-CODE PASS entry=0x%08x steps=%d module0x10-calls=%d synthetic-input=1 synthetic-service-return=0",
                ENTRY, steps, calls.size()
            ));
        }
        finally {
            emu.dispose();
        }
    }
}
