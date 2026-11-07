int count_alen(char *str)
{
    int i = 0;
    if (!str) return 0;
    while (str[i] && str[i] != 'a') i++;
    return i;
}
