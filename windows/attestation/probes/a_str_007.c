#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
const char *s = "tab\there"; size_t i; printf("%zu:", sizeof("tab\there")); for (i = 0; i < sizeof("tab\there"); i++) printf(" %d", (unsigned char)s[i]); printf("\n");
return 0;
}
