/* hello.c — the smallest phcc program.
 *
 * Build and run:
 *   phcc -o hello hello.c && ./hello
 * Or skip the build entirely (see README.md):
 *   phcc -run hello.c
 */
#include <stdio.h>

int main(void)
{
    printf("Hello, world!\n");
    return 0;
}
