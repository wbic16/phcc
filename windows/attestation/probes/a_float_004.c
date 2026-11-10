#include <stdio.h>
#include <string.h>
#include <stdint.h>
int main(void){ double d = 3.141592653589793; uint64_t u; memcpy(&u, &d, 8); printf("%a %.17g %.9e %llx\n", d, d, d, (unsigned long long)u); return 0; }
