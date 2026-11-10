#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
const char *s = ""; size_t i; printf("%zu:", sizeof("")); for (i = 0; i < sizeof(""); i++) printf(" %d", (unsigned char)s[i]); printf("\n");
return 0;
}
