int count_of_2(int n)
{
    int count = 0;
    for (int i = 2; i <= n; i++) {
        int x = i;
        while (x > 0) {
            if (x % 10 == 2) count++;
            x /= 10;
        }
    }
    return count;
}
