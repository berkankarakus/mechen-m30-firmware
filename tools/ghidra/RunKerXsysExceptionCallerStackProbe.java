import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.emulate.BreakCallBack;
import ghidra.pcode.pcoderaw.PcodeOpRaw;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import java.io.ByteArrayInputStream;

public class RunKerXsysExceptionCallerStackProbe extends GhidraScript {
    private static final long ENTRY = 0xbfc34074L;
    private static final long HANDLER_BOUNDARY = 0xbfc06d6cL;
    private static final long LOW_RAM = 0x00013d00L;
    private static final int LOW_RAM_SIZE = 0x100;
    private static final long INPUT_SP = 0x9fc1be00L;
    private static final long INPUT_RA = 0x80005679L;
    private static final long INPUT_EPC = 0x81234567L;
    private static final int MAX_STEPS = 32;

    private Address addr(long value) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value);
    }

    private void require(boolean condition, String message) throws Exception {
        if (!condition) {
            throw new Exception(message);
        }
    }

    private long reg(EmulatorHelper emulator, String name) throws Exception {
        return emulator.readRegister(name).longValue() & 0xffffffffL;
    }

    private long readWord(EmulatorHelper emulator, long address) throws Exception {
        byte[] bytes = emulator.readMemory(addr(address), 4);
        return (bytes[0] & 0xffL)
            | ((bytes[1] & 0xffL) << 8)
            | ((bytes[2] & 0xffL) << 16)
            | ((bytes[3] & 0xffL) << 24);
    }

    private void mapLowRam(Memory memory) throws Exception {
        MemoryBlock block = memory.createInitializedBlock(
            "kerxsys_exception_caller_probe_ram",
            addr(LOW_RAM),
            new ByteArrayInputStream(new byte[LOW_RAM_SIZE]),
            LOW_RAM_SIZE,
            monitor,
            false
        );
        block.setRead(true);
        block.setWrite(true);
    }

    @Override
    public void run() throws Exception {
        mapLowRam(currentProgram.getMemory());

        EmulatorHelper emulator = new EmulatorHelper(currentProgram);
        try {
            emulator.registerCallOtherCallback("setISAMode", new BreakCallBack() {
                @Override
                public boolean pcodeCallback(PcodeOpRaw op) {
                    return true;
                }
            });
            emulator.writeRegister("sp", INPUT_SP);
            emulator.writeRegister("ra", INPUT_RA);
            emulator.writeRegister("EPC", INPUT_EPC);
            emulator.writeRegister("pc", ENTRY);

            boolean reachedHandlerBoundary = false;
            int steps = 0;
            long boundarySp = 0;
            for (; steps < MAX_STEPS; steps++) {
                long pc = reg(emulator, "pc");
                if (pc == HANDLER_BOUNDARY) {
                    reachedHandlerBoundary = true;
                    boundarySp = reg(emulator, "sp");
                    break;
                }

                if (!emulator.step(monitor)) {
                    throw new Exception(String.format(
                        "caller stopped at 0x%08x: %s",
                        pc,
                        emulator.getLastError()
                    ));
                }
            }

            require(reachedHandlerBoundary,
                "caller did not reach the fixed handler boundary within the step limit");
            require(boundarySp == INPUT_SP,
                String.format("caller changed sp: entry=0x%08x boundary=0x%08x", INPUT_SP, boundarySp));

            long savedEpc = readWord(emulator, LOW_RAM + 0xd8);
            long savedRa = readWord(emulator, LOW_RAM + 0xdc);
            require(savedEpc == INPUT_EPC,
                String.format("caller saved unexpected EPC: 0x%08x", savedEpc));
            require(savedRa == INPUT_RA,
                String.format("caller saved unexpected RA: 0x%08x", savedRa));

            println(String.format(
                "KER XSYS EXCEPTION CALLER STACK P-CODE PASS entry=0x%08x boundary=0x%08x steps=%d entry-sp=0x%08x boundary-sp=0x%08x saved-epc=0x%08x saved-ra=0x%08x rom-handler-executed=0",
                ENTRY,
                HANDLER_BOUNDARY,
                steps,
                INPUT_SP,
                boundarySp,
                savedEpc,
                savedRa
            ));
        }
        finally {
            emulator.dispose();
        }
    }
}
