// Report Ghidra references to explicit resident-kernel function addresses.
// Arguments: comma-separated addresses.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import java.util.LinkedHashMap;
import java.util.Map;

public class FindFunctionRefs extends GhidraScript {
    @Override
    public void run() throws Exception {
        if (getScriptArgs().length != 1) {
            throw new Exception("usage: FindFunctionRefs.java 0xbfc0a408,0xbfc0a944");
        }
        Map<Long, Integer> counts = new LinkedHashMap<>();
        var addressSpace = currentProgram.getAddressFactory().getDefaultAddressSpace();
        for (String text : getScriptArgs()[0].split(",")) {
            long value = Long.decode(text) & 0xffffffffL;
            Address target = addressSpace.getAddress(String.format("0x%08x", value));
            int count = 0;
            ReferenceIterator references = currentProgram.getReferenceManager()
                .getReferencesTo(target);
            while (references.hasNext()) {
                Reference reference = references.next();
                println(String.format(
                    "FUNCTION_REF target=0x%08x from=%s kind=%s operand=%d",
                    value, reference.getFromAddress(), reference.getReferenceType(),
                    reference.getOperandIndex()));
                count++;
            }
            counts.put(value, count);
        }
        for (Map.Entry<Long, Integer> entry : counts.entrySet()) {
            println(String.format("FUNCTION_TOTAL target=0x%08x count=%d",
                entry.getKey(), entry.getValue()));
        }
    }
}
