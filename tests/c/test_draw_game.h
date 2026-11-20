/* test_draw_game.h: a game's game.h for test_draw.c and test_wide.c (included first, so the template's own game.h, still to
   be filled in, is skipped): the main-mode word draw.c reads for the play HUD, at an address test_wide.c maps, and the
   play mode */
#ifndef GAME_H
#define GAME_H
#define GAME_MAIN_MODE 0x8C00F000u
#define GAME_HUD_MODE  1
#endif
