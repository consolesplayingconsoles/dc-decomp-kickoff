// Give the SDK's named functions their real prototypes, and the program the SDK's structs: parse
// the SDK's C headers into the program's data types, then apply every FunctionDefinition whose
// name matches a function. args: <include dir> [<include dir>...] [-Dname[=value]...]
// The first include dir is scanned for *.h (top level); every dir is also an include path. A
// function already carrying a user-set signature is left alone. Prints what parsed and what applied.
import java.io.File;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.app.cmd.function.ApplyFunctionSignatureCmd;
import ghidra.app.util.cparser.C.CParserUtils;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.Data;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.SourceType;

public class ApplyHeaders extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        List<String> dirs = new ArrayList<>(), defs = new ArrayList<>();
        for (String s : a) (s.startsWith("-D") ? defs : dirs).add(s);
        if (dirs.isEmpty()) { printerr("ApplyHeaders: no include dir"); return; }
        // the umbrella headers first (they define the base types the rest rely on), then the others
        List<String> files = new ArrayList<>();
        for (String first : new String[] {"sg_xpt.h", "shinobi.h", "kamui2.h", "ninja.h"}) {
            File f = new File(dirs.get(0), first);
            if (f.isFile()) files.add(f.getAbsolutePath());
        }
        // then the headers that include the most others first: each include chain is then read once,
        // whole, in a fresh preprocessor, before its parts are read on their own
        File[] top = new File(dirs.get(0)).listFiles();
        List<File> rest = new ArrayList<>();
        for (File f : top)
            if (f.isFile() && f.getName().toLowerCase().endsWith(".h") && !f.getName().toLowerCase().startsWith("sh4_")
                    && !files.contains(f.getAbsolutePath()))
                rest.add(f);
        Map<File, Integer> includes = new HashMap<>();
        for (File f : rest) {
            int n = 0;
            try { for (String l : java.nio.file.Files.readAllLines(f.toPath(), java.nio.charset.StandardCharsets.ISO_8859_1)) if (l.trim().startsWith("#include")) n++; } catch (Exception e) { }
            includes.put(f, n);
        }
        rest.sort((x, y) -> includes.get(y) - includes.get(x) != 0 ? includes.get(y) - includes.get(x) : x.getName().compareTo(y.getName()));
        for (File f : rest) files.add(f.getAbsolutePath());
        DataTypeManager dtm = currentProgram.getDataTypeManager();
        int before = dtm.getDataTypeCount(true);
        // one parse per header: a construct the parser cannot read costs that header, not the rest.
        // Two passes: a header that uses a type another header defines later parses on the second.
        List<String> failed = new ArrayList<>(files);
        for (int pass = 1; pass <= 2 && !failed.isEmpty(); pass++) {
            List<String> again = new ArrayList<>();
            for (String file : failed) {
                try {
                    CParserUtils.parseHeaderFiles(new DataTypeManager[] {dtm}, new String[] {file},
                        dirs.toArray(new String[0]), defs.toArray(new String[0]), dtm, monitor);
                } catch (Exception e) {
                    again.add(file);
                    if (pass == 2) {
                        String m = e.getMessage() == null ? "" : e.getMessage().replace("\n", " | ");
                        println("  parser: " + new File(file).getName() + ": " + (m.length() > 300 ? m.substring(0, 300) : m));
                    }
                }
            }
            failed = again;
        }
        println("ApplyHeaders: parsed " + files.size() + " headers (" + failed.size() + " with errors), " + (dtm.getDataTypeCount(true) - before) + " data types added");
        Map<String, FunctionDefinition> defsByName = new HashMap<>();
        Iterator<DataType> it = dtm.getAllDataTypes();
        int structs = 0;
        while (it.hasNext()) {
            DataType dt = it.next();
            if (dt instanceof FunctionDefinition) defsByName.put(dt.getName(), (FunctionDefinition) dt);
            else if (dt instanceof Structure) structs++;
        }
        println("  " + defsByName.size() + " function prototypes, " + structs + " structs");
        int applied = 0, kept = 0, missing = 0, pointers = 0, constants = 0;
        Map<String, Integer> missingByPrefix = new TreeMap<>();
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            FunctionDefinition fd = defsByName.get(f.getName());
            if (fd == null) {
                if (!f.getName().startsWith("FUN_") && !f.getName().startsWith("thunk_")) {
                    missing++;
                    String pre = f.getName().replaceFirst("^_+", "").replaceFirst("(?<=^[a-z]{2,3})[A-Z_0-9].*$", "");
                    missingByPrefix.merge(pre.length() > 6 ? pre.substring(0, 6) : pre, 1, Integer::sum);
                }
                continue;
            }
            if (f.getSignatureSource() == SourceType.USER_DEFINED) { kept++; continue; }
            if (new ApplyFunctionSignatureCmd(f.getEntryPoint(), fd, SourceType.IMPORTED).applyTo(currentProgram)) applied++;
        }
        // SH-4 code calls through pointers in literal pools (mov.l @(disp,pc); jsr): every pool word that
        // points at a function is a constant, and one pointing at a prototyped function gets the
        // prototype's pointer type, so the decompiler types the call's arguments and result
        ghidra.program.model.listing.FunctionManager fm = currentProgram.getFunctionManager();
        List<ghidra.program.model.address.Address> pools = new ArrayList<>();
        for (Data d : currentProgram.getListing().getDefinedData(true))
            if (d.isPointer() && d.getLength() == 4 && d.getValue() instanceof ghidra.program.model.address.Address
                    && fm.getFunctionAt((ghidra.program.model.address.Address) d.getValue()) != null)
                pools.add(d.getAddress());
        for (ghidra.program.model.address.Address pa : pools) {
            Data d = getDataAt(pa);
            Function target = fm.getFunctionAt((ghidra.program.model.address.Address) d.getValue());
            FunctionDefinition fd = defsByName.get(target.getName());
            try {
                if (fd != null && !(d.getDataType() instanceof Pointer && ((Pointer) d.getDataType()).getDataType() instanceof FunctionDefinition)) {
                    removeDataAt(pa);
                    d = createData(pa, new PointerDataType(fd, dtm));
                    pointers++;
                }
                MutabilitySettingsDefinition.DEF.setChoice(d, MutabilitySettingsDefinition.CONSTANT);
                constants++;
            } catch (Exception e) { /* leave the word as it was */ }
        }
        println("ApplyHeaders: " + applied + " prototypes applied, " + pointers + " pool pointers typed, " + constants + " pool pointers to functions marked constant, " + kept + " user signatures kept, " + missing + " named functions without a header prototype");
        List<Map.Entry<String, Integer>> worst = new ArrayList<>(missingByPrefix.entrySet());
        worst.sort((x, y) -> y.getValue() - x.getValue());
        StringBuilder sb = new StringBuilder("  without, by prefix:");
        for (int i = 0; i < Math.min(14, worst.size()); i++) sb.append(" ").append(worst.get(i).getKey()).append("=").append(worst.get(i).getValue());
        println(sb.toString());
    }
}
