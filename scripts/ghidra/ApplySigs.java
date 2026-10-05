// Name functions from an ExportSigs table: args <sigs.txt> <result.txt> [apply].
// A function is named only when its full hash maps to exactly one name in the table AND exactly one
// function in this program carries that hash; otherwise it is reported as ambiguous, never guessed.
import ghidra.app.script.GhidraScript;
import ghidra.feature.fid.hash.FidHashQuad;
import ghidra.feature.fid.service.FidService;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;
import java.io.*;
import java.nio.file.*;
import java.util.*;

public class ApplySigs extends GhidraScript {
  @Override public void run() throws Exception {
    String[] a = getScriptArgs();
    boolean apply = a.length > 2 && a[2].equals("apply");
    Map<Long, Set<String>> byHash = new HashMap<>();
    for (String line : Files.readAllLines(Paths.get(a[0]))) {
      String[] p = line.trim().split("\\s+");
      if (p.length < 4) continue;
      byHash.computeIfAbsent(Long.parseUnsignedLong(p[0], 16), k -> new TreeSet<>()).add(p[3]);
    }
    FidService fid = new FidService();
    Map<Long, List<Function>> here = new HashMap<>();
    for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
      FidHashQuad h = fid.hashFunction(f);
      if (h != null && byHash.containsKey(h.getFullHash()))
        here.computeIfAbsent(h.getFullHash(), k -> new ArrayList<>()).add(f);
    }
    PrintWriter o = new PrintWriter(a[1]);
    int named = 0, ambiguous = 0;
    for (var e : here.entrySet()) {
      Set<String> names = byHash.get(e.getKey());
      List<Function> fs = e.getValue();
      if (names.size() == 1 && fs.size() == 1) {
        String n = names.iterator().next();
        o.println("MATCH " + fs.get(0).getEntryPoint() + " " + n);
        if (apply) fs.get(0).setName(n, SourceType.ANALYSIS);
        named++;
      } else {
        o.println("AMBIG " + names + " at " + fs.size() + " sites: " +
                  fs.stream().map(f -> f.getEntryPoint().toString()).reduce((x, y) -> x + "," + y).get());
        ambiguous++;
      }
    }
    Set<String> found = new HashSet<>();
    for (var e : here.keySet()) found.addAll(byHash.get(e));
    for (var s : byHash.values()) for (String n : s) if (!found.contains(n)) o.println("NOTFOUND " + n);
    o.close();
    println("ApplySigs: " + named + " named, " + ambiguous + " ambiguous, table " + byHash.size() + " hashes");
  }
}
