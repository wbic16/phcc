#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
enum E { C0 = 0, C1 = 1 }; _Bool b = 42; printf("%d %zu %zu\n", (int)b, sizeof(_Bool), sizeof(enum E));
return 0;
}
