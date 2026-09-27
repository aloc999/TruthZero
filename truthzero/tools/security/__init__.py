from truthzero.tools.security.recon import SubdomainEnumTool, PortScanTool, DnsLookupTool, WhoisTool
from truthzero.tools.security.scanner import NucleiScanTool, DirFuzzTool, TechDetectTool
from truthzero.tools.security.exploit import ExploitSearchTool, PayloadGeneratorTool, ReverseShellTool
from truthzero.tools.security.crypto import HashIdentifyTool, HashCrackTool, EncoderDecoderTool

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
