#include <stdio.h>
#define S(x) #x
#define P(a,b) a##b
int main(void){ int P(ab, cd) = 7; printf("%s %d %s\n", S(hello world), abcd, S(1+2)); return 0; }
