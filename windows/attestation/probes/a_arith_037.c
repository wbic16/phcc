#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%llu %llx\n", (unsigned long long)(255u % 16u), (unsigned long long)(255u % 16u));
return 0;
}
