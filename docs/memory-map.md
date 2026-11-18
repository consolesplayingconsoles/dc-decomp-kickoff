# Dreamcast addresses worth labelling on sight

Addresses are physical; the CPU sees each region through the SH-4 mirrors (P1 `0x8xxxxxxx`
cached, P2 `0xAxxxxxxx` uncached), so `0xA05F6800` and `0x005F6800` are the same register.
Label by the low 29 bits.

| range (physical) | what | why you care |
|---|---|---|
| `0x0C000000`-`0x0CFFFFFF` | main RAM, 16 MiB | code and heap |
| `0x0C008000` | IP.BIN bootstrap, loaded here | |
| `0x0C010000` | `1ST_READ.BIN` load and entry address | the base for raw import |
| `0x0C0000B0`..`0x0C0000E0` | BIOS syscall vectors (sysinfo `B0`, ROM font `B4`, flash `B8`, GD-ROM/misc `BC`, system `E0`) | a load from `0x8C0000B4` then `jsr` is the ROM font, i.e. text rendering |
| `0x005F6800`-`0x005F6FFF` | system bus (SB) registers: DMA, interrupts, Maple | `0x005F6C00` block is Maple: controller/VMU traffic |
| `0x005F7000`-`0x005F70FF` | GD-ROM drive registers | only the BIOS/gdFs layer should touch these |
| `0x005F8000`-`0x005F9FFF` | PowerVR CLX2 (Holly) core registers | display setup, render start |
| `0x00700000`-`0x00707FFF` | AICA sound registers | |
| `0x00800000`-`0x009FFFFF` | AICA sound RAM, 2 MiB | sound driver and samples uploaded here |
| `0x04000000` / `0x05000000` | VRAM, 64-bit / 32-bit access paths | texture uploads |
| `0x10000000` | Tile Accelerator FIFO | polygon submission |
| `0xFF000000`-`0xFFFFFFFF` | SH-4 on-chip registers (cache, timers, DMAC, SCIF) | |

On a Katana build these are almost always reached through SDK wrappers (`sy*`, `pd*`, `kd`/Kamui,
Ninja), so the register map mostly helps you name those wrappers once; game code calls the wrappers.
