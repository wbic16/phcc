#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld %llu\n", (long long)((int)(42.9)), (unsigned long long)((int)(42.9)));
return 0;
}
