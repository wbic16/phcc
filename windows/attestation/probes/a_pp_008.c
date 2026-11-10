#define FOO 24
#define BAR 6
#include <stdio.h>
#if BAR * BAR == 36
#define R 1
#else
#define R 0
#endif
int main(void){ printf("%d\n", R); return 0; }
