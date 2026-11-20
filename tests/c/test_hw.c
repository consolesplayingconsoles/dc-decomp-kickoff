/* test_hw.c: template/port/runtime/hw.c, the hardware registers the game's C reads: the sound driver's ready word.
   Run with the other C tests: make -C tests/c.

   nlsndInit starts the sound CPU, then reads the driver's ready word (0xA080005C) in a counted loop. The sound CPU runs
   on its own thread in real time and the loop at the PC's speed: answered at once, the count ran out before the driver
   was up and Crazy Taxi stopped at boot with "AICADRV ERR".

    ready      a word the driver has already written reads at once
    waits      a word still 0 is read when the driver writes it (here 200 ms later), not as 0 at once
    gives_up   a driver that never writes: the read gives 0 after about two seconds, and the game's own count ends its
               loop as on the console; it does not hang */
#include <pthread.h>
#include <signal.h>
#include <time.h>
#ifndef SIGRTMIN                 /* Linux's real-time signals: hw.c's timers use them; macOS has none (not called here) */
#define SIGRTMIN SIGUSR2
#endif

#include "check.h"
#include "test_hw_game.h"
#include "hw.c"

/* what hw.c takes from the rest of the runtime: nothing of it runs in these reads */
int port_sr, port_fr15;
void interp_save(void) {}
void interp_restore(void) {}
void port_game_irq(int evt) { (void)evt; }
const struct port_entry *port_lookup(uint32_t addr) { (void)addr; return 0; }
void pvr_ta_write(const void *data, uint32_t bytes) { (void)data; (void)bytes; }
void pvr_ta_list_init(void) {}
void pvr_ta_list_cont(void) {}
void pvr_start_render(void) {}
void pvr_vram_write(uint32_t addr, const void *src, uint32_t bytes, int path32) { (void)addr; (void)src; (void)bytes; (void)path32; }

#define READY 0xA080005Cu

static double ms(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1e3 + t.tv_nsec / 1e6;
}

static void sleep_ms(int n)
{
    struct timespec t = {n / 1000, (long)(n % 1000) * 1000000};
    nanosleep(&t, 0);
}

static void *driver(void *arg)          /* the sound driver: writes its ready word 200 ms after it starts */
{
    (void)arg;
    sleep_ms(200);
    *(volatile uint32_t *)(uintptr_t)READY = 1;
    return 0;
}

int main(void)
{
    console_map(READY, 4);

    *(volatile uint32_t *)(uintptr_t)READY = 1;
    double t0 = ms();
    uint32_t v = port_mmio_r32(0x0080005Cu);
    CHECK(v == 1 && ms() - t0 < 50, "ready: 1 at once, got %u after %.0f ms", v, ms() - t0);

    *(volatile uint32_t *)(uintptr_t)READY = 0;
    sleep_ms(150);                                   /* a new wait: over 100 ms since the last read */
    pthread_t th;
    pthread_create(&th, 0, driver, 0);
    t0 = ms();
    v = port_mmio_r32(0x0080005Cu);
    double took = ms() - t0;
    pthread_join(th, 0);
    CHECK(v == 1, "waits: the read gives the driver's 1, got %u", v);
    CHECK(took > 150 && took < 1000, "waits: it took about the driver's 200 ms, took %.0f ms", took);

    *(volatile uint32_t *)(uintptr_t)READY = 0;
    sleep_ms(150);
    t0 = ms();
    v = port_mmio_r32(0x0080005Cu);
    took = ms() - t0;
    CHECK(v == 0, "gives_up: still 0, got %u", v);
    CHECK(took > 1800 && took < 3000, "gives_up: after about two seconds, took %.0f ms", took);
    return check_done("test_hw");
}
