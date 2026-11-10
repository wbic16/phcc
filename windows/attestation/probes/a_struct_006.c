#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
struct S { long long l; char a; short s; int i; };
int main(void){ printf("%zu %zu\n", sizeof(struct S), _Alignof(struct S)); return 0; }
