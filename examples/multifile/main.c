/* main.c — the program: uses the stats library, knows nothing
 * about how it is implemented. */
#include <stdio.h>
#include "stats.h"

int main(void)
{
    static const double data[] = { 1.5, 2.5, 4.0, 8.0 };
    int n = (int)(sizeof(data) / sizeof(data[0]));

    printf("mean = %.3f\n", stats_mean(data, n));
    printf("max = %.3f\n", stats_max(data, n));
    return 0;
}
