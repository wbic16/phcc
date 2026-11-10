#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%llu %llx\n", (unsigned long long)(1000000u / 999u), (unsigned long long)(1000000u / 999u));
return 0;
}
