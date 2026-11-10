#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
const char *s = "a\n\t\\"; size_t i; printf("%zu:", sizeof("a\n\t\\")); for (i = 0; i < sizeof("a\n\t\\"); i++) printf(" %d", (unsigned char)s[i]); printf("\n");
return 0;
}
