#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
struct S { union { int i; char c[4]; } u; char tag; };
int main(void){ printf("%zu %zu\n", sizeof(struct S), _Alignof(struct S)); return 0; }
