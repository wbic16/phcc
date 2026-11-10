#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
const char *s = "con" "cat"; size_t i; printf("%zu:", sizeof("con" "cat")); for (i = 0; i < sizeof("con" "cat"); i++) printf(" %d", (unsigned char)s[i]); printf("\n");
return 0;
}
