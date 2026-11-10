#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld %llu\n", (long long)((int)3.5 + (int)2.5), (unsigned long long)((int)3.5 + (int)2.5));
return 0;
}
