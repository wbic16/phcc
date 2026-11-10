#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld %llu\n", (long long)((float)16777217 == 16777216.0f ? 1 : 0), (unsigned long long)((float)16777217 == 16777216.0f ? 1 : 0));
return 0;
}
