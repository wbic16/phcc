#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%llu %lld\n", (unsigned long long)(7ull << 33), (long long)((7ll) << 33));
return 0;
}
