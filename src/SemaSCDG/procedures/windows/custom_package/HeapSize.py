import logging
import angr

lw = logging.getLogger("CustomSimProcedureWindows")


class HeapSize(angr.SimProcedure):
    def run(self, hHeap, dwFlags, lpMem):
        return 0x0
        #self.state.globals["HeapSize"][self.state.solver.eval(lpMem)]
