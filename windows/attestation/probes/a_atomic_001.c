#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
#include <stdatomic.h>
int main(void){ _Atomic int x = 5; int y = atomic_fetch_add(&x, 3); printf("%d %d\n", y, atomic_load(&x)); return 0; }
