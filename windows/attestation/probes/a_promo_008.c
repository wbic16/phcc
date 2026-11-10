#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
char a = 100; short b = -200; printf("%zu %lld\n", sizeof(a * b), (long long)(a * b));
return 0;
}
