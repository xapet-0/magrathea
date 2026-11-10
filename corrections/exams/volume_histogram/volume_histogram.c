int volume_histogram(int *histogram, int size)
{
    if (!histogram || size <= 2) return 0;
    int l = 0, r = size - 1, lmax = 0, rmax = 0, water = 0;
    while (l < r) {
        if (histogram[l] < histogram[r]) {
            if (histogram[l] >= lmax) lmax = histogram[l];
            else water += lmax - histogram[l];
            l++;
        } else {
            if (histogram[r] >= rmax) rmax = histogram[r];
            else water += rmax - histogram[r];
            r--;
        }
    }
    return water;
}
