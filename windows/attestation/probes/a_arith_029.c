#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%llu %llx\n", (unsigned long long)(5u % 17u), (unsigned long long)(5u % 17u));
return 0;
}
