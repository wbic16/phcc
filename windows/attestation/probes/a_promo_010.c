#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
unsigned char a = 255; unsigned char b = 255; printf("%zu %lld\n", sizeof(a + b), (long long)(a + b));
return 0;
}
