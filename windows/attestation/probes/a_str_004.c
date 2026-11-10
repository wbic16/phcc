#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
const char *s = "\x41\101\0"; size_t i; printf("%zu:", sizeof("\x41\101\0")); for (i = 0; i < sizeof("\x41\101\0"); i++) printf(" %d", (unsigned char)s[i]); printf("\n");
return 0;
}
