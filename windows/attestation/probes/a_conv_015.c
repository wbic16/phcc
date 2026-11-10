#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld %llu\n", (long long)((float)(double)1.5), (unsigned long long)((float)(double)1.5));
return 0;
}
