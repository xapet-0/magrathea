#include <stdlib.h>

char *longest_subarray(char *arr)
{
    int n = 0;
    while (arr && arr[n]) n++;
    int best_len = 0, best_start = 0;
    for (int i = 0; i < n; i++) {
        int odd = 0, even = 0;
        for (int j = i; j < n; j++) {
            if ((arr[j] - '0') % 2 == 0) even++;
            else odd++;
            if (odd == even && (j - i + 1) > best_len) {
                best_len = j - i + 1;
                best_start = i;
            }
        }
    }
    char *res = malloc(best_len + 1);
    if (!res)
        return NULL;
    for (int i = 0; i < best_len; i++) res[i] = arr[best_start + i];
    res[best_len] = '\0';
    return res;
}
