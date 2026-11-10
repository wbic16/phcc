#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld %llu\n", (long long)((unsigned)(3.99)), (unsigned long long)((unsigned)(3.99)));
return 0;
}
