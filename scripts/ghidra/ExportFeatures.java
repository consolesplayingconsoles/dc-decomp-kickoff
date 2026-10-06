// ExportFeatures.java <out.jsonl>: per-function features for matching a Katana executable against
// a later port of the same game that kept its symbols (references/port-symbols.md). Run it on both
// programs (-process <program> -noanalysis -readOnly).
// One JSON object per function: entry, name, size, calls (ordered target entries), strings,
// constants (scalars and literal-pool values, ints and floats as raw bits).
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.address.Address;
import ghidra.program.model.mem.Memory;
import java.io.PrintWriter;
import java.util.*;

public class ExportFeatures extends GhidraScript {
  String str(Address a) {
    Data d = getDataAt(a);
    if (d != null && d.hasStringValue()) {
      Object v = d.getValue();
      return v == null ? null : v.toString();
    }
    // undefined bytes: read a printable C string ourselves (never from code)
    try {
      Memory m = currentProgram.getMemory();
      if (m.getBlock(a) == null || m.getBlock(a).isExecute()) return null;
      StringBuilder sb = new StringBuilder();
      for (int i = 0; i < 200; i++) {
        byte b = m.getByte(a.add(i));
        if (b == 0) break;
        if (b < 0x20 || b > 0x7e) return null;
        sb.append((char) b);
      }
      return sb.length() >= 4 ? sb.toString() : null;
    } catch (Exception e) { return null; }
  }

  String esc(String s) {
    StringBuilder b = new StringBuilder("\"");
    for (char c : s.toCharArray()) {
      if (c == '"' || c == '\\') b.append('\\').append(c);
      else if (c < 0x20 || c > 0x7e) b.append(String.format("\\u%04x", (int) c));
      else b.append(c);
    }
    return b.append('"').toString();
  }

  @Override public void run() throws Exception {
    PrintWriter o = new PrintWriter(getScriptArgs()[0]);
    Memory mem = currentProgram.getMemory();
    int ptrSize = currentProgram.getDefaultPointerSize();
    FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
    while (it.hasNext() && !monitor.isCancelled()) {
      Function f = it.next();
      if (f.isThunk()) continue;
      List<String> calls = new ArrayList<>();
      LinkedHashSet<String> strs = new LinkedHashSet<>();
      List<Long> consts = new ArrayList<>();
      List<String> globs = new ArrayList<>();
      for (Instruction ins : currentProgram.getListing().getInstructions(f.getBody(), true)) {
        for (Reference r : ins.getReferencesFrom()) {
          Address t = r.getToAddress();
          if (r.getReferenceType().isCall()) {
            Function g = getFunctionAt(t);
            if (g != null && g.isThunk() && g.getThunkedFunction(true) != null) g = g.getThunkedFunction(true);
            calls.add(g == null ? t.toString() : g.getEntryPoint().toString());
            continue;
          }
          if (!r.getReferenceType().isData()) continue;
          // globals: a data address outside code (a port: referenced directly or through its GOT;
          // a Katana executable: the address held in a literal-pool word inside the code)
          try {
            ghidra.program.model.mem.MemoryBlock blk = mem.getBlock(t);
            if (blk != null && !blk.isExecute()) {
              if (getFunctionAt(t) == null && str(t) == null) globs.add(t.toString());
            } else if (blk != null && ptrSize == 4) {
              long v = mem.getInt(t) & 0xffffffffL;
              long ram = v & 0x1fffffffL;
              if (ram >= 0x0c000000L && ram < 0x0d000000L) {
                Address p = t.getNewAddress(v);
                if (getFunctionAt(p) == null && str(p) == null) globs.add(p.toString());
              }
            }
          } catch (Exception e) { }
          String s = str(t);
          if (s != null) { strs.add(s); continue; }
          // literal pool / pointer: one level of indirection
          try {
            long v = ptrSize == 8 ? mem.getLong(t) : (mem.getInt(t) & 0xffffffffL);
            Address p = t.getNewAddress(v);
            if (mem.contains(p)) {
              Function g = getFunctionAt(p);
              if (g != null && g.isThunk() && g.getThunkedFunction(true) != null) g = g.getThunkedFunction(true);
              if (g != null) { calls.add(g.getEntryPoint().toString()); continue; }
              String s2 = str(p);
              if (s2 != null) { strs.add(s2); continue; }
            } else if (r.getReferenceType().isRead()) {
              consts.add(mem.getInt(t) & 0xffffffffL);
            }
          } catch (Exception e) { }
        }
        for (int i = 0; i < ins.getNumOperands(); i++)
          for (Object x : ins.getOpObjects(i))
            if (x instanceof Scalar) {
              long v = ((Scalar) x).getUnsignedValue();
              if (v > 1 && v != 0xffffffffL) consts.add(v);
            }
      }
      StringBuilder b = new StringBuilder();
      b.append("{\"e\":\"").append(f.getEntryPoint()).append("\",\"n\":").append(esc(f.getName()))
       .append(",\"sz\":").append(f.getBody().getNumAddresses()).append(",\"c\":[");
      for (int i = 0; i < calls.size(); i++) b.append(i > 0 ? "," : "").append('"').append(calls.get(i)).append('"');
      b.append("],\"s\":[");
      int i = 0;
      for (String s : strs) b.append(i++ > 0 ? "," : "").append(esc(s));
      b.append("],\"k\":[");
      for (int j = 0; j < consts.size(); j++) b.append(j > 0 ? "," : "").append(consts.get(j));
      b.append("],\"g\":[");
      for (int j = 0; j < globs.size(); j++) b.append(j > 0 ? "," : "").append('"').append(globs.get(j)).append('"');
      b.append("]}");
      o.println(b);
    }
    o.close();
  }
}
