#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <limits.h>
int main(void){
char buf[16]; strcpy(buf, "phext"); strcat(buf, "-c"); printf("%s %zu %d\n", buf, strlen(buf), strcmp(buf, "phext-c"));
return 0;
}
