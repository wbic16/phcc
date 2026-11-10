#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
struct P { int x; const char *s; double d; }; struct P p = { .d = 2.5, .x = 3 }; printf("%d %g %d\n", p.x, p.d, p.s == 0);
return 0;
}
