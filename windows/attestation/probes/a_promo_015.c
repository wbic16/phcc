#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
short a = 32767; short b = -32768; printf("%zu %lld\n", sizeof(a < b), (long long)(a < b));
return 0;
}
