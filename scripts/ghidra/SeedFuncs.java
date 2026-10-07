// Seed functions the analysis cannot reach on its own: args <addrs.txt> (one hex address per line,
// '#' comments allowed). Run as a -preScript before analysis: each address is disassembled and made a
// function, so auto-analysis then follows its calls too. Addresses that do not decode are skipped.
import ghidra.app.script.GhidraScript;
import java.nio.file.*;

public class SeedFuncs extends GhidraScript {
  @Override public void run() throws Exception {
    int ok = 0, bad = 0;
    for (String line : Files.readAllLines(Paths.get(getScriptArgs()[0]))) {
      String s = line.split("#")[0].trim();
      if (s.isEmpty()) continue;
      var addr = toAddr(Long.parseLong(s.replace("0x", ""), 16));
      if (getFunctionAt(addr) != null) continue;
      if (disassemble(addr) && createFunction(addr, null) != null) ok++; else bad++;
    }
    println("SeedFuncs: " + ok + " seeded, " + bad + " skipped");
  }
}
