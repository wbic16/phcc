#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
struct S { char a[3]; short s; long l; };
int main(void){ printf("%zu %zu\n", sizeof(struct S), _Alignof(struct S)); return 0; }
