#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
enum E { B0 = 2147483647 }; printf("%ld %zu\n", (long)B0, sizeof(enum E));
return 0;
}
