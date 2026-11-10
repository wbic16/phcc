#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
int a[2][3] = { [1] = {4, 5} }; printf("%d %d %d %d\n", a[0][0], a[1][0], a[1][1], a[1][2]);
return 0;
}
