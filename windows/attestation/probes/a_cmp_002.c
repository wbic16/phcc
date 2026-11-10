#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%d %d %d %d\n", (-3 < 4), (-3 == 4), (-3 >= 4), ((-3 < 4) ? -3 : 4));
return 0;
}
