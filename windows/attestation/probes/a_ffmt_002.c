#include <stdio.h>
#include <string.h>
#include <stdint.h>
int main(void){ float f = 1.5f; uint32_t u; memcpy(&u, &f, 4); printf("%a %.9g %lx\n", (double)f, (double)f, (unsigned long)u); return 0; }
