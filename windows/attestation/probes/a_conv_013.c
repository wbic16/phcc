#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld %llu\n", (long long)((long long)(int)2147483647), (unsigned long long)((long long)(int)2147483647));
return 0;
}
