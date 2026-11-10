#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%d\n", _Generic("s", int: 1, double: 2, float: 3, char: 4, char *: 5, long: 6, void *: 7, default: 0));
return 0;
}
