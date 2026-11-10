#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%llu %llx\n", (unsigned long long)(123456789u % 987654321u), (unsigned long long)(123456789u % 987654321u));
return 0;
}
