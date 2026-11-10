#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
printf("%d %zu\n", '\x41', sizeof('\x41'));
return 0;
}
