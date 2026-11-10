#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld\n", (long long)(123456789123456789ll % 1000000007ll));
return 0;
}
