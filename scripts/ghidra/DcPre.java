// Pre-analysis: seed the entry point (the image base) and turn on the instruction finder for a raw
// Dreamcast 1ST_READ.BIN. Import at the base the binary was linked for (see linkbase.py).
import ghidra.app.script.GhidraScript;
public class DcPre extends GhidraScript {
  @Override public void run() throws Exception {
    setAnalysisOption(currentProgram, "Aggressive Instruction Finder", "true");
    var entry = currentProgram.getImageBase();
    disassemble(entry);
    createFunction(entry, "_start");
    addEntryPoint(entry);
  }
}
