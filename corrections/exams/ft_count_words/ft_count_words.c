int ft_count_words(char *str)
{
    int c = 0, in_w = 0;
    if (!str) return 0;
    for (int i = 0; str[i]; i++) {
        if (str[i] == ' ' || str[i] == '\t' || str[i] == '\n') in_w = 0;
        else if (!in_w) { in_w = 1; c++; }
    }
    return c;
}
