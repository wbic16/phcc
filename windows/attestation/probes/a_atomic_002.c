#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
#include <stdatomic.h>
int main(void){ _Atomic int x = 5; int ok = atomic_compare_exchange_strong(&x, &(int){5}, 9); printf("%d %d\n", ok, atomic_load(&x)); return 0; }
