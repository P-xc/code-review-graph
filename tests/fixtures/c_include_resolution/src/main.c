#include "sibling.h"
#include <stdio.h>
#include "nested/deep.h"

int use_all(void) {
    return sibling_value() + deep_value();
}
