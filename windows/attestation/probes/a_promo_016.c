#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
int a = -1; unsigned int b = 1; printf("%zu %lld\n", sizeof(a + b), (long long)(a + b));
return 0;
}
