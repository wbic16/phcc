#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
short a = -300; unsigned short b = 60000; printf("%zu %lld\n", sizeof(a * b), (long long)(a * b));
return 0;
}
