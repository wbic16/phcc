#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld\n", (long long)(9223372036854775807ll % 3ll));
return 0;
}
