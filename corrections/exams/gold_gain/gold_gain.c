#include <stdlib.h>

int gold_gain(int **mine, int n)
{
    if (!mine || n <= 0) return 0;
    int *dp = malloc(sizeof(int) * n);
    int *next = malloc(sizeof(int) * n);
    if (!dp || !next) {
        free(dp);
        free(next);
        return 0;
    }
    for (int r = 0; r < n; r++) dp[r] = mine[r][0];
    for (int c = 1; c < n; c++) {
        for (int r = 0; r < n; r++) {
            int best = dp[r];
            if (r > 0 && dp[r - 1] > best) best = dp[r - 1];
            if (r + 1 < n && dp[r + 1] > best) best = dp[r + 1];
            next[r] = mine[r][c] + best;
        }
        for (int r = 0; r < n; r++) dp[r] = next[r];
    }
    int ans = dp[0];
    for (int r = 1; r < n; r++) if (dp[r] > ans) ans = dp[r];
    free(dp);
    free(next);
    return ans;
}
