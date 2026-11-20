# The C tests: one test_<file>.c per runtime file of template/port/runtime, built against that file and run; a test
# exits nonzero when a check fails. On the Mac, with Xcode's command-line tools and SDL 3 (brew install sdl3):
#
#   make -C tests/c
#
# On Linux (or in the port image, template/port/Dockerfile) the same command; Xvfb gives the OpenGL tests a screen there.

RUNTIME := ../../template/port/runtime
BUILD   := build
SDL     := $(shell pkg-config --cflags --libs sdl3)
CFLAGS  := -O1 -g -I. -I$(RUNTIME) -I$(RUNTIME)/../third_party/sa_numeric -DPORT_NAME='"test"' -DPORT_TITLE='"test"'

ifeq ($(shell uname -s),Darwin)
CC      := cc
LDMAP   := -Wl,-pagezero_size,0x1000          # the console's addresses are below 4 GB: a small page zero leaves them free
GL      := -framework OpenGL
RUN     :=
else
CC      := clang-16
LDMAP   :=
GL      := -lGL
RUN     := xvfb-run -a -s "-screen 0 1280x960x24"
endif

TESTS := $(BUILD)/test_draw $(BUILD)/test_boot $(BUILD)/test_system $(BUILD)/test_bios $(BUILD)/test_vmu $(BUILD)/test_nlib \
         $(BUILD)/test_hw $(BUILD)/test_platform $(BUILD)/test_pvr

.PHONY: test clean
test: $(TESTS)
	@status=0; for t in $(TESTS); do $(RUN) ./$$t || status=1; done; exit $$status

$(BUILD)/test_draw: test_draw.c check.h $(RUNTIME)/draw.c $(RUNTIME)/render.h | $(BUILD)
	$(CC) $(CFLAGS) -o $@ test_draw.c $(RUNTIME)/draw.c $(SDL) $(GL) -lm $(LDMAP)

$(BUILD)/test_boot: test_boot.c test_boot_game.h check.h $(RUNTIME)/boot.c | $(BUILD)
	$(CC) $(CFLAGS) -include test_boot_game.h -o $@ test_boot.c $(RUNTIME)/boot.c $(LDMAP)

$(BUILD)/test_platform: test_platform.c test_platform_game.h check.h $(RUNTIME)/platform.c | $(BUILD)
	$(CC) $(CFLAGS) -o $@ test_platform.c $(SDL) $(GL) -lm $(LDMAP)

$(BUILD)/test_pvr: test_pvr.c test_platform_game.h check.h $(RUNTIME)/pvr.c | $(BUILD)
	$(CC) $(CFLAGS) -o $@ test_pvr.c $(SDL) $(GL) -lm $(LDMAP)

# the tests that include their runtime file whole (to reach its static functions) build from the test alone
$(BUILD)/test_%: test_%.c check.h $(RUNTIME)/%.c | $(BUILD)
	$(CC) $(CFLAGS) -o $@ $< -lm $(LDMAP)

$(BUILD):
	mkdir -p $@

clean:
	rm -rf $(BUILD)
