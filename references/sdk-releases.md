# Katana SDK releases: what exists, what to search for

What the skill knows about each release, so the user knows what to look for. These are names and
file names as they have been seen in public archives (archive.org items, collectors' sites,
preservation sites), given as search terms. Nothing here is a download link, and the sources
disclaimer in SKILL.md applies: the user decides what they are entitled to obtain and use.

Two catalogues cover most of the list: archive.org's `official-katana-sdks` item
(https://archive.org/details/official-katana-sdks) and
sega-dreamcast-info.com's SDK archive page
(https://www.sega-dreamcast-info.com/en/dreamcast-develppement-sdk-library-archive), which also
holds the Shinobi and Kamui library sources and the 0.40 release.

| release | date (newest library) | seen as | notes |
|---|---|---|---|
| 0.20 Pre 7 | 1998 | `SEGA Katana Dreamcast SDK Version 0.20 Pre 7.iso` | PC-side (NEC Arc1A PowerVR board); x86 COFF import libraries, no SH-4 code |
| 0.40 Release 4 | May 1998 | `Dreamcast Katana SDK Version 0.40 Release.4.zip` | first SH-4 libraries (778 signatures) |
| Release 2 | 1998 | `SEGA Katana Dreamcast SDK R2.iso` | NEC Arc1A era; x86 import libraries only |
| Release 4 (4.01) | Jun 1998 | `SEGA Katana Dreamcast SDK R4..iso` | Set 4 unit; 1,035 signatures |
| Set 5.05 | Aug 1998 | no SDK dump; the Tower of Babel dev kit demo and its link map (`KTN505`) | 690 signatures from the demo |
| 1.0B2 | Oct 1998 | `Katana SDK 1.0B2.zip` | 3,923 signatures |
| 1.00J | Nov-Dec 1998 | `Dreamcast SDK for Sega Library Ver.1.00J.zip`, `DCSDK_100J.iso` | InstallShield 3 installer (`is3_extract.py`); 3,985 signatures; VF3tb's Kamui era |
| 1.20J, 1.30J | 1999 | named in collectors' lists, no public dump seen | |
| 1.42J | Apr 1999 | `SEGA Katana Dreamcast SDK R1.42J.iso` | InstallShield 3; 2,943 signatures + 2,141 from its 13 prebuilt samples with maps |
| Release 8 (Europe) | Apr 1999 | `European Dreamcast SDK release 8.zip` | 3,419 signatures; Hydro Thunder's release |
| 8.1 | 1999 | named in collectors' lists, no public dump seen | |
| 1.55J | Jul 1999 | `SEGA Katana Dreamcast SDK R1.55J DISK1.ISO` ... `DISK3.ISO` (Redump has it) | 3,953 signatures; the complete tbg-decomp builds with it |
| Release 9 (Europe) | Nov 1999 | `DCSDK9_1.ISO` (archive.org `dcsdk-9e`) | 5,883 signatures |
| Release 10.1 | May 2000 | `R10.1_000518` folder in `github.com/Kochise/dreamcast-docs` | 8,619 signatures; the build SDK of this skill's samples |
| 2.00J | Sep 2000 | `SEGA Katana Dreamcast SDK R2.00J.ISO` | 4,739 signatures |
| Release 11b (11a is the same file) | Feb 2001 | `SEGA Katana Dreamcast SDK R11b.iso` | 8,506 signatures; the last public release. "R12" was asked for on forums in 2021, nobody had it |
| Network SDK 1.04 | 1999 | `Sega Katana Dreamcast Network SDK 1.04.iso` (holds `NETSDK10.ISO`) | modem/PPP/TCP/socket/DNS/mail/IRC; 1,533 signatures |
| Shinobi, Kamui library sources | 1998-1999 | `The source code of the Dreamcast Shinobi development library.zip`, `... Kamui ...zip` | with their `.LIB` files; 1,540 + 1,570 signatures |

Also seen, not SDKs: the Windows CE for Dreamcast toolkits (1.0, 1.1, 2.0, 2.1: a different world, this
skill stops at `0WINCEOS.BIN`), the Modem SDK 1.00 (Apr 2000, collectors' lists), and `OFFICIAL
KATANA SDKs.zip` on archive.org (`official-katana-sdks`), a bundle of several of the above.

The release numbering, from a 2007 collectors' thread: Release 2 = NEC Arc1A PowerVR PCI board;
Releases 3-4 = Set 3/4 units; Releases 5-7 = Set 5.00-5.23 (HKT-0100/0110); Releases 8-11 = Set
5.24 (HKT-0120). Japanese numbering (1.xxJ, 2.00J) ran in parallel with the same libraries.

## The compiler each release ships

Matching C needs the compiler the game was built with, not just its libraries. `shc.exe`'s own
banner per release:

| release | SH C compiler |
|---|---|
| 0.40 Release 4 | SH SERIES C Compiler Ver. 5.0 (Release 10), C++ 1.0 |
| Release 4 | Ver. 5.0 (Release 27) |
| 1.0B2, 1.00J | Ver. 5.0 (Release 28) |
| Release 8 (Europe) | SH SERIES C/C++ Compiler Ver. 5.1 (Release 03) |
| 1.42J | Ver. 5.1 (Release 04) |
| 1.55J, Release 9 | Ver. 5.1 (Release 08) |
| Release 10.1, Release 11b | Ver. 5.1 (Release 11) |
| 2.00J | Ver. 6.0 AD (Release 04) |

So a game whose banners say 1999 libraries was compiled by SHC 5.1 R03-R08, and byte-matching it
through R10.1's R11 compiler is not guaranteed: when `sdk_scan.py` names the release, build with
that release's `shc` (step 6's `SDK_PATH`), and say so in the repo's README.

## Prototypes and dev kit dumps as material

A prototype disc sometimes carries what retail never does: the linker's `.ELF` (with or without
debug info), a `.map`, or a build log inside a data pack. Where to look whether one exists:
https://www.sega-dreamcast-info.com/en/releases-prototypes-sega-dreamcast-iso (about 300
Dreamcast prototypes, each described, plus the eleven published Katana dev kit dumps) and Hidden
Palace (https://hiddenpalace.org/Prototypes_by_system/Dreamcast, several hundred, with archive.org
mirrors). A dev kit's own disk holds GD-ROM emulation images and project folders, never the SDK
(that lived on the Windows host), but a studio's project folder can hold link maps, ELFs with
debug info and source. Seen so far: Tower of Babel (1998 demo + link map), Eurocom (Hydro
Thunder ELF with DWARF, 2,753 named functions), Hydro Thunder Jul 28 1999 prototype (link map
inside `LOO3.R2`).
