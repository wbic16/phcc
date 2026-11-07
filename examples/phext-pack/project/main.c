/* main.c — prints the greeting. If you are running this binary,
 * this source reached you through a phext: it was packed into one,
 * unpacked somewhere else, and built there. */
#include <stdio.h>
#include "greet.h"

int main(void)
{
    printf("%s\n", greeting());
    return 0;
}
