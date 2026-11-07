int rectangle_perimeter(int length, int breadth)
{
    if (length <= 0 || breadth <= 0) return 0;
    return (2 * length) + (2 * breadth);
}
