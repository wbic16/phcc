#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%llu %llx\n", (unsigned long long)(65535u & 257u), (unsigned long long)(65535u & 257u));
return 0;
}
