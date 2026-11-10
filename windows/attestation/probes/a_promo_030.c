#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
signed char a = -128; signed char b = 127; printf("%zu %lld\n", sizeof(a < b), (long long)(a < b));
return 0;
}
