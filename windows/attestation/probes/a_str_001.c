#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
const char *s = "hello"; size_t i; printf("%zu:", sizeof("hello")); for (i = 0; i < sizeof("hello"); i++) printf(" %d", (unsigned char)s[i]); printf("\n");
return 0;
}
