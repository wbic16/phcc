#define FOO 24
#define BAR 6
#include <stdio.h>
#if FOO > 10 && BAR < 10
#define R 1
#else
#define R 0
#endif
int main(void){ printf("%d\n", R); return 0; }
