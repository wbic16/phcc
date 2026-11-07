/* stats.c — implementation of the library declared in stats.h. */
#include "stats.h"

double stats_mean(const double *xs, int n)
{
    double sum = 0.0;
    int i;
    if (n <= 0) return 0.0;
    for (i = 0; i < n; i++) sum += xs[i];
    return sum / n;
}

double stats_max(const double *xs, int n)
{
    double m;
    int i;
    if (n <= 0) return 0.0;
    m = xs[0];
    for (i = 1; i < n; i++) if (xs[i] > m) m = xs[i];
    return m;
}
