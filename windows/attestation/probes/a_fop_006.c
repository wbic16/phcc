#include <stdio.h>
#include <string.h>
#include <stdint.h>
int main(void){ double d = 1.5 - 2.5; uint64_t u; memcpy(&u, &d, 8); printf("%a %llx\n", d, (unsigned long long)u); return 0; }
