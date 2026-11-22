/* game.h: the addresses of this game that the runtime needs. Each is a console address from this repo's functions.txt
   or globals.txt (the cached mirror, 0x8C......). Fill them in, then remove the #error. port/README.md says how each
   one is found. The commented-out ones are optional: the runtime does without them. */
#ifndef GAME_H
#define GAME_H

#error "port/runtime/game.h: fill in this game's addresses (port/README.md), then remove this line"

/* the start code: what runs before main (the entry, 0x8C010000 + the IP.BIN's bootstrap offset), and the three calls the
   runtime makes in its place (runner.c game_main) */
#define GAME_START      0x00000000u
#define GAME_INITSCT    0x00000000u   /* _INITSCT: the bss clear and the initial data copy */
#define GAME_INITLIBH   0x00000000u   /* _INITLIBH: the library modules' entries */
#define GAME_MAIN       0x00000000u   /* main, or what the start code calls in its place */

/* the compiler runtime's errno, which the division helpers set on a division by 0 */
#define GAME_ERRNO      0x00000000u

/* interrupts (hw.c): the word the game's exception code copies INTEVT to */
#define GAME_INTEVT_COPY       0x00000000u
/* when the HOLLY interrupts find only the library's default handler in the table (Kamui's handler not registered there):
   that default handler, and the handler Kamui registers with kmiRegisterPhIntHandler (kmiInterruptHandlerSH). Both
   defined, hw.c runs game.c's port_game_irq for them: Kamui's handler, then the vertical blank chain */
/* #define GAME_DEFAULT_HANDLER   0x00000000u */
/* #define GAME_KAMUI_HANDLER     0x00000000u */

/* syIntInit's two arguments as syHwInit passes them (the two words it reads), for game.c's syHwInit; a game whose C
   covers syHwInit drops that function from game.c and these with it */
#define GAME_SYINTINIT_ARG1    0x00000000u
#define GAME_SYINTINIT_ARG2    0x00000000u

/* the NAOMI library's list pointers (nlib.c, platform.c's list report): a game without the NAOMI library has none */
#define GAME_NL_LIST_PTRS      0x00000000u
/* the NAOMI library's near plane, which nlPerspective and nlFrustum set: nlib.c clips at it when a model's lighting
   context holds no near W */
/* #define GAME_NL_NEAR           0x00000000u */

/* the game's sub-mode word, logged with the main mode below by boot.c with PORT_BOOT_LOG */
/* #define GAME_SUB_MODE          0x00000000u */

/* widescreen: the game's main mode word, and the main mode whose 2D is the play HUD. With PORT_WIDESCREEN=1 the HUD's
   pieces at the top and bottom go to the screen's sides (draw.c mark_hud); left undefined, the HUD stays in the 4:3
   middle. Crazy Taxi's: its MainLoop mode 0x8C1EE234 (0 attract, 1 the game, 3 menu), HUD mode 1 */
/* #define GAME_MAIN_MODE         0x00000000u */
/* #define GAME_HUD_MODE          1 */

#endif
