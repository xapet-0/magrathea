#include <stddef.h>
int frequency_character(char c, char *str) {
    int count = 0;
    
    if (c == '\0' || str == NULL) {
        return 0;
    }
    
    for (int i = 0; str[i] != '\0'; i++) {
        if (str[i] == c) {
            count++;
        }
    }
    
    return count;
}