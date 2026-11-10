#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld %llu\n", (long long)((unsigned long)(-4)), (unsigned long long)((unsigned long)(-4)));
return 0;
}
