#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
char s[] = { [0] = 'p', [3] = 'x' }; printf("%zu %d %d %d\n", sizeof s, s[0], s[1], s[3]);
return 0;
}
