int occ_z(char *str)
{
    int c = 0;
    for (int i = 0; str && str[i]; i++)
        if (str[i] == 'Z') c++;
    return c;
}
