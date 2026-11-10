#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld %llu\n", (long long)((long)4294967295u), (unsigned long long)((long)4294967295u));
return 0;
}
