int volume_cuboid(int l, int b, int h)
{
    if (l <= 0 || b <= 0 || h <= 0) return 0;
    return l * b * h;
}
