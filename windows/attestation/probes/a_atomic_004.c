#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
#include <stdatomic.h>
int main(void){ _Atomic unsigned x = 12; unsigned r1 = atomic_fetch_or(&x, 3); unsigned r2 = atomic_fetch_and(&x, 6); printf("%u %u %u\n", r1, r2, atomic_load(&x)); return 0; }
