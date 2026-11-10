static int val(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int atoi_base(const char *str, int str_base)
{
    if (!str || str_base < 2 || str_base > 16) return 0;
    int i = 0, sign = 1;
    unsigned long res = 0;
    while (str[i] == ' ' || (str[i] >= 9 && str[i] <= 13)) i++;
    if (str[i] == '-' || str[i] == '+') {
        if (str[i] == '-') sign = -1;
        i++;
    }
    int v;
    while ((v = val(str[i])) >= 0 && v < str_base) {
        res = res * str_base + v;
        i++;
    }
    return (int)(res * sign);
}
