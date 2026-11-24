// Probe native Ghidra MIPS ISA-mode transitions in the extracted template helper.
// ROM helper effects and the callback body are deliberately synthetic/omitted.
import ghidra.app.plugin.processors.sleigh.SleighLanguage;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.emu.PcodeEmulator;
import ghidra.pcode.emu.PcodeThread;
import ghidra.pcode.exec.PcodeExecutorStatePiece.Reason;
import ghidra.pcode.exec.SleighProgramCompiler;
import ghidra.pcode.utils.Utils;
import ghidra.program.model.address.AddressSpace;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;
import java.math.BigInteger;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class RunKernelInitNativeModeProbe extends GhidraScript {
    private static final long ENTRY = 0xbfc322f8L;
    private static final long STOP_CALLBACK = 0x9fc27f00L;
    private static final long RAM_BASE = 0x9fc10000L;
    private static final long RAM_END = 0x9fc30000L;
    private static final long ROM_CLEAR = 0xbfc045f4L;
    private static final long ROM_COPY = 0xbfc04634L;
    private static final int MAX_STEPS = 12000;
    // Little-endian MIPS16e `jrc ra` (no delay slot). This synthetic return
    // stub exercises native MIPS16 -> MIPS32 switching; it is not ROM code.
    private static final byte[] MIPS16_RETURN_STUB = { (byte)0xa0, (byte)0xe8 };

    private void require(boolean condition, String message) throws Exception {
        if (!condition) throw new Exception(message);
    }

    private long reg(PcodeThread<byte[]> thread, Register register,
            SleighLanguage language) {
        byte[] value = thread.getState().getVar(register, Reason.INSPECT);
        return Utils.bytesToLong(value, register.getMinimumByteSize(),
            language.isBigEndian()) & 0xffffffffL;
    }

    private long word(PcodeThread<byte[]> thread, AddressSpace space, long at,
            SleighLanguage language) {
        byte[] bytes = thread.getState().getVar(space, at, 4, true, Reason.INSPECT);
        return Utils.bytesToLong(bytes, 4, language.isBigEndian()) & 0xffffffffL;
    }

    private long mode(PcodeThread<byte[]> thread, Register isa) {
        RegisterValue value = thread.getContext().getRegisterValue(isa);
        return value.getUnsignedValueIgnoreMask().longValue() & 1L;
    }

    private long relpMode(PcodeThread<byte[]> thread, Register relp) {
        RegisterValue value = thread.getContext().getRegisterValue(relp);
        return value.getUnsignedValueIgnoreMask().longValue() & 1L;
    }

    private void putWord(PcodeEmulator emulator, AddressSpace space,
            long at, long value) {
        byte[] bytes = new byte[] {
            (byte)value, (byte)(value >>> 8), (byte)(value >>> 16), (byte)(value >>> 24)
        };
        emulator.getSharedState().setVar(space, at, bytes.length, true, bytes);
    }

    private void copy(PcodeEmulator emulator, AddressSpace space,
            long destination, long source, int length) {
        byte[] bytes = emulator.getSharedState().getVar(space, source, length,
            true, Reason.INSPECT);
        emulator.getSharedState().setVar(space, destination, length, true, bytes);
    }

    @Override
    public void run() throws Exception {
        if (getScriptArgs().length < 1 || getScriptArgs().length > 2)
            throw new Exception("usage: RunKernelInitNativeModeProbe.java KER_INIT.BIN [forward|reverse|seeded]");
        String copyMode = getScriptArgs().length == 2 ? getScriptArgs()[1] : "forward";
        require(copyMode.equals("forward") || copyMode.equals("reverse") || copyMode.equals("seeded"),
            "copy mode must be forward, reverse, or seeded");
        SleighLanguage language = (SleighLanguage)currentProgram.getLanguage();
        AddressSpace space = language.getDefaultSpace();
        Register isa = language.getRegister("ISA_MODE");
        Register relp = language.getRegister("RELP");
        Register ra = language.getRegister("ra");
        Register v0 = language.getRegister("v0");
        require(isa != null && relp != null && ra != null && v0 != null,
            "MIPS language is missing a required register");

        byte[] image = java.nio.file.Files.readAllBytes(
            java.nio.file.Paths.get(getScriptArgs()[0]));
        require(image.length > 0x800, "ker_init.bin truncated before FUN_bfc322f8");
        PcodeEmulator emulator = new PcodeEmulator(language);
        emulator.getSharedState().setVar(space, 0xbfc32000L, image.length, true, image);
        emulator.getSharedState().setVar(space, RAM_BASE,
            (int)(RAM_END - RAM_BASE), true, new byte[(int)(RAM_END - RAM_BASE)]);
        emulator.getSharedState().setVar(space, ROM_CLEAR,
            MIPS16_RETURN_STUB.length, true, MIPS16_RETURN_STUB);
        emulator.getSharedState().setVar(space, ROM_COPY,
            MIPS16_RETURN_STUB.length, true, MIPS16_RETURN_STUB);

        // Synthetic source image and callback slot. These are fixtures, not
        // claims about the absent ROM clear/copy helper effects.
        byte[] source = new byte[0x208];
        Arrays.fill(source, (byte)0x5a);
        source[0] = 0x00;
        source[1] = 0x7f;
        source[2] = (byte)0xc2;
        source[3] = (byte)0x9f;
        emulator.getSharedState().setVar(space, 0x9fc12000L, source.length, true, source);
        if (copyMode.equals("seeded"))
            putWord(emulator, space, 0x9fc1aad8L, STOP_CALLBACK);

        PcodeThread<byte[]> thread = emulator.newThread();
        var library = thread.getUseropLibrary();
        require(library.getUserops().containsKey("setISAMode"),
            "native MIPS setISAMode userop was not loaded");
        thread.getExecutor().execute(SleighProgramCompiler.compileProgram(language,
            "kernel-template-init",
            "sp = 0x9fc2ff00; s8 = 0x9fc2fe00; a0 = 0x01010101; "
                + "a1 = 0x02020202; a2 = 0x03030303; a3 = 0x04040404; "
                + "ra = 0x00700100; v0 = 0;", library), library);
        // ISA_MODE=0 selects 32-bit instructions; RELP=1 keeps the processor
        // configured for MIPS16e when a tagged function pointer switches mode.
        RegisterValue mips32 = new RegisterValue(isa, BigInteger.ZERO)
            .assign(relp, new RegisterValue(relp, BigInteger.ONE));
        thread.overrideContext(mips32);
        thread.overrideCounter(space.getAddress(ENTRY));

        List<String> calls = new ArrayList<>();
        boolean reachedCallback = false;
        boolean reachedNullDispatch = false;
        long callbackA0 = 0, callbackA1 = 0, callbackA2 = 0, callbackA3 = 0;
        int steps = 0;
        for (; steps < MAX_STEPS; steps++) {
            long address = thread.getCounter().getOffset() & 0xffffffffL;
            if (address == 0 && copyMode.equals("reverse")) {
                require(word(thread, space, 0x9fc1aad8L, language) == 0,
                    "reverse-copy control unexpectedly populated callback slot");
                reachedNullDispatch = true;
                println("KERNEL TEMPLATE COPY CONTROL PASS direction=reverse callback-slot=0 indirect-target=0");
                break;
            }
            if (address == STOP_CALLBACK) {
                require(mode(thread, isa) == 0 && relpMode(thread, relp) == 1,
                    String.format("expected MIPS32/MIPS16e callback context, ISA_MODE=%d RELP=%d",
                        mode(thread, isa), relpMode(thread, relp)));
                reachedCallback = true;
                callbackA0 = reg(thread, language.getRegister("a0"), language);
                callbackA1 = reg(thread, language.getRegister("a1"), language);
                callbackA2 = reg(thread, language.getRegister("a2"), language);
                callbackA3 = reg(thread, language.getRegister("a3"), language);
                break;
            }
            if (address == ROM_CLEAR || address == ROM_COPY) {
                require(mode(thread, isa) == 1 && relpMode(thread, relp) == 1,
                    String.format("expected native MIPS16e ROM entry at %08x, ISA_MODE=%d RELP=%d",
                        address, mode(thread, isa), relpMode(thread, relp)));
                long returnAddress = reg(thread, ra, language);
                require((returnAddress & 3L) == 0,
                    String.format("expected aligned MIPS32 return address: %08x", returnAddress));
                String call = String.format("%08x:mode=%d:ra=%08x:%08x,%08x,%08x,%08x",
                    address, mode(thread, isa), returnAddress,
                    reg(thread, language.getRegister("a0"), language),
                    reg(thread, language.getRegister("a1"), language),
                    reg(thread, language.getRegister("a2"), language),
                    reg(thread, language.getRegister("a3"), language));
                calls.add(call);
                println("NATIVE KERNEL ROM EDGE " + call);
                if (address == ROM_COPY && !copyMode.equals("seeded")) {
                    long a0 = reg(thread, language.getRegister("a0"), language);
                    long a1 = reg(thread, language.getRegister("a1"), language);
                    long a2 = reg(thread, language.getRegister("a2"), language);
                    require(a2 <= 0x1000, String.format("implausible copy length %08x", a2));
                    if (copyMode.equals("forward")) {
                        copy(emulator, space, a0, a1, (int)a2);
                        println(String.format("SYNTHETIC ROM COPY direction=forward dst=%08x src=%08x len=%08x", a0, a1, a2));
                    } else {
                        copy(emulator, space, a1, a0, (int)a2);
                        println(String.format("SYNTHETIC ROM COPY direction=reverse dst=%08x src=%08x len=%08x", a1, a0, a2));
                    }
                }
                thread.getState().setVar(v0,
                    emulator.getArithmetic().fromConst(0, v0.getMinimumByteSize()));
                // The absent routine's result remains synthetic, but execute
                // a real MIPS16e return instruction so Ghidra performs the
                // ISA_MODE transition from the tagged/untagged RA naturally.
                thread.stepInstruction();
                require(thread.getCounter().getOffset() == returnAddress
                        && mode(thread, isa) == 0 && relpMode(thread, relp) == 1,
                    String.format("synthetic MIPS16 return failed: pc=%08x ISA_MODE=%d RELP=%d expected-ra=%08x",
                        thread.getCounter().getOffset(), mode(thread, isa),
                        relpMode(thread, relp), returnAddress));
                continue;
            }
            if (address < ENTRY || address >= 0xbfc33000L
                    || (address >= RAM_BASE && address < RAM_END))
                throw new Exception(String.format("unexpected control flow pc=%08x mode=%d",
                    address, mode(thread, isa)));
            thread.stepInstruction();
        }

        require(copyMode.equals("reverse") ? reachedNullDispatch : reachedCallback,
            "did not reach the expected callback/negative-control boundary within step limit");
        if (reachedCallback)
            require(word(thread, space, 0x9fc1aad8L, language) == STOP_CALLBACK,
                "callback slot does not contain the expected synthetic pointer");
        String[] expected = {
            "9fc1a48c,00000000,000007f4,",
            "9fc1aad8,9fc12000,00000014,",
            "9fc1a980,9fc12014,00000020,",
            "bfc080f8,9fc12200,00000004,"
        };
        long[] expectedRa = { 0xbfc32348L, 0xbfc3236cL, 0xbfc32390L, 0xbfc323b4L };
        require(calls.size() == expected.length,
            "expected exactly four ROM boundaries before callback: " + calls);
        for (int i = 0; i < expected.length; i++) {
            long target = i == 0 ? ROM_CLEAR : ROM_COPY;
            String prefix = String.format("%08x:mode=1:", target);
            require(calls.get(i).startsWith(prefix)
                    && calls.get(i).contains(":" + expected[i]),
                "unexpected native ROM call " + i + ": " + calls.get(i));
            int raAt = calls.get(i).indexOf(":ra=") + 4;
            long returnAddress = Long.parseUnsignedLong(
                calls.get(i).substring(raAt, raAt + 8), 16);
            require(returnAddress == expectedRa[i] && (returnAddress & 3L) == 0
                    && returnAddress >= ENTRY
                    && returnAddress < 0xbfc32400L,
                "unexpected return address for call " + i + ": " + calls.get(i));
        }
        if (reachedCallback) {
            require(callbackA0 == 0xfffffff0L && callbackA1 == 0xbfc0855dL
                    && callbackA2 == 0,
                String.format("unexpected callback args %08x,%08x,%08x,%08x",
                    callbackA0, callbackA1, callbackA2, callbackA3));
            println(String.format(
                "KERNEL TEMPLATE ISA MODE PASS mode=%s entry=%08x callback=%08x "
                    + "rom-entry-isa-mode=1 relp=1 callback-isa-mode=%d relp=1 "
                    + "synthetic-mips16-return-stubs=2 "
                    + "args=%08x,%08x,%08x,%08x steps=%d",
                copyMode, ENTRY, STOP_CALLBACK, mode(thread, isa), callbackA0, callbackA1,
                callbackA2, callbackA3, steps));
        }
    }
}
