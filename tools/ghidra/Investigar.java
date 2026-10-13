// Mostra a função que contém cada endereço pedido: assembly, pseudocódigo C e quem chama.
// Roda no Ghidra sem tela (analyzeHeadless), chamado pelo comando `fortuna investigar`.
// @category Fortuna

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.symbol.Reference;

import java.io.FileWriter;
import java.io.PrintWriter;

public class Investigar extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2) {
            printerr("uso: Investigar.java <saida.md> <endereco> [endereco...]");
            return;
        }
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        try (PrintWriter out = new PrintWriter(new FileWriter(args[0]))) {
            out.println("# Investigação: " + currentProgram.getName());
            out.println();
            out.println("Processador no Ghidra: `" + currentProgram.getLanguageID() + "`");
            for (int i = 1; i < args.length; i++) {
                Address at = toAddr(args[i]);
                out.println();
                out.println("## " + args[i]);
                Function function = getFunctionContaining(at);
                if (function == null) {
                    disassemble(at);
                    createFunction(at, null);
                    function = getFunctionContaining(at);
                }
                if (function == null) {
                    out.println("Nenhuma função encontrada nesse endereço.");
                    continue;
                }
                out.println("Função `" + function.getName() + "` em " + function.getEntryPoint()
                        + ", " + function.getBody().getNumAddresses() + " bytes.");
                out.println();
                out.println("### Quem chama");
                int callers = 0;
                for (Reference ref : getReferencesTo(function.getEntryPoint())) {
                    Function caller = getFunctionContaining(ref.getFromAddress());
                    out.println("- " + ref.getFromAddress() + (caller != null ? " em `" + caller.getName() + "`" : "")
                            + " (" + ref.getReferenceType() + ")");
                    if (++callers == 20) {
                        out.println("- ...");
                        break;
                    }
                }
                if (callers == 0) out.println("Ninguém chama direto; deve ser chamada por ponteiro.");
                out.println();
                out.println("### Assembly perto do endereço");
                out.println("```");
                Instruction instruction = getInstructionContaining(at);
                for (int back = 0; back < 8 && instruction != null && instruction.getPrevious() != null
                        && function.getBody().contains(instruction.getPrevious().getAddress()); back++) {
                    instruction = instruction.getPrevious();
                }
                for (int n = 0; n < 24 && instruction != null; n++, instruction = instruction.getNext()) {
                    String mark = instruction.getAddress().equals(at) || instruction.contains(at) ? ">>" : "  ";
                    out.println(mark + " " + instruction.getAddress() + "  " + instruction);
                }
                out.println("```");
                out.println();
                out.println("### Pseudocódigo");
                DecompileResults result = decompiler.decompileFunction(function, 120, monitor);
                out.println("```c");
                out.println(result.decompileCompleted() ? result.getDecompiledFunction().getC() : "(o decompilador desistiu: " + result.getErrorMessage() + ")");
                out.println("```");
            }
        }
        decompiler.dispose();
        println("relatório em " + args[0]);
    }
}
