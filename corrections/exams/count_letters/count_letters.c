int count_letters(char *str)
{
    int c = 0;
    if (!str) return 0;
    for (int i = 0; str[i]; i++) {
        if ((str[i] >= 'a' && str[i] <= 'z') || (str[i] >= 'A' && str[i] <= 'Z'))
            c++;
    }
    return c;
}
