int is_consonant(char c)
{
    if (c >= 'a' && c <= 'z')
        return (c != 'a' && c != 'e' && c != 'i' && c != 'o' && c != 'u');
    if (c >= 'A' && c <= 'Z')
        return (c != 'A' && c != 'E' && c != 'I' && c != 'O' && c != 'U');
    return 0;
}
