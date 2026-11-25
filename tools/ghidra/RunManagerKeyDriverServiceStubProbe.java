// Execute manager.ap's real key.drv service-stub boundary with a synthetic config getter and exception return.
import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.emulate.BreakCallBack;
import ghidra.pcode.pcoderaw.PcodeOpRaw;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import java.io.ByteArrayInputStream;
import java.math.BigInteger;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;

/** Measure the manager caller ABI and execute its resident selector stub. */
public class RunManagerKeyDriverServiceStubProbe extends GhidraScript {
    private static final long ENTRY = 0x7f056200L;
    private static final long CONFIG_GETTER = 0x7f0962bcL;
    private static final long SERVICE_STUB = 0xbfc13de0L;
    private static final long SERVICE_BREAK = SERVICE_STUB + 2;
    private static final long DRIVER_NAME = 0x7f056240L;
    private static final long STOP = 0x700300L;
    private static final long STACK = 0x10003f00L;
    private static final String EXPECTED_SHA256 =
        "d94d2406d5e88efee1ffacff2d399ce7d865410ac7458efdb9f185eae359af7a";
    private static final String EXPECTED_CONFIG_SHA256 =
        "900f814711f50446802ee36bcc2d1560df55b9d2fb4e2d964bb35004517b6d19";

    private Address address(long value) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value);
    }

    private void require(boolean condition, String message) throws Exception {
        if (!condition) throw new Exception(message);
    }

    private long register(EmulatorHelper emulator, String name) throws Exception {
        return emulator.readRegister(name).longValue() & 0xffffffffL;
    }

    private long readLe32(byte[] data, int offset) {
        return Integer.toUnsignedLong((data[offset] & 0xff)
            | ((data[offset + 1] & 0xff) << 8)
            | ((data[offset + 2] & 0xff) << 16)
            | ((data[offset + 3] & 0xff) << 24));
    }

    private void requireMips16ListingContext(long pc, String boundary) throws Exception {
        BigInteger context = currentProgram.getProgramContext().getValue(
            currentProgram.getRegister("ISA_MODE"), address(pc), false);
        require(BigInteger.ONE.equals(context),
            String.format("%s has no MIPS16 listing context at 0x%08x: %s",
                boundary, pc, context));
    }

    private void addWritableBlock(Memory memory, long start, int size, String name)
            throws Exception {
        MemoryBlock block = memory.getBlock(address(start));
        if (block == null) {
            block = memory.createInitializedBlock(name, address(start),
                new ByteArrayInputStream(new byte[size]), size, monitor, false);
        }
        block.setRead(true);
        block.setWrite(true);
        block.setExecute(true);
    }

    private void runProfile(int value50, int value51, int value52) throws Exception {
        Memory memory = currentProgram.getMemory();
        addWritableBlock(memory, STACK - 0x100, 0x300, "manager_key_service_stub_stack");

        EmulatorHelper emulator = new EmulatorHelper(currentProgram);
        List<Integer> getterIds = new ArrayList<>();
        int[] serviceCalls = {0};
        int[] serviceStubEntries = {0};
        long[] serviceArguments = new long[4];
        int steps;
        boolean returned = false;
        try {
            emulator.registerCallOtherCallback("setISAMode", new BreakCallBack() {
                @Override public boolean pcodeCallback(PcodeOpRaw op) { return true; }
            });
            emulator.setContextRegister(currentProgram.getRegister("ISA_MODE"), BigInteger.ONE);
            emulator.writeRegister("sp", STACK);
            emulator.writeRegister("ra", STOP | 1L);
            emulator.writeRegister("a0", 0);
            emulator.writeRegister("a1", 0);
            emulator.writeRegister("a2", 0);
            emulator.writeRegister("a3", 0);
            emulator.writeRegister("s0", 0);
            emulator.writeRegister("s1", 0);
            emulator.writeRegister("pc", ENTRY);

            for (steps = 0; steps < 2000; steps++) {
                long pc = register(emulator, "pc") & ~1L;
                if (pc == STOP) {
                    returned = true;
                    break;
                }

                // The overlay is decoded under LoadAP's MIPS16 program context.
                emulator.setContextRegister(
                    currentProgram.getRegister("ISA_MODE"), BigInteger.ONE);

                if (pc == CONFIG_GETTER) {
                    requireMips16ListingContext(pc, "config getter boundary");
                    long item = register(emulator, "a0");
                    require(item == 0x52 || item == 0x51 || item == 0x50,
                        String.format("unexpected config item id 0x%08x", item));
                    long ra = register(emulator, "ra");
                    require((ra & 1L) == 1L,
                        String.format("config getter return address lacks MIPS16 tag: 0x%08x", ra));
                    getterIds.add((int)item);
                    int value = item == 0x52 ? value52 : item == 0x51 ? value51 : value50;
                    emulator.writeRegister("v0", value);
                    emulator.writeRegister("pc", ra & ~1L);
                    continue;
                }

                if (pc == SERVICE_STUB) {
                    requireMips16ListingContext(pc, "resident service stub entry");
                    serviceStubEntries[0]++;
                    require(serviceStubEntries[0] == 1,
                        "unexpected repeated resident service stub entry");
                    require(emulator.step(monitor),
                        "resident service selector instruction failed: " + emulator.getLastError());
                    long nextPc = register(emulator, "pc") & ~1L;
                    require(nextPc == SERVICE_BREAK,
                        String.format("resident selector instruction advanced to %08x, expected %08x",
                            nextPc, SERVICE_BREAK));
                    require(register(emulator, "v1") == 15,
                        String.format("resident stub loaded selector %d, expected 15",
                            register(emulator, "v1")));
                    continue;
                }

                if (pc == SERVICE_BREAK) {
                    requireMips16ListingContext(pc, "resident service break boundary");
                    require(serviceStubEntries[0] == 1,
                        "break boundary was reached without executing the resident selector stub");
                    require(serviceCalls[0] == 0, "unexpected repeated key.drv service call");
                    require(register(emulator, "v1") == 15,
                        String.format("resident service stub selected %d, expected selector 15",
                            register(emulator, "v1")));
                    for (int index = 0; index < 4; index++)
                        serviceArguments[index] = register(emulator, "a" + index);
                    long ra = register(emulator, "ra");
                    require((ra & 1L) == 1L,
                        String.format("service return address lacks MIPS16 tag: 0x%08x", ra));
                    serviceCalls[0]++;
                    emulator.writeRegister("v0", 0);
                    emulator.writeRegister("pc", ra & ~1L);
                    continue;
                }

                if (!emulator.step(monitor))
                    throw new Exception(String.format("manager key.drv service-stub path stopped at %08x: %s",
                        pc, emulator.getLastError()));
            }

            require(returned, "key.drv caller did not return within 2000 instructions");
            require(getterIds.equals(List.of(0x52, 0x51, 0x50)),
                "unexpected config-getter sequence: " + getterIds);
            require(serviceCalls[0] == 1, "expected one intercepted resident service break");
            require(serviceStubEntries[0] == 1,
                "expected one executed resident selector stub");
            long packed = ((long)(value50 & 0xffff) << 24)
                | ((long)(value51 & 0xffff) << 8)
                | (long)(value52 & 0xffff);
            require(serviceArguments[0] == 9
                    && serviceArguments[1] == (packed & 0xffffffffL)
                    && serviceArguments[2] == DRIVER_NAME
                    && serviceArguments[3] == 10,
                String.format("unexpected service call args: %08x/%08x/%08x/%08x expected=%08x/%08x/%08x/%08x",
                    serviceArguments[0], serviceArguments[1], serviceArguments[2], serviceArguments[3],
                    9, packed, DRIVER_NAME, 10));

            println(String.format(
                "MANAGER KEY-DRIVER SERVICE-STUB PASS getter-order=%s values=%04x,%04x,%04x packed=%08x selector-v1=%02x call-args=(%08x,%08x,%08x,%08x) steps=%d exception-return=synthetic",
                getterIds, value52, value51, value50, packed,
                15, serviceArguments[0], serviceArguments[1], serviceArguments[2],
                serviceArguments[3], steps));
        }
        finally {
            emulator.dispose();
        }
    }

    @Override
    public void run() throws Exception {
        require(getScriptArgs().length == 2,
            "usage: RunManagerKeyDriverServiceStubProbe.java MANAGER.AP CONFIG.BIN");
        byte[] manager = Files.readAllBytes(Paths.get(getScriptArgs()[0]));
        String digest = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(manager));
        require(EXPECTED_SHA256.equals(digest), "manager.ap SHA-256 mismatch: " + digest);
        require(manager.length >= 0x2b8
                && readLe32(manager, 0x08) == 0x200
                && readLe32(manager, 0x0c) == 0xb8
                && readLe32(manager, 0x10) == SERVICE_STUB,
            "manager.ap resident segment does not map file 0x200..0x2b7 to the selector stub");
        byte[] expectedStubBytes = {(byte)0x0f, (byte)0x6b, (byte)0x05, (byte)0xe8};
        byte[] mappedStubBytes = new byte[expectedStubBytes.length];
        currentProgram.getMemory().getBytes(address(SERVICE_STUB), mappedStubBytes);
        require(java.util.Arrays.equals(expectedStubBytes, mappedStubBytes)
                && java.util.Arrays.equals(expectedStubBytes,
                    java.util.Arrays.copyOfRange(manager, 0x200, 0x204)),
            "resident selector stub bytes differ from the hash-pinned manager.ap segment");
        MemoryBlock stubBlock = currentProgram.getMemory().getBlock(address(SERVICE_STUB));
        require(stubBlock != null && stubBlock.getStart().getOffset() == SERVICE_STUB
                && stubBlock.getSize() == 0xb8,
            "LoadAP did not map the expected 0xb8-byte resident stub segment");
        require(currentProgram.getMemory().getBlock(address(ENTRY)) != null
                && currentProgram.getMemory().getBlock(address(CONFIG_GETTER)) != null,
            "manager code is not mapped");
        byte[] config = Files.readAllBytes(Paths.get(getScriptArgs()[1]));
        String configSha256 = HexFormat.of().formatHex(
            MessageDigest.getInstance("SHA-256").digest(config));
        require(EXPECTED_CONFIG_SHA256.equals(configSha256),
            "config.bin SHA-256 mismatch: " + configSha256);
        require(config.length > 0x2a8, "config.bin is truncated before items 0x50..0x52");

        // Verified config.bin layout: item directory begins at 0x10, each record is offset/length.
        int[] values = new int[3];
        int[] ids = {0x50, 0x51, 0x52};
        for (int i = 0; i < ids.length; i++) {
            int index = 0x10 + ids[i] * 8;
            long offset = Integer.toUnsignedLong((config[index] & 0xff)
                | ((config[index + 1] & 0xff) << 8)
                | ((config[index + 2] & 0xff) << 16)
                | ((config[index + 3] & 0xff) << 24));
            long length = Integer.toUnsignedLong((config[index + 4] & 0xff)
                | ((config[index + 5] & 0xff) << 8)
                | ((config[index + 6] & 0xff) << 16)
                | ((config[index + 7] & 0xff) << 24));
            require(length >= 2 && offset + length <= config.length,
                String.format("config item %02x has invalid payload range %x+%x", ids[i], offset, length));
            values[i] = (config[(int)offset] & 0xff) | ((config[(int)offset + 1] & 0xff) << 8);
        }
        require(values[0] == 1 && values[1] == 2 && values[2] == 2,
            String.format("unexpected config item first words: %04x,%04x,%04x",
                values[0], values[1], values[2]));
        require(getScriptArgs().length == 2, "unexpected args");
        runProfile(values[0], values[1], values[2]);
        runProfile(0x11, 0x22, 0x33);
        println(String.format("MANAGER KEY-DRIVER SERVICE-STUB COMPLETE manager-sha256=%s config-sha256=%s config-items=50,51,52 selector-15-service-semantics=unknown",
            digest, configSha256));
    }
}
