#include <stdio.h>
#define MAX(a,b) ((a) > (b) ? (a) : (b))
#define CAT3(a,b,c) a##b##c
int main(void){ int CAT3(x,y,z) = MAX(3, 9); printf("%d %d\n", xyz, MAX(-5, -9)); return 0; }
