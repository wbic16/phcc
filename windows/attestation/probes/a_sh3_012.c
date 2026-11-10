#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%llu %lld\n", (unsigned long long)(3ull << 32), (long long)((3ll) << 32));
return 0;
}
