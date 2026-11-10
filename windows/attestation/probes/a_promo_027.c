#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
unsigned short a = 65535; int b = 1; printf("%zu %lld\n", sizeof(a < b), (long long)(a < b));
return 0;
}
