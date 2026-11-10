#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
#include <stdatomic.h>
int main(void){ _Atomic long x = 100; atomic_fetch_sub(&x, 58); printf("%ld\n", atomic_load(&x)); return 0; }
