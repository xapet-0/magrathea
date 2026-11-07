int lengthOfLongestSubstring(char *s)
{
    if (!s) return 0;
    int last[256];
    for (int i = 0; i < 256; i++) last[i] = -1;
    int best = 0, start = 0;
    for (int i = 0; s[i]; i++) {
        unsigned char c = (unsigned char)s[i];
        if (last[c] >= start) start = last[c] + 1;
        last[c] = i;
        if (i - start + 1 > best) best = i - start + 1;
    }
    return best;
}
