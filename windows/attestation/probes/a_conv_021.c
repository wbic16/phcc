#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%lld %llu\n", (long long)((double)9007199254740993ll == 9007199254740992.0 ? 1 : 0), (unsigned long long)((double)9007199254740993ll == 9007199254740992.0 ? 1 : 0));
return 0;
}
