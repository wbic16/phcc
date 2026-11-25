#!/bin/sh
# Build phccd (static, libtcc linked in) from the phcc tree.
# Run from the repository root after `make` has produced libtcc.a.
set -e
cc -O2 -static -I. -o dist/phccd dist/phccd.c libtcc.a -ldl -lpthread -lm
echo "built dist/phccd:"
sha256sum dist/phccd
file dist/phccd || true
