int ft_pow(int nb, int power)
{
    if (power < 0) return 0;
    if (power == 0) return 1;
    int r = 1;
    while (power-- > 0) r *= nb;
    return r;
}
