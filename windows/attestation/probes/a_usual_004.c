#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%zu\n", sizeof(1u + 1l));
return 0;
}
