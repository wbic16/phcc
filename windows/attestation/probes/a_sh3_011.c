#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%llu %lld\n", (unsigned long long)(1ull << 63), (long long)((1ll) << 63));
return 0;
}
