#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld %llu\n", (long long)((double)(float)0.1), (unsigned long long)((double)(float)0.1));
return 0;
}
