int is_anagram(char *a, char *b)
{
    int cnt[256] = {0};
    for (int i = 0; a && a[i]; i++) cnt[(unsigned char)a[i]]++;
    for (int i = 0; b && b[i]; i++) cnt[(unsigned char)b[i]]--;
    for (int i = 0; i < 256; i++) if (cnt[i] != 0) return 0;
    return 1;
}
