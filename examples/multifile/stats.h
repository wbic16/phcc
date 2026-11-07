/* stats.h — a tiny statistics library.
 *
 * Header discipline in one place: the include guard keeps this
 * header safe to include from any number of translation units, and
 * the header alone is the library's whole public contract.
 */
#ifndef STATS_H
#define STATS_H

/* Arithmetic mean of xs[0..n). Returns 0.0 when n <= 0. */
double stats_mean(const double *xs, int n);

/* Largest element of xs[0..n). Returns 0.0 when n <= 0. */
double stats_max(const double *xs, int n);

#endif /* STATS_H */
