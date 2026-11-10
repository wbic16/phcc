#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
struct P { int x; int y; } p = (struct P){ .y = 4, .x = 3 }; printf("%d %d\n", p.x, p.y);
return 0;
}
