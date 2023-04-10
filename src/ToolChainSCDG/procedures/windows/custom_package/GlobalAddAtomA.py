import angr


class GlobalAddAtomA(angr.SimProcedure):
    def run(self, pMessage):
        return self.state.solver.BVS(
            "retval_{}".format(self.display_name), self.arch.bits
        )
