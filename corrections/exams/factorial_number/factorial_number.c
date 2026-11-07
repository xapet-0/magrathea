int factorial_number(int num)
{
    if (num < 0) return 0;
    if (num == 0 || num == 1) return 1;
    return num * factorial_number(num - 1);
}
