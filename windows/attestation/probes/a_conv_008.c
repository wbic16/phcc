#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld %llu\n", (long long)((long)(1e10)), (unsigned long long)((long)(1e10)));
return 0;
}
