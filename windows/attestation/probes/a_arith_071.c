#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%llu %llx\n", (unsigned long long)(4000000000u | 7u), (unsigned long long)(4000000000u | 7u));
return 0;
}
