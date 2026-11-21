// Trace the confirmation control request in setting.ap; all resident UI calls
// are intercepted and no firmware/device state is changed.
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

public class RunSettingConfirmProbe extends GhidraScript {
    private static final long ENTRY = 0x489146e8L;
    private static final long MODE_HELPER = 0x48914a10L;
    private static final long STOP = 0x700300L;
    private static final long RAM = 0x10000000L;
    private static final long STACK = RAM + 0x3000L;
    private static final long SYSRAM = 0x9fc00000L;
    private static final long[] API_TARGETS = {
        0x48b54679L, 0x48b5463dL, 0x48454841L, 0x484547adL,
        0xbfc16589L, 0x48a14601L, 0x48454601L, 0xbfc16585L,
        0x4845473dL
    };

    private Address addr(long value) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(value);
    }

    private String hex(long value) {
        return String.format("0x%08x", value & 0xffffffffL);
    }

    private void addRam(Memory memory, long start, long size, String name) throws Exception {
        MemoryBlock block = memory.createInitializedBlock(
            name, addr(start), new ByteArrayInputStream(new byte[(int)size]), size, monitor, false
        );
        block.setRead(true);
        block.setWrite(true);
        block.setExecute(true);
    }

    private String dumpStack(EmulatorHelper emu, long address, int length) throws Exception {
        if (address < STACK - 0x1000 || address + length > STACK + 0x1000) {
            return "<outside-stack:" + hex(address) + ">";
        }
        byte[] bytes = emu.readMemory(addr(address), length);
        StringBuilder result = new StringBuilder();
        for (byte value : bytes) {
            if (result.length() > 0) result.append(' ');
            result.append(String.format("%02x", value & 0xff));
        }
        return result.toString();
    }

    private int byteAt(EmulatorHelper emu, long address) throws Exception {
        return emu.readMemory(addr(address), 1)[0] & 0xff;
    }

    private boolean isZeroBuffer(EmulatorHelper emu, long address, int length) throws Exception {
        for (int i = 0; i < length; i++) {
            if (byteAt(emu, address + i) != 0) return false;
        }
        return true;
    }

    private long wordAt(EmulatorHelper emu, long address) throws Exception {
        byte[] bytes = emu.readMemory(addr(address), 4);
        return (bytes[0] & 0xffL) | ((bytes[1] & 0xffL) << 8)
            | ((bytes[2] & 0xffL) << 16) | ((bytes[3] & 0xffL) << 24);
    }

    @Override
    public void run() throws Exception {
        int input = getScriptArgs().length == 0 ? 1 : Integer.decode(getScriptArgs()[0]);
        Memory memory = currentProgram.getMemory();
        addRam(memory, RAM, 0x4000, "setting_confirm_probe_ram");
        addRam(memory, SYSRAM, 0x20000, "setting_confirm_probe_sysram");
        memory.setBytes(addr(SYSRAM + 0x15601), new byte[] {0});
        memory.setBytes(addr(SYSRAM + 0x1578e), new byte[] {1});

        EmulatorHelper emu = new EmulatorHelper(currentProgram);
        Register isa = currentProgram.getRegister("ISA_MODE");
        try {
            emu.registerCallOtherCallback("setISAMode", new BreakCallBack() {
                @Override public boolean pcodeCallback(PcodeOpRaw op) { return true; }
            });
            emu.setContextRegister(isa, BigInteger.ONE);
            emu.writeRegister("sp", STACK);
            emu.writeRegister("ra", STOP | 1L);
            emu.writeRegister("a0", input);
            emu.writeRegister("a1", 0);
            emu.writeRegister("a2", 0);
            emu.writeRegister("a3", 0);
            emu.writeRegister("s1", 0);
            emu.writeRegister("pc", ENTRY);

            boolean sawTextId = false;
            boolean sawEntryControl = false;
            for (int steps = 0; steps < 100000; steps++) {
                long pc = emu.readRegister("pc").longValue() & 0xffffffffL;
                // MIPS16 return pointers may have bit 0 set. The context register
                // carries the mode, so normalize the emulator PC before decoding.
                if ((pc & 1L) != 0) {
                    pc &= ~1L;
                    emu.writeRegister("pc", pc);
                }
                if (pc == STOP) {
                    throw new Exception("confirmation API was not reached");
                }
                if (pc == MODE_HELPER) {
                    emu.writeRegister("v0", 1);
                    emu.writeRegister("pc", emu.readRegister("ra").longValue() & ~1L);
                    continue;
                }

                boolean handled = false;
                for (long target : API_TARGETS) {
                    if (pc != (target & ~1L)) continue;
                    long a0 = emu.readRegister("a0").longValue() & 0xffffffffL;
                    long a1 = emu.readRegister("a1").longValue() & 0xffffffffL;
                    long a2 = emu.readRegister("a2").longValue() & 0xffffffffL;
                    long a3 = emu.readRegister("a3").longValue() & 0xffffffffL;
                    String detail = "";
                    if (target == 0x48b54679L) {
                        if (a0 != 0x85) throw new Exception("unexpected prompt text ID " + hex(a0));
                        sawTextId = true;
                    }
                    if (target == 0x48a14601L) {
                        if (!sawTextId) throw new Exception("confirmation request preceded text ID");
                        if (byteAt(emu, a0) != 0x0a || byteAt(emu, a0 + 1) != 0x10
                            || byteAt(emu, a0 + 2) != 1 || wordAt(emu, a1) != 0x010100faL
                            || wordAt(emu, a1 + 4) != 0x48554680L) {
                            throw new Exception("confirmation payload mismatch: control="
                                + dumpStack(emu, a0, 8) + " data=" + dumpStack(emu, a1, 16));
                        }
                        detail = " control=" + dumpStack(emu, a0, 8)
                            + " data=" + dumpStack(emu, a1, 16);
                    }
                    if (target == 0xbfc16589L && input == 0
                        && a3 == 2 && byteAt(emu, a0) == 0x09
                        && byteAt(emu, a0 + 1) == 0x10
                        && byteAt(emu, a0 + 2) == 1) {
                        sawEntryControl = true;
                    }
                    println("UI API " + hex(target) + " args=" + hex(a0) + ","
                        + hex(a1) + "," + hex(a2) + "," + hex(a3) + detail);
                    if (target == 0xbfc16585L && input == 0 && sawEntryControl
                        && a0 == 6 && a3 == 0x19) {
                        if (steps != 178 || a1 != RAM + 0x2f68 || a2 != 0
                            || !isZeroBuffer(emu, a1, 8)) {
                            throw new Exception("unexpected event-poll boundary: steps=" + steps
                                + " args=" + hex(a0) + "," + hex(a1) + "," + hex(a2)
                                + "," + hex(a3) + " buffer=" + dumpStack(emu, a1, 8));
                        }
                        println("SETTING EVENT POLL BOUNDARY PASS steps=" + steps
                            + " control=0x1009 event-buffer-before-call="
                            + dumpStack(emu, a1, 8));
                        return;
                    }
                    if (target == 0x48a14601L) {
                        println("SETTING CONFIRM REQUEST PASS steps=" + steps
                            + " control=0x100a status=1 field-capacity=250 payload=0x48554680");
                        return;
                    }
                    emu.writeRegister("v0", 0);
                    emu.writeRegister("pc", emu.readRegister("ra").longValue() & ~1L);
                    handled = true;
                    break;
                }
                if (handled) continue;
                if (!emu.step(monitor)) {
                    throw new Exception("emulation stopped at " + hex(pc) + ": " + emu.getLastError());
                }
            }
            throw new Exception("step limit reached at " + hex(emu.readRegister("pc").longValue()));
        } finally {
            emu.dispose();
        }
    }
}
