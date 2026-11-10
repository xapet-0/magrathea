int find_pivot(int *arr, int n)
{
    long total = 0, left = 0;
    for (int i = 0; i < n; i++) total += arr[i];
    for (int i = 0; i < n; i++) {
        if (left == total - left - arr[i]) return i;
        left += arr[i];
    }
    return -1;
}
