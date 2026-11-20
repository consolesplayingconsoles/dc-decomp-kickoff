/* test_hw_game.h: a game's game.h for test_hw.c (included first, so the template's own game.h, still to be filled in, is
   skipped): the interrupt words hw.c names, at addresses nothing in the test reads */
#ifndef GAME_H
#define GAME_H
#define GAME_INTEVT_COPY       0x8C00F200u
#define GAME_DEFAULT_HANDLER   0x8C00F210u
#define GAME_NL_LIST_PTRS      0x00000000u   /* no NAOMI library: hw.c's flush check stays off */
#endif
