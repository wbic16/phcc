/* main.c — the consumer side: includes the same header and calls
 * the library without knowing where it lives. */
#include <stdio.h>
#include "shared.h"

int main(void)
{
    printf("twice(21) = %d\n", twice(21));
    return 0;
}
