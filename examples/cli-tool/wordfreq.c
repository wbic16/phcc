/* wordfreq.c — count word frequencies.
 *
 * Usage:
 *   wordfreq            read stdin
 *   wordfreq FILE       read FILE
 *
 * Words are runs of letters/digits, folded to lower case. Output is
 * one "word count" line per word, most frequent first, ties broken
 * alphabetically — so the output is deterministic and diff-able.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

#define MAX_WORDS 256
#define MAX_LEN    64

static char words[MAX_WORDS][MAX_LEN];
static int  counts[MAX_WORDS];
static int  nwords = 0;

static void add_word(const char *w)
{
    int i;
    for (i = 0; i < nwords; i++)
        if (strcmp(words[i], w) == 0) { counts[i]++; return; }
    if (nwords < MAX_WORDS) {
        strcpy(words[nwords], w);
        counts[nwords] = 1;
        nwords++;
    }
}

static int cmp(const void *a, const void *b)
{
    int ia = *(const int *)a, ib = *(const int *)b;
    if (counts[ia] != counts[ib]) return counts[ib] - counts[ia];
    return strcmp(words[ia], words[ib]);
}

int main(int argc, char **argv)
{
    FILE *in = stdin;
    int c, n = 0, idx[MAX_WORDS], i;
    char buf[MAX_LEN];

    if (argc > 2) {
        fprintf(stderr, "usage: %s [file]\n", argv[0]);
        return 2;
    }
    if (argc == 2) {
        in = fopen(argv[1], "r");
        if (!in) { perror(argv[1]); return 1; }
    }

    while ((c = getc(in)) != EOF) {
        if (isalnum((unsigned char)c)) {
            if (n < MAX_LEN - 1) buf[n++] = tolower((unsigned char)c);
        } else if (n > 0) {
            buf[n] = '\0'; add_word(buf); n = 0;
        }
    }
    if (n > 0) { buf[n] = '\0'; add_word(buf); }
    if (in != stdin) fclose(in);

    for (i = 0; i < nwords; i++) idx[i] = i;
    qsort(idx, nwords, sizeof(int), cmp);
    for (i = 0; i < nwords; i++)
        printf("%s %d\n", words[idx[i]], counts[idx[i]]);
    return 0;
}
