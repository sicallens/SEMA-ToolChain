from .GetSystemInfo import GetSystemInfo

class GetNativeSystemInfo(GetSystemInfo):
    def run(self, lpSystemInfo):
        return 0x1

