#define K 3
#include <stdio.h>
#if K == 0
#define R 10
#elif K == 1
#define R 11
#elif K == 2
#define R 12
#elif K == 3
#define R 13
#else
#define R 14
#endif
int main(void){ printf("%d\n", R); return 0; }
