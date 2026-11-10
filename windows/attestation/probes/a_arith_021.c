#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%llu %llx\n", (unsigned long long)(2u % 3u), (unsigned long long)(2u % 3u));
return 0;
}
