# Standalone build + test for the phext library.
#   make            build the test binary
#   make test       build and run the conformance suite
#   make test-xz    build and run the suite with the xz seal compiled in
#                   (PHEXT_WITH_XZ, links -llzma; the seal tests run in
#                   this build - see PARITY.md D-7)
#   make CC=../../phcc TCCFLAGS=-B../..   build with phcc itself
#                                        (dogfood; build phcc first —
#                                         -B points phcc at its own tree)
CC ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -O2
TESTDIR := $(CURDIR)

test_phext: test_phext.c ../phext.c ../phext.h
	$(CC) $(CFLAGS) $(TCCFLAGS) -I.. -o $@ test_phext.c ../phext.c

test: test_phext
	@scratch=$$(mktemp -d); cp test_phext $$scratch/; \
	 (cd $$scratch && ./test_phext $(TESTDIR)); status=$$?; \
	 rm -rf $$scratch; exit $$status

test_phext_xz: test_phext.c ../phext.c ../phext.h
	$(CC) $(CFLAGS) $(TCCFLAGS) -DPHEXT_WITH_XZ -I.. -o $@ test_phext.c ../phext.c -llzma

test-xz: test_phext_xz
	@scratch=$$(mktemp -d); cp test_phext_xz $$scratch/; \
	 (cd $$scratch && ./test_phext_xz $(TESTDIR)); status=$$?; \
	 rm -rf $$scratch; exit $$status

clean:
	rm -f test_phext test_phext_xz

.PHONY: test test-xz clean
