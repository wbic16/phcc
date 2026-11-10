#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld %llu\n", (long long)((unsigned int)(-3)), (unsigned long long)((unsigned int)(-3)));
return 0;
}
