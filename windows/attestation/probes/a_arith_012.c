#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%llu %llx\n", (unsigned long long)(1u / 1u), (unsigned long long)(1u / 1u));
return 0;
}
