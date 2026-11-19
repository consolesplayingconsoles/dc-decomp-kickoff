/* game.h: the addresses of this game that the runtime needs. Each is a console address from this repo's functions.txt
   or globals.txt (the cached mirror, 0x8C......). Fill them in, then remove the #error. port/README.md says how each
   one is found; the values in the comments are Crazy Taxi's, the game this runtime was first brought up on. */
#ifndef GAME_H
#define GAME_H

#error "port/runtime/game.h: fill in this game's addresses (port/README.md), then remove this line"

/* the start code: what runs before main (the entry, 0x8C010000 + the IP.BIN's bootstrap offset; Crazy Taxi 0x8C14AB60),
   and the three calls the runtime makes in its place (runner.c game_main) */
#define GAME_START      0x00000000u   /* Crazy Taxi 0x8C14AB60 */
#define GAME_INITSCT    0x00000000u   /* _INITSCT: the bss clear and the initial data copy (Crazy Taxi 0x8C14AB98) */
#define GAME_INITLIBH   0x00000000u   /* _INITLIBH: the library modules' entries (Crazy Taxi 0x8C14AB88) */
#define GAME_MAIN       0x00000000u   /* main, or what the start code calls in its place (Crazy Taxi thunk_MainLoop 0x8C02AB40) */

/* the compiler runtime's errno, which the division helpers set on a division by 0 (Crazy Taxi 0x8C2B7BA0) */
#define GAME_ERRNO      0x00000000u

/* interrupts (hw.c, game.c): the word the game's exception code copies INTEVT to (Crazy Taxi 0x8C16E1D8), the library's
   default handler that the HOLLY events start with (Crazy Taxi 0x8C16DD08), the handler Kamui registers with
   kmiRegisterPhIntHandler (Crazy Taxi kmiInterruptHandlerSH 0x8C16C810), and syIntInit's two arguments as syHwInit
   passes them (Crazy Taxi: the words at 0x8C175060 and 0x8C177A9C) */
#define GAME_INTEVT_COPY       0x00000000u
#define GAME_DEFAULT_HANDLER   0x00000000u
#define GAME_KAMUI_HANDLER     0x00000000u
#define GAME_SYINTINIT_ARG1    0x00000000u
#define GAME_SYINTINIT_ARG2    0x00000000u

/* the NAOMI library's list pointers (nlib.c, platform.c's list report): a game without the NAOMI library has none
   (Crazy Taxi 0x8C2B8CBC) */
#define GAME_NL_LIST_PTRS      0x00000000u

#endif
