#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
long a = -5; unsigned long b = 5; printf("%zu %lld\n", sizeof(a + b), (long long)(a + b));
return 0;
}
