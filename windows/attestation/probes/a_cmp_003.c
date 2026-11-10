#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%d %d %d %d\n", (100 < -100), (100 == -100), (100 >= -100), ((100 < -100) ? 100 : -100));
return 0;
}
