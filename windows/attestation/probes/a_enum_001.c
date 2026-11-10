#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
enum E { A0, A1 = 5, A2, A3 = -3 }; printf("%d %d %d %d %zu\n", A0, A1, A2, A3, sizeof(enum E));
return 0;
}
