#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%llu %lld\n", (unsigned long long)(255ull << 60), (long long)((255ll) << 60));
return 0;
}
