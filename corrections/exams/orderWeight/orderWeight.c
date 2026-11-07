#include <stdlib.h>

static int wsum(const char *s)
{
    int sum = 0;
    for (int i = 0; s[i]; i++) sum += s[i] - '0';
    return sum;
}

static int scmp(const char *a, const char *b)
{
    while (*a && *a == *b) { a++; b++; }
    return (unsigned char)*a - (unsigned char)*b;
}

char *orderWeight(char *strng)
{
    if (!strng) return NULL;
    char *words[1024];
    int n = 0, i = 0;
    while (strng[i]) {
        while (strng[i] == ' ') i++;
        if (strng[i]) {
            int s = i;
            while (strng[i] && strng[i] != ' ') i++;
            int len = i - s;
            words[n] = malloc(len + 1);
            if (!words[n]) {
                for (int k = 0; k < n; k++) free(words[k]);
                return NULL;
            }
            for (int j = 0; j < len; j++) words[n][j] = strng[s + j];
            words[n][len] = '\0';
            n++;
        }
    }
    for (int a = 0; a < n; a++) {
        for (int b = a + 1; b < n; b++) {
            int wa = wsum(words[a]), wb = wsum(words[b]);
            if (wa > wb || (wa == wb && scmp(words[a], words[b]) > 0)) {
                char *t = words[a]; words[a] = words[b]; words[b] = t;
            }
        }
    }
    int total = 0;
    for (int a = 0; a < n; a++) {
        int l = 0; while (words[a][l]) l++;
        total += l + 1;
    }
    char *res = malloc(total + 1);
    if (!res) {
        for (int k = 0; k < n; k++) free(words[k]);
        return NULL;
    }
    int pos = 0;
    for (int a = 0; a < n; a++) {
        if (a > 0) res[pos++] = ' ';
        for (int j = 0; words[a][j]; j++) res[pos++] = words[a][j];
        free(words[a]);
    }
    res[pos] = '\0';
    return res;
}
