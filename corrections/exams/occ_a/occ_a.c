int occ_a(char *str)
{
    int c = 0;
    for (int i = 0; str && str[i]; i++)
        if (str[i] == 'A') c++;
    return c;
}
