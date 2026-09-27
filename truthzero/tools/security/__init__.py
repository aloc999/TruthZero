from truthzero.tools.security.crypto import EncoderDecoderTool, HashCrackTool, HashIdentifyTool
from truthzero.tools.security.exploit import ExploitSearchTool, PayloadGeneratorTool, ReverseShellTool
from truthzero.tools.security.recon import DnsLookupTool, PortScanTool, SubdomainEnumTool, WhoisTool
from truthzero.tools.security.scanner import DirFuzzTool, NucleiScanTool, TechDetectTool

SECURITY_TOOLS = [
    SubdomainEnumTool,
    PortScanTool,
    DnsLookupTool,
    WhoisTool,
    NucleiScanTool,
    DirFuzzTool,
    TechDetectTool,
    ExploitSearchTool,
    PayloadGeneratorTool,
    ReverseShellTool,
    HashIdentifyTool,
    HashCrackTool,
    EncoderDecoderTool,
]
