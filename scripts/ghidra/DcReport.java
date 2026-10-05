// Post-analysis report: function/string inventory plus string xrefs, written to args[0].
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.data.StringDataInstance;
import ghidra.program.model.symbol.Reference;
import java.io.PrintWriter;
public class DcReport extends GhidraScript {
  @Override public void run() throws Exception {
    PrintWriter o = new PrintWriter(getScriptArgs()[0]);
    FunctionManager fm = currentProgram.getFunctionManager();
    o.println("FUNCTIONS " + fm.getFunctionCount());
    for (Function f : fm.getFunctions(true))
      o.println("F " + f.getEntryPoint() + " " + f.getBody().getNumAddresses() + " " + f.getName());
    for (Data d : currentProgram.getListing().getDefinedData(true)) {
      if (!d.hasStringValue()) continue;
      String s = StringDataInstance.getStringDataInstance(d).getStringValue();
      if (s == null || s.length() < 5) continue;
      StringBuilder fns = new StringBuilder();
      for (Reference r : getReferencesTo(d.getAddress())) {
        Function f = getFunctionContaining(r.getFromAddress());
        fns.append(f == null ? r.getFromAddress().toString() : f.getName()).append(',');
      }
      o.println("S " + d.getAddress() + " [" + fns + "] " + s.replace('\n', ' '));
    }
    o.close();
  }
}
