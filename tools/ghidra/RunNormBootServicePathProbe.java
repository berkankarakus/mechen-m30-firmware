// Execute the real NORMBREC MIPS16 routine through synthetic ROM pointer slots.
// The slot targets and their effects are fixtures, not recovered ROM code.
import ghidra.app.plugin.processors.sleigh.SleighLanguage;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.emu.PcodeEmulator;
import ghidra.pcode.emu.PcodeThread;
import ghidra.pcode.exec.PcodeExecutorStatePiece.Reason;
import ghidra.pcode.exec.PcodeUseropLibrary;
import ghidra.pcode.exec.SleighProgramCompiler;
import ghidra.pcode.utils.Utils;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;
import java.math.BigInteger;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.List;

public class RunNormBootServicePathProbe extends GhidraScript {
    private static final long BASE = 0xbfc08000L;
    private static final long ENTRY = 0xbfc08028L;
    private static final long STOP = 0x00704000L;
    private static final long SLOT_A8 = 0xbfc002a8L;
    private static final long SLOT_A0 = 0xbfc002a0L;
    private static final long SLOT_94 = 0xbfc00294L;
    private static final long SLOT_A4 = 0xbfc002a4L;
    private static final long TARGET_A8 = 0x00703000L;
    private static final long TARGET_94 = 0x00703020L;
    private static final long TARGET_A0 = 0x00703040L;
    private static final long TARGET_A4 = 0x00703060L;
    private static final long BUFFER = 0xbfc10000L;
    private static final long STACK = 0x9fc21000L;
    private static final int MAX_STEPS = 4000;
    private static final String EXPECTED_SHA256 =
        "dacb549733c6af1727ed2dd8efe091ff6386ef3a111329f5407475ee620c5ace";

    private void require(boolean condition, String message) throws Exception {
        if (!condition) throw new Exception(message);
    }

    private Address addr(AddressSpace space, long value) {
        return space.getAddress(value & 0xffffffffL);
    }

    private long reg(PcodeThread<byte[]> thread, Register register,
            SleighLanguage language) {
        byte[] value = thread.getState().getVar(register, Reason.INSPECT);
        return Utils.bytesToLong(value, register.getMinimumByteSize(),
            language.isBigEndian()) & 0xffffffffL;
    }

    private long mode(PcodeThread<byte[]> thread, Register register) {
        RegisterValue value = thread.getContext().getRegisterValue(register);
        return value.getUnsignedValueIgnoreMask().longValue() & 1L;
    }

    private void putWord(PcodeEmulator emulator, AddressSpace space,
            long address, long value) {
        byte[] bytes = new byte[] {
            (byte)value, (byte)(value >>> 8), (byte)(value >>> 16), (byte)(value >>> 24)
        };
        emulator.getSharedState().setVar(space, address, bytes.length, true, bytes);
    }

    private void putBytes(PcodeEmulator emulator, AddressSpace space,
            long address, byte[] bytes) {
        emulator.getSharedState().setVar(space, address, bytes.length, true, bytes);
    }

    @Override
    public void run() throws Exception {
        require(getScriptArgs().length == 1,
            "usage: RunNormBootServicePathProbe.java NORMBREC.BIN");
        byte[] image = Files.readAllBytes(Paths.get(getScriptArgs()[0]));
        require(image.length == 0x200,
            String.format("unexpected NORMBREC size: 0x%x", image.length));
        String hash = java.util.HexFormat.of().formatHex(
            MessageDigest.getInstance("SHA-256").digest(image));
        require(EXPECTED_SHA256.equals(hash), "NORMBREC SHA-256 mismatch: " + hash);

        SleighLanguage language = (SleighLanguage)currentProgram.getLanguage();
        AddressSpace space = language.getDefaultSpace();
        Register isa = language.getRegister("ISA_MODE");
        Register relp = language.getRegister("RELP");
        Register ra = language.getRegister("ra");
        Register v0 = language.getRegister("v0");
        Register a0 = language.getRegister("a0");
        Register a1 = language.getRegister("a1");
        Register a2 = language.getRegister("a2");
        Register a3 = language.getRegister("a3");
        require(isa != null && relp != null && ra != null && v0 != null
                && a0 != null && a1 != null && a2 != null && a3 != null,
            "MIPS language is missing a required register");

        PcodeEmulator emulator = new PcodeEmulator(language);
        emulator.getSharedState().setVar(space, BASE, image.length, true, image);
        putWord(emulator, space, SLOT_A8, TARGET_A8 | 1L);
        putWord(emulator, space, SLOT_A0, TARGET_A0 | 1L);
        putWord(emulator, space, SLOT_94, TARGET_94 | 1L);
        putWord(emulator, space, SLOT_A4, TARGET_A4 | 1L);
        putBytes(emulator, space, BUFFER, new byte[] {0, 0, 0, 0, 4, 0, 0, 0});
        putBytes(emulator, space, STACK - 0x1000, new byte[0x2000]);

        PcodeThread<byte[]> thread = emulator.newThread();
        PcodeUseropLibrary<byte[]> library = thread.getUseropLibrary();
        require(library.getUserops().containsKey("setISAMode"),
            "native MIPS setISAMode userop was not loaded");
        thread.getExecutor().execute(
            SleighProgramCompiler.compileProgram(language, "normboot-service-init",
                "sp = 0x9fc21000; ra = 0x00704001; "
                    + "a0 = 0; a1 = 0; a2 = 0; a3 = 0; v0 = 0;", library), library);
        RegisterValue mips16 = new RegisterValue(isa, BigInteger.ONE)
            .assign(relp, new RegisterValue(relp, BigInteger.ONE));
        thread.overrideContext(mips16);
        thread.overrideCounter(addr(space, ENTRY));

        long[] targets = {TARGET_A8, TARGET_94, TARGET_A4};
        long[] slots = {SLOT_A8, SLOT_94, SLOT_A4};
        List<String> calls = new ArrayList<>();
        boolean stopped = false;
        int steps = 0;
        for (; steps < MAX_STEPS; steps++) {
            long pc = thread.getCounter().getOffset() & 0xffffffffL;
            if (pc == STOP) {
                stopped = true;
                break;
            }
            int targetIndex = -1;
            for (int i = 0; i < targets.length; i++)
                if (pc == targets[i]) targetIndex = i;
            if (pc == TARGET_A0)
                throw new Exception("unexpected error-handler slot call in zero-return fixture");
            if (targetIndex >= 0) {
                require(mode(thread, isa) == 1 && mode(thread, relp) == 1,
                    String.format("expected MIPS16e at synthetic slot 0x%08x", slots[targetIndex]));
                long returnAddress = reg(thread, ra, language);
                require((returnAddress & 1L) == 1,
                    String.format("MIPS16e return address lacks mode tag: 0x%08x", returnAddress));
                calls.add(String.format(
                    "slot=0x%08x target=0x%08x args=%08x,%08x,%08x,%08x",
                    slots[targetIndex], pc, reg(thread, a0, language),
                    reg(thread, a1, language), reg(thread, a2, language),
                    reg(thread, a3, language)));
                thread.getState().setVar(v0,
                    emulator.getArithmetic().fromConst(0, v0.getMinimumByteSize()));
                thread.overrideContext(mips16);
                thread.overrideCounter(addr(space, returnAddress & ~1L));
                continue;
            }
            thread.stepInstruction();
        }

        require(stopped, "NORMBREC routine did not return within the step limit");
        require(calls.size() == 3, "unexpected call count: " + calls);
        require(calls.get(0).startsWith("slot=0xbfc002a8 target=0x00703000 "),
            "first call was not through the 0xbfc002a8 slot: " + calls.get(0));
        require(calls.get(0).endsWith("args=00000000,00001800,bfc10000,00000000"),
            "unexpected first call arguments: " + calls.get(0));
        require(calls.get(1).startsWith("slot=0xbfc00294 target=0x00703020 "),
            "second call was not through the 0xbfc00294 slot: " + calls.get(1));
        require(calls.get(1).endsWith("args=bfc10000,00000800,bfc10000,00000000"),
            "unexpected second call arguments: " + calls.get(1));
        require(calls.get(2).startsWith("slot=0xbfc002a4 target=0x00703060 "),
            "third call was not through the 0xbfc002a4 slot: " + calls.get(2));
        require(calls.get(2).endsWith("args=bfc10100,00703041,00000000,00000000"),
            "unexpected third call arguments: " + calls.get(2));
        for (String call : calls) println("NORMBREC SERVICE EDGE " + call);
        println(String.format(
            "NORMBREC SERVICE P-CODE PASS entry=0x%08x steps=%d fixture=u16_at_buffer_plus4_4 slot-effects=zero length-threshold-path=single-chunk",
            ENTRY, steps));
        println("NORMBREC SERVICE LIMIT synthetic-slot-targets no-ROM-or-boot-claim");
    }
}
