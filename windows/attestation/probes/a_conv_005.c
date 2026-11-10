#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld %llu\n", (long long)((unsigned long long)(-5)), (unsigned long long)((unsigned long long)(-5)));
return 0;
}
