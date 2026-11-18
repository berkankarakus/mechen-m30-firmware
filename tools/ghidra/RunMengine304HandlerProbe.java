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

/** Execute the real mengine 0x304 handler; stub only mmm_mp and message-ack services. */
public class RunMengine304HandlerProbe extends GhidraScript {
    private static final long ENTRY = 0x60110ddcL;
    private static final long MMM_SERVICE = 0xbfc11cc4L;
    private static final long ACK_SERVICE = 0xbfc1197cL;
    private static final long STOP = 0x700300L;
    private static final long RAM = 0x9fc14000L;
    private static final long RAM_SIZE = 0x4000L;
    private static final long ENGINE_HANDLE = 0x13572468L;
    private static final long STATE = 0x9fc15c88L;
    private static final long OUTPUT_STATE = 0x9fc15d8cL;
    private static final long MESSAGE = RAM + 0x1000L;
    private static final long PAYLOAD = RAM + 0x1020L;

    private Address addr(long value) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value);
    }

    private void bytes(EmulatorHelper emu, long address, byte[] data) throws Exception {
        emu.writeMemory(addr(address), data);
    }

    private void word(EmulatorHelper emu, long address, long value) throws Exception {
        bytes(emu, address, new byte[] {
            (byte) value, (byte) (value >>> 8), (byte) (value >>> 16), (byte) (value >>> 24)
        });
    }

    private long reg(EmulatorHelper emu, String name) throws Exception {
        return emu.readRegister(name).longValue() & 0xffffffffL;
    }

    private int readByte(EmulatorHelper emu, long address) throws Exception {
        return emu.readMemory(addr(address), 1)[0] & 0xff;
    }

    private long readWord(EmulatorHelper emu, long address) throws Exception {
        byte[] data = emu.readMemory(addr(address), 4);
        return (data[0] & 255L) | ((data[1] & 255L) << 8)
            | ((data[2] & 255L) << 16) | ((data[3] & 255L) << 24);
    }

    private void require(boolean condition, String message) throws Exception {
        if (!condition) throw new Exception(message);
    }

    private void returnFromMips16(EmulatorHelper emu) throws Exception {
        long ra = reg(emu, "ra");
        require((ra & 1L) == 1L, String.format("service return is not MIPS16-tagged: %08x", ra));
        emu.writeRegister("pc", ra & ~1L);
    }

    private void runCase(String name, int oldMode, int payload, int expectMmmCalls,
        long expectedSnapshot) throws Exception {
        EmulatorHelper emu = new EmulatorHelper(currentProgram);
        int mmmCalls = 0;
        int ackCalls = 0;
        int steps = 0;
        try {
            bytes(emu, RAM, new byte[(int) RAM_SIZE]);
            bytes(emu, STATE, new byte[0x180]);
            bytes(emu, MESSAGE, new byte[0x30]);
            word(emu, 0x9fc15c0cL, ENGINE_HANDLE);
            word(emu, STATE, 2); // engine status: selects the 0x1c transition branch
            bytes(emu, STATE + 0x2c, new byte[] {(byte) oldMode});
            word(emu, OUTPUT_STATE, 0xabcdef01L);
            word(emu, MESSAGE + 4, PAYLOAD);
            bytes(emu, PAYLOAD, new byte[] {(byte) payload});

            emu.registerCallOtherCallback("setISAMode", new BreakCallBack() {
                @Override public boolean pcodeCallback(PcodeOpRaw op) { return true; }
            });
            emu.setContextRegister(currentProgram.getRegister("ISA_MODE"), BigInteger.ONE);
            emu.writeRegister("sp", RAM + RAM_SIZE - 0x100);
            emu.writeRegister("ra", STOP | 1L);
            emu.writeRegister("a0", MESSAGE);
            emu.writeRegister("a1", 0);
            emu.writeRegister("a2", 0);
            emu.writeRegister("a3", 0);
            emu.writeRegister("s0", 0);
            emu.writeRegister("s1", 0);
            emu.writeRegister("pc", ENTRY);

            boolean returned = false;
            for (steps = 0; steps < 3000; steps++) {
                long pc = reg(emu, "pc");
                long base = pc & ~1L;
                if (base == STOP) {
                    returned = true;
                    break;
                }
                if (base == MMM_SERVICE) {
                    mmmCalls++;
                    long context = reg(emu, "a0");
                    long command = reg(emu, "a1");
                    long output = reg(emu, "a2");
                    require(context == ENGINE_HANDLE && command == 0x1c,
                        String.format("unexpected mmm_mp request: %08x %08x %08x", context, command, output));
                    require(output >= RAM && output + 0x18 <= RAM + RAM_SIZE,
                        String.format("snapshot buffer is not in synthetic RAM: %08x", output));
                    bytes(emu, output, new byte[0x18]);
                    word(emu, output + 0x0c, expectedSnapshot);
                    emu.writeRegister("v0", 0);
                    returnFromMips16(emu);
                    continue;
                }
                if (base == ACK_SERVICE) {
                    ackCalls++;
                    require(reg(emu, "a0") == MESSAGE && reg(emu, "a1") == 1,
                        String.format("unexpected message ack: %08x %08x", reg(emu, "a0"), reg(emu, "a1")));
                    emu.writeRegister("v0", 0);
                    returnFromMips16(emu);
                    continue;
                }
                if (!emu.step(monitor)) {
                    throw new Exception(String.format("%s stopped at %08x: %s", name, pc, emu.getLastError()));
                }
            }
            require(returned, name + " handler did not return");
            println(String.format("MENGINE 0x304 HANDLER TRACE %s status=%08x payload-memory=%02x +2b=%02x +2c=%02x +2e=%02x mmm=%d ack=%d",
                name, readWord(emu, STATE), readByte(emu, PAYLOAD),
                readByte(emu, STATE + 0x2b), readByte(emu, STATE + 0x2c),
                readByte(emu, STATE + 0x2e), mmmCalls, ackCalls));
            require(mmmCalls == expectMmmCalls,
                name + " mmm_mp call count=" + mmmCalls + " expected=" + expectMmmCalls);
            require(ackCalls == 1, name + " acknowledgement count=" + ackCalls);
            require(readByte(emu, STATE + 0x2b) == (payload & 0x30), name + " +0x2b mask mismatch");
            require(readByte(emu, STATE + 0x2c) == (payload & 0x0f), name + " +0x2c mask mismatch");
            require(readByte(emu, STATE + 0x2e) == (payload & 0xc0), name + " +0x2e mask mismatch");
            require(readWord(emu, OUTPUT_STATE) == (expectMmmCalls == 1 ? expectedSnapshot : 0xabcdef01L),
                name + " snapshot copy behavior mismatch");
            println(String.format("MENGINE 0x304 HANDLER CASE %s steps=%d payload=0x%02x mmm-requests=%d ack=%d snapshot=0x%08x",
                name, steps, payload, mmmCalls, ackCalls, readWord(emu, OUTPUT_STATE)));
        } finally {
            emu.dispose();
        }
    }

    @Override
    public void run() throws Exception {
        Memory memory = currentProgram.getMemory();
        MemoryBlock ram = memory.getBlock(addr(RAM));
        if (ram == null) {
            ram = memory.createInitializedBlock("mengine_304_probe_ram", addr(RAM),
                new ByteArrayInputStream(new byte[(int) RAM_SIZE]), RAM_SIZE, monitor, false);
        }
        require(ram.getStart().equals(addr(RAM)) && ram.getSize() == RAM_SIZE
                && "mengine_304_probe_ram".equals(ram.getName()),
            "refusing unexpected synthetic RAM block");
        ram.setRead(true);
        ram.setWrite(true);
        ram.setExecute(true);

        byte[] pointer = new byte[4];
        memory.getBytes(addr(0x60110ea0L), pointer);
        long service = (pointer[0] & 255L) | ((pointer[1] & 255L) << 8)
            | ((pointer[2] & 255L) << 16) | ((pointer[3] & 255L) << 24);
        require(service == 0xbfc11cc5L,
            String.format("unexpected mmm_mp service pointer: %08x", service));
        Register isa = currentProgram.getRegister("ISA_MODE");
        BigInteger mode = currentProgram.getProgramContext().getValue(isa, addr(ENTRY), false);
        require(BigInteger.ONE.equals(mode), "0x304 handler does not have MIPS16 context");

        runCase("enter-mode-3", 2, 0xa3, 1, 0x12345678L);
        runCase("already-mode-3", 3, 0x53, 0, 0x87654321L);
        println("MENGINE 0x304 HANDLER DYNAMIC PASS entry=60110ddc payloads=0xa3,0x53 "
            + "state-masks=0x30,0x0f,0xc0 transition-snapshot=verified services=stubbed");
    }
}
