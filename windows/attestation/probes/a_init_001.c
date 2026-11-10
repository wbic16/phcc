#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
int a[6] = { [2] = 5, [4] = 9 }; printf("%d %d %d %d\n", a[0], a[2], a[4], a[5]);
return 0;
}
