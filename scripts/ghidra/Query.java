// Ad-hoc queries on an analysed program: args <out.txt> <cmd> <addr> [<cmd> <addr> ...]
//   dec <addr>    decompile the function containing addr
//   xref <addr>   references to addr, with the containing function of each
//   callers <addr> the functions that call the function at addr, through its thunks too (in a shared
//                 library the callers reach an exported function through its PLT stub)
//   asm <addr>    disassembly of the function containing addr
// Run with -process <program> -noanalysis, so it takes seconds on a saved project.
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;

public class Query extends GhidraScript {
  @Override public void run() throws Exception {
    String[] a = getScriptArgs();
    PrintWriter o = new PrintWriter(a[0]);
    DecompInterface dec = new DecompInterface();
    dec.openProgram(currentProgram);
    for (int i = 1; i + 1 < a.length; i += 2) {
      var addr = toAddr(Long.parseLong(a[i + 1].replace("0x", ""), 16));
      Function f = getFunctionContaining(addr);
      o.println("=== " + a[i] + " " + addr + (f == null ? " (no function)" : " in " + f.getName() + " @" + f.getEntryPoint()));
      switch (a[i]) {
        case "mkdec":
          // Code Ghidra never made a function of: start after the previous rts + delay slot,
          // create the function there (in memory; -readOnly does not save it), then decompile.
          if (f == null) {
            var p = addr;
            while (!(currentProgram.getMemory().getShort(p) == 0x000b)) p = p.subtract(2);
            var start = p.add(4);
            disassemble(start);
            f = createFunction(start, null);
            o.println("  created " + (f == null ? "nothing" : f.getName()) + " at " + start);
          }
          // fall through
        case "dec":
          if (f != null) {
            var r = dec.decompileFunction(f, 120, monitor);
            o.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : "decompile failed: " + r.getErrorMessage());
          }
          break;
        case "xref":
          for (Reference r : getReferencesTo(addr)) {
            Function g = getFunctionContaining(r.getFromAddress());
            o.println("  " + r.getFromAddress() + " " + r.getReferenceType() + " " + (g == null ? "-" : g.getName()));
          }
          break;
        case "callers": {
          Function t = getFunctionAt(addr) != null ? getFunctionAt(addr) : f;
          if (t == null) break;
          java.util.List<ghidra.program.model.address.Address> ends = new java.util.ArrayList<>();
          ends.add(t.getEntryPoint());
          var thunks = t.getFunctionThunkAddresses(true);
          if (thunks != null) ends.addAll(java.util.Arrays.asList(thunks));
          java.util.Set<String> seen = new java.util.TreeSet<>();
          for (var e : ends)
            for (Reference r : getReferencesTo(e)) {
              Function g = getFunctionContaining(r.getFromAddress());
              if (g != null && !g.isThunk()) seen.add(g.getEntryPoint() + " " + g.getName() + (e.equals(t.getEntryPoint()) ? "" : " (via stub " + e + ")"));
            }
          for (String x : seen) o.println("  " + x);
          break;
        }
        case "asm":
          if (f != null)
            for (Instruction ins : currentProgram.getListing().getInstructions(f.getBody(), true))
              o.println("  " + ins.getAddress() + "  " + ins);
          break;
      }
    }
    dec.dispose();
    o.close();
  }
}
