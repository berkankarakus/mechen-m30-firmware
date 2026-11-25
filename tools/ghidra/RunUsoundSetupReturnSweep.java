// Sweep isolated synthetic return values through the USB Audio setup callers.
import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.emulate.BreakCallBack;
import ghidra.pcode.pcoderaw.PcodeOpRaw;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import java.io.ByteArrayInputStream;
import java.math.BigInteger;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class RunUsoundSetupReturnSweep extends GhidraScript {
    private static final long ENTRY = 0xbfc322e4L;
    private static final long STOP = 0x700300L;
    private static final long MODULE10 = 0xbfc326a8L;
    private static final long MODULE0F = 0xbfc326acL;
    private static final long DATA = 0x9fc33c00L;
    private static final int DATA_SIZE = 0x154;
    private static final int BSS_SIZE = 0xd4;
    private static final long STACK = 0x9fc35000L;

    private Address address(long value) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value);
    }

    private long register(EmulatorHelper emulator, String name) throws Exception {
        return emulator.readRegister(name).longValue() & 0xffffffffL;
    }

    private void resetRegion(Memory memory, long start, int size) throws Exception {
        memory.setBytes(address(start), new byte[size]);
    }

    private String runProfile(
        Memory memory,
        byte[] initialData,
        int targetCall,
        long selectedReturn
    ) throws Exception {
        memory.setBytes(address(DATA), initialData);
        resetRegion(memory, STACK, 0x1000);
        resetRegion(memory, 0xc0000000L, 0x3000);
        resetRegion(memory, 0xc0020000L, 0x1000);
        resetRegion(memory, 0xc0050000L, 0x1000);
        resetRegion(memory, 0xc0080000L, 0x5000);

        EmulatorHelper emulator = new EmulatorHelper(currentProgram);
        List<String> calls = new ArrayList<>();
        int callIndex = 0;
        try {
            emulator.registerCallOtherCallback("setISAMode", new BreakCallBack() {
                @Override
                public boolean pcodeCallback(PcodeOpRaw op) {
                    return true;
                }
            });
            emulator.setContextRegister(currentProgram.getRegister("ISA_MODE"), BigInteger.ONE);
            emulator.writeRegister("sp", STACK + 0x800);
            emulator.writeRegister("ra", STOP | 1L);
            emulator.writeRegister("s0", 0);
            emulator.writeRegister("s1", 0);
            emulator.writeRegister("a0", DATA + 0x20);
            emulator.writeRegister("a1", 0);
            emulator.writeRegister("a2", 0);
            emulator.writeRegister("a3", 0);
            emulator.writeRegister("pc", ENTRY);

            for (int steps = 0; steps < 250000; steps++) {
                long pc = register(emulator, "pc") & ~1L;
                if (pc == STOP) {
                    byte[] copiedRate = new byte[3];
                    memory.getBytes(address(DATA + 0xa3), copiedRate);
                    byte[] expectedRate = Arrays.copyOfRange(initialData, 8, 11);
                    if (!Arrays.equals(copiedRate, expectedRate)) {
                        throw new Exception(String.format(
                            "module-0x10 rate copy mismatch: got=%02x%02x%02x expected=%02x%02x%02x",
                            copiedRate[0] & 0xff, copiedRate[1] & 0xff, copiedRate[2] & 0xff,
                            expectedRate[0] & 0xff, expectedRate[1] & 0xff, expectedRate[2] & 0xff
                        ));
                    }
                    String trace = String.join(";", calls);
                    return String.format(
                        "profile=%s steps=%d outcome=stop calls=%d trace=[%s]",
                        profileName(targetCall, selectedReturn), steps, callIndex, trace
                    );
                }

                if (pc == MODULE0F || pc == MODULE10) {
                    long a0 = register(emulator, "a0");
                    long a1 = register(emulator, "a1");
                    long a2 = register(emulator, "a2");
                    long a3 = register(emulator, "a3");
                    long ra = register(emulator, "ra");
                    int module = pc == MODULE0F ? 0x0f : 0x10;
                    callIndex++;
                    long returnValue = callIndex == targetCall ? selectedReturn : 0;
                    if (module == 0x10) {
                        if (a2 != 3 || a3 != 0) {
                            throw new Exception(String.format(
                                "unexpected module-0x10 copy arguments: %08x/%08x/%08x/%08x",
                                a0, a1, a2, a3
                            ));
                        }

                        byte[] source = new byte[(int)a2];
                        memory.getBytes(address(a1), source);
                        memory.setBytes(address(a0), source);
                    }
                    calls.add(String.format(
                        "%d:module=0x%02x,args=%08x/%08x/%08x/%08x,ra=%08x,ret=%08x",
                        callIndex, module, a0, a1, a2, a3, ra, returnValue
                    ));
                    emulator.writeRegister("v0", returnValue);
                    emulator.writeRegister("pc", ra & ~1L);
                    continue;
                }

                if (!emulator.step(monitor)) {
                    return String.format(
                        "profile=%s steps=%d outcome=emulator-stop-at-%08x calls=%d trace=[%s] error=%s",
                        profileName(targetCall, selectedReturn), steps, pc, callIndex,
                        String.join(";", calls), emulator.getLastError()
                    );
                }
            }

            return String.format(
                "profile=%s outcome=step-limit calls=%d trace=[%s]",
                profileName(targetCall, selectedReturn), callIndex, String.join(";", calls)
            );
        }
        finally {
            emulator.dispose();
        }
    }

    private String profileName(int targetCall, long selectedReturn) {
        if (targetCall == 0) {
            return "baseline";
        }

        return String.format("call=%d-return=%08x", targetCall, selectedReturn);
    }

    @Override
    public void run() throws Exception {
        if (getScriptArgs().length != 1) {
            throw new Exception("usage: RunUsoundSetupReturnSweep.java USOUND.DRV");
        }

        byte[] driver = Files.readAllBytes(Paths.get(getScriptArgs()[0]));
        if (driver.length < 0x2a54) {
            throw new Exception("usound.drv is truncated");
        }

        Memory memory = currentProgram.getMemory();
        byte[] data = new byte[DATA_SIZE + BSS_SIZE];
        System.arraycopy(driver, 0x2900, data, 0, DATA_SIZE);
        var dataBlock = memory.createInitializedBlock(
            "usound_setup_sweep_data_bss", address(DATA), new ByteArrayInputStream(data),
            data.length, monitor, false
        );
        dataBlock.setRead(true);
        dataBlock.setWrite(true);

        var stackBlock = memory.createInitializedBlock(
            "usound_setup_sweep_stack", address(STACK),
            new ByteArrayInputStream(new byte[0x1000]), 0x1000, monitor, false
        );
        stackBlock.setRead(true);
        stackBlock.setWrite(true);

        mapWritableRegion(memory, "usound_setup_sweep_mmio0", 0xc0000000L, 0x3000);
        mapWritableRegion(memory, "usound_setup_sweep_mmio2", 0xc0020000L, 0x1000);
        mapWritableRegion(memory, "usound_setup_sweep_mmio5", 0xc0050000L, 0x1000);
        mapWritableRegion(memory, "usound_setup_sweep_mmio8", 0xc0080000L, 0x5000);

        List<String> profiles = new ArrayList<>();
        profiles.add(runProfile(memory, data, 0, 0));
        for (int callIndex = 1; callIndex <= 11; callIndex++) {
            profiles.add(runProfile(memory, data, callIndex, 1));
            profiles.add(runProfile(memory, data, callIndex, 0xffffffffL));
        }

        for (String profile : profiles) {
            println("USOUND SETUP RETURN SWEEP " + profile);
        }
        println(String.format(
            "USOUND SETUP RETURN SWEEP PASS profiles=%d isolated-calls=11 return-values=00000001,ffffffff module-0x10-copy=synthetic-and-verified synthetic-module-return=0-except-selected synthetic-mmio=zeroed",
            profiles.size()
        ));
    }

    private void mapWritableRegion(
        Memory memory,
        String name,
        long start,
        int size
    ) throws Exception {
        var block = memory.createInitializedBlock(
            name, address(start), new ByteArrayInputStream(new byte[size]), size, monitor, false
        );
        block.setRead(true);
        block.setWrite(true);
    }
}
