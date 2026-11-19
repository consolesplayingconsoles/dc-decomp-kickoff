# The C tests: one test_<file>.c per runtime file of template/port/runtime, built against that file and run; a test
# exits nonzero when a check fails. They need the port image's compiler, SDL 3, OpenGL (Mesa) and Xvfb:
#
#   docker run --rm -v "$PWD":/work -w /work <port image> make -C tests/c
#
# (the port image: template/port/Dockerfile).

RUNTIME := ../../template/port/runtime
CC      := clang-16
CFLAGS  := -O1 -g -I$(RUNTIME) -DPORT_NAME='"test"' -DPORT_TITLE='"test"'
SDL     := $(shell pkg-config --cflags --libs sdl3)
BUILD   := build
RUN     := xvfb-run -a -s "-screen 0 1280x960x24"

TESTS := $(BUILD)/test_draw $(BUILD)/test_boot

.PHONY: test clean
test: $(TESTS)
	@status=0; for t in $(TESTS); do $(RUN) ./$$t || status=1; done; exit $$status

$(BUILD)/test_draw: test_draw.c $(RUNTIME)/draw.c $(RUNTIME)/render.h | $(BUILD)
	$(CC) $(CFLAGS) -o $@ test_draw.c $(RUNTIME)/draw.c $(SDL) -lGL -lm

$(BUILD)/test_boot: test_boot.c test_boot_game.h $(RUNTIME)/boot.c | $(BUILD)
	$(CC) $(CFLAGS) -include test_boot_game.h -o $@ test_boot.c $(RUNTIME)/boot.c

$(BUILD):
	mkdir -p $@

clean:
	rm -rf $(BUILD)
