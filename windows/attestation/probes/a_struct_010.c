#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
struct S { unsigned long long a; unsigned char b; unsigned long long c; };
int main(void){ printf("%zu %zu\n", sizeof(struct S), _Alignof(struct S)); return 0; }
