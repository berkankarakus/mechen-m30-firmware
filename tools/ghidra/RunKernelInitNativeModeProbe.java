// Probe native Ghidra MIPS ISA-mode transitions in the extracted template helper.
// ROM helper effects and the callback body are deliberately synthetic/omitted.
import ghidra.app.plugin.processors.sleigh.SleighLanguage;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.emu.PcodeEmulator;
import ghidra.pcode.emu.PcodeThread;
import ghidra.pcode.exec.PcodeExecutorStatePiece.Reason;
import ghidra.pcode.exec.SleighProgramCompiler;
import ghidra.pcode.utils.Utils;
import ghidra.program.model.address.Address;
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

    private void putWord(PcodeEmulator emulator, AddressSpace space,
            long at, long value) {
        byte[] bytes = new byte[] {
            (byte)value, (byte)(value >>> 8), (byte)(value >>> 16), (byte)(value >>> 24)
        };
        emulator.getSharedState().setVar(space, at, bytes.length, true, bytes);
    }

    @Override
    public void run() throws Exception {
        if (getScriptArgs().length != 1)
            throw new Exception("usage: RunKernelInitNativeModeProbe.java KER_INIT.BIN");
        SleighLanguage language = (SleighLanguage)currentProgram.getLanguage();
        AddressSpace space = language.getDefaultSpace();
        Register isa = language.getRegister("ISA_MODE");
        Register relp = language.getRegister("RELP");
        Register sp = language.getRegister("sp");
        Register ra = language.getRegister("ra");
        Register v0 = language.getRegister("v0");
        Register pc = language.getRegister("pc");
        require(isa != null && relp != null && sp != null && ra != null
                && v0 != null && pc != null,
            "MIPS language is missing a required register");

        byte[] image = java.nio.file.Files.readAllBytes(
            java.nio.file.Paths.get(getScriptArgs()[0]));
        require(image.length > 0x800, "ker_init.bin truncated before FUN_bfc322f8");
        PcodeEmulator emulator = new PcodeEmulator(language);
        emulator.getSharedState().setVar(space, 0xbfc32000L, image.length, true, image);
        emulator.getSharedState().setVar(space, RAM_BASE,
            (int)(RAM_END - RAM_BASE), true, new byte[(int)(RAM_END - RAM_BASE)]);

        // Synthetic source image and callback slot. These are fixtures, not
        // claims about the absent ROM clear/copy helper effects.
        byte[] source = new byte[0x208];
        Arrays.fill(source, (byte)0x5a);
        source[0] = 0x00;
        source[1] = 0x7f;
        source[2] = (byte)0xc2;
        source[3] = (byte)0x9f;
        emulator.getSharedState().setVar(space, 0x9fc12000L, source.length, true, source);
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
        RegisterValue mips32 = new RegisterValue(isa, BigInteger.ZERO)
            .assign(relp, new RegisterValue(relp, BigInteger.ZERO));
        thread.overrideContext(mips32);
        thread.overrideCounter(space.getAddress(ENTRY));

        List<String> calls = new ArrayList<>();
        boolean reachedCallback = false;
        long callbackA0 = 0, callbackA1 = 0, callbackA2 = 0, callbackA3 = 0;
        int steps = 0;
        for (; steps < MAX_STEPS; steps++) {
            long address = thread.getCounter().getOffset() & 0xffffffffL;
            if (address == STOP_CALLBACK) {
                require(mode(thread, isa) == 0,
                    String.format("expected native MIPS32 callback entry, mode=%d",
                        mode(thread, isa)));
                reachedCallback = true;
                callbackA0 = reg(thread, language.getRegister("a0"), language);
                callbackA1 = reg(thread, language.getRegister("a1"), language);
                callbackA2 = reg(thread, language.getRegister("a2"), language);
                callbackA3 = reg(thread, language.getRegister("a3"), language);
                break;
            }
            if (address == ROM_CLEAR || address == ROM_COPY) {
                require(mode(thread, isa) == 1,
                    String.format("expected native MIPS16 ROM entry at %08x, mode=%d",
                        address, mode(thread, isa)));
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
                thread.getState().setVar(v0,
                    emulator.getArithmetic().fromConst(0, v0.getMinimumByteSize()));
                // Return from each absent ROM helper to the actual MIPS32
                // caller boundary, explicitly modeling the mode transition.
                thread.overrideContext(mips32);
                thread.overrideCounter(space.getAddress(returnAddress));
                continue;
            }
            if (address < ENTRY || address >= 0xbfc33000L
                    || (address >= RAM_BASE && address < RAM_END))
                throw new Exception(String.format("unexpected control flow pc=%08x mode=%d",
                    address, mode(thread, isa)));
            thread.stepInstruction();
        }

        require(reachedCallback, "did not reach callback within step limit");
        require(word(thread, space, 0x9fc1aad8L, language) == STOP_CALLBACK,
            "synthetic callback slot changed before indirect call");
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
        require(callbackA0 == 0xfffffff0L && callbackA1 == 0xbfc0855dL
                && callbackA2 == 0,
            String.format("unexpected callback args %08x,%08x,%08x,%08x",
                callbackA0, callbackA1, callbackA2, callbackA3));
        for (String call : calls) println("NATIVE KERNEL ROM EDGE " + call);
        println(String.format(
            "KERNEL TEMPLATE ISA MODE PASS entry=%08x callback=%08x rom-entry-mode=1 "
                + "callback-mode=%d synthetic-mips32-returns=4 "
                + "args=%08x,%08x,%08x,%08x steps=%d",
            ENTRY, STOP_CALLBACK, mode(thread, isa), callbackA0, callbackA1,
            callbackA2, callbackA3, steps));
    }
}
