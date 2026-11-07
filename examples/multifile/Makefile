# Makefile — library + program, built in separate steps.
#
# The compiler is a variable on purpose: the same Makefile drives
# phcc, gcc and clang —
#   make                    (system default compiler)
#   make CC=tcc             (phcc; add -B<tree> when running in-tree)
#   make CC=gcc / CC=clang
CC      ?= cc
CFLAGS  ?= -O2 -Wall
AR      ?= ar

all: app

libstats.a: stats.o
	$(AR) rcs $@ stats.o

stats.o: stats.c stats.h
	$(CC) $(CFLAGS) -c stats.c -o stats.o

main.o: main.c stats.h
	$(CC) $(CFLAGS) -c main.c -o main.o

app: main.o libstats.a
	$(CC) main.o -L. -lstats -o app

run: app
	./app

clean:
	rm -f app *.o *.a

.PHONY: all run clean
