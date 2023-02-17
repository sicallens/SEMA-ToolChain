import angr
import claripy
import logging

lw = logging.getLogger("CustomSimProcedureWindows")

class FindFirstFileW(angr.SimProcedure):
    def run(self, lpFileName, lpFindFileData):
        #print(self.state.mem(lpFileName).string.resolved)
        # TODO check if string is valid and not symbolic
        try:
            name = self.state.mem[lpFileName].wstring.concrete
            if hasattr(name, "decode"):
                name = name.decode("utf-16-le")
            lw.info(name)
        except:
            name = self.state.memory.load(lpFileName,0x20)
            lw.info(name)
            pass
        # self.state.memory.store(lpFindFileData, claripy.BVS("WIN32_FIND_DATA", 8 * 320))
        # return self.state.solver.BVS(
        #     "retval_{}".format(self.display_name), self.arch.bits
        # )
        if self.state.globals["FindFirstFile"] == 0:
            self.state.globals["FindFirstFile"] == 1
            self.state.memory.store(lpFindFileData, claripy.BVS("dwFileAttributes", 8 * 4))
            self.state.memory.store(lpFindFileData+0x4, claripy.BVS("ftCreationTime", 8 * 8))
            self.state.memory.store(lpFindFileData+0xc, claripy.BVS("ftLastAccessTime", 8 * 8))
            self.state.memory.store(lpFindFileData+0x14, claripy.BVS("ftLastWriteTime", 8 * 8))
            self.state.memory.store(lpFindFileData+0x1c, claripy.BVS("nFileSizeHigh", 8 * 4))
            self.state.memory.store(lpFindFileData+0x20, claripy.BVS("nFileSizeLow", 8 * 4))
            self.state.memory.store(lpFindFileData+0x24, claripy.BVS("dwReserved0", 8 * 4))
            self.state.memory.store(lpFindFileData+0x28, claripy.BVS("dwReserved1", 8 * 4))
            self.state.memory.store(lpFindFileData+0x2c, claripy.BVS("cFileName", 8 * 260))
            self.state.memory.store(lpFindFileData+0x2c, claripy.BVV("abcdef.cmd"))
            self.state.memory.store(lpFindFileData+0x36, claripy.BVV(0x0,8 * 250))
            self.state.memory.store(lpFindFileData+0x130, claripy.BVS("cAlternateFileName", 8 * 14))
            ret_val = self.state.solver.BVS("retval_{}".format(self.display_name), self.arch.bits)
            self.state.solver.add(ret_val != -1)
            return ret_val
        else:
            self.state.globals["GetLastError"] = 2
            return -1
