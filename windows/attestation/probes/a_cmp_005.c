#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%d %d %d %d\n", (0 < -1), (0 == -1), (0 >= -1), ((0 < -1) ? 0 : -1));
return 0;
}
