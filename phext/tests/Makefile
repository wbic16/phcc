# Standalone build + test for the phext library.
#   make            build the test binary
#   make test       build and run the conformance suite
#   make CC=../../tcc TCCFLAGS=-B../..   build with phcc itself
#                                        (dogfood; build phcc first —
#                                         -B points tcc at its own tree)
CC ?= cc
CFLAGS ?= -std=c99 -Wall -Wextra -O2
TESTDIR := $(CURDIR)

test_phext: test_phext.c ../phext.c ../phext.h
	$(CC) $(CFLAGS) $(TCCFLAGS) -I.. -o $@ test_phext.c ../phext.c

test: test_phext
	@scratch=$$(mktemp -d); cp test_phext $$scratch/; \
	 (cd $$scratch && ./test_phext $(TESTDIR)); status=$$?; \
	 rm -rf $$scratch; exit $$status

clean:
	rm -f test_phext

.PHONY: test clean
