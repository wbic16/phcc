#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
struct S { unsigned a:3; unsigned b:5; unsigned c:8; };
int main(void){ printf("%zu %zu\n", sizeof(struct S), _Alignof(struct S)); return 0; }
