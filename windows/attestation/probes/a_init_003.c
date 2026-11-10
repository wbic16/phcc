#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
int *p = (int[]){10, 20, 30}; printf("%d %d %d\n", p[0], p[1], p[2]);
return 0;
}
