# Binary Reverse Engineering

## File Identification
```bash
file target_binary                          # ELF/PE/Mach-O, arch, stripped/linked
binwalk target_binary                       # embedded files, firmware headers, compressed sections
binwalk -e target_binary                    # extract embedded files recursively
rabin2 -I target_binary                     # binary info: arch, bits, endian, compiler, crypto
readelf -h target_binary                    # ELF header: entry point, sections, program headers
readelf -s target_binary | grep FUNC        # exported/imported function symbols
objdump -x target.exe | grep -i dll        # PE imports and DLL dependencies
```

## Static Analysis
```bash
strings -a -n 6 target_binary               # all printable strings, min length 6
strings -e l target_binary                   # extract UTF-16LE strings (Windows binaries)
rabin2 -z target_binary                      # strings with section/address context
objdump -d -M intel target_binary            # full disassembly, Intel syntax
objdump -d target_binary | grep -A5 "call"   # find all function calls
nm -D target_binary                          # dynamic symbol table (shared libraries)
```

## Ghidra Workflow
- Import binary → Auto Analysis with all analyzers enabled
- Entry point → follow `main()` or `_start` → identify `__libc_start_main` arg1 as real main
- Window → Function Call Graph for control flow overview
- Defined Strings window → filter for URLs, flags, passwords, paths
- Cross-references (Ctrl+Shift+F) on interesting strings/functions to trace usage
- Decompiler: rename variables (L key), retype (Ctrl+L), add structs for clarity
- Search → Memory → byte pattern `\x89\xe5` to find function prologues
- Patch bytes: right-click instruction → Patch Instruction → modify opcode

## GDB Commands
```bash
gdb -q ./target                              # quiet start
set disassembly-flavor intel                 # Intel syntax
info functions                               # list all known functions
break *0x401234                              # break at address
break main                                   # break at symbol
run < input.txt                              # run with stdin from file
stepi                                        # single instruction step
nexti                                        # step over calls
x/20wx $rsp                                  # examine 20 words at stack pointer
x/s 0x402000                                 # examine as string
x/10i $rip                                   # examine 10 instructions at instruction pointer
info registers                               # all register values
vmmap                                        # memory map (GEF/pwndbg)
heap bins                                    # heap bin state (GEF/pwndbg)
set {int}0x401234 = 0x90909090               # write NOPs at address
catch syscall write                          # break on write syscall
```

## Frida Dynamic Instrumentation
```javascript
// Attach to process and hook function
frida -U -n target_app -l hook.js

// hook.js — intercept exported function
Interceptor.attach(Module.findExportByName(null, "strcmp"), {
  onEnter(args) {
    console.log("strcmp(" + Memory.readUtf8String(args[0]) + ", " + Memory.readUtf8String(args[1]) + ")");
  },
  onLeave(retval) { console.log("=> " + retval); }
});

// Hook function at offset from module base
var base = Module.findBaseAddress("libtarget.so");
Interceptor.attach(base.add(0x1234), {
  onEnter(args) { console.log("arg0: " + args[0].toInt32()); }
});

// Scan memory for pattern
Memory.scan(base, 0x10000, "48 8b 05 ?? ?? ?? ??", { onMatch(addr, size) { console.log("Found at: " + addr); } });
```

## Anti-Reversing Bypass
```bash
# Detect ptrace anti-debug
grep -c "ptrace" < <(ltrace ./target 2>&1)
# Bypass: LD_PRELOAD fake ptrace that returns 0
echo 'long ptrace(int r, ...) { return 0; }' > fake.c && gcc -shared -o fake.so fake.c
LD_PRELOAD=./fake.so ./target

# UPX unpacking
upx -d packed_binary -o unpacked_binary
# Custom packer: set breakpoint at OEP, dump with gcore
gdb -ex "catch syscall execve" -ex run -ex "gcore dump" ./packed

# Windows anti-debug bypass in x64dbg
# Patch IsDebuggerPresent to return 0: mov eax, 0; ret
# ScyllaHide plugin for comprehensive anti-anti-debug
```

## CTF Patterns
```bash
# XOR key brute-force
python3 -c "
data = open('encrypted','rb').read()
for key in range(256):
    dec = bytes([b ^ key for b in data])
    if b'flag{' in dec or b'CTF{' in dec: print(f'Key={key}: {dec}')
"

# Z3 constraint solving for keygen
from z3 import *
s = Solver()
flag = [BitVec(f'f{i}', 8) for i in range(20)]
for c in flag: s.add(c >= 0x20, c <= 0x7e)
s.add(flag[0] == ord('f'), flag[1] == ord('l'))  # add constraints from binary
s.check(); m = s.model(); print(''.join(chr(m[c].as_long()) for c in flag))

# Angr symbolic execution
import angr
p = angr.Project('./target', auto_load_libs=False)
state = p.factory.entry_state()
simgr = p.factory.simulation_manager(state)
simgr.explore(find=0x401337, avoid=0x401000)  # find=success_addr, avoid=fail_addr
print(simgr.found[0].posix.dumps(0))           # stdin that reaches target
```

## Binary Patching
```bash
# radare2 patching
r2 -w target_binary                          # open in write mode
s 0x401234                                   # seek to address
wa nop;nop;nop                               # write NOP sled
wa jmp 0x401300                              # write unconditional jump
wx 9090                                      # write raw hex bytes
wao jnz                                      # convert je to jnz (invert conditional)

# Python patching
with open('target','rb') as f: data = bytearray(f.read())
data[0x1234:0x1237] = b'\x90\x90\x90'        # NOP out 3 bytes at offset
with open('patched','wb') as f: f.write(data)
```
