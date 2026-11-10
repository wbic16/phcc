#include <stdio.h>
#ifdef __STDC__
#define STDCFLAG 1
#else
#define STDCFLAG 0
#endif
int main(void){ printf("%ld %d\n", (long)__STDC_VERSION__, STDCFLAG); return 0; }
