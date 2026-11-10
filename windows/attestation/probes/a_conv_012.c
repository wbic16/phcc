#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld %llu\n", (long long)((int)(unsigned char)200), (unsigned long long)((int)(unsigned char)200));
return 0;
}
