#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
const char *s = "\377\376"; size_t i; printf("%zu:", sizeof("\377\376")); for (i = 0; i < sizeof("\377\376"); i++) printf(" %d", (unsigned char)s[i]); printf("\n");
return 0;
}
