// Export function-ID hashes of named functions: args <names.txt> <sigs.txt>.
// names.txt lines: "<hex addr> <name>" (addresses in this program). Each address gets a function
// (created if missing) and that name; sigs.txt gets "fullHash specificHash codeUnits name" per function.
import ghidra.app.script.GhidraScript;
import ghidra.feature.fid.hash.FidHashQuad;
import ghidra.feature.fid.service.FidService;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;
import java.io.*;
import java.nio.file.*;

public class ExportSigs extends GhidraScript {
  @Override public void run() throws Exception {
    String[] a = getScriptArgs();
    // Folder mode (one headless run over many programs): <names-dir> <sigs-dir>, each program
    // reads <names-dir>/<program>.names and writes <sigs-dir>/<program>.sigs.
    String names = a[0], sigs = a[1];
    if (Files.isDirectory(Paths.get(names))) {
      String base = currentProgram.getName().replaceAll("\\.elf$", "");
      names = names + "/" + base + ".names";
      sigs = sigs + "/" + base + ".sigs";
    }
    FidService fid = new FidService();
    PrintWriter o = new PrintWriter(sigs);
    int ok = 0, miss = 0;
    for (String line : Files.readAllLines(Paths.get(names))) {
      String[] p = line.trim().split("\\s+");
      if (p.length < 2) continue;
      var addr = toAddr(Long.parseLong(p[0], 16));
      disassemble(addr);
      Function f = getFunctionAt(addr);
      if (f == null) f = createFunction(addr, p[1]);
      if (f == null) { println("no function at " + p[0] + " " + p[1]); miss++; continue; }
      f.setName(p[1], SourceType.IMPORTED);
      FidHashQuad h = fid.hashFunction(f);
      if (h == null) { miss++; continue; }                     // too short to hash
      o.printf("%016x %016x %d %s%n", h.getFullHash(), h.getSpecificHash(), h.getCodeUnitSize(), p[1]);
      ok++;
    }
    o.close();
    println("ExportSigs: " + ok + " hashed, " + miss + " skipped");
  }
}
