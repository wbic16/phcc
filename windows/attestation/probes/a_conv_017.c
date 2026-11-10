#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld %llu\n", (long long)((unsigned char)257), (unsigned long long)((unsigned char)257));
return 0;
}
