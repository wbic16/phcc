/* dll.c — the library side. Defining BUILDING_DLL before the
 * include makes shared.h export (not import) the symbol. */
#define BUILDING_DLL
#include "shared.h"

int twice(int x)
{
    return 2 * x;
}
